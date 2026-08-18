# -*- coding: utf-8 -*-
"""SSO V3 của SEO Optimize (APPS.md app 4 — 19/08/2026).

Ghim 4 luật: (1) vai dịch ACTIONS-FIRST, fail-closed viewer; (2) app KHÔNG ghi/tạo
tài khoản — users.json chỉ đọc di sản (lệnh user 19/08 "mọi truy xuất tài khoản từ
khối nền"); (3) cửa quản trị nội bộ 404 khi SSO KỂ CẢ vai owner; (4) nguồn khóa =
KÉT V3, không fallback .env/api.txt."""
import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from seo import common, khoa_v3, server, users


# ── (1) vai_tu_claims: Actions-first ─────────────────────────────────────────────
def test_vai_tu_claims_actions_first():
    ca = [
        ("van_hanh", "", "seo"),                       # KD L2
        ("van_hanh,sua", "", "leader"),                # KD L3
        ("van_hanh,sua,toan_quyen", "", "manager"),    # KD L4
        ("van_hanh,sua,toan_quyen,quan_tri", "", "owner"),  # Owner
        ("", "", "viewer"),                            # Actions RỖNG ≠ thiếu — Manager BP khác
        ("la_lung", "", "viewer"),                     # hành động lạ → fail-closed
    ]
    for actions, role, want in ca:
        assert server.vai_tu_claims(actions, role) == want, (actions, role)
    # Actions CÓ MẶT thì Role bị bỏ qua hoàn toàn (kể cả role cao)
    assert server.vai_tu_claims("", "admin") == "viewer"


def test_vai_tu_claims_fallback_role_khi_thieu_actions():
    # gateway đời cũ không gửi Actions → dịch Role, nhận cả danh pháp mới lẫn cũ
    assert server.vai_tu_claims(None, "admin") == "owner"
    assert server.vai_tu_claims(None, "manager") == "manager"
    assert server.vai_tu_claims(None, "leader") == "leader"
    assert server.vai_tu_claims(None, "seo") == "seo"
    assert server.vai_tu_claims(None, "vai-la") == "viewer"   # roles.DEFAULT fail-closed
    assert server.vai_tu_claims(None, "") == "viewer"


# ── server thật trên cổng ephemeral (stdlib, không TestClient) ───────────────────
@pytest.fixture(scope="module")
def goi():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), server.make_handler())
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    port = srv.server_address[1]

    def _goi(method: str, path: str, headers: dict | None = None, body: dict | None = None):
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}{path}", method=method,
            data=json.dumps(body).encode() if body is not None else None,
            headers={"Content-Type": "application/json",
                     "Sec-Fetch-Site": "same-origin", **(headers or {})})
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                return r.status, json.loads(r.read().decode() or "{}")
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read().decode() or "{}")

    yield _goi
    srv.shutdown()


def _h(actions: str | None, user: str = "kd2") -> dict:
    h = {"X-Remote-User": user}
    if actions is not None:
        h["X-Remote-Actions"] = actions
    return h


OWNER = "van_hanh,sua,toan_quyen,quan_tri"


def test_health_khong_can_dang_nhap(goi):
    st, d = goi("GET", "/api/health")
    assert st == 200 and d["ok"] is True


def test_whoami_sso_va_an_pane_quan_tri(goi):
    st, d = goi("GET", "/api/whoami", _h(OWNER, "sep"))
    assert st == 200 and d["auth"] is True and d["sso"] is True
    assert d["role"] == "owner"
    assert "users" not in d["perms"]          # pane Tài khoản/API key tự ẩn trên board
    assert "delete" in d["perms"]             # quyền VẬN HÀNH giữ nguyên
    st, d = goi("GET", "/api/whoami", _h("van_hanh"))
    assert d["role"] == "seo" and d["sso"] is True


def test_khong_danh_tinh_thi_401_ke_ca_users_json_trong(goi):
    # SSO bật + users.json không tồn tại → vẫn BẮT đăng nhập (hết chế-độ-mở V2)
    st, _ = goi("GET", "/api/markets")
    assert st == 401


