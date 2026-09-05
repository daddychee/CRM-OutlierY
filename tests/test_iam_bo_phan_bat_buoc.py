# -*- coding: utf-8 -*-
"""GĐ3 — IAM: cấm tạo tài khoản bộ phận RỖNG (05/09/2026).

Đi kèm bản vá RBAC fail-open (mục A2). Sửa RBAC là bịt hậu quả; chặn ở đây là bịt
NGUỒN: cột `bo_phan` cho phép rỗng (migration 001 DEFAULT '') và `tao_tai_khoan`
không kiểm gì, nên Owner bỏ trống ô bộ phận là tạo ra tài khoản "vô bộ phận".

Sau bản vá RBAC, tài khoản vô bộ phận không còn nguy hiểm (chỉ thấy tài liệu công
khai) — nhưng nó vẫn là trạng thái VÔ NGHĨA về nghiệp vụ, và là mìn nếu ai đó nới
lại luật RBAC sau này. Chặn từ gốc.
"""
import pytest

from nen.iam import iam


@pytest.fixture
def conn(tmp_path, monkeypatch):
    monkeypatch.setenv("IAM_DB", str(tmp_path / "iam.db"))
    c = iam.ket_noi()
    yield c
    c.close()


def test_tu_choi_bo_phan_rong(conn):
    chu = iam.tao_tai_khoan(conn, None, "owner1", "matkhau123", "Ban quản trị", 5)
    for xau in ["", "   ", None]:
        with pytest.raises(iam.LoiIam):
            iam.tao_tai_khoan(conn, chu, "nv1", "matkhau123", xau, 1)


def test_bo_phan_hop_le_van_tao_duoc(conn):
    chu = iam.tao_tai_khoan(conn, None, "owner1", "matkhau123", "Ban quản trị", 5)
    tk = iam.tao_tai_khoan(conn, chu, "nv1", "matkhau123", "Kinh doanh", 1)
    assert tk is not None
    assert iam.lay_tai_khoan(conn, "nv1")["bo_phan"] == "Kinh doanh"
