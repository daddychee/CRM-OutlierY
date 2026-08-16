"""Lớp vỏ DUY NHẤT gọi LLM (GLM/z.ai OpenAI-compatible). Logic domain chỉ nhận callback.

Cấu hình đọc từ .env (giống Niche Research / Author Extract):
  LLM_PROVIDER=glm · GLM_API_KEY · GLM_MODEL=glm-5.2 · GLM_BASE_URL=https://api.z.ai/api/paas/v4

Bẫy đã trả giá (kế thừa Niche Research, xác nhận lại bằng probe thật 2026-07-04):
- GLM 5.x là model REASONING → mặc định gửi `thinking:{type:disabled}`, nếu không reasoning
  ăn hết max_tokens. Bật lại bằng GLM_THINKING=enabled.
- Mọi call STREAMING (SSE) với fallback non-streaming — output dài (chia beat cả transcript)
  không được dựa vào một response đơn dễ timeout.
- `extract_json` tự vá: chịu ```json fence, văn xuôi bao quanh, trailing comma, JSON bị cắt.
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path


def load_env(env_path: str | Path) -> dict:
    cfg = dict(os.environ)
    p = Path(env_path)
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            cfg.setdefault(k.strip(), v.strip())        # env thật ưu tiên hơn .env
    return cfg


# z.ai dùng 429 cho CẢ HAI việc: nghẽn tốc độ VÀ hết tiền (code 1113). Đo thật
# 2026-07-15: {"error":{"code":"1113","message":"Insufficient balance ... recharge."}}
# Retry 4 lần + backoff khi tài khoản hết tiền = bắt user chờ 50 giây rồi báo sai nguyên nhân.
_NO_BALANCE = ("1113", "insufficient balance", "no resource package", "recharge")


def _no_balance(body: str) -> bool:
    low = (body or "").lower()
    return any(m in low for m in _NO_BALANCE)


class LLM:
    def __init__(self, env_path: str | Path, kind: str = "oe"):
        cfg = load_env(env_path)
        self.kind = kind                                # nhãn cho sổ ghi token
        provider = cfg.get("LLM_PROVIDER", "glm").lower()
        if provider != "glm":
            raise NotImplementedError(f"provider {provider!r} chưa hỗ trợ (MVP chỉ GLM).")
        self.key = cfg.get("GLM_API_KEY")
        self.model = cfg.get("GLM_MODEL", "glm-5.2")
        self.base = cfg.get("GLM_BASE_URL", "https://api.z.ai/api/paas/v4").rstrip("/")
        self.thinking = cfg.get("GLM_THINKING", "disabled").lower() == "enabled"
        if not self.key:
            raise SystemExit("Thiếu GLM_API_KEY trong .env")

    def complete(self, system: str, user: str, *, max_tokens: int = 8000,
                 temperature: float = 0.3, timeout: int = 180) -> str:
        """Trả text thô của model. Streaming SSE, fallback non-streaming khi đứt giữa chừng."""
        body = {
            "model": self.model,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if not self.thinking:
            body["thinking"] = {"type": "disabled"}
        for attempt in range(4):
            try:
                return self._stream(dict(body, stream=True), timeout)
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    # Hết tiền thì chờ bao lâu cũng vô ích → dừng ngay, nói đúng nguyên nhân.
                    detail = ""
                    try:
                        detail = e.read().decode("utf-8", "replace")
                    except Exception:  # noqa: BLE001
                        pass
                    if _no_balance(detail):
                        raise RuntimeError(
                            "LLM HẾT TIỀN trong tài khoản API (z.ai code 1113) — không phải "
                            "nghẽn tốc độ. Nạp thêm tiền rồi bấm ↻ Tiếp tục; pipeline giữ "
                            "checkpoint nên không mất bước nào đã xong."
                        ) from e
                if e.code in (429, 503, 500):           # rate-limit/quá tải → backoff & thử lại
                    if attempt == 3:
                        raise RuntimeError(f"LLM rate-limit kéo dài (HTTP {e.code}) — chờ rồi thử lại")
                    time.sleep(5 * (attempt + 1))
                    continue
                raise                                   # lỗi HTTP khác → ném thẳng
            except Exception:                           # noqa: BLE001 — đứt stream → non-streaming
                with urllib.request.urlopen(self._req(dict(body, stream=False)), timeout=timeout) as r:
                    data = json.loads(r.read())
                self._record(data.get("usage"))
                return data["choices"][0]["message"]["content"]

    def _req(self, body: dict) -> urllib.request.Request:
        return urllib.request.Request(
            f"{self.base}/chat/completions",
            data=json.dumps(body).encode("utf-8"),
            headers={"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"},
        )

    def _stream(self, body: dict, timeout: int) -> str:
        out = []
        seen_usage = None
        with urllib.request.urlopen(self._req(body), timeout=timeout) as r:
            for raw in r:
                line = raw.decode("utf-8").strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    obj = json.loads(data)
                except json.JSONDecodeError:
                    continue
                # GLM đính `usage` vào chunk CUỐI, và làm vậy kể cả khi KHÔNG gửi
                # stream_options.include_usage (probe key thật 2026-07-15) → không cần
                # đụng payload, chỉ nhặt khi đi ngang qua.
                if obj.get("usage"):
                    seen_usage = obj["usage"]
                try:
                    delta = obj["choices"][0]["delta"]
                except (KeyError, IndexError):
                    continue
                if delta.get("content"):
                    out.append(delta["content"])
        self._record(seen_usage)
        text = "".join(out)
        if not text:
            raise RuntimeError("stream rỗng")
        return text

    def _record(self, usage_obj) -> None:
        """Ghi token vào sổ vận hành. Không bao giờ được làm gãy pipeline (luật A6)."""
        try:
            from voiceprofile.usage import record_openai_usage
            record_openai_usage(usage_obj, "glm", self.model, kind=self.kind)
        except Exception:  # noqa: BLE001 — thiếu package/đĩa đầy: bỏ ghi, chạy tiếp
            pass


_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


def extract_json(text: str):
    """Parser tự vá: bóc ```json fence / văn xuôi bao quanh / trailing comma / JSON bị cắt."""
    if not text:
        raise ValueError("text rỗng")
    m = _FENCE.search(text)
    if m:
        text = m.group(1)
    start = min((i for i in (text.find("{"), text.find("[")) if i != -1), default=-1)
    if start == -1:
        raise ValueError("không thấy JSON trong output")
    frag = text[start:]
    for candidate in (frag, _repair(frag)):
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    raise ValueError("không parse được JSON kể cả sau khi vá")


def _repair(s: str) -> str:
    """Vá JSON bị cắt: bỏ trailing comma, đóng nốt ngoặc còn thiếu (cứu prefix hợp lệ)."""
    s = re.sub(r",\s*([}\]])", r"\1", s)
    depth = {"{": 0, "[": 0}
    in_str = esc = False
    closers = []
    for ch in s:
        if esc:
            esc = False
            continue
        if ch == "\\":
            esc = True
            continue
        if ch == '"':
            in_str = not in_str
        elif not in_str:
            if ch in "{[":
                closers.append("}" if ch == "{" else "]")
            elif ch in "}]" and closers:
                closers.pop()
    if in_str:
        s += '"'
    return s + "".join(reversed(closers))
