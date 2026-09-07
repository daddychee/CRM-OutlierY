# -*- coding: utf-8 -*-
"""Test QUẢN LÝ TÀI SẢN — vật lý (kiểm kê + bàn giao) và số (mật khẩu ở Vault).

Bất biến:
- Sổ tài sản KHÔNG bao giờ chứa mật khẩu. Tài sản số chỉ giữ `vault_id` trỏ sang
  két; ai cần đăng nhập thì sang Vault (chỉ Owner, mở bằng master, ghi nhật ký).
- Bàn giao là sổ CHỈ-THÊM: mỗi lần đổi người giữ một dòng, không sửa dòng cũ —
  hỏi "tháng trước máy này ai cầm" luôn trả lời được.
- Người nghỉ việc mà còn giữ tài sản thì phải nêu ra, không im lặng.
"""
import pytest

from src import tai_san

NGUOI = [{"ten": "ngocth", "ho_ten": "Trần Hồng Ngọc", "ma": "NS-005"},
         {"ten": "thiennc", "ho_ten": "Nguyễn Chu Thiện", "ma": "NS-006"}]


def _vat_ly(**kw):
    d = dict(nguoi="lanne", loai="vat_ly", ten="MacBook Pro 14", nhom="may_tinh",
             ma_dinh_danh="C02XY1234", ngay_mua="2026-03-15", nguyen_gia=45_000_000,
             tien_te="VND", noi_de="Văn phòng", ghi_chu="")
    d.update(kw)
    return tai_san.luu_tai_san(**d)


def _so(**kw):
    d = dict(nguoi="lanne", loai="so", ten="Kênh OUTLAND", nhom="kenh_youtube",
             ma_dinh_danh="UC_outland", ngay_mua="2026-01-10", nguyen_gia=0,
             tien_te="VND", vault_id="3f9a1c22", ghi_chu="")
    d.update(kw)
    return tai_san.luu_tai_san(**d)


# ---------- khai tài sản ----------

def test_khai_hai_loai_tai_san():
    a = _vat_ly()
    b = _so()
    assert a["ma"].startswith("TS-") and b["ma"].startswith("TS-")
    assert a["loai"] == "vat_ly" and b["loai"] == "so"
    assert len(tai_san.doc_tai_san()) == 2


def test_so_tai_san_khong_bao_gio_chua_mat_khau():
    """Vault giữ bí mật, sổ tài sản giữ danh mục — hai kho, hai vai."""
    d = _so()
    assert "mat_khau" not in d and "password" not in d
    assert d["vault_id"] == "3f9a1c22"          # chỉ mã trỏ sang két
    # có cố truyền mật khẩu vào cũng bị từ chối
    with pytest.raises(TypeError):
        tai_san.luu_tai_san(nguoi="lanne", loai="so", ten="X", nhom="kenh_youtube",
                            mat_khau="bimat123")


def test_validate_chat():
    with pytest.raises(ValueError):
        _vat_ly(loai="tai_san_la")
    with pytest.raises(ValueError):
        _vat_ly(nhom="nhom_la")
    with pytest.raises(ValueError):
        _vat_ly(ten="")
    with pytest.raises(ValueError):
        _vat_ly(nguyen_gia=-1)
    with pytest.raises(ValueError):
        _vat_ly(ngay_mua="15/03/2026")
    assert tai_san.doc_tai_san() == []           # không bản ghi hỏng nào lọt vào


def test_sua_giu_nguyen_ma():
    a = _vat_ly()
    b = tai_san.luu_tai_san(nguoi="lanne", ma=a["ma"], loai="vat_ly",
                            ten="MacBook Pro 14 (2026)", nhom="may_tinh",
                            noi_de="Kho", nguyen_gia=45_000_000)
    assert b["ma"] == a["ma"] and b["noi_de"] == "Kho"
    assert len(tai_san.doc_tai_san()) == 1


# ---------- bàn giao ----------

