# -*- coding: utf-8 -*-
"""LÀM GỌN RadarY (Owner 16/08): quản trị org đóng khi SSO (404 kể cả owner nội
bộ), tab Quản trị ẩn trong app.js, nguồn khóa DUY NHẤT là két OUTLIERY (khoa_v3
— gateway chết thì run dừng với thông điệp rõ, không rơi về bảng nội bộ)."""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def app_sso(tmp_path, monkeypatch):
    monkeypatch.setenv("RADARY_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("RADARY_TRUST_PROXY", "1")
    monkeypatch.setenv("RADARY_SCHEDULER", "0")
    import radary.api as api
    return api.app


# owner NỘI BỘ app (claims Actions đầy đủ) — quản trị vẫn phải 404 khi SSO
_CLAIMS_OWNER = {"X-Remote-User": "sep-lam-gon",
                 "X-Remote-Actions": "them_video,tao_pool,toan_quyen,quan_tri"}

_QUAN_TRI = [
    ("get", "/api/orgs/1/keys"), ("post", "/api/orgs/1/keys"),
    ("post", "/api/orgs/1/keys/1/test"), ("delete", "/api/orgs/1/keys/1"),
    ("post", "/api/orgs/1/keys/harvest-bulk"),
    ("get", "/api/orgs/1/members"), ("post", "/api/orgs/1/members/1/pwreset"),
    ("delete", "/api/orgs/1/members/1"),
    ("post", "/api/orgs/1/invites"), ("get", "/api/orgs/1/invites"),
    ("delete", "/api/orgs/1/invites/1"),
    ("get", "/api/orgs/1/llm"), ("put", "/api/orgs/1/llm"),
    ("post", "/api/orgs/1/llm/test"),
]


def test_quan_tri_org_dong_404_khi_sso(app_sso):
    c = TestClient(app_sso, headers=_CLAIMS_OWNER)
    # body HỢP LỆ theo model từng route (superset — trường thừa Pydantic bỏ qua):
    # gửi rác 422 ở tầng validate là chưa chạm guard, không chứng minh được 404.
    body = {"key": "AIza-x", "keys_text": "AIza-x", "role": "viewer",
            "provider": "claude", "model": "", "workspace_id": 0, "backup": False}
    for method, duong in _QUAN_TRI:
        r = getattr(c, method)(duong, **({"json": body} if method in ("post", "put") else {}))
        assert r.status_code == 404, (method, duong, r.status_code)
        assert "OUTLIERY" in r.json().get("detail", "")   # nói rõ quản trị dời nhà


def test_app_js_an_tab_quan_tri_khi_sso():
    js = (Path(__file__).resolve().parents[1] / "web" / "app.js").read_text(encoding="utf-8")
    assert "!me.sso && (role === 'owner' || role === 'manager')" in js   # lọc tab
    assert "${tab === 'admin' && !me.sso &&" in js                        # chặn cả render


def test_khoa_v3_gateway_chet_loi_ro_khong_fallback(monkeypatch):
    from radary import khoa_v3
    monkeypatch.setenv("GATEWAY_URL", "http://127.0.0.1:1")   # cổng chết
    with pytest.raises(RuntimeError) as e:
        khoa_v3.lay_khoa("harvest")
    assert "OUTLIERY" in str(e.value)


def test_khoa_v3_viec_chua_cap_va_thanh_cong(monkeypatch):
    from radary import khoa_v3

    class _Resp:
        def __init__(self, data): self._d = json.dumps(data).encode()
        def read(self): return self._d
        def __enter__(self): return self
        def __exit__(self, *a): return False

    du_lieu = {"harvest": {"khoa": [{"id": "api-001", "key": "AIza-x-1"},
                                    {"id": "api-002", "key": "AIza-x-2"}],
                           "che_do": "xoay_vong", "model": ""}}
    monkeypatch.setattr(khoa_v3.urllib.request, "urlopen",
                        lambda url, timeout=5: _Resp(du_lieu))
    assert khoa_v3.lay_khoa("harvest") == ["AIza-x-1", "AIza-x-2"]
    with pytest.raises(RuntimeError) as e:
        khoa_v3.lay_khoa("quet_dinh_ky")                      # việc chưa cấp khóa
    assert "API Keys" in str(e.value)


def test_run_cycle_dung_ro_khi_thieu_khoa(tmp_path, monkeypatch):
    """scan.run_cycle: gateway chết → tag NO-KEY kèm 'loi' nguyên văn — run dừng,
    KHÔNG đọc bảng api_keys nội bộ (nguồn cũ nghỉ)."""
    monkeypatch.setenv("RADARY_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("GATEWAY_URL", "http://127.0.0.1:1")
    from radary import db, scan
    conn = db.connect(tmp_path / "radary.db")
    with conn:
        conn.execute("INSERT INTO orgs(id, name, created_ts) VALUES (1, 'T', 0)")
        conn.execute("INSERT INTO workspaces(id, org_id, name, created_ts) "
                     "VALUES (1, 1, 'ws', 0)")
        # bảng nội bộ CÓ khóa — nếu run vẫn NO-KEY nghĩa là không còn fallback
        conn.execute("INSERT INTO api_keys(org_id, key) VALUES (1, 'AIza-noi-bo')")
    kq = scan.run_cycle(conn, 1)
    conn.close()
    assert kq["tag"] == "NO-KEY"
    assert "OUTLIERY" in kq["loi"]                            # thông điệp rõ, không âm thầm
