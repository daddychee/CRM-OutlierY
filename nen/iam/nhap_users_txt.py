# -*- coding: utf-8 -*-
"""Migration users.txt (hệ cũ) → iam.db. Dùng khi THAY THẾ thật (P7).

Chạy:  python -m nen.iam.nhap_users_txt <đường users.txt>
Format cũ: ten:bcrypt:bo_phan:level[:phai_doi]  (hash bcrypt giữ nguyên — không ai
phải đổi mật khẩu vì migration). Idempotent: tên đã có trong iam.db → bỏ qua.
"""
import sys

from nen.iam import iam


def nhap(duong: str) -> tuple[int, int]:
    """Trả (số nhập, số bỏ qua)."""
    conn = iam.ket_noi()
    nhap_moi = bo_qua = 0
    with open(duong, "r", encoding="utf-8") as f:
        for dong in f:
            dong = dong.strip()
            if not dong or dong.startswith("#"):
                continue
            phan = dong.split(":")
            if len(phan) < 4:
                continue
            ten, mk_hash, bo_phan, level = phan[0], phan[1], phan[2], int(phan[3])
            phai_doi = len(phan) > 4 and phan[4].strip() == "1"
            if iam.lay_tai_khoan(conn, ten):
                bo_qua += 1
                continue
            # Ghi thẳng (hash sẵn — không qua tao_tai_khoan vì hàm đó hash lại)
            with conn:
                conn.execute(
                    "INSERT INTO tai_khoan (ten, mk_bcrypt, nguoi_ma, bo_phan, level, "
                    "admin_uy_quyen, phai_doi_mk, khoa, tao_luc) VALUES (?,?,NULL,?,?,0,?,0,?)",
                    (ten, mk_hash, bo_phan, level, int(phai_doi), iam._gio()))
            iam.ghi_nhat_ky(conn, "(migration)", "nhap_users_txt", ten)
            nhap_moi += 1
    return nhap_moi, bo_qua


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Cách dùng: python -m nen.iam.nhap_users_txt <đường users.txt>")
        sys.exit(1)
    n, b = nhap(sys.argv[1])
    print(f"Đã nhập {n} tài khoản, bỏ qua {b} (đã tồn tại).")