def test_ban_giao_la_so_chi_them():
    a = _vat_ly()
    tai_san.ban_giao("lanne", a["ma"], "ngocth", "2026-04-01", "nhận máy mới")
    tai_san.ban_giao("lanne", a["ma"], "thiennc", "2026-06-15", "Ngọc chuyển bộ phận")
    ls = tai_san.lich_su_ban_giao(a["ma"])
    assert len(ls) == 2                          # giữ cả hai lượt, không đè
    assert ls[-1]["nguoi_giu"] == "thiennc"
    assert tai_san.nguoi_dang_giu(a["ma"]) == "thiennc"


def test_thu_hoi_ve_kho():
    a = _vat_ly()
    tai_san.ban_giao("lanne", a["ma"], "ngocth", "2026-04-01", "")
    tai_san.ban_giao("lanne", a["ma"], "", "2026-08-01", "thu hồi khi nghỉ việc")
    assert tai_san.nguoi_dang_giu(a["ma"]) == ""      # rỗng = đang ở kho
    assert len(tai_san.lich_su_ban_giao(a["ma"])) == 2


def test_ban_giao_tai_san_khong_co_thi_chan():
    with pytest.raises(ValueError):
        tai_san.ban_giao("lanne", "TS-khong-co", "ngocth", "2026-04-01", "")


# ---------- tổng hợp ----------

def test_tong_hop_theo_loai_va_nguoi_giu():
    a = _vat_ly()
    _vat_ly(ten="iPhone 15", nhom="dien_thoai", ma_dinh_danh="IMEI-9", nguyen_gia=22_000_000)
    _so()
    tai_san.ban_giao("lanne", a["ma"], "ngocth", "2026-04-01", "")
    kq = tai_san.tong_hop(NGUOI)
    assert kq["so_vat_ly"] == 2 and kq["so_tai_san_so"] == 1
    assert kq["nguyen_gia_vat_ly"] == 67_000_000
    assert kq["dang_o_kho"] == 1                  # iPhone chưa bàn giao
    d = {x["ten"]: x for x in kq["theo_nguoi"]}
    assert d["Trần Hồng Ngọc"]["so_tai_san"] == 1


def test_canh_bao_nguoi_nghi_viec_con_giu_tai_san():
    """Người rời danh sách nhân sự mà còn giữ máy → phải nêu ra, không im lặng."""
    a = _vat_ly()
    tai_san.ban_giao("lanne", a["ma"], "daroi", "2026-04-01", "")
    kq = tai_san.tong_hop(NGUOI)                  # 'daroi' không có trong NGUOI
    assert any(c["nguoi_giu"] == "daroi" for c in kq["canh_bao"])


def test_tai_san_so_thieu_vault_id_thi_nhac():
    _so(vault_id="")
    kq = tai_san.tong_hop(NGUOI)
    assert any("Vault" in c["ly_do"] for c in kq["canh_bao"])


# ---------- route ----------

def _client():
    from fastapi.testclient import TestClient
    from src.main import app
    return TestClient(app, headers={"X-Remote-User": "lanne", "X-Remote-Level": "2",
                                    "X-Remote-Role": "viewer",
                                    "X-Remote-Dept": "K%E1%BA%BF%20to%C3%A1n",
                                    "X-Remote-Apps": "to-chuc,finance"})


def test_route_tab_assets_render():
    _vat_ly()
    _so()
    b = _client().get("/finance?tab=assets").text
    assert "Danh mục tài sản" in b and "Bàn giao / thu hồi" in b
    assert "MacBook Pro 14" in b and "Kênh OUTLAND" in b
    assert "không có cột mật khẩu" in b


