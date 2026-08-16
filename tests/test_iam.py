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
    # Ghim LUẬT (không ghim số): phiên bản schema = số file .sql trong migrations/
    # — ghim số mặt chữ là test tự vỡ mỗi lần thêm migration (bài học self-test 05/08).
    so_migration = len(list(iam.DUONG_MIGRATIONS.glob("*.sql")))
    v = conn.execute("SELECT phien_ban FROM schema_version").fetchone()["phien_ban"]
    assert v == so_migration >= 1


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
    iam.gan_override(conn, ow, "nv", "*", "nap_tai_lieu", True, "ly do test")
    assert iam.co_quyen(nv, "nap_tai_lieu", conn=conn)
    iam.gan_override(conn, ow, "nv", "*", "nap_tai_lieu", None)     # gỡ tick
    assert not iam.co_quyen(nv, "nap_tai_lieu", conn=conn)


def test_vao_app_theo_min_level(conn):
    ow = _owner(conn)
    iam.tao_tai_khoan(conn, ow, "nv", "123456", "Kinh doanh", 2)
    nv = iam.claims_cua(iam.lay_tai_khoan(conn, "nv"))
    assert iam.co_quyen(nv, "vao", "app-mau", conn)   # min_level 1
    assert iam.vai_cho_app(nv, "app-mau") == "viewer"
    assert iam.vai_cho_app(ow, "app-mau") == "admin"   # danh pháp mới — hết vai "owner"


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


def test_sua_nguoi_doi_truong_va_trang_thai(conn):
    """sua_nguoi (trả nợ 'hồ sơ chỉ tạo được'): None = giữ nguyên; trạng thái chỉ
    trong 3 giá trị; KHÔNG có xóa hồ sơ — nghỉ việc = 'nghi' (gỡ mềm); có vết."""
    ow = _owner(conn)
    ns = iam.tao_nguoi(conn, ow, "Người Sửa", "Kinh doanh", "SEO")
    iam.sua_nguoi(conn, ow, ns["ma"], ho_ten="Người Đã Sửa", trang_thai="nghi")
    moi = next(n for n in iam.liet_ke_nguoi(conn) if n["ma"] == ns["ma"])
    assert moi["ho_ten"] == "Người Đã Sửa" and moi["trang_thai"] == "nghi"
    assert moi["bo_phan"] == "Kinh doanh" and moi["vi_tri"] == "SEO"  # None = giữ
    with pytest.raises(iam.LoiIam):
        iam.sua_nguoi(conn, ow, ns["ma"], trang_thai="xoa-han")  # ngoài 3 trạng thái
    with pytest.raises(iam.LoiIam):
        iam.sua_nguoi(conn, ow, "NS-999", trang_thai="nghi")     # hồ sơ không tồn tại
    nk = iam.doc_nhat_ky(conn, 5)
    assert any(d["hanh_dong"] == "sua_nguoi" and ns["ma"] in d["chi_tiet"]
               for d in nk)                                       # luật sắt 3: có vết


def test_ho_so_mo_rong_luu_va_validate(conn):
    """Hồ sơ ĐẦY ĐỦ (DE.md mục 12.1): 5 cột mới lưu đúng; cap_bac ngoài thang /
    vị trí ngoài CSV / CẶP bộ phận×vị trí sai (bài học 01/08) / bộ phận ngoài
    danh mục 5 / CCCD không đủ 12 số / ngày sai dạng — đều LoiIam."""
    ow = _owner(conn)
    ns = iam.tao_nguoi(conn, ow, "Đầy Đủ", "Kinh doanh", "SEO",
                       ngay_sinh="1998-04-12", cccd="079098012345",
                       dia_chi="123 Lê Lợi", ngay_vao="2026-07-31",
                       cap_bac="staff")
    assert ns["cccd"] == "079098012345" and ns["cap_bac"] == "staff"
    assert ns["ngay_sinh"] == "1998-04-12" and ns["dia_chi"] == "123 Lê Lợi"
    with pytest.raises(iam.LoiIam):
        iam.tao_nguoi(conn, ow, "A", "Kinh doanh", cap_bac="boss")
    with pytest.raises(iam.LoiIam):
        iam.tao_nguoi(conn, ow, "B", "Vận hành - Sản xuất", "SEO")   # cặp sai
    with pytest.raises(iam.LoiIam):
        iam.tao_nguoi(conn, ow, "C", "Kinh doanh", "Phi công")       # ngoài CSV
    with pytest.raises(iam.LoiIam):
        iam.tao_nguoi(conn, ow, "D", "IT")                           # ngoài danh mục 5
    with pytest.raises(iam.LoiIam):
        iam.tao_nguoi(conn, ow, "E", "Kinh doanh", cccd="123")
    with pytest.raises(iam.LoiIam):
        iam.tao_nguoi(conn, ow, "F", "Kinh doanh", ngay_sinh="12/04/1998")