def test_cua_quan_tri_404_ke_ca_owner(goi):
    cua_get = ["/api/users", "/api/resets", "/api/admin-keys"]
    cua_post = ["/api/login", "/api/forgot", "/api/reset-approve", "/api/reset-drop",
                "/api/change-password", "/api/user-save", "/api/user-passwd",
                "/api/user-disable", "/api/user-remove", "/api/admin-keys"]
    for p in cua_get:
        st, d = goi("GET", p, _h(OWNER, "sep"))
        assert st == 404 and "OUTLIERY" in d["error"], p
    for p in cua_post:
        st, d = goi("POST", p, _h(OWNER, "sep"), body={})
        assert st == 404 and "OUTLIERY" in d["error"], p
    # mọi cửa phải là endpoint THẬT của app (chống gõ nhầm tên khi thêm/bớt)
    assert server._CUA_QUAN_TRI <= (set(server.PERM_OF) | server._OPEN)


def test_khong_tu_tao_tai_khoan_trong_app(goi):
    """Lệnh user 19/08: app không ghi/tạo tài khoản — request SSO của người MỚI
    không được đẻ bản ghi users.json (V2 sync_sso từng upsert mỗi request)."""
    p = Path(common.ROOT) / "users.json"
    assert not p.exists()
    st, _ = goi("GET", "/api/whoami", _h("van_hanh", "nguoi-moi-toanh"))
    assert st == 200
    goi("GET", "/api/markets", _h("van_hanh", "nguoi-moi-toanh"))
    assert not p.exists()                     # vẫn không có — không upsert


def test_gioi_han_di_san_chi_doc(goi):
    # users.json snapshot V2 còn giới hạn thị trường → _sso ĐỌC được, không ghi thêm
    p = Path(common.ROOT) / "users.json"
    common.write_json(p, {"users": [{"name": "kdscope", "role": "seo",
                                     "markets": ["Spain"], "sso": True}]})
    try:
        st, d = goi("GET", "/api/whoami", _h("van_hanh", "kdscope"))
        assert st == 200 and d["markets"] == ["Spain"]
        sau = users._load()["users"]
        assert len(sau) == 1                  # không đẻ thêm bản ghi
    finally:
        p.unlink()


def test_vai_thap_van_bi_chan_quyen_van_hanh(goi):
    # viewer (Manager BP khác) gọi endpoint sinh → 403 thiếu quyền, không phải 404
    st, d = goi("POST", "/api/generate", _h("", "quanly-vh"), body={})
    assert st == 403 and d.get("need_perm") == "generate"


# ── (4) nguồn khóa = KÉT, không fallback ─────────────────────────────────────────
def test_load_keys_khong_fallback_env(monkeypatch):
    monkeypatch.setenv("YOUTUBE_API_KEYS", "AIzaSyCCCCCCCCCCCCCCCCCCC-9999")
    with pytest.raises(RuntimeError) as e:
        common.load_keys()                    # GATEWAY_URL cổng chết (conftest)
    assert "OUTLIERY" in str(e.value)         # thông điệp rõ, không âm thầm ăn .env


def test_khoa_youtube_tu_ket(monkeypatch):
    monkeypatch.setattr(khoa_v3, "_cap_phat", lambda: {
        "trich_kenh": {"khoa": [{"id": "api-001", "key": "AIza-a"},
                                {"id": "api-002", "key": "AIza-b"}],
                       "che_do": "xoay_vong", "model": ""}})
    assert common.load_keys() == ["AIza-a", "AIza-b"]     # đủ pool, đúng thứ tự cấp


def test_llm_viec_anh_xa_nha(monkeypatch):
    monkeypatch.setattr(khoa_v3, "_cap_phat", lambda: {
        "sinh_metadata": {"khoa": [{"id": "api-003", "key": "sk-x", "nha": "glm"}],
                          "che_do": "mot_khoa", "model": "glm-4.5-air"}})
    assert khoa_v3.llm_viec() == ("glm", "sk-x", "glm-4.5-air")
    monkeypatch.setattr(khoa_v3, "_cap_phat", lambda: {
        "sinh_metadata": {"khoa": [{"id": "api-004", "key": "sk-y", "nha": "gemini"}],
                          "che_do": "mot_khoa", "model": ""}})
    with pytest.raises(RuntimeError) as e:
        khoa_v3.llm_viec()                    # nhà chưa hỗ trợ → nói thẳng, không đoán base URL
    assert "chưa hỗ trợ" in str(e.value)


def test_viec_chua_cap_khoa_bao_ro(monkeypatch):
    monkeypatch.setattr(khoa_v3, "_cap_phat", lambda: {})
    with pytest.raises(RuntimeError) as e:
        khoa_v3.khoa_youtube()
    assert "trich_kenh" in str(e.value) and "API Keys" in str(e.value)
