# -*- coding: utf-8 -*-
"""PHÂN CÔNG — trục B của mô hình quyền (Owner chốt 24/08/2026).

Ghim đúng những gì user chốt, không ghim chi tiết cài đặt:
  · GIAO VIỆC là của Manager trở lên — **Leader KHÔNG** (đảo luật `chan_owner` 02/08 hệ V2).
  · Người nhận phải VÀO ĐƯỢC app — kiểm ở NỀN. Đây là chỗ hỏng 24/08: app SEO kiểm tên
    bằng sổ di sản V2 của chính nó nên tên người mới bị từ chối (400) còn tên người đã
    đổi bộ phận/đã khóa thì vẫn nhận.
  · Phân công hỏng lặng lẽ (người đổi bộ phận, bị khóa) phải NỔI LÊN được — `phan_cong_mo_coi`.
"""
import bcrypt
import pytest

from nen.iam import iam

_gensalt_goc = bcrypt.gensalt
APP = "seo-optimize"


@pytest.fixture()
def conn(tmp_path, monkeypatch):
    monkeypatch.setenv("IAM_DB", str(tmp_path / "iam.db"))
    monkeypatch.setattr(bcrypt, "gensalt", lambda rounds=12: _gensalt_goc(4))
    c = iam.ket_noi()
    yield c
    c.close()


def _tk(conn, ai, ten, bo_phan, level):
    return iam.claims_cua(iam.tao_tai_khoan(conn, ai, ten, "mk-" + ten + "-123", bo_phan, level,
                                            phai_doi_mk=False))


@pytest.fixture()
def he(conn):
    """Bộ người tối thiểu phản chiếu đúng ca thật 24/08."""
    ow = _tk(conn, None, "owner", "Ban quản trị", 5)
    return {
        "conn": conn, "owner": ow,
        "manager": _tk(conn, ow, "mng", "Kinh doanh", 4),
        "leader": _tk(conn, ow, "ld", "Kinh doanh", 3),
        "seo": _tk(conn, ow, "nv", "Kinh doanh", 2),
        # Vai vận hành: KHÔNG vào được app SEO (bộ phận khác) — ca `thanhtran` đứng tên
        # 7 kênh mà không vào nổi app.
        "ngoai": _tk(conn, ow, "vh", "Vận hành - Sản xuất", 2),
    }


def test_migration_dung_bang():
    """Phiên bản schema = số file .sql (ghim LUẬT, không ghim số — bài học self-test 05/08)."""
    assert (iam.DUONG_MIGRATIONS / "007_phan_cong.sql").exists()


def test_manager_giao_duoc_leader_thi_khong(he):
    """Luật user chốt 24/08 — một dòng test cho một câu quyết định."""
    c = he["conn"]
    assert iam.dat_phan_cong(c, he["manager"], APP, "kenh", "cf-01", ["nv"]) == ["nv"]
    assert iam.nguoi_cua(c, APP, "kenh", "cf-01") == ["nv"]
    with pytest.raises(iam.LoiIam):
        iam.dat_phan_cong(c, he["leader"], APP, "kenh", "cf-01", ["ld"])
    with pytest.raises(iam.LoiIam):
        iam.dat_phan_cong(c, he["seo"], APP, "kenh", "cf-01", ["nv"])
    assert iam.nguoi_cua(c, APP, "kenh", "cf-01") == ["nv"], "bị chặn thì KHÔNG được ghi gì"


def test_owner_luon_giao_duoc(he):
    assert iam.dat_phan_cong(he["conn"], he["owner"], APP, "kenh", "cf-01", ["nv"]) == ["nv"]


def test_nguoi_nhan_phai_vao_duoc_app(he):
    """Chỗ hỏng 24/08 — nay kiểm ở nền, và kiểm bằng CHÍNH luật vào app."""
    with pytest.raises(iam.LoiIam, match="không vào được app"):
        iam.dat_phan_cong(he["conn"], he["manager"], APP, "kenh", "cf-01", ["vh"])
    with pytest.raises(iam.LoiIam, match="Không có tài khoản"):
        iam.dat_phan_cong(he["conn"], he["manager"], APP, "kenh", "cf-01", ["nguoi-la"])
    assert iam.nguoi_cua(he["conn"], APP, "kenh", "cf-01") == []


def test_tai_khoan_khoa_khong_nhan_viec(he):
    c = he["conn"]
    iam.sua_tai_khoan(c, he["owner"], "nv", khoa=True)
    with pytest.raises(iam.LoiIam, match="khóa"):
        iam.dat_phan_cong(c, he["manager"], APP, "kenh", "cf-01", ["nv"])


