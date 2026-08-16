# -*- coding: utf-8 -*-
"""Test gateway P2: đăng nhập qua iam.db, ép đổi mật khẩu, quản trị, proxy + claims.

Test proxy là TÍCH HỢP THẬT: app-mau chạy uvicorn thread ở :9190 (đúng cổng hợp
đồng), gateway chuyển tiếp sang — kiểm claims tiêm đúng và header giả mạo bị vứt.
"""
import importlib.util
import threading
import time
from pathlib import Path

import bcrypt
import httpx
import pytest
import uvicorn
from fastapi.testclient import TestClient

from nen.gateway.main import app as gateway_app
from nen.iam import iam

ROOT = Path(__file__).resolve().parents[1]
_gensalt_goc = bcrypt.gensalt


@pytest.fixture()
def iam_db(tmp_path, monkeypatch):
    monkeypatch.setenv("IAM_DB", str(tmp_path / "iam.db"))
    monkeypatch.setattr(bcrypt, "gensalt", lambda rounds=12: _gensalt_goc(4))
    conn = iam.ket_noi()
    ow = iam.claims_cua(iam.tao_tai_khoan(
        conn, None, "owner-test", "mk-test", "Ban quản trị", 5, phai_doi_mk=False))
    iam.tao_tai_khoan(conn, ow, "nhanvien", "mk-nv-6", "Kinh doanh", 2,
                      phai_doi_mk=False)
    conn.close()
    return tmp_path / "iam.db"


@pytest.fixture()
def client(iam_db):
    return TestClient(gateway_app, follow_redirects=False)


def _login(client, ten="owner-test", mk="mk-test"):
    return client.post("/login", data={"ten": ten, "mat_khau": mk})


@pytest.fixture(scope="module")
def app_mau_server():
    # Hệ dev đang bật sẵn app-mau ở :9190 → dùng luôn, không bind trùng cổng
    try:
        if httpx.get("http://127.0.0.1:9190/health", timeout=2).status_code == 200:
            yield
            return
    except httpx.HTTPError:
        pass
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
    r = _login(client, mk="sai")
    assert r.status_code == 401
    assert "Sai tên đăng nhập" in r.text


def test_dang_nhap_dung_vao_trang_chu(client):
    # UI_FLOW.md mục 1: đăng nhập xong vào THẲNG Hỏi–đáp như V1 — trang
    # "bảng chọn app" đã xóa hẳn (Owner chốt 16/08/2026).
    assert _login(client).status_code == 303
    r = client.get("/")
    assert r.status_code == 303
    assert r.headers["location"] == "/app/tri-thuc/hoi-dap"


def test_dang_xuat_mat_phien(client):
    _login(client)
    client.get("/logout")
    assert client.get("/").status_code == 303


def test_user_bi_xoa_phien_chet_theo(client, iam_db):
    _login(client)
    conn = iam.ket_noi()
    with conn:
        conn.execute("DELETE FROM tai_khoan WHERE ten='owner-test'")
    conn.close()
    assert client.get("/").status_code == 303   # đọc SỐNG → phiên chết ngay


def test_api_chua_dang_nhap_tra_401_json(client):
    r = client.get("/app/app-mau/health", headers={"accept": "application/json"})
    assert r.status_code == 401


# ---------- ép đổi mật khẩu (YC6 kế thừa) ----------

def test_phai_doi_mk_bi_ep_sang_trang_doi(client, iam_db):
    conn = iam.ket_noi()
    ow = iam.claims_cua(iam.lay_tai_khoan(conn, "owner-test"))
    iam.tao_tai_khoan(conn, ow, "moi", "mk-tam-6", "Kinh doanh", 2)  # phai_doi mặc định
    conn.close()
    _login(client, "moi", "mk-tam-6")
    r = client.get("/")
    assert r.status_code == 303
    assert r.headers["location"] == "/doi-mat-khau"
    # đổi xong thì vào được — "/" giờ 303 sang Hỏi–đáp (UI_FLOW.md mục 1),
    # không còn bị ép về /doi-mat-khau nữa
    client.post("/doi-mat-khau", data={"mk_moi": "mk-moi-6", "mk_lai": "mk-moi-6"})
    r = client.get("/")
    assert r.status_code == 303
    assert r.headers["location"] == "/app/tri-thuc/hoi-dap"


# ---------- trang quản trị ----------

def test_quan_tri_nhan_vien_403(client):
    _login(client, "nhanvien", "mk-nv-6")
    assert client.get("/quan-tri").status_code == 403


def test_quan_tri_owner_vao_va_tao_tai_khoan(client):
    _login(client)
    assert client.get("/quan-tri").status_code == 200
    r = client.post("/quan-tri/tao-tai-khoan", data={
        "ten": "tk-moi", "mat_khau": "mk-tam-6", "bo_phan": "Kinh doanh", "level": 2})
    assert "Đã tạo tài khoản tk-moi" in r.text
    conn = iam.ket_noi()
    assert iam.lay_tai_khoan(conn, "tk-moi")["phai_doi_mk"] == 1
    conn.close()


def test_quan_tri_xoa_phai_go_lai_ten(client):
    _login(client)
    r = client.post("/quan-tri/sua", data={
        "ten": "nhanvien", "hanh_dong": "xoa", "gia_tri": "go-sai"})
    assert "gõ lại đúng tên" in r.text
    conn = iam.ket_noi()
    assert iam.lay_tai_khoan(conn, "nhanvien") is not None   # chưa bị xóa
    conn.close()


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
    assert "owner" in r.text             # vai theo phan_quyen.json


def test_proxy_phat_x_remote_apps(client, app_mau_server):
    """UI_FLOW.md mục 2: gateway phát danh sách app user được vào qua
    X-Remote-Apps — sidebar các app dựng từ claims này, không tự đoán quyền.
    Header giả từ trình duyệt phải bị vứt (nằm trong _HEADER_CAM)."""
    _login(client)
    r = client.get("/app/app-mau/", headers={"X-Remote-Apps": "vault,gia-mao"})
    assert r.status_code == 200
    assert "gia-mao" not in r.text                    # header giả bị vứt
    assert "app-mau" in r.text                        # owner vào được app-mau
    assert "quan-tri" in r.text                       # owner mở được trang quản trị


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
