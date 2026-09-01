# -*- coding: utf-8 -*-
"""SỔ GỌI API (01/09/2026 — Owner phê 'đã yêu cầu mà chưa nối'): mọi call ra
dịch vụ ngoài (YouTube per key, LLM per app·việc) ghi MỘT DÒNG JSON-lines về
nền — app tự đủ ghi qua POST /api/so-goi loopback (khuôn heartbeat), app trong
repo cha ghi thẳng. Command Center đọc tổng hợp: units/calls hôm nay per key
(join với két theo ĐUÔI 4), sống/chết theo CALL THẬT gần nhất — không probe
đốt quota, không bịa số.
"""
import asyncio
import json

import httpx
import pytest

from nen.common import so_goi


@pytest.fixture(autouse=True)
def _san(tmp_path, monkeypatch):
    monkeypatch.setenv("SO_GOI_DIR", str(tmp_path / "so-goi"))
    yield


def test_ghi_va_tom_tat_hom_nay(monkeypatch):
    so_goi.ghi("radary", "youtube", duoi="4Yx1", units=1, ok=True)
    so_goi.ghi("radary", "youtube", duoi="4Yx1", units=100, ok=True)
    so_goi.ghi("seo-optimize", "youtube", duoi="2Fd3", units=1, ok=False,
               ma_loi="403 quota")
    so_goi.ghi("ai-agent", "llm", viec="writer", model="glm-4.5-air", ms=1200,
               ok=True)
    tt = so_goi.tom_tat_hom_nay()
    assert tt["youtube"]["theo_duoi"]["4Yx1"]["units"] == 101
    assert tt["youtube"]["theo_duoi"]["4Yx1"]["ok_cuoi"] is True
    assert tt["youtube"]["theo_duoi"]["2Fd3"]["ok_cuoi"] is False
    assert "403" in tt["youtube"]["theo_duoi"]["2Fd3"]["ma_loi"]
    assert tt["youtube"]["tong_units"] == 102
    assert tt["llm"]["calls"] == 1
    assert tt["llm"]["theo_viec"]["ai-agent · writer"]["calls"] == 1


def test_dong_hong_khong_giet_tom_tat(tmp_path):
    so_goi.ghi("x", "youtube", duoi="abcd", units=1)
    # dòng rác chen vào (app ghi dở/crash giữa dòng) → bỏ qua, không nổ
    f = next((tmp_path / "so-goi").rglob("*.log"))
    with open(f, "a", encoding="utf-8") as fh:
        fh.write("{hong\n")
    tt = so_goi.tom_tat_hom_nay()
    assert tt["youtube"]["tong_units"] == 1


# ---------- route loopback cho app tự đủ ----------

def _post(body, client_addr=("127.0.0.1", 50000)):
    from nen.gateway.main import app as gw

    async def run():
        tr = httpx.ASGITransport(app=gw, client=client_addr)
        async with httpx.AsyncClient(transport=tr, base_url="http://t") as cl:
            return await cl.post("/api/so-goi", json=body)
    return asyncio.run(run())


def test_route_loopback_ghi_duoc():
    r = _post({"app": "radary", "dich_vu": "youtube", "duoi": "4Yx1",
               "units": 3, "ok": True})
    assert r.status_code == 200
    assert so_goi.tom_tat_hom_nay()["youtube"]["theo_duoi"]["4Yx1"]["units"] == 3


def test_route_khong_loopback_404():
    r = _post({"app": "x", "dich_vu": "youtube"}, client_addr=("192.168.1.9", 1))
    assert r.status_code == 404


def test_route_thieu_truong_400():
    assert _post({"app": "x"}).status_code == 400
