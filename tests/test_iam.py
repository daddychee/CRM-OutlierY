# -*- coding: utf-8 -*-
"""Test IAM (P2) — ghim: schema migration, 2 giỏ quyền, 3 luật sắt Admin ủy quyền,
chống tự khóa, nhật ký, migration users.txt. Đây là 'ONE runnable check' của IAM."""
import bcrypt
import pytest

from nen.iam import iam
from nen.iam.nhap_users_txt import nhap


_gensalt_goc = bcrypt.gensalt


@pytest.fixture()
def conn(tmp_path, monkeypatch):
    monkeypatch.setenv("IAM_DB", str(tmp_path / "iam.db"))
    # bcrypt rounds=4 cho test nhanh — không đổi hành vi, chỉ đổi tốc độ
    monkeypatch.setattr(bcrypt, "gensalt", lambda rounds=12: _gensalt_goc(4))
    c = iam.ket_noi()
    yield c
    c.close()


def _owner(conn):
    tk = iam.tao_tai_khoan(conn, None, "owner", "mk-owner", "Ban quản trị", 5,
                           phai_doi_mk=False)
    return iam.claims_cua(tk)


# ---------- khởi tạo + migration ----------

def test_migrate_ghi_phien_ban(conn):
    v = conn.execute("SELECT phien_ban FROM schema_version").fetchone()["phien_ban"]
    assert v == 1


def test_user_dau_tien_phai_owner(conn):
    with pytest.raises(iam.LoiIam):
        iam.tao_tai_khoan(conn, None, "nhanvien", "123456", "Kinh doanh", 2)
    _owner(conn)  # level 5 thì được


def test_xac_thuc_dung_sai(conn):
    _owner(conn)
    assert iam.xac_thuc(conn, "owner", "mk-owner")["level"] == 5
    assert iam.xac_thuc(conn, "owner", "sai") is None
    assert iam.xac_thuc(conn, "khong-co", "mk") is None


def test_tai_khoan_khoa_khong_dang_nhap_duoc(conn):
    ow = _owner(conn)
    iam.tao_tai_khoan(conn, ow, "nv", "123456", "Kinh doanh", 2)
    iam.sua_tai_khoan(conn, ow, "nv", khoa=True)
    assert iam.xac_thuc(conn, "nv", "123456") is None


# ---------- hai giỏ quyền ----------

def test_gio_owner_tuyet_doi_chi_level5(conn):
    ow = _owner(conn)
    iam.tao_tai_khoan(conn, ow, "admin", "123456", "Kinh doanh", 4)
    iam.sua_tai_khoan(conn, ow, "admin", admin_uy_quyen=True)
    admin = iam.claims_cua(iam.lay_tai_khoan(conn, "admin"))
    assert iam.co_quyen(ow, "vault", conn=conn)
    assert not iam.co_quyen(admin, "vault", conn=conn)      # admin ủy quyền vẫn KHÔNG


def test_gio_uy_quyen_owner_va_admin(conn):
    ow = _owner(conn)
    iam.tao_tai_khoan(conn, ow, "admin", "123456", "Kinh doanh", 4)
    iam.tao_tai_khoan(conn, ow, "quanly4", "123456", "Kinh doanh", 4)
    iam.sua_tai_khoan(conn, ow, "admin", admin_uy_quyen=True)
    admin = iam.claims_cua(iam.lay_tai_khoan(conn, "admin"))
    l4_thuong = iam.claims_cua(iam.lay_tai_khoan(conn, "quanly4"))
    assert iam.co_quyen(admin, "quan_tai_khoan", conn=conn)
    assert not iam.co_quyen(l4_thuong, "quan_tai_khoan", conn=conn)  # L4 thường: không


def test_tick_owner_tuyet_doi_bi_chan(conn):
    ow = _owner(conn)
    iam.tao_tai_khoan(conn, ow, "nv", "123456", "Kinh doanh", 2)
    with pytest.raises(iam.LoiIam):
        iam.gan_override(conn, ow, "nv", "*", "vault", True)


def test_tick_le_thang_luat_mac_dinh(conn):
    ow = _owner(conn)
    iam.tao_tai_khoan(conn, ow, "nv", "123456", "Kinh doanh", 2)
    nv = iam.claims_cua(iam.lay_tai_khoan(conn, "nv"))
    assert not iam.co_quyen(nv, "nap_tai_lieu", conn=conn)          # mặc định: không
    iam.gan_override(conn, ow, "nv", "*", "nap_tai_lieu", True)     # tick cho
    assert iam.co_quyen(nv, "nap_tai_lieu", conn=conn)
    iam.gan_override(conn, ow, "nv", "*", "nap_tai_lieu", None)     # gỡ tick
    assert not iam.co_quyen(nv, "nap_tai_lieu", conn=conn)


def test_vao_app_theo_min_level(conn):
    ow = _owner(conn)
    iam.tao_tai_khoan(conn, ow, "nv", "123456", "Kinh doanh", 2)
    nv = iam.claims_cua(iam.lay_tai_khoan(conn, "nv"))
    assert iam.co_quyen(nv, "vao", "app-mau", conn)   # min_level 1
    assert iam.vai_cho_app(nv, "app-mau") == "viewer"
    assert iam.vai_cho_app(ow, "app-mau") == "owner"