def test_dat_thay_ca_cum_va_go_het(he):
    c = he["conn"]
    iam.dat_phan_cong(c, he["manager"], APP, "kenh", "cf-01", ["nv", "ld"])
    assert iam.nguoi_cua(c, APP, "kenh", "cf-01") == ["ld", "nv"]
    iam.dat_phan_cong(c, he["manager"], APP, "kenh", "cf-01", ["nv"])
    assert iam.nguoi_cua(c, APP, "kenh", "cf-01") == ["nv"], "đặt = THAY cả cụm"
    iam.dat_phan_cong(c, he["manager"], APP, "kenh", "cf-01", [])
    assert iam.nguoi_cua(c, APP, "kenh", "cf-01") == [], "rỗng = gỡ hết"


def test_pham_vi_gom_theo_loai_va_giu_sao(he):
    c = he["conn"]
    iam.dat_phan_cong(c, he["manager"], APP, "kenh", "cf-01", ["nv"])
    iam.dat_phan_cong(c, he["manager"], APP, "kenh", "ed-01", ["nv"])
    iam.dat_phan_cong(c, he["manager"], APP, "thi_truong", "*", ["ld"])
    assert iam.pham_vi(c, "nv", APP) == {"kenh": ["cf-01", "ed-01"]}
    # '*' đi thẳng ra ngoài — nền KHÔNG diễn giải hộ, app tự hiểu là "tất cả loại này"
    assert iam.pham_vi(c, "ld", APP) == {"thi_truong": ["*"]}
    assert iam.pham_vi(c, "nv", "radary") == {}, "phạm vi KHÔNG rò sang app khác"


def test_ghi_nhat_ky_moi_lan_giao(he):
    c = he["conn"]
    iam.dat_phan_cong(c, he["manager"], APP, "kenh", "cf-01", ["nv"], ghi_chu="nhận task mới")
    d = [r for r in iam.doc_nhat_ky(c) if r["hanh_dong"] == "phan_cong"]
    assert d and d[0]["ai"] == "mng" and "cf-01" in d[0]["chi_tiet"] and "nv" in d[0]["chi_tiet"]


def test_mo_coi_noi_len_khi_nguoi_roi_app(he):
    """Người đổi bộ phận / bị khóa thì phân công không tự sai — nó ngừng có tác dụng LẶNG LẼ.
    Đúng 11 kênh mồ côi đo được ở SEO hôm 24/08."""
    c = he["conn"]
    iam.dat_phan_cong(c, he["manager"], APP, "kenh", "cf-01", ["nv"])
    assert iam.phan_cong_mo_coi(c, APP) == []
    iam.sua_tai_khoan(c, he["owner"], "nv", bo_phan="Vận hành - Sản xuất")
    mc = iam.phan_cong_mo_coi(c, APP)
    assert len(mc) == 1 and mc[0]["ma"] == "cf-01" and "không vào được app" in mc[0]["ly_do"]
    iam.sua_tai_khoan(c, he["owner"], "nv", khoa=True)
    assert "khóa" in iam.phan_cong_mo_coi(c, APP)[0]["ly_do"]


def test_thieu_app_hay_ma_thi_tu_choi(he):
    for xau in (("", "kenh", "cf-01"), (APP, "", "cf-01"), (APP, "kenh", "  ")):
        with pytest.raises(iam.LoiIam):
            iam.dat_phan_cong(he["conn"], he["manager"], *xau, ["nv"])


def test_luat_giao_viec_khai_trong_phan_quyen_json(he):
    """Hành động `phan_cong` phải NẰM TRONG luật ngoài code — không khai thì co_quyen
    fail-closed về Owner và Manager mất quyền giao việc mà không ai hiểu vì sao."""
    hd = iam.hanh_dong_cua_app(APP)
    assert iam.HANH_DONG_PHAN_CONG in hd and hd[iam.HANH_DONG_PHAN_CONG]["min_level"] == 4
    assert iam.HANH_DONG_PHAN_CONG in iam.cac_hanh_dong(he["manager"], APP, he["conn"])
    assert iam.HANH_DONG_PHAN_CONG not in iam.cac_hanh_dong(he["leader"], APP, he["conn"])
    # Tên khóa KHÔNG được chứa substring mà vai_cho_app dò (bẫy nas_cap_cao 30/07):
    # dính là Manager/Leader bị đẩy nhầm vai chỉ vì thêm một hành động mới.
    assert not any(t in iam.HANH_DONG_PHAN_CONG
                   for t in ("sua", "tao", "them", "xoa", "toan_quyen", "quan_tri"))
    assert iam.vai_cho_app(he["manager"], APP, he["conn"]) == "manager"
    assert iam.vai_cho_app(he["leader"], APP, he["conn"]) == "leader"


