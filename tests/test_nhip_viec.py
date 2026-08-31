# -*- coding: utf-8 -*-
"""B4 giám sát (31/08/2026) — HEARTBEAT việc nền (pattern dead-man's switch
của Healthchecks): đảo chiều giám sát cho loại lỗi nguy hiểm nhất — job nền
chết IM LẶNG (ca thật: RadarY scheduler chết theo app 07/2026; kho Qdrant rỗng
3 ngày 31/07). Job chạy xong tự ping POST /api/nhip-viec/<ma>; quá chu kỳ
không thấy nhịp → tab Applications báo trễ.

Luật NGOÀI code: nen/rules/nhip_viec.json (thêm việc = thêm dòng, không sửa
code). Nhịp ghi data/nhip_viec.json nguyên tử. Route chỉ nhận LOOPBACK
(script SYSTEM không có session) + mã phải khai trong luật — sai → 404 lặng lẽ.
"""
import asyncio
import json
from pathlib import Path

import httpx
import pytest

from nen.common import nhip_viec

LUAT_MAU = {"viec": [
    {"ma": "backup-dem", "ten": "Backup 19:00", "chu_ky_phut": 1560},
    {"ma": "thieu-truong"},  # thiếu ten/chu_ky_phut → phải bị bỏ qua
]}


@pytest.fixture()
def san(tmp_path, monkeypatch):
    luat = tmp_path / "nhip_viec.json"
    luat.write_text(json.dumps(LUAT_MAU, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("NHIP_VIEC_LUAT", str(luat))
    monkeypatch.setenv("NHIP_VIEC_DATA", str(tmp_path / "data" / "nhip.json"))
    return tmp_path


def test_doc_luat_bo_muc_thieu_truong(san):
    ds = nhip_viec.doc_luat()
    assert [v["ma"] for v in ds] == ["backup-dem"]


def test_ghi_nhip_ma_la_bi_tu_choi(san):
    assert nhip_viec.ghi_nhip("khong-ton-tai") is False
    assert nhip_viec.ghi_nhip("backup-dem") is True


def test_tom_tat_chua_co_nhip_roi_co_roi_tre(san, monkeypatch):
    t = [1_000_000.0]
    monkeypatch.setattr(nhip_viec, "_gio", lambda: t[0])
    # chưa từng ping → nói thẳng "chưa có nhịp", không đoán ok/tre
    tt = nhip_viec.tom_tat()[0]
    assert tt["ma"] == "backup-dem" and tt["nhip_cuoi"] is None and tt["tre"] is None
    # ping xong → trong hạn
    nhip_viec.ghi_nhip("backup-dem")
    tt = nhip_viec.tom_tat()[0]
    assert tt["tre"] is False and tt["nhip_cuoi"]
    # tua quá chu kỳ → trễ
    t[0] += (1560 + 1) * 60
    tt = nhip_viec.tom_tat()[0]
    assert tt["tre"] is True


def test_ghi_nhip_nguyen_tu_song_qua_doc_lai(san):
    nhip_viec.ghi_nhip("backup-dem")
    du_lieu = json.loads(
        Path(nhip_viec._duong_data()).read_text(encoding="utf-8"))
    assert "backup-dem" in du_lieu


# ---------- route gateway ----------

def _goi_post(duong, client_addr=("127.0.0.1", 50000)):
    from nen.gateway.main import app as gateway_app

    async def run():
        tr = httpx.ASGITransport(app=gateway_app, client=client_addr)
        async with httpx.AsyncClient(transport=tr, base_url="http://t") as cl:
            return await cl.post(duong)
    return asyncio.run(run())


def test_route_loopback_ghi_duoc_nhip(san):
    r = _goi_post("/api/nhip-viec/backup-dem")
    assert r.status_code == 200 and r.json()["ok"] is True
    assert nhip_viec.tom_tat()[0]["tre"] is False


def test_route_ma_la_404_lang_le(san):
    assert _goi_post("/api/nhip-viec/khong-co").status_code == 404


def test_route_khong_loopback_404(san):
    """Máy LAN không được ping hộ — heartbeat là lời khai của chính máy chủ."""
    r = _goi_post("/api/nhip-viec/backup-dem", client_addr=("192.168.1.9", 1))
    assert r.status_code == 404
