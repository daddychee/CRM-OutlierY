# -*- coding: utf-8 -*-
"""Dọn ô tick di sản V2 slug 'seo' trong quyen_override.

BỆNH: di trú V2 (19/08) ghi quyen_override với app_slug='seo' và tên hành động
đời cũ, trong khi hợp đồng V3 khai slug 'seo-optimize' với tên hành động mới.
co_quyen chỉ tra app_slug IN (<slug thật>, '*') nên các dòng này KHÔNG khớp gì:
tick vẫn nằm trong DB, vẫn hiện trong sổ P5 toàn hệ, mà không ai được/mất quyền
— ô CHẾT LẶNG LẼ (cùng họ bài học 04/08 "sổ map theo danh tính cũ").

QUYẾT ĐỊNH OWNER 19/08: XÓA, không quy đổi. Lý do: quy đổi = HỒI SINH tick đang
chết → đổi quyền người đang làm việc (đo thật: lamtn bị tước toàn quyền vận hành
SEO, huonggiangsss được thêm vai admin — nghịch luật "Quản trị chỉ Owner" 04/08).
Xóa giữ nguyên hành vi hiện tại: mọi người chạy theo luật mặc định V3. Muốn hạn
chế ai thì tick lại bằng UI — bảng giờ đã ghi đúng slug seo-optimize.

Mặc định LIỆT KÊ (không ghi). Xóa thật: --chay (backup VACUUM INTO chạy TRƯỚC —
kỷ luật 19/08). Idempotent: chạy lại khi sổ đã sạch chỉ báo "không còn dòng nào".
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nen.iam import iam  # noqa: E402

SLUG_CU = "seo"


def _doc(conn):
    return [dict(r) for r in conn.execute(
        "SELECT * FROM quyen_override WHERE app_slug=? ORDER BY ten_tai_khoan, hanh_dong",
        (SLUG_CU,))]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--chay", action="store_true", help="xóa thật (mặc định chỉ liệt kê)")
    tham_so = ap.parse_args()

    conn = iam.ket_noi()
    try:
        cu = _doc(conn)
        if not cu:
            print(f"Không còn dòng nào mang slug '{SLUG_CU}' — sổ đã sạch.")
            return 0
        print(f"{len(cu)} dòng di sản slug '{SLUG_CU}' (KHÔNG có hiệu lực, sẽ XÓA):\n")
        print(f"{'TÀI KHOẢN':16} {'HÀNH ĐỘNG':18} {'ĐẶT':6} LÝ DO")
        for r in cu:
            print(f"{r['ten_tai_khoan']:16} {r['hanh_dong']:18} "
                  f"{('cho' if r['cho_phep'] else 'chặn'):6} {r['ly_do'] or '—'}")

        if not tham_so.chay:
            print("\n(chỉ liệt kê — thêm --chay để xóa thật; backup tự chạy trước khi ghi)")
            return 0

        bk = ROOT / "data" / "nen" / "backup" / "iam-truoc-don-slug-seo.db"
        bk.parent.mkdir(parents=True, exist_ok=True)
        conn.execute("VACUUM INTO ?", (str(bk),))
        print(f"\nĐã backup: {bk}")

        with conn:
            conn.execute("DELETE FROM quyen_override WHERE app_slug=?", (SLUG_CU,))
        iam.ghi_nhat_ky(conn, "(don so)", "don_override_chet",
                        f"xóa {len(cu)} dòng slug '{SLUG_CU}' (di sản V2, không hiệu lực)")
        print(f"Đã xóa {len(cu)} dòng. Còn lại slug cũ: {len(_doc(conn))}")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
