# -*- coding: utf-8 -*-
"""MIGRATION MỘT LẦN: khóa YouTube từ bảng api_keys nội bộ radary → KÉT V3
(trang API Keys) + cấp phát theo VIỆC (làm gọn RadarY — Owner 16/08).

- Đọc data/radary/radary.db (bảng api_keys, Fernet bằng data/radary/secret.key;
  giá trị chưa mã hóa thời tiền-Phase-4 đọc thẳng).
- Nạp két loại 'youtube' (them_api_key — bí mật Fernet của KÉT, UI chỉ thấy đuôi).
- Cấp phát GIỮ ĐÚNG NGĂN V2: cột harvest=1 → việc 'harvest'; harvest=0 → việc
  'quet_dinh_ky'; đều xoay_vong (nhiều khóa cùng loại — mockup K5 vòng 4).
- IDEMPOTENT: marker két 'api.di_tru.radary_khoa' — chạy lại không nạp đôi.
- Vết audit CHỈ ĐUÔI 4 — không bao giờ in/ghi giá trị khóa.
- Bảng api_keys nội bộ SAU migration: NGHỈ (app không đọc nữa — khoa_v3), KHÔNG
  xóa (sử liệu).

Chạy tay (Owner quyết thời điểm):  python scripts/di_tru_khoa_radary.py
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cryptography.fernet import Fernet  # noqa: E402

from nen.ket_cau_hinh import ket  # noqa: E402

MARKER = "api.di_tru.radary_khoa"


def _giai_ma(gia_tri: str, f: Fernet | None) -> str:
    if gia_tri.startswith("gAAAA") and f is not None:
        return f.decrypt(gia_tri.encode("ascii")).decode("utf-8")
    return gia_tri


def di_tru(db_radary: Path, secret_key: Path, conn_ket) -> list[dict]:
    """Trả [{id, duoi, viec}] các khóa đã nạp; [] nếu marker đã có (idempotent)."""
    if ket.lay_cau_hinh(conn_ket, MARKER):
        return []
    f = Fernet(secret_key.read_bytes().strip()) if secret_key.exists() else None
    rc = sqlite3.connect(db_radary)
    rc.row_factory = sqlite3.Row
    try:
        rows = rc.execute(
            "SELECT key, harvest FROM api_keys ORDER BY harvest, backup, id").fetchall()
    finally:
        rc.close()
    ra: list[dict] = []
    theo_viec: dict[str, list[str]] = {"harvest": [], "quet_dinh_ky": []}
    da_nap: set[str] = set()
    for r in rows:
        try:
            gia_tri = _giai_ma(r["key"], f)
        except Exception:
            continue                     # khóa rách/không giải mã được — bỏ, không chết cả đợt
        if not gia_tri or gia_tri in da_nap:
            continue                     # trùng giá trị trong chính bảng → nạp MỘT lần
        da_nap.add(gia_tri)
        viec = "harvest" if r["harvest"] else "quet_dinh_ky"
        kid = ket.them_api_key(conn_ket, "youtube", gia_tri)
        theo_viec[viec].append(kid)
        ra.append({"id": kid, "duoi": gia_tri[-4:], "viec": viec})
    for viec, ids in theo_viec.items():
        if ids:
            ket.luu_cap_phat_viec(conn_ket, "radary", viec, ids, "xoay_vong")
    ket.dat_cau_hinh(conn_ket, MARKER, str(len(ra)))
    return ra


def main() -> None:
    db = ROOT / "data" / "radary" / "radary.db"
    sk = ROOT / "data" / "radary" / "secret.key"
    conn = ket.ket_noi()
    try:
        ds = di_tru(db, sk, conn)
    finally:
        conn.close()
    if not ds:
        print("Da di tru truoc do (marker co) — khong nap doi.")
        return
    # Vết audit CHỈ ĐUÔI (trả nợ két-không-vết) — tuyệt đối không in giá trị khóa
    from nen.iam import iam
    ic = iam.ket_noi()
    try:
        for m in ds:
            iam.ghi_nhat_ky(ic, "script-di-tru", "api_key_di_tru_radary",
                            f"{m['id']} viec={m['viec']} ••••{m['duoi']}")
    finally:
        ic.close()
    print(f"Da nap {len(ds)} khoa YouTube vao ket + cap phat radary "
          f"(harvest={sum(1 for x in ds if x['viec'] == 'harvest')}, "
          f"quet_dinh_ky={sum(1 for x in ds if x['viec'] == 'quet_dinh_ky')}). "
          "Chi tiet xem Audit Log (chi duoi 4).")


if __name__ == "__main__":
    main()