def test_route_khai_va_ban_giao():
    c = _client()
    r = c.post("/finance/tai-san", data={
        "loai": "vat_ly", "ten": "Sony FX3", "nhom": "may_quay",
        "ma_dinh_danh": "SN-777", "nguyen_gia": "95000000", "tien_te": "VND",
        "noi_de": "Studio"}, follow_redirects=False)
    assert r.status_code == 303
    ts = tai_san.doc_tai_san()[0]
    r2 = c.post("/finance/tai-san/ban-giao",
                data={"ma": ts["ma"], "nguoi_giu": "ngocth", "ngay": "2026-08-01"},
                follow_redirects=False)
    assert r2.status_code == 303
    assert tai_san.nguoi_dang_giu(ts["ma"]) == "ngocth"
    b = c.get(f"/finance/tai-san/{ts['ma']}/lich-su").text
    assert "Lịch sử bàn giao" in b and "2026-08-01" in b
    assert c.get("/finance/tai-san/TS-khong-co/lich-su").status_code == 404


def test_route_nhom_lech_loai_thi_422():
    r = _client().post("/finance/tai-san", data={
        "loai": "so", "ten": "X", "nhom": "may_tinh"})     # nhóm vật lý cho loại số
    assert r.status_code == 422
    assert tai_san.doc_tai_san() == []


# ══════════ GỘP THUÊ BAO + CÂY CHA–CON (Owner chốt 07/09) ══════════

def _tk_email(**kw):
    d = dict(nguoi="lanne", loai="so", ten="nuoikenh01@gmail.com", nhom="email",
             ma_dinh_danh="nuoikenh01@gmail.com", vault_id="aa11")
    d.update(kw)
    return tai_san.luu_tai_san(**d)


# ---------- chu kỳ trả phí gắn thẳng vào tài sản ----------

def test_tai_san_mang_chu_ky_tra_phi():
    """Envato vừa là tài sản số vừa phải gia hạn — MỘT bản ghi, không khai hai lần."""
    d = tai_san.luu_tai_san("lanne", "so", "Envato", "phan_mem", vault_id="bb22",
                            phi=16.5, tien_te="USD", chu_ky="thang",
                            ngay_gia_han="2026-10-05", danh_muc="CHI-NGOAI",
                            vi="payoneer")
    assert d["chu_ky"] == "thang" and d["ngay_gia_han"] == "2026-10-05"
    assert d["phi"] == 16.5


def test_khong_chu_ky_thi_khong_doi_ngay_gia_han():
    d = _vat_ly()                                  # máy tính mua đứt
    assert d["chu_ky"] == "" and d["ngay_gia_han"] == ""


def test_co_chu_ky_thi_bat_buoc_ngay_gia_han_va_ma_khoan():
    with pytest.raises(ValueError):
        tai_san.luu_tai_san("lanne", "so", "X", "phan_mem", chu_ky="thang")
    with pytest.raises(ValueError):                # thiếu mã khoản để ghi bút toán
        tai_san.luu_tai_san("lanne", "so", "X", "phan_mem", chu_ky="thang",
                            ngay_gia_han="2026-10-05")


def test_den_han_gom_moi_tai_san_co_chu_ky():
    tai_san.luu_tai_san("lanne", "so", "Envato", "phan_mem", phi=16.5, tien_te="USD",
                        chu_ky="thang", ngay_gia_han="2026-09-10",
                        danh_muc="CHI-NGOAI", vi="payoneer")
    tai_san.luu_tai_san("lanne", "so", "Proxy 911", "proxy_ip", phi=86, tien_te="USD",
                        chu_ky="thang", ngay_gia_han="2026-09-02",
                        danh_muc="CHI-PROXY", vi="payoneer")
    _vat_ly()                                       # không chu kỳ → không vào danh sách
    ds = tai_san.den_han("2026-09-05", trong_ngay=14)
    ten = [d["ten"] for d in ds]
    assert ten == ["Proxy 911", "Envato"]           # quá hạn trước, sắp tới sau
    assert ds[0]["qua_han"] is True and ds[1]["qua_han"] is False