def test_sua_nguoi_kiem_cap_sau_gop_va_grandfather(conn):
    ow = _owner(conn)
    ns = iam.tao_nguoi(conn, ow, "Người Ghép", "Kinh doanh", "SEO")
    with pytest.raises(iam.LoiIam):     # đổi MỘT MÌNH bộ phận → cặp SAU GỘP sai
        iam.sua_nguoi(conn, ow, ns["ma"], bo_phan="Vận hành - Sản xuất")
    iam.sua_nguoi(conn, ow, ns["ma"], bo_phan="Vận hành - Sản xuất",
                  vi_tri="Editor (Dựng video)")          # đổi cả cặp hợp lệ
    # hồ sơ CŨ ngoài danh mục (grandfather 04/08): không đụng bộ phận/vị trí thì
    # vẫn đổi được trạng thái; cột mới thiếu → DEFAULT '' , đọc không vỡ
    with conn:
        conn.execute(
            "INSERT INTO nguoi (ma, ho_ten, bo_phan, vi_tri, trang_thai, tao_luc) "
            "VALUES ('NS-090', 'Người Cũ', 'IT', 'Content', 'hoat_dong', '2026-01-01')")
    iam.sua_nguoi(conn, ow, "NS-090", trang_thai="nghi")
    cu = next(n for n in iam.liet_ke_nguoi(conn) if n["ma"] == "NS-090")
    assert cu["trang_thai"] == "nghi" and cu["cap_bac"] == ""


def test_sua_nguoi_can_quyen_nhan_su(conn):
    ow = _owner(conn)
    ns = iam.tao_nguoi(conn, ow, "Người Sửa", "Kinh doanh")
    iam.tao_tai_khoan(conn, ow, "nv", "123456", "Kinh doanh", 2)
    nv = iam.claims_cua(iam.lay_tai_khoan(conn, "nv"))
    with pytest.raises(iam.LoiIam):
        iam.sua_nguoi(conn, nv, ns["ma"], trang_thai="nghi")     # nhân viên thường: chặn


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


# ---------- Permissions v2 (DE.md mục 14 — acting, hành động app, vai admin) ----------

def _nv(conn, ow, ten="nv", bo_phan="Kinh doanh", level=2):
    iam.tao_tai_khoan(conn, ow, ten, "123456", bo_phan, level)
    return iam.claims_cua(iam.lay_tai_khoan(conn, ten))


def test_hoi_quy_khong_le_khong_acting_y_nguyen(conn):
    """HỒI QUY QUAN TRỌNG NHẤT (luật ghim V2): sổ override RỖNG + không acting →
    co_quyen/vai trên ma trận level×bộ phận×app phải Y HỆT luật thường quy."""
    ow = _owner(conn)
    ca = [("Kinh doanh", 2), ("Kinh doanh", 4), ("Hành chính Nhân sự", 3),
          ("Vận hành - Sản xuất", 1), ("", 2)]      # ca cuối: user "trắng" (luật #4)
    for i, (bp, lv) in enumerate(ca):
        u = _nv(conn, ow, f"u{i}", bp, lv)
        u = iam.hieu_luc(u, conn)                    # không acting → giữ nguyên
        assert u["level"] == lv and "level_that" not in u
        # vào app theo min_level + bộ phận (L4+ bỏ rào) — y luật cũ
        assert iam.co_quyen(u, "vao", "ai-agent", conn) is True
        assert iam.co_quyen(u, "vao", "data-analytics", conn) == \
            (lv >= 4 or (bp == "Kinh doanh" and lv >= 2))
        # hành động app: mặc định theo min_level trong luật
        assert iam.co_quyen(u, "nap_tai_lieu", "ai-agent", conn) == (lv >= 4)
        assert iam.co_quyen(u, "giam_sat", "ai-agent", conn) is False
        assert iam.co_quyen(u, "kpi", "to-chuc", conn) == (lv >= 4)
    # Owner: đủ mọi hành động + vai admin
    assert iam.cac_hanh_dong(ow, "ai-agent", conn) == \
        ["nap_tai_lieu", "nguon_ngoai", "giam_sat", "duyet_qa", "quan_tri"]
    assert iam.vai_cho_app(ow, "ai-agent", conn) == "admin"


