# -*- coding: utf-8 -*-
"""Gieo PHÂN CÔNG ban đầu cho SEO Optimize từ `profile.created_by` (24/08/2026).

Trước 24/08 câu *"ai được ghi lên kênh nào"* trả lời bằng `created_by` nằm trong app. Nay
nó là bảng `phan_cong` của khối nền. Script này chuyển trạng thái ĐANG CHẠY sang sổ mới để
**không ai mất quyền trong lúc đổi** — người đang sửa được kênh nào thì sau khi đổi vẫn sửa
được đúng kênh đó.

**Người không vào được app thì KHÔNG gieo** (khóa, đổi bộ phận, tài khoản không còn): gieo
vào là chép nguyên cái hỏng-câm cũ sang sổ mới. Những kênh đó liệt kê riêng dưới nhãn
*CẦN GIAO LẠI* để Manager quyết — máy không đoán hộ.

    python tools/scripts/gieo_phan_cong_seo.py                # chỉ LIỆT KÊ (mặc định)
    python tools/scripts/gieo_phan_cong_seo.py --chay         # GHI (tự backup iam.db trước)
    python tools/scripts/gieo_phan_cong_seo.py --chay --boi Bot

Chạy lại được nhiều lần: `dat_phan_cong` đặt cả cụm nên không nhân đôi.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

GOC = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(GOC))

from nen.iam import iam                                            # noqa: E402

APP = "seo-optimize"
LOAI = "kenh"


def _ho_so_kenh() -> list[dict]:
    thu_muc = Path(os.environ.get("SEO_DATA_DIR") or (GOC / "data" / APP)) / "profiles"
    ra = []
    for f in sorted(thu_muc.glob("*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except Exception as e:                                     # noqa: BLE001
            print(f"  ! bỏ qua {f.name}: {e}")
            continue
        ra.append({"slug": d.get("slug") or f.stem,
                   "ten": d.get("channel") or f.stem,
                   "nguoi_tao": (d.get("created_by") or "").strip()})
    return ra


def _sao_luu(conn) -> Path:
    """Backup TRƯỚC mọi thao tác ghi hàng loạt — kỷ luật mặc định, không đợi nhắc."""
    dich = Path(iam._duong_db()).parent / \
        f"iam-truoc-gieo-phan-cong-{datetime.now():%Y%m%d-%H%M}.db"
    conn.execute("VACUUM INTO ?", (str(dich),))
    return dich


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--chay", action="store_true", help="GHI thật (mặc định chỉ liệt kê)")
    ap.add_argument("--boi", default="", help="tài khoản đứng tên thao tác (mặc định: Owner đầu tiên)")
    t = ap.parse_args()

    conn = iam.ket_noi()
    try:
        if t.boi:
            tk = iam.lay_tai_khoan(conn, t.boi)
            if not tk:
                print(f"Không có tài khoản '{t.boi}'.")
                return 2
        else:
            tk = next((x for x in iam.liet_ke_tai_khoan(conn)
                       if x["level"] >= iam.OWNER_LEVEL and not x["khoa"]), None)
            if not tk:
                print("Không tìm thấy tài khoản Owner nào để đứng tên thao tác.")
                return 2
        ai_lam = iam.claims_cua(tk)

        gieo, can_giao_lai, chua_ai, da_co = [], [], [], []
        for k in _ho_so_kenh():
            if iam.nguoi_cua(conn, APP, LOAI, k["slug"]):
                da_co.append(k)
                continue
            if not k["nguoi_tao"]:
                chua_ai.append(k)
                continue
            nguoi = iam.lay_tai_khoan(conn, k["nguoi_tao"])
            if not nguoi:
                k["ly_do"] = "tài khoản không còn"
            elif nguoi["khoa"]:
                k["ly_do"] = "tài khoản đang khóa"
            elif not iam.co_quyen(iam.claims_cua(nguoi), "vao", APP, conn):
                k["ly_do"] = f"không vào được app (bộ phận {nguoi['bo_phan']}, cấp {nguoi['level']})"
            else:
                gieo.append(k)
                continue
            can_giao_lai.append(k)

        print(f"\n=== SEO Optimize — gieo phân công từ created_by "
              f"({'GHI THẬT' if t.chay else 'chỉ liệt kê'}) ===")
        print(f"Người đứng tên thao tác: {ai_lam['ten']}\n")
        print(f"GIEO ĐƯỢC ({len(gieo)}):")
        for k in gieo:
            print(f"  {k['slug']:45} -> {k['nguoi_tao']}")
        print(f"\nCẦN GIAO LẠI — người tạo không dùng được app nữa ({len(can_giao_lai)}):")
        for k in can_giao_lai:
            print(f"  {k['slug']:45} (tạo bởi {k['nguoi_tao']}: {k['ly_do']})")
        print(f"\nCHƯA AI ĐỨNG TÊN ({len(chua_ai)}):")
        for k in chua_ai:
            print(f"  {k['slug']}")
        if da_co:
            print(f"\nĐÃ CÓ PHÂN CÔNG, KHÔNG ĐỤNG ({len(da_co)}):")
            for k in da_co:
                print(f"  {k['slug']:45} -> {', '.join(iam.nguoi_cua(conn, APP, LOAI, k['slug']))}")

        if not t.chay:
            print("\n(Chưa ghi gì. Thêm --chay để ghi thật.)")
            return 0
        if not gieo:
            print("\nKhông có gì để ghi.")
            return 0
        print(f"\nBackup: {_sao_luu(conn)}")
        for k in gieo:
            iam.dat_phan_cong(conn, ai_lam, APP, LOAI, k["slug"], [k["nguoi_tao"]],
                              ghi_chu="gieo từ created_by (đổi sang trục B 24/08)")
        print(f"Đã ghi {len(gieo)} phân công.")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
