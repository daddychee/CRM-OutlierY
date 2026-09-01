# -*- coding: utf-8 -*-
"""B2 giám sát (31/08/2026) — TRẠM ĐO LỖI ở proxy gateway.

Mọi request app đều qua chuyen_tiep → đó là chỗ đo tự nhiên: app trả 5xx /
cổng chết / timeout đều được ghi nhận theo CỔNG (1-1 với app trong hợp đồng),
cửa sổ trượt 5 phút, kèm vết bền JSON-lines qua nen/common/nhat_ky.py.
Trước B2: 5xx của app đi xuyên proxy không để lại vết nào (điều tra 31/08).
"""
import asyncio
import threading
import time

import bcrypt
import httpx
import pytest
import uvicorn
from fastapi import FastAPI
from fastapi.responses import Response as FResponse
from fastapi.testclient import TestClient
from starlette.requests import Request

from nen.common import dem_loi, proxy
from nen.iam import iam

_gensalt_goc = bcrypt.gensalt


@pytest.fixture(autouse=True)
def _sach(tmp_path, monkeypatch):
    """Mỗi test một trạng thái đếm sạch + log về tmp (không ghi data/logs thật)."""
    monkeypatch.setenv("LOGS_DIR", str(tmp_path / "logs"))
    dem_loi.xoa_het()
    yield
    dem_loi.xoa_het()


# ---------- bộ đếm cửa sổ trượt ----------

def test_cua_so_truot_dem_loi_va_yeu_cau(monkeypatch):
    t = [1000.0]
    monkeypatch.setattr(dem_loi, "_gio", lambda: t[0])
    for _ in range(8):
        dem_loi.ghi_yeu_cau(9190)
    dem_loi.ghi_loi(9190, 500, "/api/x")
    dem_loi.ghi_loi(9190, 502, "/api/y")
    tt = dem_loi.tom_tat()[9190]
    assert tt["yeu_cau"] == 8 and tt["loi"] == 2
    assert tt["gan_nhat"]["status"] == 502 and tt["gan_nhat"]["duong"] == "/api/y"
    # quá cửa sổ → không còn tính (trượt, không tích lũy vô hạn)
    t[0] += dem_loi.CUA_SO + 1
    tt = dem_loi.tom_tat().get(9190, {"yeu_cau": 0, "loi": 0})
    assert tt["yeu_cau"] == 0 and tt["loi"] == 0


def test_ghi_loi_de_vet_ben_nhat_ky(tmp_path):
    dem_loi.ghi_loi(9190, 500, "/api/x")
    files = list((tmp_path / "logs").rglob("*.log"))
    assert files, "phải có vết JSON-lines trên đĩa"
    nd = files[0].read_text(encoding="utf-8")
    assert "loi_app" in nd and "9190" in nd and "/api/x" in nd


def test_bao_loi_khong_lam_ngap_dia():
    """Bão 5xx (app hỏng nặng) → đĩa chỉ nhận tới trần mỗi cửa sổ, RAM vẫn đếm đủ."""
    for i in range(dem_loi.TRAN_GHI_DIA + 50):
        dem_loi.ghi_loi(9190, 500, f"/x{i}")
    tt = dem_loi.tom_tat()[9190]
    assert tt["loi"] == dem_loi.TRAN_GHI_DIA + 50  # RAM đếm đủ


# ---------- móc trong proxy ----------

@pytest.fixture(scope="module")
def stub_loi():
    stub = FastAPI()

    @stub.get("/ok")
    async def ok():
        return {"ok": True}

    @stub.get("/loi")
    async def loi():
        return FResponse("chet", status_code=500)

    @stub.get("/cham")
    async def cham():
        await asyncio.sleep(2)
        return {"ok": True}

    server = uvicorn.Server(uvicorn.Config(
        stub, host="127.0.0.1", port=0, log_level="warning"))
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    for _ in range(50):
        if server.started:
            break
        time.sleep(0.1)
    assert server.started
    yield server.servers[0].sockets[0].getsockname()[1]
    server.should_exit = True
    t.join(timeout=5)


def _req(path="/", method="GET"):
    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}
    scope = {"type": "http", "http_version": "1.1", "method": method,
             "scheme": "http", "path": path, "raw_path": path.encode(),
             "query_string": b"", "headers": [(b"host", b"t")],
             "client": ("127.0.0.1", 1), "server": ("t", 80)}
    return Request(scope, receive)


def _goi(cong, duong):
    return asyncio.run(proxy.chuyen_tiep(
        _req("/" + duong), cong, "/app/stub", duong, "tester", []))


def test_proxy_ghi_nhan_5xx_va_dem_yeu_cau(stub_loi):
    r = _goi(stub_loi, "ok")
    assert r.status_code == 200
    r = _goi(stub_loi, "loi")
    assert r.status_code == 500
    tt = dem_loi.tom_tat()[stub_loi]
    assert tt["yeu_cau"] == 2 and tt["loi"] == 1
    assert tt["gan_nhat"]["status"] == 500


def test_proxy_cong_chet_ghi_nhan_502():
    r = _goi(1, "x")  # cổng 1: không gì nghe
    assert r.status_code == 502
    tt = dem_loi.tom_tat()[1]
    assert tt["loi"] == 1 and tt["gan_nhat"]["status"] == 502


