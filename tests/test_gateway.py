# -*- coding: utf-8 -*-
"""Test gateway P1: đăng nhập/session, menu, proxy + claims, sức khỏe.

Test proxy là TÍCH HỢP THẬT: app-mau chạy uvicorn thread ở :9190 (đúng cổng hợp
đồng), gateway chuyển tiếp sang — kiểm claims tiêm đúng và header giả mạo bị vứt.
"""
import importlib.util
import threading
import time
from pathlib import Path

import bcrypt
import pytest
import uvicorn
from fastapi.testclient import TestClient

from nen.gateway.main import app as gateway_app

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def users_file(tmp_path, monkeypatch):
    h = bcrypt.hashpw(b"mk-test", bcrypt.gensalt(rounds=4)).decode()
    f = tmp_path / "users.txt"
    f.write_text(f"owner-test:{h}:Ban quản trị:5\n", encoding="utf-8")
    monkeypatch.setenv("NEN_USERS", str(f))
    return f


@pytest.fixture()
def client(users_file):
    return TestClient(gateway_app, follow_redirects=False)


def _login(client):
    return client.post("/login", data={"ten": "owner-test", "mat_khau": "mk-test"})


@pytest.fixture(scope="module")
def app_mau_server():
    spec = importlib.util.spec_from_file_location(
        "app_mau_main", ROOT / "apps" / "app-mau" / "src" / "main.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    server = uvicorn.Server(uvicorn.Config(
        mod.app, host="127.0.0.1", port=9190, log_level="warning"))
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    for _ in range(50):
        if server.started:
            break
        time.sleep(0.1)
    assert server.started, "app-mau khong khoi dong duoc trong test"
    yield
    server.should_exit = True
    t.join(timeout=5)


# ---------- auth ----------

def test_chua_dang_nhap_bi_day_ve_login(client):
    r = client.get("/")
    assert r.status_code == 303
    assert r.headers["location"] == "/login"


def test_health_khong_can_dang_nhap(client):
    assert client.get("/health").status_code == 200


def test_dang_nhap_sai_401(client):
    r = client.post("/login", data={"ten": "owner-test", "mat_khau": "sai"})
    assert r.status_code == 401
    assert "Sai tên đăng nhập" in r.text


def test_dang_nhap_dung_vao_trang_chu(client):
    assert _login(client).status_code == 303
    r = client.get("/")
    assert r.status_code == 200
    assert "App mẫu" in r.text            # menu từ hợp đồng app
    assert "owner-test" in r.text


def test_dang_xuat_mat_phien(client):
    _login(client)
    client.get("/logout")
    assert client.get("/").status_code == 303


def test_user_bi_xoa_phien_chet_theo(client, users_file):
    _login(client)
    users_file.write_text("", encoding="utf-8")   # xóa user (đọc SỐNG mỗi request)
    assert client.get("/").status_code == 303


def test_api_chua_dang_nhap_tra_401_json(client):
    r = client.get("/app/app-mau/health", headers={"accept": "application/json"})
    assert r.status_code == 401


# ---------- proxy + claims (tích hợp thật) ----------

def test_proxy_app_la_404(client):
    _login(client)
    assert client.get("/app/khong-co/").status_code == 404


def test_proxy_tiem_claims_va_vut_header_gia(client, app_mau_server):
    _login(client)
    r = client.get("/app/app-mau/", headers={
        "X-Remote-User": "hacker",       # giả mạo từ trình duyệt — phải bị vứt
        "X-Remote-Role": "owner",
        "X-Remote-Level": "5",
    })
    assert r.status_code == 200
    assert "owner-test" in r.text        # claims thật từ session gateway
    assert "hacker" not in r.text        # header giả không lọt qua
    assert "owner" in r.text             # vai tạm level 5 → owner


def test_proxy_health_qua_gateway(client, app_mau_server):
    _login(client)
    r = client.get("/app/app-mau/health")
    assert r.status_code == 200
    assert r.json()["app"] == "app-mau"


def test_suc_khoe_bao_dung_trang_thai(client, app_mau_server):
    _login(client)
    r = client.get("/suc-khoe")
    assert r.status_code == 200
    assert "đang chạy" in r.text
