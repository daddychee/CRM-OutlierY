# -*- coding: utf-8 -*-
"""Tạo users TEST vào iam.db (P2 — thay bản users.txt của P1).

Chạy từ root:  python -m nen.gateway.tao_user_test
3 tài khoản: owner / quanly / nhanvien — mật khẩu chung: test123
(quanly được bật admin_uy_quyen để thử vai Admin ủy quyền.)
KHÔNG dùng cho bản thay thế thật — user thật migrate từ hệ cũ.
"""
from nen.iam import iam


def main() -> None:
    conn = iam.ket_noi()
    if iam.dem_tai_khoan(conn) > 0:
        print("iam.db đã có tài khoản — không ghi đè. Xóa data/nen/iam.db nếu muốn làm lại.")
        return
    owner = iam.tao_tai_khoan(conn, None, "owner", "test123", "Ban quản trị", 5,
                              phai_doi_mk=False)
    claims_owner = iam.claims_cua(owner)
    iam.tao_tai_khoan(conn, claims_owner, "quanly", "test123", "Kinh doanh", 4,
                      phai_doi_mk=False)
    iam.sua_tai_khoan(conn, claims_owner, "quanly", admin_uy_quyen=True)
    iam.tao_tai_khoan(conn, claims_owner, "nhanvien", "test123",
                      "Vận hành - Sản xuất", 2, phai_doi_mk=False)
    print("Đã tạo trong iam.db: owner(L5) / quanly(L4, Admin ủy quyền) / "
          "nhanvien(L2) — mật khẩu: test123")


if __name__ == "__main__":
    main()
