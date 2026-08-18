"""LLM wrapper — provider cấu hình qua .env (anthropic | glm/zai | openai-compat).

Gọi qua urllib (không cần SDK). Có hook offline (`set_hook`) để test không tốn credit
(pattern kế thừa Outline Extract). LLM chỉ làm việc ngữ nghĩa; Python luôn validate output.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time as _t
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from . import common, khoa_v3

# ── đo token (đọc field `usage` API trả về — KHÔNG tự ước lượng) ──
USAGE = {"calls": 0, "in": 0, "out": 0, "cache_hits": 0, "saved_in": 0, "saved_out": 0}
# `USAGE[k] += n` là 3 bước bytecode (đọc → cộng → ghi), về nguyên tắc KHÔNG nguyên tử, mà từ khi
# `gather()` chạy nhiều call cùng lúc thì có nhiều thread cùng cộng. Đây là sổ token/tiền user nhìn
# nên không được phép hụt.
# NÓI RÕ ĐỘ CHẮC: tôi đã thử bỏ lock ra và chạy 400 call × 6 vòng ở cả MAX_PARALLEL=4 lẫn 32 trên
# Python 3.14 — KHÔNG lần nào hụt số. Nên đừng đọc lock này như "đã sửa một bug đo được"; nó là
# hàng rào đúng-theo-định-nghĩa, giá gần như 0. Đừng gỡ với lý do "chạy thử thấy không sao".
_USAGE_LOCK = threading.Lock()
MAX_PARALLEL = 4       # trần call trong MỘT `gather()` — xem GLOBAL_PARALLEL bên dưới

# ── TRẦN THẬT, TOÀN SERVER ────────────────────────────────────────────────────────────────────
# `MAX_PARALLEL` chỉ giới hạn TRONG MỘT `gather()`. Nhiều người bấm Sinh cùng lúc thì mỗi job có
# pool riêng ⇒ trần nhân lên theo số job. ĐO THẬT (3 job × gather 4 việc): **cao điểm 12 call
# cùng lúc** trong khi `jobs.py` vẫn ghi rằng trần là 4. Tức trần cũ chỉ có trên giấy, và cái
# giữ cho nhà cung cấp không trả 429 xưa nay là "may chưa ai bấm cùng lúc".
# `_GATE` là trần THẬT: đếm ở `_post`, chỗ DUY NHẤT mọi provider đi qua.
# Vì sao 8 chứ không phải 4: một người dùng một mình vẫn được trọn 4 (gather tự cap), nên đặt 8
# KHÔNG làm chậm ca thường mà vẫn hạ cao điểm 12 → 8. Chỉnh bằng `LLM_MAX_PARALLEL` trong .env.
GLOBAL_PARALLEL = 8
_GATE = threading.BoundedSemaphore(GLOBAL_PARALLEL)
_GATE_N = GLOBAL_PARALLEL

# Thử lại khi nhà cung cấp bảo "từ từ". TRƯỚC ĐÂY KHÔNG CÓ MỘT DÒNG NÀO: một cú 429 là
# `_post` raise thẳng, giết cả lần sinh — sau khi đã tiêu quota YouTube và vài call LLM trước đó.
# Với 7 người dùng chung một key thì 429 thôi là chuyện thường ngày, không phải sự cố hiếm.
RETRY_ON = (408, 409, 425, 429, 500, 502, 503, 504)   # 4xx còn lại (400/401/403) thử lại vô ích
RETRIES = 4
BACKOFF = 1.6          # giây, nhân đôi mỗi lần


def set_global_parallel(n: int) -> None:
    """Đổi trần toàn server (đọc .env lúc khởi động). Không có call nào đang chạy thì mới gọi."""
    global _GATE, _GATE_N, GLOBAL_PARALLEL
    n = max(1, min(64, int(n)))
    GLOBAL_PARALLEL = _GATE_N = n
    _GATE = threading.BoundedSemaphore(n)

# Cache đĩa: chỉ cho call PHÂN TÍCH (nhiệt độ thấp — phân vai tag, extract profile/format).
# Call SÁNG TẠO (title/description, temp cao) không cache → nút "↻ Sinh lại" vẫn ra bản mới,
# giữ nguyên tắc multi-variant / né trùng metadata khi re-up.
CACHE_MAX_TEMP = 0.3

# Deliverable (title/tag/description/chapter) LUÔN theo ngôn ngữ nội dung video (kịch bản/title
# gốc — thường English). UI/log tiếng Việt; KẾT QUẢ không bao giờ dịch sang tiếng Việt.
OUTPUT_LANG_RULE = (
    "QUAN TRỌNG: Viết TOÀN BỘ kết quả (title, description, chapter, tag) bằng ĐÚNG ngôn ngữ "
    "của kịch bản/title gốc (thường là tiếng Anh). TUYỆT ĐỐI KHÔNG dịch sang tiếng Việt."
)

_HOOK = None  # test injection: fn(system, user) -> str


def set_hook(fn) -> None:
    """Cắm hàm giả cho test offline. Truyền None để tắt."""
    global _HOOK
    _HOOK = fn


def usage_reset() -> None:
    with _USAGE_LOCK:
        for k in USAGE:
            USAGE[k] = 0


def usage_snapshot() -> dict:
    """Token đã dùng + tiền ước tính. Giá đọc từ .env (USD/1 triệu token) — không có thì để None."""
    common.load_env()
    pin = _f(os.environ.get("LLM_PRICE_IN"))
    pout = _f(os.environ.get("LLM_PRICE_OUT"))
    with _USAGE_LOCK:                                # chụp MỘT LẦN: đọc rời từng field trong lúc
        snap = dict(USAGE)                           # thread khác đang cộng là ra bản số không khớp nhau
    snap["total"] = snap["in"] + snap["out"]
    snap["cost"] = round(snap["in"] / 1e6 * pin + snap["out"] / 1e6 * pout, 6) \
        if (pin or pout) else None
    snap["saved_cost"] = round(snap["saved_in"] / 1e6 * pin + snap["saved_out"] / 1e6 * pout, 6) \
        if (pin or pout) else None
    return snap


def gather(jobs: dict) -> dict:
    """Chạy nhiều call LLM ĐỘC LẬP song song → `{tên: (kết quả, lỗi)}`.

    KHÔNG ném: caller tự quyết call nào hỏng là chặn cả lần chạy, call nào chỉ ghi cờ mềm —
    `niche_format.rebuild` cần đúng sự phân biệt đó (title/description hỏng = hỏng thật;
    package/community hỏng = ghi `soft_errors`, giữ phần đã làm được).
    Chỉ dùng cho call KHÔNG phụ thuộc kết quả của nhau. `jobs` giữ nguyên thứ tự khai báo.
    """
    if not jobs:
        return {}
    if len(jobs) == 1:                               # 1 việc thì đừng dựng pool cho tốn công
        name, fn = next(iter(jobs.items()))
        try:
            return {name: (fn(), None)}
        except Exception as e:                       # noqa: BLE001 — caller phân loại
            return {name: (None, e)}
    out: dict = {}
    with ThreadPoolExecutor(max_workers=min(len(jobs), MAX_PARALLEL)) as ex:
        futs = {name: ex.submit(fn) for name, fn in jobs.items()}
    for name, f in futs.items():                     # ra khỏi `with` = đã chờ xong hết
        try:
            out[name] = (f.result(), None)
        except Exception as e:                       # noqa: BLE001
            out[name] = (None, e)
    return out


def _f(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _cache_path(key: str):
    d = common.ROOT / ".cache" / "llm"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{key}.json"


def _cache_key(provider: str, model: str, system: str, user: str, max_tokens: int, temperature: float) -> str:
    raw = "\x00".join([provider, model, system, user, str(max_tokens), f"{temperature:.2f}"])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def _default_model(provider: str) -> str:
    return {"anthropic": "claude-sonnet-5", "glm": "glm-5.2",
            "zai": "glm-5.2", "z.ai": "glm-5.2"}.get(provider, "gpt-4o-mini")


def call(system: str, user: str, *, max_tokens: int = 1024, temperature: float = 0.4,
         json_mode: bool = False, cache: bool | None = None) -> str:
    """Gọi LLM 1 lượt, trả text. Dùng hook nếu đã set (test).

    json_mode=True (dùng bởi call_json): với GLM z.ai bật response_format json_object + TẮT thinking
    (reasoning model ăn token → truncate JSON; tắt cho tác vụ có cấu trúc → nhanh & sạch).
    cache=None → tự bật khi temperature ≤ CACHE_MAX_TEMP (call phân tích, kết quả nên ổn định).
    """
    if _HOOK is not None:
        return _HOOK(system, user)
    if khoa_v3.bat():
        # V3 (19/08/2026): sau gateway OUTLIERY thì khóa + model lấy từ KÉT theo việc
        # sinh_metadata — KHÔNG đọc .env (chống hai nguồn khóa lệch nhau, khuôn radary/niche).
        provider, key, model = khoa_v3.llm_viec()
        model = model or _default_model(provider)
        pfx = re.sub(r"\W", "", provider).upper()
    else:
        common.load_env()
        # MẶC ĐỊNH là glm (user chốt 2026-07-30: "dùng GLM, đừng dùng anthropic nữa"). Trước đây
        # mặc định anthropic ⇒ `.env` thiếu/đổi tên là âm thầm gọi sang nhà ĐÃ HẾT CREDIT, và lỗi trả
        # về là "credit balance too low" — chẳng liên quan gì tới nguyên nhân thật (thiếu LLM_PROVIDER).
        provider = (os.environ.get("LLM_PROVIDER") or "glm").lower()
        pfx = re.sub(r"\W", "", provider).upper()             # glm→GLM, z.ai→ZAI (biến .env theo provider)
        key = os.environ.get("LLM_API_KEY") or os.environ.get(f"{pfx}_API_KEY") or ""
        model = os.environ.get("LLM_MODEL") or os.environ.get(f"{pfx}_MODEL") or _default_model(provider)
        if not key:
            raise RuntimeError(f"Thiếu LLM_API_KEY / {pfx}_API_KEY trong .env")

    use_cache = (temperature <= CACHE_MAX_TEMP) if cache is None else cache
    ck = _cache_key(provider, model, system, user, max_tokens, temperature) if use_cache else ""
    if ck:
        f = _cache_path(ck)
        if f.exists():
            try:
                hit = json.loads(f.read_text(encoding="utf-8"))
                with _USAGE_LOCK:                             # tiết kiệm được đúng bằng lần gọi trước
                    USAGE["cache_hits"] += 1
                    USAGE["saved_in"] += int(hit.get("in", 0))
                    USAGE["saved_out"] += int(hit.get("out", 0))
                return hit["text"]
            except Exception:                                # noqa: BLE001 — cache hỏng → gọi lại
                pass

    if provider == "anthropic":
        text, used = _anthropic(system, user, key, model, max_tokens, temperature,
                                json_mode=json_mode)
    else:
        base = os.environ.get("LLM_BASE_URL") or os.environ.get(f"{pfx}_BASE_URL") or (
            "https://api.z.ai/api/paas/v4" if provider in ("glm", "zai", "z.ai")
            else "https://api.openai.com/v1")
        is_glm = provider in ("glm", "zai", "z.ai")
        text, used = _openai_compat(system, user, key, model, base, max_tokens, temperature,
                                    json_mode=json_mode, no_think=(json_mode and is_glm))
    with _USAGE_LOCK:
        USAGE["calls"] += 1
        USAGE["in"] += used[0]
        USAGE["out"] += used[1]
    if ck:
        try:
            _cache_path(ck).write_text(json.dumps({"text": text, "in": used[0], "out": used[1]},
                                                  ensure_ascii=False), encoding="utf-8")
        except Exception:                                    # noqa: BLE001 — không ghi được cache thì thôi
            pass
    return text


def call_json(system: str, user: str, **kw):
    """Như call() nhưng bật json_mode + ép parse JSON từ output."""
    kw.setdefault("json_mode", True)
    return extract_json(call(system, user, **kw))


def _post(url: str, headers: dict, payload: dict) -> dict:
    """Chỗ DUY NHẤT mọi provider gọi ra mạng ⇒ đặt cả trần đồng thời lẫn thử-lại ở đây.

    **Ngủ chờ thì phải NHẢ chỗ** (`_GATE` release trước khi `sleep`): giữ chỗ trong lúc nằm đợi
    là tự bóp trần của chính mình — call đang bị nhà cung cấp bảo "từ từ" lại chặn nốt call
    của người khác vốn có thể đi được.
    """
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type": "application/json", **headers})
    last = ""
    for attempt in range(RETRIES + 1):
        code, body, wait = 0, "", 0.0
        with _GATE:                                   # trần THẬT toàn server
            try:
                with urllib.request.urlopen(req, timeout=90) as r:
                    return json.loads(r.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                code = e.code
                body = e.read().decode("utf-8", "replace")[:300]
                # Nhà cung cấp nói rõ đợi bao lâu thì NGHE HỌ, đừng tự đoán bằng backoff.
                try:
                    wait = float((e.headers or {}).get("Retry-After") or 0)
                except (TypeError, ValueError):
                    wait = 0.0
                last = f"LLM API {code}: {body}"
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                code, last = 599, f"LLM API mạng lỗi: {e}"
        if code and code not in RETRY_ON:
            raise RuntimeError(last)                  # 400/401 có thử lại 100 lần cũng thế
        if attempt >= RETRIES:
            raise RuntimeError(f"{last} (đã thử lại {RETRIES} lần)")
        _t.sleep(max(wait, BACKOFF * (2 ** attempt)))


def _anthropic(system, user, key, model, max_tokens, temperature,
               *, json_mode=False) -> tuple[str, tuple[int, int]]:
    d = _post("https://api.anthropic.com/v1/messages",
              {"x-api-key": key, "anthropic-version": "2023-06-01"},
              {"model": model, "max_tokens": max_tokens, "temperature": temperature,
               "system": system, "messages": [{"role": "user", "content": user}]})
    u = d.get("usage") or {}
    # Anthropic báo cắt cụt bằng stop_reason="max_tokens" (openai-compat dùng
    # finish_reason="length"). Thiếu nhánh này thì JSON cụt vẫn trôi xuống extract_json
    # và báo lỗi mơ hồ — đúng ca đã cắn 2026-07-28.
    if json_mode and d.get("stop_reason") == "max_tokens":
        raise RuntimeError(
            f"LLM viết dài quá {max_tokens} token nên JSON bị cắt giữa chừng "
            f"(đã sinh {u.get('output_tokens', '?')} token). "
            "Cần nới max_tokens của call này, hoặc bắt prompt trả lời ngắn hơn.")
    return ("".join(b.get("text", "") for b in d.get("content", [])),
            (int(u.get("input_tokens", 0)), int(u.get("output_tokens", 0))))


def _openai_compat(system, user, key, model, base, max_tokens, temperature,
                   *, json_mode=False, no_think=False) -> tuple[str, tuple[int, int]]:
    payload = {"model": model, "max_tokens": max_tokens, "temperature": temperature,
               "messages": [{"role": "system", "content": system},
                            {"role": "user", "content": user}]}
    if json_mode:
        payload["response_format"] = {"type": "json_object"}   # ép JSON (z.ai/openai)
    if no_think:
        payload["thinking"] = {"type": "disabled"}             # z.ai: tắt reasoning
    d = _post(f"{base.rstrip('/')}/chat/completions", {"Authorization": f"Bearer {key}"}, payload)
    u = d.get("usage") or {}
    ch = (d.get("choices") or [{}])[0]
    # finish_reason="length" = output BỊ CẮT giữa chừng. Với json_mode thì JSON chắc chắn mất
    # dấu đóng ⇒ parse kiểu gì cũng thua. Báo đúng nguyên nhân ngay đây, đừng để extract_json
    # báo mơ hồ "LLM không trả JSON hợp lệ" rồi ngồi đoán là fence hay là gì.
    if json_mode and ch.get("finish_reason") == "length":
        raise RuntimeError(
            f"LLM viết dài quá {max_tokens} token nên JSON bị cắt giữa chừng "
            f"(đã sinh {u.get('completion_tokens', '?')} token). "
            "Cần nới max_tokens của call này, hoặc bắt prompt trả lời ngắn hơn.")
    return (ch.get("message", {}).get("content") or "",
            (int(u.get("prompt_tokens", 0)), int(u.get("completion_tokens", 0))))


def as_list(out) -> list:
    """Ép về list: nếu LLM bọc array trong object ({\"titles\":[...]}), lấy list value đầu tiên."""
    if isinstance(out, list):
        return out
    if isinstance(out, dict):
        for v in out.values():
            if isinstance(v, list):
                return v
    return []


def extract_json(text: str):
    """Lấy JSON từ text LLM: bỏ ```fence, tìm object/array cân bằng đầu tiên."""
    t = re.sub(r"^```(?:json)?|```$", "", (text or "").strip(), flags=re.M).strip()
    try:
        return json.loads(t)
    except Exception:                                  # noqa: BLE001
        pass
    for open_c, close_c in (("{", "}"), ("[", "]")):
        i = t.find(open_c)
        if i < 0:
            continue
        depth = 0
        for j in range(i, len(t)):
            if t[j] == open_c:
                depth += 1
            elif t[j] == close_c:
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(t[i:j + 1])
                    except Exception:                  # noqa: BLE001
                        break
    # Thông báo phải đủ để CHẨN được, không chỉ để biết "có lỗi": dài bao nhiêu, có dấu hiệu
    # bị cắt cụt không (đó là nguyên nhân phổ biến nhất với model hay viết dài), và ĐUÔI text —
    # đuôi mới cho biết nó dừng ở đâu, đầu text thì lúc nào cũng trông bình thường.
    raw = text or ""
    cut = raw.count("{") > raw.count("}") or raw.count("[") > raw.count("]")
    raise RuntimeError(
        f"LLM không trả JSON hợp lệ ({len(raw)} ký tự"
        f"{', NGOẶC KHÔNG CÂN → nhiều khả năng bị cắt vì chạm max_tokens' if cut else ''}). "
        f"Đầu: {raw[:150]!r} … Đuôi: {raw[-150:]!r}")


if __name__ == "__main__":                             # self-test offline
    set_hook(lambda s, u: '```json\n{"ok": true, "n": 3}\n```')
    assert call_json("s", "u") == {"ok": True, "n": 3}
    set_hook(lambda s, u: 'rác trước [1,2,3] rác sau')
    assert call_json("s", "u") == [1, 2, 3]
    set_hook(None)

    # ── cache đĩa: chỉ call phân tích (temp thấp) mới cache; call sáng tạo luôn gọi mới ──
    import tempfile
    from pathlib import Path
    real_root, calls = common.ROOT, []

    def fake(system, user, key, model, base, max_tokens, temperature, **kw):
        calls.append(temperature)
        return '{"r":1}', (100, 20)

    with tempfile.TemporaryDirectory() as tmp:
        common.ROOT = Path(tmp)
        os.environ.update(LLM_PROVIDER="glm", GLM_API_KEY="x", GLM_MODEL="m")
        globals()["_openai_compat"] = fake
        usage_reset()
        assert call_json("sys", "u", temperature=0.2) == {"r": 1}      # miss → gọi thật
        assert call_json("sys", "u", temperature=0.2) == {"r": 1}      # hit → không gọi
        assert len(calls) == 1, calls
        assert USAGE["calls"] == 1 and USAGE["in"] == 100 and USAGE["cache_hits"] == 1, USAGE
        assert USAGE["saved_in"] == 100 and USAGE["saved_out"] == 20, USAGE
        call_json("sys", "u", temperature=0.7)                         # sáng tạo → KHÔNG cache
        call_json("sys", "u", temperature=0.7)
        assert len(calls) == 3, calls
        os.environ["LLM_PRICE_IN"], os.environ["LLM_PRICE_OUT"] = "1", "2"
        snap = usage_snapshot()
        assert snap["total"] == USAGE["in"] + USAGE["out"] and snap["cost"] > 0, snap
    common.ROOT = real_root
    print("llm.py self-test OK - parse JSON, cache call phan tich, do token/tien")

    # ── gather(): chạy song song THẬT, cô lập lỗi, và sổ token không hụt ──

    def _slow(ms, val):
        def f():
            _t.sleep(ms / 1000)
            return val
        return f

    def _boom():
        raise RuntimeError("hỏng có chủ ý")

    t0 = _t.perf_counter()
    r = gather({"a": _slow(300, 1), "b": _slow(300, 2), "c": _slow(300, 3)})
    el = (_t.perf_counter() - t0) * 1000
    assert el < 700, f"3 việc 300ms chạy song song phải xong <700ms, đo được {el:.0f}ms"
    assert [r[k][0] for k in ("a", "b", "c")] == [1, 2, 3], r     # giữ đúng tên, không lẫn kết quả
    assert all(r[k][1] is None for k in r), r

    r = gather({"ok": _slow(10, "x"), "die": _boom})
    assert r["ok"] == ("x", None), r                              # 1 việc hỏng KHÔNG kéo việc kia chết
    assert r["die"][0] is None and isinstance(r["die"][1], RuntimeError), r
    assert gather({}) == {}
    assert gather({"one": lambda: 7})["one"] == (7, None)         # 1 việc: không dựng pool

    # USAGE cộng từ nhiều thread — không có lock là hụt số, mà đó là sổ tiền user nhìn
    set_hook(None)
    globals()["_openai_compat"] = lambda *a, **k: ('{"r":1}', (10, 5))
    with tempfile.TemporaryDirectory() as tmp:
        common.ROOT = Path(tmp)
        usage_reset()
        N = 40
        gather({f"j{i}": (lambda i=i: call_json("s", f"u{i}", temperature=0.9)) for i in range(N)})
        assert USAGE["calls"] == N, USAGE                         # temp 0.9 → không cache, gọi đủ N lần
        assert USAGE["in"] == 10 * N and USAGE["out"] == 5 * N, USAGE
    common.ROOT = real_root
    print("llm.py self-test OK - gather song song, co lap loi, USAGE khong hut khi da luong")