def test_proxy_timeout_thanh_504_va_ghi_nhan(stub_loi, monkeypatch):
    """Trước B2 timeout nổ exception thô lên FastAPI (500 không vết); giờ 504 +
    ghi nhận — bài học LLM_TIMEOUT 19/07: mọi lời gọi ra ngoài phải có vết."""
    monkeypatch.setattr(proxy, "_lay_client",
                        lambda: httpx.AsyncClient(timeout=0.3))
    r = _goi(stub_loi, "cham")
    assert r.status_code == 504
    tt = dem_loi.tom_tat()[stub_loi]
    assert tt["loi"] == 1 and tt["gan_nhat"]["status"] == 504


# ---------- P1 command center: latency p50/p95 + nút chết runtime ----------

def test_latency_p50_p95(monkeypatch):
    """Proxy đo ms mỗi request → tom_tat trả p50/p95 trong cửa sổ."""
    t = [1000.0]
    monkeypatch.setattr(dem_loi, "_gio", lambda: t[0])
    for ms in [100, 200, 300, 400, 500, 600, 700, 800, 900, 1000]:
        dem_loi.ghi_yeu_cau(9190, ms=ms)
    tt = dem_loi.tom_tat()[9190]
    assert tt["p50"] == 500 and tt["p95"] >= 900
    # quá cửa sổ → hết số liệu, trả None (không bịa 0)
    t[0] += dem_loi.CUA_SO + 1
    tt = dem_loi.tom_tat().get(9190, {})
    assert tt.get("p50") is None


def test_yeu_cau_khong_ms_van_dem_duoc():
    """Tương thích ngược: gọi không ms (chỗ chưa đo) vẫn đếm request, p50 None."""
    dem_loi.ghi_yeu_cau(9190)
    tt = dem_loi.tom_tat()[9190]
    assert tt["yeu_cau"] == 1 and tt["p50"] is None


def test_tom_tat_dem_loi_theo_loai():
    """Donut UI cần lỗi phân loại: 5xx app / 502 cổng chết / 504 timeout."""
    dem_loi.ghi_loi(9190, 500, "/a")
    dem_loi.ghi_loi(9190, 503, "/b")
    dem_loi.ghi_loi(9190, 502, "/c")
    dem_loi.ghi_loi(9190, 504, "/d")
    tl = dem_loi.tom_tat()[9190]["theo_loai"]
    assert tl == {"5xx": 2, "502": 1, "504": 1}


def test_nut_chet_runtime_dem_rieng():
    """POST trả 404/405 = người dùng bấm trúng NÚT CHẾT — đếm riêng, không trộn
    vào 'loi' 5xx (bệnh khác nhau: nút chết là UI↔server lệch, 5xx là app nổ)."""
    dem_loi.ghi_nut_chet(9190, 404, "/api/chia-chuong")
    dem_loi.ghi_nut_chet(9190, 405, "/api/x")
    tt = dem_loi.tom_tat()[9190]
    assert tt["nut_chet"] == 2
    assert tt["nut_chet_gan_nhat"]["duong"] == "/api/x"
    assert tt["loi"] == 0


def test_proxy_do_ms_va_bat_post_404(stub_loi):
    """Tích hợp: qua chuyen_tiep thật — GET ok có ms; POST vào đường không tồn
    tại → 404 ghi nút chết."""
    r = _goi(stub_loi, "ok")
    assert r.status_code == 200
    tt = dem_loi.tom_tat()[stub_loi]
    assert tt["p50"] is not None and tt["p50"] >= 0

    async def run():
        return await proxy.chuyen_tiep(
            _req("/khong-co", method="POST"), stub_loi, "/app/stub",
            "khong-co", "tester", [])
    r = asyncio.run(run())
    assert r.status_code == 404
    tt = dem_loi.tom_tat()[stub_loi]
    assert tt["nut_chet"] == 1


# ---------- tab Applications hiện số lỗi ----------

@pytest.fixture()
def owner_client(tmp_path, monkeypatch):
    monkeypatch.setenv("IAM_DB", str(tmp_path / "iam.db"))
    monkeypatch.setattr(bcrypt, "gensalt", lambda rounds=12: _gensalt_goc(4))
    conn = iam.ket_noi()
    iam.tao_tai_khoan(conn, None, "owner-test", "mk-test", "Ban quản trị", 5,
                      phai_doi_mk=False)
    conn.close()
    from nen.gateway.main import app as gateway_app
    client = TestClient(gateway_app, follow_redirects=False)
    client.post("/login", data={"ten": "owner-test", "mat_khau": "mk-test"})
    return client


def test_trang_applications_hien_so_loi(owner_client, monkeypatch):
    from nen.gateway import main as gw
    monkeypatch.setattr(gw, "doc_hop_dong", lambda: [
        {"slug": "stub", "ten": "Stub App", "cong": 9190, "health": "/health",
         "tien_to": [], "du_lieu": []}])
    dem_loi.ghi_yeu_cau(9190)
    dem_loi.ghi_loi(9190, 500, "/api/vo")
    r = owner_client.get("/general/applications")
    assert r.status_code == 200
    assert "/api/vo" in r.text  # lỗi gần nhất hiện trên tab, kèm đường dẫn