# ---------- ba luật sắt ----------

def test_luat_sat_1_khong_tu_nang_quyen(conn):
    ow = _owner(conn)
    iam.tao_tai_khoan(conn, ow, "admin", "123456", "Kinh doanh", 4)
    iam.sua_tai_khoan(conn, ow, "admin", admin_uy_quyen=True)
    admin = iam.claims_cua(iam.lay_tai_khoan(conn, "admin"))
    with pytest.raises(iam.LoiIam):
        iam.sua_tai_khoan(conn, admin, "admin", level=5)


def test_luat_sat_2_khong_dung_owner(conn):
    ow = _owner(conn)
    iam.tao_tai_khoan(conn, ow, "admin", "123456", "Kinh doanh", 4)
    iam.sua_tai_khoan(conn, ow, "admin", admin_uy_quyen=True)
    admin = iam.claims_cua(iam.lay_tai_khoan(conn, "admin"))
    with pytest.raises(iam.LoiIam):
        iam.sua_tai_khoan(conn, admin, "owner", khoa=True)
    with pytest.raises(iam.LoiIam):
        iam.xoa_tai_khoan(conn, admin, "owner")
    with pytest.raises(iam.LoiIam):
        iam.doi_mat_khau(conn, admin, "owner", "hack123")


def test_luat_sat_3_moi_thao_tac_co_vet(conn):
    ow = _owner(conn)
    iam.tao_tai_khoan(conn, ow, "nv", "123456", "Kinh doanh", 2)
    iam.sua_tai_khoan(conn, ow, "nv", level=3)
    iam.xoa_tai_khoan(conn, ow, "nv")
    hanh_dong = [r["hanh_dong"] for r in iam.doc_nhat_ky(conn)]
    assert "tao_tai_khoan" in hanh_dong
    assert "sua_tai_khoan" in hanh_dong
    assert "xoa_tai_khoan" in hanh_dong


def test_chi_owner_duoc_bat_admin_uy_quyen(conn):
    ow = _owner(conn)
    iam.tao_tai_khoan(conn, ow, "admin", "123456", "Kinh doanh", 4)
    iam.sua_tai_khoan(conn, ow, "admin", admin_uy_quyen=True)
    iam.tao_tai_khoan(conn, ow, "nv", "123456", "Kinh doanh", 2)
    admin = iam.claims_cua(iam.lay_tai_khoan(conn, "admin"))
    with pytest.raises(iam.LoiIam):
        iam.sua_tai_khoan(conn, admin, "nv", admin_uy_quyen=True)


# ---------- chống tự khóa ----------

def test_owner_khong_tu_xoa_minh(conn):
    ow = _owner(conn)
    with pytest.raises(iam.LoiIam):
        iam.xoa_tai_khoan(conn, ow, "owner")


def test_tu_doi_mat_khau_minh_luon_duoc(conn):
    ow = _owner(conn)
    iam.tao_tai_khoan(conn, ow, "nv", "123456", "Kinh doanh", 2, phai_doi_mk=True)
    nv = iam.claims_cua(iam.lay_tai_khoan(conn, "nv"))
    iam.doi_mat_khau(conn, nv, "nv", "mk-moi-6")      # tự đổi: không cần quyền gì
    assert iam.xac_thuc(conn, "nv", "mk-moi-6")
    assert iam.lay_tai_khoan(conn, "nv")["phai_doi_mk"] == 0


# ---------- hồ sơ người ----------

def test_tao_nguoi_ma_tu_sinh(conn):
    ow = _owner(conn)
    ns1 = iam.tao_nguoi(conn, ow, "Nguyễn Văn A", "Kinh doanh", "SEO")
    ns2 = iam.tao_nguoi(conn, ow, "Trần Thị B", "Vận hành - Sản xuất")
    assert ns1["ma"] == "NS-001" and ns2["ma"] == "NS-002"


def test_nhan_vien_khong_tao_duoc_nguoi(conn):
    ow = _owner(conn)
    iam.tao_tai_khoan(conn, ow, "nv", "123456", "Kinh doanh", 2)
    nv = iam.claims_cua(iam.lay_tai_khoan(conn, "nv"))
    with pytest.raises(iam.LoiIam):
        iam.tao_nguoi(conn, nv, "Ai Đó", "Kinh doanh")


# ---------- migration users.txt hệ cũ ----------

def test_nhap_users_txt_giu_hash_va_level(conn, tmp_path):
    h = bcrypt.hashpw(b"mk-cu", bcrypt.gensalt(rounds=4)).decode()
    f = tmp_path / "users.txt"
    f.write_text(
        "# comment\n"
        f"sep:{h}:Ban quản trị:5\n"
        f"nv-cu:{h}:Kinh doanh:2:1\n", encoding="utf-8")
    n, b = nhap(str(f))
    assert (n, b) == (2, 0)
    assert iam.xac_thuc(conn, "sep", "mk-cu")["level"] == 5   # hash GIỮ NGUYÊN
    assert iam.lay_tai_khoan(conn, "nv-cu")["phai_doi_mk"] == 1
    n2, b2 = nhap(str(f))                                     # idempotent
    assert (n2, b2) == (0, 2)
