# -*- coding: utf-8 -*-
"""MIGRATION MỘT LẦN: khóa API của SEO Optimize (file .env hệ cũ) → KÉT V3
(trang API Keys) + cấp phát theo VIỆC (khuôn scripts/di_tru_khoa_niche.py).

NGUỒN: .env hệ cũ C:\\OutlierY\\apps\\seo-optimize (CHỈ ĐỌC — không ghi gì vào
C:\\; snapshot data/seo-optimize CỐ Ý không mang .env theo). Đường nguồn đổi
được bằng tham số dòng lệnh. Nhận thêm api.txt cạnh .env nếu có (mỗi dòng 1 key
YouTube — thiết kế V2).

ÁNH XẠ (đúng viec_api khai trong apps.json):
  YOUTUBE_API_KEYS / YOUTUBE_API_KEY / YOUTUBE_API_KEY_1..N (tách dấu phẩy,
    dedup)            → loại youtube → việc trich_kenh, chế độ XOAY VÒNG
  GLM_API_KEY         → loại llm (nhà glm, model từ GLM_MODEL) → việc sinh_metadata
  ANTHROPIC_API_KEY   → loại llm (nhà claude)                  → việc sinh_metadata
  OPENAI_API_KEY      → loại llm (nhà chatgpt)                 → việc sinh_metadata
KHÔNG đụng LLM_PROVIDER/PORT (cấu hình chạy, không phải secret); KHÔNG đụng
users.json (tài khoản về khối nền — lệnh user 19/08).

IDEMPOTENT: marker két 'api.di_tru.seo_khoa'. Vết audit CHỈ ĐUÔI 4 ký tự —
không bao giờ in/ghi giá trị khóa.

Chạy tay (Owner quyết thời điểm):
    python scripts/di_tru_khoa_seo.py [đường/tới/.env]
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nen.ket_cau_hinh import ket  # noqa: E402

MARKER = "api.di_tru.seo_khoa"
NGUON_MAC_DINH = [
    ROOT / "data" / "seo-optimize" / ".env",
    Path(r"C:\OutlierY\apps\seo-optimize\.env"),          # hệ cũ — CHỈ ĐỌC
]
_KEY_RE = re.compile(r"^AIza[A-Za-z0-9_-]{20,}$")         # khuôn seo/common.py
_YT_ENV_RE = re.compile(r"^YOUTUBE_API_KEYS?(?:_\d+)?$")
# biến .env → (nhà LLM trong két)
ANH_XA_LLM = {"GLM_API_KEY": "glm", "ANTHROPIC_API_KEY": "claude",
              "OPENAI_API_KEY": "chatgpt"}


def _doc_env(p: Path) -> dict[str, str]:
    ra: dict[str, str] = {}
    # utf-8-sig: .env hệ cũ có thể mang BOM PowerShell (bẫy 30/07 seo/common.load_env)
    for line in p.read_text(encoding="utf-8-sig").splitlines():
        s = line.strip().lstrip("\ufeff")
        if s and not s.startswith("#") and "=" in s:
            k, v = s.split("=", 1)
            v = v.strip().strip("'\"")
            if v:                              # khóa CÓ GIÁ TRỊ thật mới di trú
                ra[k.strip()] = v
    return ra


def _khoa_youtube(env: dict[str, str], env_path: Path) -> list[str]:
    """Gom pool key YouTube: api.txt cạnh .env trước (thiết kế V2), rồi mọi biến
    YOUTUBE_API_KEY* (tách phẩy/khoảng trắng), dedup giữ thứ tự."""
    keys: list[str] = []
    api_txt = env_path.with_name("api.txt")
    if api_txt.is_file():
        for line in api_txt.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if _KEY_RE.match(s) and s not in keys:
                keys.append(s)
    for bien in sorted(b for b in env if _YT_ENV_RE.match(b)):
        for s in re.split(r"[,\s]+", env[bien]):
            s = s.strip()
            if _KEY_RE.match(s) and s not in keys:
                keys.append(s)
    return keys


def di_tru(env_path: Path, conn_ket) -> list[dict]:
    """Trả [{id, duoi, loai, viec}]; [] nếu marker đã có (idempotent)."""
    if ket.lay_cau_hinh(conn_ket, MARKER):
        return []
    env = _doc_env(env_path)
    model = env.get("GLM_MODEL", "")
    ra: list[dict] = []
    yt_ids: list[str] = []
    for gia_tri in _khoa_youtube(env, env_path):
        kid = ket.them_api_key(conn_ket, "youtube", gia_tri)
        yt_ids.append(kid)
        ra.append({"id": kid, "duoi": gia_tri[-4:], "loai": "youtube",
                   "viec": "trich_kenh"})
    llm_ids: list[str] = []
    for bien, nha in ANH_XA_LLM.items():
        gia_tri = env.get(bien)
        if not gia_tri:
            continue
        kid = ket.them_api_key(conn_ket, "llm", gia_tri, nha=nha,
                               model=model if nha == "glm" else "")
        llm_ids.append(kid)
        ra.append({"id": kid, "duoi": gia_tri[-4:], "loai": "llm",
                   "viec": "sinh_metadata"})
    if not ra:
        return []   # .env không có khóa nào → KHÔNG đặt marker (chưa nạp gì thì
                    # không cần chống nạp đôi; có key thật thì chạy lại vẫn ăn)
    if yt_ids:
        ket.luu_cap_phat_viec(conn_ket, "seo-optimize", "trich_kenh", yt_ids,
                              "xoay_vong")
    if llm_ids:
        # GLM đứng đầu ANH_XA_LLM → là khóa CHÍNH (khoa[0] — LLM_PROVIDER=glm hệ cũ);
        # key nhà khác nằm dự phòng trong cấp phát, Owner đổi ở General › API Keys.
        ket.luu_cap_phat_viec(conn_ket, "seo-optimize", "sinh_metadata", llm_ids,
                              "du_phong" if len(llm_ids) > 1 else "mot_khoa", model)
    ket.dat_cau_hinh(conn_ket, MARKER, str(len(ra)))
    return ra


def main() -> None:
    if len(sys.argv) > 1:
        nguon = Path(sys.argv[1])
    else:
        nguon = next((p for p in NGUON_MAC_DINH if p.is_file()), None)
    if not nguon or not nguon.is_file():
        print("Khong tim thay .env nguon — truyen duong dan lam tham so.")
        return
    conn = ket.ket_noi()
    try:
        ds = di_tru(nguon, conn)
    finally:
        conn.close()
    if not ds:
        print("Da di tru truoc do (marker co) hoac .env khong co khoa nao — "
              "khong nap gi.")
        return
    from nen.iam import iam
    ic = iam.ket_noi()
    try:
        for m in ds:
            iam.ghi_nhat_ky(ic, "script-di-tru", "api_key_di_tru_seo",
                            f"{m['id']} {m['loai']} viec={m['viec']} ••••{m['duoi']}")
    finally:
        ic.close()
    print(f"Da nap {len(ds)} khoa tu {nguon} vao ket + cap phat seo-optimize "
          "(trich_kenh xoay vong / sinh_metadata). Chi tiet xem Audit Log (chi duoi 4).")


if __name__ == "__main__":
    main()