def test_chi_thue_bao_thang_quy_ve_thang():
    tai_san.ghi_ty_gia_test = None
    tai_san.luu_tai_san("lanne", "so", "Gói năm", "phan_mem", phi=12_000_000,
                        tien_te="VND", chu_ky="nam", ngay_gia_han="2027-01-01",
                        danh_muc="CHI-NGOAI", vi="vietcombank")
    tai_san.luu_tai_san("lanne", "so", "Gói tháng", "phan_mem", phi=500_000,
                        tien_te="VND", chu_ky="thang", ngay_gia_han="2026-10-01",
                        danh_muc="CHI-NGOAI", vi="vietcombank")
    assert tai_san.chi_dinh_ky_thang() == 1_500_000.0    # 12tr/12 + 500k


def test_day_gia_han_sau_khi_ghi():
    d = tai_san.luu_tai_san("lanne", "so", "Envato", "phan_mem", phi=16.5,
                            tien_te="USD", chu_ky="thang", ngay_gia_han="2026-09-10",
                            danh_muc="CHI-NGOAI", vi="payoneer")
    assert tai_san.day_gia_han(d["ma"])["ngay_gia_han"] == "2026-10-10"


# ---------- cây cha–con: mất email là mất cả chùm ----------

def test_tai_khoan_con_tro_ve_email_goc():
    e = _tk_email()
    k = tai_san.luu_tai_san("lanne", "so", "Kênh OUTLAND", "kenh_youtube",
                            dang_nhap_bang=e["ma"], vault_id="cc33")
    g = tai_san.luu_tai_san("lanne", "so", "GA OUTLAND", "analytics",
                            dang_nhap_bang=e["ma"])
    assert k["dang_nhap_bang"] == e["ma"]
    con = tai_san.tai_khoan_con(e["ma"])
    assert {c["ten"] for c in con} == {"Kênh OUTLAND", "GA OUTLAND"}
    assert g["ma"] in {c["ma"] for c in con}


def test_khong_cho_tro_vao_chinh_no_hoac_vong_lap():
    a = _tk_email()
    with pytest.raises(ValueError):
        tai_san.luu_tai_san("lanne", ma=a["ma"], loai="so", ten=a["ten"],
                            nhom="email", dang_nhap_bang=a["ma"])   # tự trỏ mình
    b = tai_san.luu_tai_san("lanne", "so", "Kênh X", "kenh_youtube",
                            dang_nhap_bang=a["ma"])
    with pytest.raises(ValueError):                                  # a → b → a
        tai_san.luu_tai_san("lanne", ma=a["ma"], loai="so", ten=a["ten"],
                            nhom="email", dang_nhap_bang=b["ma"])


def test_cha_khong_ton_tai_thi_chan():
    with pytest.raises(ValueError):
        tai_san.luu_tai_san("lanne", "so", "Kênh X", "kenh_youtube",
                            dang_nhap_bang="TS-khong-co")


def test_canh_bao_email_goc_chua_cat_ket_keo_theo_ca_chum():
    """Email gốc chưa có mật khẩu trong két mà đang đỡ 3 tài khoản → nêu rõ số con."""
    e = _tk_email(vault_id="")
    for t in ("Kênh A", "Kênh B", "GA A"):
        tai_san.luu_tai_san("lanne", "so", t, "kenh_youtube", dang_nhap_bang=e["ma"])
    kq = tai_san.tong_hop(NGUOI)
    c = next(c for c in kq["canh_bao"] if c["ma"] == e["ma"])
    assert "3" in c["ly_do"]                    # nói rõ đang đỡ mấy tài khoản


def test_tach_id_va_mat_khau():
    """ID đăng nhập nằm THẲNG trên sổ (tra cứu nhanh); mật khẩu CHỈ ở Vault."""
    d = tai_san.luu_tai_san("lanne", "so", "Kênh OUTLAND", "kenh_youtube",
                            tai_khoan="nuoikenh01@gmail.com", vault_id="cc33")
    assert d["tai_khoan"] == "nuoikenh01@gmail.com"   # ID: xem được ngay
    assert "mat_khau" not in d                        # mật khẩu: không bao giờ ở đây
    assert d["vault_id"] == "cc33"                    # chỉ mã trỏ sang két
