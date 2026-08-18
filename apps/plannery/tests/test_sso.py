# -*- coding: utf-8 -*-
"""Test SSO V3 (19/08/2026) — ghim: Actions-first dịch vai, VÁ BẪY users.json/
ADMIN_USERS không còn thắng header khi SSO, X-Remote-* ngoài loopback bị bỏ,
cửa quản trị nội bộ đóng 404 khi SSO, standalone (không TRUST_PROXY) giữ nguyên."""
import importlib
import json
import sys
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1]
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))


@pytest.fixture()
def sv(tmp_path, monkeypatch):
    monkeypatch.setenv("PLANNER_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("PLANNER_TRUST_PROXY", "1")
    import server
    return importlib.reload(server)   # nạp lại theo env của test


def _h(**kw):
    d = {"X-Remote-User": "thanhtho"}
    for k, v in kw.items():
        d[k.replace("_", "-")] = v
    return d


def test_actions_first_dich_vai(sv):
    ip = "127.0.0.1"
    assert sv.identity(_h(X_Remote_Actions="vao,khai_kenh_video"), ip)[1] == "seo"
    assert sv.identity(_h(X_Remote_Actions="vao,sua"), ip)[1] == "leader"
    assert sv.identity(_h(X_Remote_Actions="vao,sua,toan_quyen"), ip)[1] == "manager"
    assert sv.identity(_h(X_Remote_Actions="sua,toan_quyen,quan_tri"), ip)[1] == "admin"
    assert sv.identity(_h(X_Remote_Actions="vao"), ip)[1] == "viewer"
    # Actions RỖNG → fallback X-Remote-Role (giữ tương thích 'owner' V2)
    assert sv.identity(_h(X_Remote_Role="manager"), ip)[1] == "manager"
    assert sv.identity(_h(X_Remote_Role="owner"), ip)[1] == "admin"
    assert sv.identity(_h(), ip) == ("thanhtho", "viewer")


def test_va_bay_so_rieng_khong_thang_header(sv):
    ip = "127.0.0.1"
    # users.json có tên với vai manager — SSO bật thì header VẪN quyết (vá bẫy V2)
    sv._save_udb({"users": {"phpthao": {"name": "", "email": "", "role": "manager"}},
                  "invites": {}})
    assert sv.identity({"X-Remote-User": "phpthao"}, ip)[1] == "viewer"
    # ADMIN_USERS ('admin') cũng không thắng khi SSO — tự động hóa phải gửi Role
    assert sv.identity({"X-Remote-User": "admin"}, ip)[1] == "viewer"
    assert sv.identity({"X-Remote-User": "admin",
                        "X-Remote-Role": "admin"}, ip)[1] == "admin"


def test_standalone_giu_nguyen_hanh_vi_cu(sv, monkeypatch):
    monkeypatch.setenv("PLANNER_TRUST_PROXY", "0")
    ip = "127.0.0.1"
    sv._save_udb({"users": {"phpthao": {"name": "", "email": "", "role": "manager"}},
                  "invites": {}})
    assert sv.identity({"X-Remote-User": "admin"}, ip)[1] == "admin"
    assert sv.identity({"X-Remote-User": "phpthao"}, ip)[1] == "manager"


def test_header_ngoai_loopback_bi_bo(sv):
    # Header từ client LAN trực tiếp = giả mạo → bỏ, rơi về khách vãng lai
    assert sv.identity({"X-Remote-User": "admin", "X-Remote-Role": "admin"},
                       "192.168.1.50") == (None, "viewer")


def test_sso_dong_cua_quan_tri_qua_http(sv):
    srv = ThreadingHTTPServer(("127.0.0.1", 0), sv.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    goc = f"http://127.0.0.1:{srv.server_address[1]}"

    def goi(duong, headers=None, body=None):
        req = urllib.request.Request(goc + duong, data=body)
        for k, v in (headers or {}).items():
            req.add_header(k, v)
        if body is not None:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                return r.status, json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            return e.code, {}

    try:
        chu = {"X-Remote-User": "thanh", "X-Remote-Actions": "sua,toan_quyen,quan_tri"}
        # Cửa nội bộ đóng 404 VÔ ĐIỀU KIỆN khi SSO — kể cả admin
        assert goi("/invite", chu)[0] == 404
        assert goi("/logout", chu)[0] == 404
        assert goi("/api/users", chu)[0] == 404
        assert goi("/api/users", chu, b'{"action":"make_invite"}')[0] == 404
        assert goi("/api/register", None, b'{}')[0] == 404
        assert goi("/api/role", None, b'{"code":"x"}')[0] == 404
        # Đường nghiệp vụ vẫn sống: /api/me trả vai đúng + cờ sso; state đọc được
        code, me = goi("/api/me", {"X-Remote-User": "thanhtho",
                                   "X-Remote-Actions": "vao,khai_kenh_video"})
        assert (code, me["role"], me["sso"]) == (200, "seo", True)
        assert goi("/api/state")[0] == 200
        # viewer ghi /api/plan → 403 (RBAC server-side giữ nguyên)
        assert goi("/api/plan", {"X-Remote-User": "xem", "X-Remote-Actions": "vao"},
                   b'{"_rev":0}')[0] == 403
    finally:
        srv.shutdown()
