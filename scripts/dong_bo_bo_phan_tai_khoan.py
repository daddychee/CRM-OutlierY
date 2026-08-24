# -*- coding: utf-8 -*-
"""Đồng bộ bộ phận TÀI KHOẢN theo HỒ SƠ nhân sự (một nguồn sự thật).

BỆNH (Owner báo 19/08): "chuyển bộ phận trong HR nhưng Permissions vẫn vai cũ".
Quyền tính theo `tai_khoan.bo_phan`, còn HR sửa `nguoi.bo_phan` — bản cũ
`sua_nguoi` không đồng bộ nên hai sổ trôi khỏi nhau: người đã chuyển phòng vẫn
giữ quyền phòng cũ. Code đã vá (sua_nguoi kéo theo tài khoản; sửa bộ phận ở tab
Accounts bị chặn khi tài khoản đã nối hồ sơ). Script này dọn bản ghi LỆCH SẴN.

Mặc định LIỆT KÊ. Ghi thật: --chay (backup VACUUM INTO chạy TRƯỚC). Idempotent.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nen.iam import iam  # noqa: E402

CAU_LECH = """SELECT n.ma, n.ho_ten, n.bo_phan AS bp_ho_so, n.vi_tri,
                     t.ten AS tk, t.bo_phan AS bp_tk
              FROM nguoi n JOIN tai_khoan t ON t.nguoi_ma = n.ma
              WHERE n.bo_phan <> t.bo_phan
              ORDER BY n.ma"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--chay", action="store_true", help="ghi thật (mặc định liệt kê)")
    ap.add_argument("--chi", default="", help="chỉ xử lý các mã NS này (ngăn bằng dấu phẩy)")
    tham_so = ap.parse_args()
    loc = {m.strip() for m in tham_so.chi.split(",") if m.strip()}

    conn = iam.ket_noi()
    try:
        lech = [dict(r) for r in conn.execute(CAU_LECH)]
        if loc:
            lech = [r for r in lech if r["ma"] in loc]
        if not lech:
            print("Không có tài khoản nào lệch bộ phận so với hồ sơ.")
            return 0
        print(f"{len(lech)} tài khoản lệch (sẽ lấy theo HỒ SƠ):\n")
        for r in lech:
            print(f"  {r['ma']} · {r['ho_ten']}  [{r['vi_tri'] or '—'}]")
            print(f"      {r['tk']}: '{r['bp_tk']}' → '{r['bp_ho_so']}'")

        if not tham_so.chay:
            print("\n(chỉ liệt kê — thêm --chay để ghi thật; backup tự chạy trước)")
            return 0

        bk = ROOT / "data" / "nen" / "backup" / "iam-truoc-dong-bo-bo-phan.db"
        bk.parent.mkdir(parents=True, exist_ok=True)
        if bk.exists():
            bk.unlink()
        conn.execute("VACUUM INTO ?", (str(bk),))
        print(f"\nĐã backup: {bk}")

        for r in lech:
            with conn:
                conn.execute("UPDATE tai_khoan SET bo_phan=? WHERE ten=?",
                             (r["bp_ho_so"], r["tk"]))
            iam.ghi_nhat_ky(conn, "(dong bo bo phan)", "sua_tai_khoan",
                            f"{r['tk']}: bo_phan '{r['bp_tk']}' → '{r['bp_ho_so']}' "
                            f"(theo hồ sơ {r['ma']})")
        con_lai = [dict(r) for r in conn.execute(CAU_LECH)]
        print(f"Đã đồng bộ {len(lech)} tài khoản. Còn lệch: {len(con_lai)}")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
