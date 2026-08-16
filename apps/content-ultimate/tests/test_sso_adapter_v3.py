# -*- coding: utf-8 -*-
"""Adapter SSO V3 (_vai_sso — Permissions v2): ƯU TIÊN X-Remote-Actions
(quan_tri→admin · sua→leader · còn lại creator DEFAULT fail-closed), fallback
X-Remote-Role DANH PHÁP MỚI (admin→admin · manager/leader→leader · viewer/lạ→
creator); SSO bật KHÔNG BAO GIỜ trả None ở giữa (bản cũ vai lạ→None→rơi về
ADMIN_USERS rỗng = ai cũng admin — đã bịt); user trắng không nổ."""
import contentultimate.server as srv


class _Handler:
    def __init__(self, headers=None, ip="127.0.0.1"):
        self.headers = headers or {}
        self.client_address = (ip, 12345)


def _vai(monkeypatch, headers, ip="127.0.0.1", bat="1"):
    monkeypatch.setenv("CU_TRUST_PROXY", bat)
    return srv._vai_sso(_Handler(headers, ip))


def test_actions_uu_tien(monkeypatch):
    assert _vai(monkeypatch, {"X-Remote-Actions": "quan_tri"}) == "admin"
    assert _vai(monkeypatch, {"X-Remote-Actions": "sua,quan_tri"}) == "admin"
    assert _vai(monkeypatch, {"X-Remote-Actions": "sua"}) == "leader"
    assert _vai(monkeypatch, {"X-Remote-Actions": ""}) == "creator"      # rỗng fail-closed
    assert _vai(monkeypatch, {"X-Remote-Actions": "kpi,nap_tai_lieu"}) == "creator"
    # có Actions thì Role bị bỏ qua — Actions là nguồn sự thật
    assert _vai(monkeypatch, {"X-Remote-Actions": "", "X-Remote-Role": "admin"}) == "creator"


def test_fallback_role_danh_phap_moi(monkeypatch):
    assert _vai(monkeypatch, {"X-Remote-Role": "admin"}) == "admin"
    assert _vai(monkeypatch, {"X-Remote-Role": "manager"}) == "leader"   # trần vận hành 04/08
    assert _vai(monkeypatch, {"X-Remote-Role": "leader"}) == "leader"
    assert _vai(monkeypatch, {"X-Remote-Role": "viewer"}) == "creator"
    assert _vai(monkeypatch, {"X-Remote-Role": "owner"}) == "creator"    # vai cũ hết giá trị
    assert _vai(monkeypatch, {}) == "creator"                            # user trắng không nổ


def test_chi_none_khi_tat_hoac_khong_loopback(monkeypatch):
    assert _vai(monkeypatch, {"X-Remote-Role": "admin"}, bat="0") is None
    assert _vai(monkeypatch, {"X-Remote-Role": "admin"}, ip="192.168.1.9") is None
