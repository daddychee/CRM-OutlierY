# -*- coding: utf-8 -*-
"""GĐ4 — Chuẩn mật khẩu (05/09/2026).

LỖ N8 (rà 05/09): `iam.py` chỉ đòi `len(mat_khau) >= 6`, không kiểm độ mạnh.
Nghịch lý: `nas_sync.mat_khau_dat_chuan` ĐÃ CÓ chuẩn mạnh hơn hẳn (>=8, HOA +
thường + số, không chứa tên đăng nhập) nhưng chỉ dùng để BÁO trạng thái NAS, không
chặn việc đặt mật khẩu yếu ở IAM.

→ Dùng lại chính hàm đã có (mở rộng chuẩn có sẵn, không phát minh mới). Lợi kép:
mật khẩu đạt chuẩn IAM thì đồng bộ NAS cũng không bị Windows từ chối.

TƯƠNG THÍCH NGƯỢC: chỉ áp cho mật khẩu ĐẶT MỚI. 20 tài khoản hiện có (mật khẩu đã
băm bcrypt, không đọc lại được) vẫn đăng nhập bình thường cho tới khi họ tự đổi.
"""
import pytest

from nen.iam import iam


@pytest.fixture
def conn(tmp_path, monkeypatch):
    monkeypatch.setenv("IAM_DB", str(tmp_path / "iam.db"))
    c = iam.ket_noi()
    yield c
    c.close()


YEU = ["123456", "abcdef", "ABCDEF", "abc12345", "ABC12345", "Ab1"]
MANH = ["MatKhau123", "Xy9zAbcd", "Trung1Nam2"]


@pytest.mark.parametrize("mk", YEU)
def test_tu_choi_mat_khau_yeu(conn, mk):
    with pytest.raises(iam.LoiIam):
        iam.tao_tai_khoan(conn, None, "owner1", mk, "Ban quản trị", 5)


@pytest.mark.parametrize("mk", MANH)
def test_chap_nhan_mat_khau_manh(conn, mk):
    tk = iam.tao_tai_khoan(conn, None, "owner1", mk, "Ban quản trị", 5)
    assert tk is not None


def test_tu_choi_mat_khau_chua_ten_dang_nhap(conn):
    """Windows từ chối mật khẩu chứa tên tài khoản → NAS không sinh được."""
    with pytest.raises(iam.LoiIam):
        iam.tao_tai_khoan(conn, None, "nguyenvan", "Nguyenvan123", "Ban quản trị", 5)
