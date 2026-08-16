# -*- coding: utf-8 -*-
"""Test trang Niches + Channels (Đ1 khối đế): gate Manager+/Owner, luồng
niche-trước-kênh, khai tử gõ lại mã, audit có vết, export CSV."""
import bcrypt
import pytest
from fastapi.testclient import TestClient

from nen.gateway.main import app as gateway_app
from nen.iam import iam

_gensalt_goc = bcrypt.gensalt


@pytest.fixture()
def he(tmp_path, monkeypatch):
    monkeypatch.setenv("IAM_DB", str(tmp_path / "iam.db"))
    monkeypatch.setenv("DANH_BA_DB", str(tmp_path / "danh_ba.db"))
    monkeypatch.setattr(bcrypt, "gensalt", lambda rounds=12: _gensalt_goc(4))
    conn = iam.ket_noi()
    ow = iam.claims_cua(iam.tao_tai_khoan(
        conn, None, "owner-t", "mk-test", "Ban quản trị", 5, phai_doi_mk=False))
    iam.tao_tai_khoan(conn, ow, "quanly", "mk-ql-6", "Kinh doanh", 4,
                      phai_doi_mk=False)
    iam.tao_tai_khoan(conn, ow, "nhanvien", "mk-nv-6", "Kinh doanh", 2,
                      phai_doi_mk=False)
    conn.close()


def _login(ten, mk):
    c = TestClient(gateway_app, follow_redirects=False)
    c.post("/login", data={"ten": ten, "mat_khau": mk})
    return c


def test_gate_l2_khong_vao_l4_vao(he):
    assert _login("nhanvien", "mk-nv-6").get("/general/niches").status_code == 403
    assert _login("quanly", "mk-ql-6").get("/general/niches").status_code == 200
    assert _login("quanly", "mk-ql-6").get("/general/channels").status_code == 200


def test_niche_truoc_kenh_va_luong_tao(he):
    c = _login("quanly", "mk-ql-6")
    r = c.post("/general/niches/create", data={"ten_chuan": "Life In",
                                               "trang_thai": "khai_thac"})
    assert "N-LIFE-IN" in r.text
    r = c.post("/general/markets/create", data={"ten": "US", "ngon_ngu": "English"})
    assert "TT-US" in r.text
    r = c.post("/general/channels/create", data={
        "ten_chuan": "Outland", "ngach_ma": "N-LIFE-IN", "thi_truong_ma": "TT-US",
        "channel_id": "UCabc", "loai_kenh": "compilation", "trang_thai": "sandbox"})
    assert "K-OUTLAND" in r.text
    # tạo kênh vào ngách KHÔNG tồn tại → lỗi hiện trên trang, không 500
    r = c.post("/general/channels/create",
               data={"ten_chuan": "Mồ côi", "ngach_ma": "N-KHONG-CO"})
    assert r.status_code == 200 and "K-MO-COI" not in r.text


def test_doi_vong_doi_va_audit_co_vet(he):
    c = _login("quanly", "mk-ql-6")
    c.post("/general/niches/create", data={"ten_chuan": "Space"})
    c.post("/general/channels/create",
           data={"ten_chuan": "Astro", "ngach_ma": "N-SPACE"})
    r = c.post("/general/channels/trang-thai",
               data={"ma": "K-ASTRO", "trang_thai": "hoat_dong"})
    assert "hoat_dong" in r.text
    conn = iam.ket_noi()
    nk = "".join(str(dict(d)) for d in iam.doc_nhat_ky(conn, 50))
    conn.close()
    assert "K-ASTRO" in nk and "danh_ba" in nk        # mọi thao tác có vết


def test_khai_tu_chi_owner_va_phai_go_lai_ma(he):
    ql = _login("quanly", "mk-ql-6")
    ql.post("/general/niches/create", data={"ten_chuan": "OLD"})
    ql.post("/general/channels/create",
            data={"ten_chuan": "Time Vault", "ngach_ma": "N-OLD"})
    assert ql.post("/general/channels/khai-tu",
                   data={"ma": "K-TIME-VAULT", "go_lai": "K-TIME-VAULT"}
                   ).status_code == 403               # Manager không được khai tử
    ow = _login("owner-t", "mk-test")
    r = ow.post("/general/channels/khai-tu",
                data={"ma": "K-TIME-VAULT", "go_lai": "go-sai"})
    assert "Retype" in r.text                          # gõ sai mã → chặn
    r = ow.post("/general/channels/khai-tu",
                data={"ma": "K-TIME-VAULT", "go_lai": "K-TIME-VAULT"})
    assert "Retired" in r.text
    assert "khai_tu" in ow.get("/general/channels?ma=K-TIME-VAULT").text


def test_lien_ket_app_chi_owner(he):
    ql = _login("quanly", "mk-ql-6")
    ql.post("/general/niches/create", data={"ten_chuan": "Life In"})
    ql.post("/general/channels/create",
            data={"ten_chuan": "Outland", "ngach_ma": "N-LIFE-IN"})
    assert ql.post("/general/channels/link",
                   data={"ma": "K-OUTLAND", "app_slug": "seo-optimize",
                         "khoa": "outland-o-01"}).status_code == 403
    ow = _login("owner-t", "mk-test")
    r = ow.post("/general/channels/link",
                data={"ma": "K-OUTLAND", "app_slug": "seo-optimize",
                      "khoa": "outland-o-01"})
    assert "outland-o-01" in ow.get("/general/channels?ma=K-OUTLAND").text


def test_export_csv(he):
    c = _login("quanly", "mk-ql-6")
    c.post("/general/niches/create", data={"ten_chuan": "Life In"})
    r = c.get("/general/channels/export")
    assert r.status_code == 200 and "N-LIFE-IN" in r.text
    assert "text/csv" in r.headers["content-type"]
