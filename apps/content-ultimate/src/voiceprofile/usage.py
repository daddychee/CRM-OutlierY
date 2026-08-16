"""So ghi van hanh (ledger): token LLM · nhat ky job · truy cap — nguon cho tab Quan ly.

Ghi APPEND-ONLY JSONL vao ROOT/admin/. Day la du lieu runtime cua team (ten dang nhap
+ IP) nen NGOAI git theo luat A2 — `admin/` da co trong .gitignore.

LUAT SONG CON: khong ham nao trong file nay duoc phep nem loi ra ngoai. Mat mot dong
so ghi la chuyen nho; giet mot job viet 30 phut vi day o cung, quyen file hay JSON rach
thi khong (luat A6 — loi nguon ngoai chi lam trong cot, khong duoc gay pipeline).

Danh tinh nguoi dung di xuong subprocess CLI qua bien moi truong CU_USER / CU_JOB do
voiceprofile/server.py dat: lop LLM chay trong subprocess nen khong nhin thay HTTP
header X-Remote-User cua nginx.

Doc/tong hop la viec cua contentultimate/server.py — file nay chi ghi va tra dong tho.
"""
from __future__ import annotations

import json
import os
import secrets
import threading
import time
from pathlib import Path

ROOT = Path(os.environ.get("CU_DATA_DIR") or Path(__file__).resolve().parents[2])  # V3: CU_DATA_DIR tro kho du lieu ra data/content-ultimate (Luat 6); mac dinh giu canh repo nhu V2
ADMIN_DIR = ROOT / "admin"

USAGE = "usage.jsonl"        # 1 dong = 1 lan goi LLM
HISTORY = "history.jsonl"    # 1 dong = 1 job (viet kich ban / extract giong)
ACCESS = "access.jsonl"      # 1 dong = 1 cap (user, IP) moi trong gio do

_LOCK = threading.Lock()

# Ten user chua biet: job chay ngoai web (CLI tay) hoac may ca nhan khong co nginx.
ANON = "?"


def _who() -> str:
    return (os.environ.get("CU_USER") or "").strip() or ANON


def _append(name: str, row: dict) -> None:
    """Noi mot dong JSON. Nuot MOI loi (xem docstring dau file).

    Dong ngan (< 4KB) + che do "a" (O_APPEND) => mot write() duy nhat, cac tien trinh
    CLI ghi song song khong xen vao giua dong nhau tren Linux. Vi the moi truong `meta`
    phai giu nho — dung nhet ca outline vao day.
    """
    try:
        # 0o700: so ghi chua TEN DANG NHAP + IP cua team = du lieu ca nhan, khong de
        # user khac tren may doc (cung muc voi cookies.txt 600 — luat C2).
        ADMIN_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
        line = json.dumps(row, ensure_ascii=False)[:3500] + "\n"
        path = ADMIN_DIR / name
        new = not path.exists()
        with _LOCK:
            with path.open("a", encoding="utf-8") as f:
                f.write(line)
            if new:
                path.chmod(0o600)
    except Exception:  # noqa: BLE001 — co y: so ghi khong bao gio duoc giet job
        pass


def record_usage(provider: str, model: str, tokens_in, tokens_out, *,
                 kind: str = "", cached=0, reasoning=0) -> None:
    """Ghi token cua MOT lan goi LLM. Goi tu lop vo LLM (voiceprofile/llm.py, oe/llm.py).

    Con so lay TU RESPONSE cua provider — do that, khong uoc luong (luat A1). Lan goi
    hong giua chung (vd GLM tra rong vi finish_reason=length) van ton tien: cu lan nao
    provider tra usage ve la ghi lan do.
    """
    _append(USAGE, {
        "ts": time.time(), "user": _who(), "job": (os.environ.get("CU_JOB") or "").strip(),
        "kind": kind, "provider": provider, "model": model,
        "in": int(tokens_in or 0), "out": int(tokens_out or 0),
        "cached": int(cached or 0), "reasoning": int(reasoning or 0),
    })


def record_openai_usage(usage, provider: str, model: str, kind: str = "") -> None:
    """Chuan hoa khoi `usage` dang OpenAI (GLM/OpenAI/Gemini) roi ghi.

    Hinh dang do that tren z.ai (probe 2026-07-15):
      {"prompt_tokens":12,"completion_tokens":14,"total_tokens":26,
       "prompt_tokens_details":{"cached_tokens":0},
       "completion_tokens_details":{"reasoning_tokens":0}}
    """
    if not isinstance(usage, dict):
        return
    pd = usage.get("prompt_tokens_details") or {}
    cd = usage.get("completion_tokens_details") or {}
    record_usage(provider, model, usage.get("prompt_tokens"), usage.get("completion_tokens"),
                 kind=kind,
                 cached=pd.get("cached_tokens", 0) if isinstance(pd, dict) else 0,
                 reasoning=cd.get("reasoning_tokens", 0) if isinstance(cd, dict) else 0)


def record_job(row: dict) -> None:
    """Ghi mot job da ket thuc (xong / loi / bi huy). Goi tu voiceprofile/server.py."""
    _append(HISTORY, {"ts": time.time(), **row})


def record_access(user: str, ip: str, path: str) -> None:
    """Ghi mot cap (user, IP) — chi khi la cap MOI trong gio do (loc o server)."""
    _append(ACCESS, {"ts": time.time(), "user": user or ANON, "ip": ip, "path": path})


def read_rows(name: str, since: float | None = None) -> list[dict]:
    """Doc mot so ghi. Dong rach (ghi dut giua chung) bi bo qua chu khong lam gay tab."""
    out: list[dict] = []
    try:
        p = ADMIN_DIR / name
        if not p.exists():
            return out
        for ln in p.read_text(encoding="utf-8", errors="replace").splitlines():
            ln = ln.strip()
            if not ln:
                continue
            try:
                row = json.loads(ln)
            except json.JSONDecodeError:
                continue
            if not isinstance(row, dict):
                continue
            if since is not None and float(row.get("ts") or 0) < since:
                continue
            out.append(row)
    except OSError:
        pass
    return out


def new_job_id() -> str:
    """Id job de noi cac dong usage cua subprocess voi dong history cua server.

    Co duoi ngau nhien: tu khi job chay THEO NGUOI (2026-07-16), hai nguoi bam cung
    mot mili-giay la chuyen that — id trung thi token cua hai nguoi tron vao nhau
    trong so ghi (test_jobs bat duoc dung loi nay).
    """
    return f"{int(time.time() * 1000):x}-{secrets.token_hex(3)}"
