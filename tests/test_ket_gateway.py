# -*- coding: utf-8 -*-
"""Test két nối gateway (P3): /general/ai-models chỉ Owner (giỏ tuyệt đối — Admin ủy quyền
cũng KHÔNG vào được), API loopback, key write-only."""
import asyncio

import bcrypt
import httpx
import pytest
from fastapi.testclient import TestClient

from nen.gateway.main import app as gateway_app
from nen.iam import iam
from nen.ket_cau_hinh import ket

_gensalt_goc = bcrypt.gensalt


@pytest.fixture()
def he(tmp_path, monkeypatch):
    monkeypatch.setenv("IAM_DB", str(tmp_path / "iam.db"))
    monkeypatch.setenv("KET_DB", str(tmp_path / "ket.db"))
    monkeypatch.setenv("KET_KEY", str(tmp_path / "ket.key"))
    monkeypatch.setattr(bcrypt, "gensalt", lambda rounds=12: _gensalt_goc(4))
    conn = iam.ket_noi()
    ow = iam.claims_cua(iam.tao_tai_khoan(
        conn, None, "owner-test", "mk-test", "Ban quản trị", 5, phai_doi_mk=False))
    iam.tao_tai_khoan(conn, ow, "admin", "mk-admin", "Kinh doanh", 4,
                      phai_doi_mk=False)
    iam.sua_tai_khoan(conn, ow, "admin", admin_uy_quyen=True)
    conn.close()


@pytest.fixture()
def client(he):
    return TestClient(gateway_app, follow_redirects=False)


def _login(client, ten, mk):
    return client.post("/login", data={"ten": ten, "mat_khau": mk})


def test_cai_dat_admin_uy_quyen_van_403(client):
    _login(client, "admin", "mk-admin")
    assert client.get("/general/ai-models").status_code == 403   # giỏ Owner tuyệt đối


def test_owner_luu_vai_llm_va_key_write_only(client):
    _login(client, "owner-test", "mk-test")
    assert client.get("/general/ai-models").status_code == 200
    r = client.post("/general/ai-models/llm", data={
        "vai": "writer", "provider": "openai_compatible", "model": "glm-4.5-air",
        "base_url": "https://api.z.ai/api/paas/v4", "api_key": "sk-that-9999"})
    assert r.status_code == 303
    trang = client.get("/general/ai-models").text
    assert "glm-4.5-air" in trang
    assert "••••9999" in trang            # chỉ đuôi
    assert "sk-that-9999" not in trang    # KHÔNG bao giờ hiện lại key
    # sửa model, bỏ trống key → key cũ GIỮ NGUYÊN
    client.post("/general/ai-models/llm", data={"vai": "writer", "model": "glm-5",
                                      "provider": "", "base_url": "", "api_key": ""})
    conn = ket.ket_noi()
    assert ket.lay_bi_mat(conn, "llm.writer.api_key") == "sk-that-9999"
    assert ket.lay_cau_hinh(conn, "llm.writer.model") == "glm-5"
    conn.close()


def test_api_loopback_tra_du_va_chan_khong_loopback(he):
    conn = ket.ket_noi()
    ket.dat_cau_hinh(conn, "llm.writer.model", "glm-4.5-air")
    ket.dat_bi_mat(conn, "llm.writer.api_key", "sk-noi-bo-1234")
    conn.close()

    async def goi(client_addr):
        transport = httpx.ASGITransport(app=gateway_app, client=client_addr)
        async with httpx.AsyncClient(transport=transport,
                                     base_url="http://t") as c:
            return await c.get("/api/cau-hinh/llm/writer")

    r = asyncio.run(goi(("127.0.0.1", 50000)))     # app phụ loopback
    assert r.status_code == 200
    assert r.json()["api_key"] == "sk-noi-bo-1234"
    assert r.json()["timeout"] == 60 and r.json()["retry"] == 0

    r2 = asyncio.run(goi(("192.168.1.50", 50000)))  # máy LAN gọi thẳng → chặn
    assert r2.status_code == 403
