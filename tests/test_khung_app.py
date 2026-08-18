# -*- coding: utf-8 -*-
"""KHUNG MỞ APP GIỮ SIDEBAR (Owner 16/08 — "mở app vẫn còn sidebar"): app ngoài
khai giao_dien 'khung' mở qua GET /open/<slug> = shell OUTLIERY (sidebar+topbar)
+ iframe /app/<slug>/; gate y hệt cửa vào app; native/lạ → 404; /app trực tiếp
sống nguyên; proxy cắt X-Frame-Options/CSP-frame-ancestors CHỈ cho app khung."""
import bcrypt
import pytest
from fastapi.testclient import TestClient

from nen.common.sidebar import sb_apps_tu_claims
from nen.gateway.main import app as gateway_app
from nen.iam import iam

_gensalt_goc = bcrypt.gensalt


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("IAM_DB", str(tmp_path / "iam.db"))
    monkeypatch.setattr(bcrypt, "gensalt", lambda rounds=12: _gensalt_goc(4))
    conn = iam.ket_noi()
    ow = iam.claims_cua(iam.tao_tai_khoan(
        conn, None, "owner-test", "mk-test", "Ban quản trị", 5, phai_doi_mk=False))
    iam.tao_tai_khoan(conn, ow, "nhanvien", "mk-nv-6", "Kinh doanh", 2,
                      phai_doi_mk=False)
    conn.close()
    return TestClient(gateway_app, follow_redirects=False)


def _login(client, ten="owner-test", mk="mk-test"):
    return client.post("/login", data={"ten": ten, "mat_khau": mk})


def test_open_chua_dang_nhap_ve_login(client):
    r = client.get("/open/radary")
    assert r.status_code == 303 and r.headers["location"] == "/login"


def test_open_radary_khung_du_sidebar_va_iframe(client):
    _login(client)
    r = client.get("/open/radary")
    assert r.status_code == 200
    b = r.text
    assert '<iframe class="khung-app" src="/app/radary/"' in b   # nội dung = iframe
    assert 'class="sidebar"' in b and "OUTLIERY" in b            # shell chuẩn
    assert "RadarY" in b and "Content Ultimate" in b             # nhóm Tools đủ app
    assert 'class="nav-item active" href="/open/radary"' in b    # mục đang mở active
    assert "<title>RadarY — OUTLIERY</title>" in b


def test_open_khoi_quan_ly_nam_gon_trong_popup(client):
    """Owner phê 17/08 'không đưa khối dưới sidebar ra ngoài': HR/Finance/General/
    Profile/Log out phải nằm GỌN TRONG popup sb-mgmt ghim đáy (y cấu trúc base.html
    các app) — pane bên trên CHỈ còn Home + Tools; Home trỏ '/' (vị trí AI Agent)."""
    _login(client)
    b = client.get("/open/radary").text
    assert 'id="sb-mgmt"' in b and 'id="sb-mgmt-nut"' in b and 'id="sb-mgmt-muc"' in b
    truoc, sau = b.split('id="sb-mgmt"', 1)               # pane vs khối popup đáy
    for duong in ('href="/hr"', 'href="/finance"', 'href="/general"',
                  'href="/profile"', 'href="/logout"', 'href="/tracking"',
                  'href="/vault"'):
        assert duong not in truoc, duong                  # không còn link phẳng ở pane
        # các mục theo quyền Owner đều có mặt TRONG popup
        assert duong in sau, duong
    assert 'class="nav-item" href="/"' in truoc           # Home = chỗ của AI Agent
    assert "mgmt-mui" in sau                              # nút chip + mũi tên popup


def test_open_gate_y_het_cua_vao_app(client):
    # content-ultimate: chỉ VH L2+ — nhanvien KD bị chặn y luật proxy
    _login(client, "nhanvien", "mk-nv-6")
    assert client.get("/open/content-ultimate").status_code == 403
    assert client.get("/open/radary").status_code == 200         # radary mọi bộ phận L1
    _login(client)
    assert client.get("/open/content-ultimate").status_code == 200


def test_open_native_va_slug_la_404(client):
    _login(client)
    assert client.get("/open/ai-agent").status_code == 404       # native không qua khung
    assert client.get("/open/to-chuc").status_code == 404
    assert client.get("/open/khong-co").status_code == 404


def test_sidebar_href_khung_vs_native():
    ds = {a["slug"]: a["href"] for a in sb_apps_tu_claims(
        ["radary", "content-ultimate"])}
    assert ds == {"radary": "/open/radary",
                  "content-ultimate": "/open/content-ultimate"}


def test_proxy_cat_header_khung_va_wiring(client, monkeypatch):
    """_bo_vi_khung: cắt XFO + CSP-có-frame-ancestors (CSP thường giữ); proxy_app
    truyền khung=True đúng app khai, native False — bắt tại chỗ nối chuyen_tiep."""
    from nen.common.proxy import _bo_vi_khung
    assert _bo_vi_khung("x-frame-options", "DENY")
    assert _bo_vi_khung("content-security-policy", "frame-ancestors 'none'")
    assert not _bo_vi_khung("content-security-policy", "default-src 'self'")
    assert not _bo_vi_khung("etag", "abc")

    import nen.gateway.main as gw
    bat: dict = {}

    async def _gia(request, **kw):
        bat.update(kw)
        from fastapi.responses import Response as R
        return R("ok")

    monkeypatch.setattr(gw, "chuyen_tiep", _gia)
    _login(client)
    client.get("/app/radary/board")
    assert bat["khung"] is True
    client.get("/app/app-mau/")
    assert bat["khung"] is False


def test_ui_a2_a3_modal_va_badge(client):
    """UI A2/A3 theo chuẩn A1: API Keys có modal Add key + khối transcript hiện
    (bug loop 4 loại cũ); Permissions dùng badge overrides — logic/field y nguyên."""
    _login(client)
    b = client.get("/general/api-keys").text
    assert 'class="modal-bg" id="md-key"' in b and 'data-mo="md-key"' in b
    assert "YouTube Transcript" in b                    # loại thứ 4 hết vô hình (Owner chốt 17/08 đổi nhãn)
    assert 'value="transcript"' in b                    # thêm được khóa transcript từ UI
    b = client.get("/general/permissions?ten=nhanvien").text
    assert "0 overrides" in b                           # badge chuẩn trên summary
    assert 'class="badge ok">yes' in b                  # P2 badge thay chip
    # Owner 18/08 (docs/UI.md): <details> khu General phải có CHỈ BÁO mở rộng —
    # chevron trong summary xoay 90° khi [open], summary hạ cỡ 14px không ăn heading
    assert '<summary><svg class="ic chev"' in b
    assert "details.app[open] summary .chev{transform:rotate(90deg)}" in b
    assert "font-size:14px" in b.split("details.app summary{", 1)[1].split("}", 1)[0]
