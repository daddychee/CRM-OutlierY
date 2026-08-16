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
    monkeypatch.setenv("LOGS_DIR", str(tmp_path / "logs"))   # quota log về tmp
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
    assert client.get("/general/api-keys").status_code == 403   # giỏ Owner tuyệt đối


def test_ai_models_nghi_huu_redirect(client):
    """Trang 'AI Models' tự chế nghỉ hưu (Owner lệnh 16/08 — vi phạm quy trình
    duyệt mockup): GET redirect sang /general/api-keys; POST llm cũ GIỮ làm
    backend fallback."""
    _login(client, "owner-test", "mk-test")
    r = client.get("/general/ai-models")
    assert r.status_code == 303
    assert r.headers["location"] == "/general/api-keys"


def test_owner_luu_vai_llm_va_key_write_only(client):
    """Backend fallback llm.<vai>.* cũ vẫn chạy; trang API Keys MIGRATE mục cũ
    thành khóa (idempotent) và chỉ hiện ĐUÔI — không bao giờ render lại key."""
    _login(client, "owner-test", "mk-test")
    assert client.get("/general/api-keys").status_code == 200
    r = client.post("/general/ai-models/llm", data={
        "vai": "writer", "provider": "openai_compatible", "model": "glm-4.5-air",
        "base_url": "https://api.z.ai/api/paas/v4", "api_key": "sk-that-9999"})
    assert r.status_code == 303
    trang = client.get("/general/api-keys").text     # migration chạy lúc mở trang
    assert "glm-4.5-air" in trang
    assert "••••9999" in trang            # chỉ đuôi
    assert "sk-that-9999" not in trang    # KHÔNG bao giờ hiện lại key
    conn = ket.ket_noi()
    assert len(ket.liet_ke_api_keys(conn)) == 1      # mục cũ → 1 khóa LLM
    assert ket.doc_cap_phat(conn)["ai-agent"]["writer"]["khoa"] == ["api-001"]
    conn.close()
    client.get("/general/api-keys")                  # mở lại — idempotent
    conn = ket.ket_noi()
    assert len(ket.liet_ke_api_keys(conn)) == 1
    conn.close()
    # backend cũ: sửa model, bỏ trống key → key cũ GIỮ NGUYÊN (đường fallback)
    client.post("/general/ai-models/llm", data={"vai": "writer", "model": "glm-5",
                                      "provider": "", "base_url": "", "api_key": ""})
    conn = ket.ket_noi()
    assert ket.lay_bi_mat(conn, "llm.writer.api_key") == "sk-that-9999"
    assert ket.lay_cau_hinh(conn, "llm.writer.model") == "glm-5"
    conn.close()


def test_trang_api_keys_them_thu_hoi_cap_phat(client):
    """Vòng đời qua UI: thêm khóa (write-only) → cấp phát cho việc trong hợp
    đồng → thu hồi (gõ lại đuôi) gỡ khỏi cấp phát; MỌI bước có vết audit
    (trả nợ 'két không vết' — DE.md 3b)."""
    _login(client, "owner-test", "mk-test")
    r = client.post("/general/api-keys/add", data={
        "loai_chon": "llm:glm", "khoa": "sk-ui-2468", "model": "glm-4.5-air"})
    assert r.status_code == 303 and "bao=" in r.headers["location"]
    trang = client.get("/general/api-keys").text
    assert "••••2468" in trang and "sk-ui-2468" not in trang

    r = client.post("/general/api-keys/cap-phat", data={     # cấp cho việc hợp đồng
        "app_slug": "ai-agent", "viec": "writer", "them": "api-001"})
    assert r.status_code == 303
    conn = ket.ket_noi()
    assert ket.doc_cap_phat(conn)["ai-agent"]["writer"]["khoa"] == ["api-001"]
    conn.close()
    r = client.post("/general/api-keys/cap-phat", data={     # việc ngoài hợp đồng
        "app_slug": "ai-agent", "viec": "viec-bia", "them": "api-001"})
    assert "loi=" in r.headers["location"]

    r = client.post("/general/api-keys/revoke", data={"id": "api-001",
                                                      "go_lai": "sai"})
    assert "loi=" in r.headers["location"]                   # gõ sai đuôi → chặn
    r = client.post("/general/api-keys/revoke", data={"id": "api-001",
                                                      "go_lai": "2468"})
    assert "bao=" in r.headers["location"]
    conn = ket.ket_noi()
    assert ket.liet_ke_api_keys(conn) == []
    assert ket.doc_cap_phat(conn)["ai-agent"]["writer"]["khoa"] == []
    conn.close()
    conn = iam.ket_noi()
    hd = [d["hanh_dong"] for d in iam.doc_nhat_ky(conn, 20)]
    conn.close()
    assert "api_key_them" in hd and "api_cap_phat" in hd and "api_key_thu_hoi" in hd
    nk = iam.ket_noi()
    assert not any("sk-ui-2468" in d["chi_tiet"] for d in iam.doc_nhat_ky(nk, 20))
    nk.close()                                               # audit không chứa key


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