def test_vai_dich_tu_hanh_dong_va_tick_quan_tri(conn):
    """Vai dừng-tại-hit-đầu: tick quan_tri cho L4 → admin ĐÚNG app đó, app khác
    không; header không còn vai 'owner'."""
    ow = _owner(conn)
    ql = _nv(conn, ow, "ql", "Kinh doanh", 4)
    assert iam.vai_cho_app(ql, "ai-agent", conn) == "viewer"    # không nấc nào khớp
    assert iam.vai_cho_app(ql, "app-mau", conn) == "manager"    # fallback level
    iam.gan_override(conn, ow, "ql", "ai-agent", "quan_tri", True, "thay Owner quản kho")
    assert iam.vai_cho_app(ql, "ai-agent", conn) == "admin"     # tick → admin app đó
    assert iam.vai_cho_app(ql, "to-chuc", conn) == "viewer"     # app khác không lây
    assert "quan_tri" in iam.cac_hanh_dong(ql, "ai-agent", conn)
    for slug in ("ai-agent", "to-chuc", "data-analytics", "app-mau"):
        assert iam.vai_cho_app(ow, slug, conn) != "owner"       # danh pháp mới
        assert iam.vai_cho_app(ql, slug, conn) != "owner"


def test_acting_doi_mac_dinh_override_van_thang(conn):
    ow = _owner(conn)
    nv = _nv(conn, ow, "nv", "Kinh doanh", 2)
    iam.dat_cap_truy_cap(conn, ow, "nv", 4, "thay quyền tạm")
    hl = iam.hieu_luc(nv, conn)
    assert hl["level"] == 4 and hl["level_that"] == 2           # acting nâng mặc định
    assert iam.co_quyen(hl, "nap_tai_lieu", "ai-agent", conn)   # L4 hiệu lực → có
    iam.gan_override(conn, ow, "nv", "ai-agent", "nap_tai_lieu", False, "đang bàn giao")
    assert not iam.co_quyen(hl, "nap_tai_lieu", "ai-agent", conn)  # OVERRIDE > acting
    iam.dat_cap_truy_cap(conn, ow, "nv", None)                  # gỡ acting
    assert iam.hieu_luc(nv, conn)["level"] == 2


def test_acting_khong_ap_len_owner_va_ly_do_bat_buoc(conn):
    ow = _owner(conn)
    iam.tao_tai_khoan(conn, ow, "sep2", "123456", "Ban quản trị", 5)
    nv = _nv(conn, ow, "nv", "Kinh doanh", 2)
    with pytest.raises(iam.LoiIam):
        iam.dat_cap_truy_cap(conn, ow, "sep2", 2)               # L5 không hạ được
    assert iam.hieu_luc(ow, conn)["level"] == 5                 # Owner miễn nhiễm
    with pytest.raises(iam.LoiIam):
        iam.gan_override(conn, ow, "nv", "ai-agent", "nap_tai_lieu", True, "")
    with pytest.raises(iam.LoiIam):
        iam.gan_override(conn, ow, "nv", "ai-agent", "nap_tai_lieu", False, "   ")
    iam.gan_override(conn, ow, "nv", "ai-agent", "nap_tai_lieu", None)  # gỡ: không cần
