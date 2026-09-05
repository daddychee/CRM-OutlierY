# -*- coding: utf-8 -*-
"""GĐ4 — Thu hồi phiên khi đổi mật khẩu (05/09/2026).

LỖ N3 (rà 05/09): không có bảng phiên → `user_hien_tai` chỉ kiểm tài khoản còn
tồn tại + cờ khóa. Đổi mật khẩu KHÔNG giết phiên cũ; cookie bị cắp dùng được
trọn 30 ngày, cách duy nhất cắt là khóa hẳn tài khoản.

Cách làm: cột `phien_tu_luc` — cookie ký TRƯỚC mốc đó là hết hiệu lực.
"""
import time

import pytest

from nen.iam import iam


@pytest.fixture
def conn(tmp_path, monkeypatch):
    monkeypatch.setenv("IAM_DB", str(tmp_path / "iam.db"))
    c = iam.ket_noi()
    yield c
    c.close()


def test_cot_phien_tu_luc_ton_tai(conn):
    cot = [r[1] for r in conn.execute("PRAGMA table_info(tai_khoan)")]
    assert "phien_tu_luc" in cot


def test_doi_mat_khau_day_moc_len(conn):
    iam.tao_tai_khoan(conn, None, "owner1", "MatKhau123", "Ban quản trị", 5)
    chu = iam.claims_cua(iam.lay_tai_khoan(conn, "owner1"))
    truoc = iam.moc_phien(conn, "owner1")
    time.sleep(1.1)
    iam.doi_mat_khau(conn, chu, "owner1", "MatKhauMoi456")
    assert iam.moc_phien(conn, "owner1") > truoc


def test_phien_ky_truoc_moc_bi_tu_choi(conn):
    iam.tao_tai_khoan(conn, None, "owner1", "MatKhau123", "Ban quản trị", 5)
    ky_luc = int(time.time())
    time.sleep(1.1)
    iam.thu_hoi_phien(conn, "owner1")
    assert iam.phien_con_hieu_luc(conn, "owner1", ky_luc) is False


def test_phien_ky_sau_moc_van_song(conn):
    iam.tao_tai_khoan(conn, None, "owner1", "MatKhau123", "Ban quản trị", 5)
    iam.thu_hoi_phien(conn, "owner1")
    time.sleep(1.1)
    assert iam.phien_con_hieu_luc(conn, "owner1", int(time.time())) is True


def test_tai_khoan_chua_tung_thu_hoi_thi_phien_song(conn):
    """Tương thích ngược: 20 tài khoản hiện có cột rỗng → phiên vẫn sống."""
    iam.tao_tai_khoan(conn, None, "owner1", "MatKhau123", "Ban quản trị", 5)
    conn.execute("UPDATE tai_khoan SET phien_tu_luc='' WHERE ten='owner1'")
    conn.commit()
    assert iam.phien_con_hieu_luc(conn, "owner1", 0) is True


def test_moc_phien_dung_UTC_khong_dua_vao_mui_gio_may():
    """BẪY ĐÃ TRÁNH 05/09 — ghim lại để không ai đổi về `_gio()`.

    `_gio()` trả giờ ĐỊA PHƯƠNG KHÔNG múi giờ; cookie itsdangerous ký theo UTC.
    Máy chủ này đang chạy UTC nên lệch 0 giây, nhưng đổi múi giờ máy là mốc nhảy
    tới TƯƠNG LAI → mọi phiên bị coi hết hiệu lực → ĐĂNG XUẤT TOÀN BỘ NGƯỜI DÙNG.
    """
    from datetime import datetime
    moc = iam._gio_utc()
    d = datetime.fromisoformat(moc)
    assert d.tzinfo is not None, "mốc phiên PHẢI mang múi giờ tường minh"
    # và phải sát thời điểm hiện tại theo UTC (không lệch hàng giờ)
    from datetime import timezone
    lech = abs(d.timestamp() - datetime.now(timezone.utc).timestamp())
    assert lech < 5, f"mốc lệch {lech:.0f}s so với UTC — sai hệ quy chiếu"
