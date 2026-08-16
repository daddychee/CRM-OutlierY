# -*- coding: utf-8 -*-
"""MIGRATION MỘT LẦN: khóa API của Content Ultimate (file .env hệ cũ) → KÉT V3
(trang API Keys) + cấp phát theo VIỆC (khuôn scripts/di_tru_khoa_radary.py).

NGUỒN: snapshot data/content-ultimate/.env nếu có; KHÔNG có thì đọc .env của hệ
cũ C:\\OutlierY\\apps\\content-ultimate (CHỈ ĐỌC — không ghi gì vào C:\\). Đường
nguồn đổi được bằng tham số dòng lệnh.

ÁNH XẠ (đúng viec_api khai trong apps.json):
  GLM_API_KEY        → loại llm (nhà glm, model từ GLM_MODEL) → việc viet_kich_ban
                        + phan_tich_outline (cùng một khóa, 2 việc đều gọi GLM)
  ANTHROPIC_API_KEY  → loại llm (nhà claude) → viet_kich_ban (nếu có)
  TRANSCRIPT_API_KEY → loại transcript → việc lay_transcript
  YOUTUBE_API_KEY    → loại youtube    → việc lay_comment
KHÔNG đụng ADMIN_USERS / HTPASSWD_FILE (thuộc hệ tài khoản cũ — đã nghỉ, quyền về
OUTLIERY).

IDEMPOTENT: marker két 'api.di_tru.content_khoa'. Vết audit CHỈ ĐUÔI 4 ký tự —
không bao giờ in/ghi giá trị khóa.

Chạy tay (Owner quyết thời điểm):
    python scripts/di_tru_khoa_content.py [đường/tới/.env]
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nen.ket_cau_hinh import ket  # noqa: E402

MARKER = "api.di_tru.content_khoa"
NGUON_MAC_DINH = [
    ROOT / "data" / "content-ultimate" / ".env",
    Path(r"C:\OutlierY\apps\content-ultimate\.env"),      # hệ cũ — CHỈ ĐỌC
]
# biến .env → (loại két, nhà, các việc được cấp)
ANH_XA = {
    "GLM_API_KEY": ("llm", "glm", ["viet_kich_ban", "phan_tich_outline"]),
    "ANTHROPIC_API_KEY": ("llm", "claude", ["viet_kich_ban"]),
    "TRANSCRIPT_API_KEY": ("transcript", "", ["lay_transcript"]),
    "YOUTUBE_API_KEY": ("youtube", "", ["lay_comment"]),
}


def _doc_env(p: Path) -> dict[str, str]:
    ra: dict[str, str] = {}
    for line in p.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s and not s.startswith("#") and "=" in s:
            k, v = s.split("=", 1)
            if v.strip():
                ra[k.strip()] = v.strip()
    return ra


def di_tru(env_path: Path, conn_ket) -> list[dict]:
    """Trả [{id, duoi, loai, viec}]; [] nếu marker đã có (idempotent)."""
    if ket.lay_cau_hinh(conn_ket, MARKER):
        return []
    env = _doc_env(env_path)
    model = env.get("GLM_MODEL", "")
    ra: list[dict] = []
    theo_viec: dict[str, list[str]] = {}
    for bien, (loai, nha, cac_viec) in ANH_XA.items():
        gia_tri = env.get(bien)
        if not gia_tri:
            continue
        kid = ket.them_api_key(conn_ket, loai, gia_tri, nha=nha,
                               model=model if nha == "glm" else "")
        for viec in cac_viec:
            theo_viec.setdefault(viec, []).append(kid)
        ra.append({"id": kid, "duoi": gia_tri[-4:], "loai": loai,
                   "viec": ",".join(cac_viec)})
    for viec, ids in theo_viec.items():
        ket.luu_cap_phat_viec(conn_ket, "content-ultimate", viec, ids,
                              "du_phong" if len(ids) > 1 else "mot_khoa",
                              model if viec in ("viet_kich_ban", "phan_tich_outline") else "")
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
        print("Da di tru truoc do (marker co) — khong nap doi.")
        return
    from nen.iam import iam
    ic = iam.ket_noi()
    try:
        for m in ds:
            iam.ghi_nhat_ky(ic, "script-di-tru", "api_key_di_tru_content",
                            f"{m['id']} {m['loai']} viec={m['viec']} ••••{m['duoi']}")
    finally:
        ic.close()
    print(f"Da nap {len(ds)} khoa tu {nguon} vao ket + cap phat content-ultimate. "
          "Chi tiet xem Audit Log (chi duoi 4).")


if __name__ == "__main__":
    main()