# ---------- 3 đường dây gateway (khuôn api-khoa: app hỏi qua loopback) ----------

def _goi(url: str, dia_chi=("127.0.0.1", 50000), method="GET", **kw):
    import asyncio

    import httpx

    from nen.gateway.main import app as gateway_app

    async def chay():
        transport = httpx.ASGITransport(app=gateway_app, client=dia_chi)
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
            return await c.request(method, url, **kw)
    return asyncio.run(chay())


def test_duong_danh_sach_nguoi_chi_tra_ai_vao_duoc_app(he):
    """Đường vá thẳng lỗi 24/08: hộp thoại giao việc lấy tên TỪ ĐÂY, không từ sổ của app."""
    r = _goi(f"/api/quyen/tai-khoan/{APP}")
    assert r.status_code == 200
    ten = {t["ten"]: t for t in r.json()["tai_khoan"]}
    assert set(ten) == {"owner", "mng", "ld", "nv"}, "vh (bộ phận khác) KHÔNG được liệt kê"
    assert ten["mng"]["vai"] == "manager" and ten["nv"]["vai"] == "viewer"
    # Khóa tài khoản là biến mất khỏi ô chọn ngay — không đợi ai dọn tay
    iam.sua_tai_khoan(he["conn"], he["owner"], "nv", khoa=True)
    assert "nv" not in {t["ten"] for t in _goi(f"/api/quyen/tai-khoan/{APP}").json()["tai_khoan"]}


def test_duong_pham_vi_va_chan_goi_tu_LAN(he):
    iam.dat_phan_cong(he["conn"], he["manager"], APP, "kenh", "cf-01", ["nv"])
    r = _goi(f"/api/quyen/pham-vi/{APP}?ten=nv")
    assert r.status_code == 200 and r.json()["pham_vi"] == {"kenh": ["cf-01"]}
    # App bind loopback nên đường từ xa duy nhất là proxy ĐÃ xác thực; máy LAN gọi
    # thẳng vào đây là chặn (khuôn api-khoa).
    assert _goi(f"/api/quyen/pham-vi/{APP}?ten=nv", ("192.168.1.50", 50000)).status_code == 403
    assert _goi(f"/api/quyen/tai-khoan/{APP}", ("192.168.1.50", 50000)).status_code == 403


def test_duong_giao_viec_xac_thuc_bang_COOKIE_khong_bang_loopback(he, monkeypatch):
    """App chuyển tiếp nguyên cookie người bấm; gateway tự biết ai và tự kiểm quyền.

    Không cookie → 401 KỂ CẢ gọi từ loopback: app không cầm gì để tự xưng danh, nên app
    có lỗi cũng không tự phong quyền cho ai được."""
    from fastapi.testclient import TestClient

    from nen.gateway.main import app as gateway_app

    assert _goi("/api/quyen/phan-cong", method="POST",
                json={"app": APP, "loai": "kenh", "ma": "cf-01",
                      "nguoi": ["nv"]}).status_code == 401

    c = TestClient(gateway_app, follow_redirects=False)
    c.post("/login", data={"ten": "mng", "mat_khau": "mk-mng-123"})
    r = c.post("/api/quyen/phan-cong",
               json={"app": APP, "loai": "kenh", "ma": "cf-01", "nguoi": ["nv"]})
    assert r.status_code == 200 and r.json()["nguoi"] == ["nv"]
    assert iam.nguoi_cua(he["conn"], APP, "kenh", "cf-01") == ["nv"]

    # Leader đăng nhập thật vẫn bị chặn Ở NỀN (không chỉ ẩn nút bên app)
    c2 = TestClient(gateway_app, follow_redirects=False)
    c2.post("/login", data={"ten": "ld", "mat_khau": "mk-ld-123"})
    r2 = c2.post("/api/quyen/phan-cong",
                 json={"app": APP, "loai": "kenh", "ma": "cf-01", "nguoi": ["ld"]})
    assert r2.status_code == 400 and "giao việc" in r2.json()["loi"]
    assert iam.nguoi_cua(he["conn"], APP, "kenh", "cf-01") == ["nv"], "bị chặn thì không đổi gì"


def test_duong_giao_viec_bao_ly_do_doc_duoc(he):
    from fastapi.testclient import TestClient

    from nen.gateway.main import app as gateway_app
    c = TestClient(gateway_app, follow_redirects=False)
    c.post("/login", data={"ten": "mng", "mat_khau": "mk-mng-123"})
    r = c.post("/api/quyen/phan-cong",
               json={"app": APP, "loai": "kenh", "ma": "cf-01", "nguoi": ["vh"]})
    assert r.status_code == 400 and "không vào được app" in r.json()["loi"]
