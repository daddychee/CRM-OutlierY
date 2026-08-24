# -*- coding: utf-8 -*-
"""Bước 1 — khung app: /health + trang /tasky + luật claims (fail-closed)."""
from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)

CLAIMS = {"X-Remote-User": "hant", "X-Remote-Level": "2",
          "X-Remote-Dept": "V%E1%BA%ADn%20h%C3%A0nh%20-%20S%E1%BA%A3n%20xu%E1%BA%A5t",
          "X-Remote-Name": "Nguy%E1%BB%85n%20Thu%20H%C3%A0"}


def test_health_tra_dung_hop_dong_app():
    r = client.get("/health")
    assert r.status_code == 200
    d = r.json()
    assert d["trang_thai"] == "ok" and d["app"] == "tasky"


def test_khong_co_claims_thi_401_khong_lo_trang():
    """App bind loopback nhưng vẫn fail-closed: không danh tính → không vào."""
    r = client.get("/tasky")
    assert r.status_code == 401


def test_co_claims_thi_vao_duoc_va_hien_dung_ten():
    r = client.get("/tasky", headers=CLAIMS)
    assert r.status_code == 200
    assert "Nguyễn Thu Hà" in r.text          # X-Remote-Name đã unquote
    assert "Vận hành - Sản xuất" in r.text     # X-Remote-Dept đã unquote


def test_dept_tieng_viet_duoc_unquote_trong_claims():
    """Proxy quote() header (phải ASCII) — app so RBAC trên chuỗi gốc, không so
    chuỗi %-encoded (nếu quên unquote thì luật 'cùng bộ phận' sẽ sai lặng lẽ)."""
    from src.main import lay_user
    u = lay_user(x_remote_user="hant", x_remote_level="3", x_remote_role="leader",
                 x_remote_dept="Kinh%20doanh", x_remote_name="")
    assert u["bo_phan"] == "Kinh doanh" and u["level"] == 3


def test_co_hanh_dong_doc_dung_header_phay():
    from src.main import cac_hanh_dong
    assert cac_hanh_dong("vao, giao_viec ,bao_cao_bo_phan") == {
        "vao", "giao_viec", "bao_cao_bo_phan"}
    assert cac_hanh_dong("") == set()
