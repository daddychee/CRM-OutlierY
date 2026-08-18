# -*- coding: utf-8 -*-
"""Pool theo THỊ TRƯỜNG (docs/RADARY_THI_TRUONG.md, 18/08/2026): gateway phát
danh mục thị trường từ danh bạ cho app phụ qua LOOPBACK — RadarY đối chiếu từ
đế, không tự đẻ sổ phân loại (DE.md luật 2). Khuôn test_loopback_api_khoa."""
import asyncio

import httpx
import pytest

from nen.common import danh_ba


@pytest.fixture()
def seed_tt(tmp_path, monkeypatch):
    monkeypatch.setenv("DANH_BA_DB", str(tmp_path / "danh_ba.db"))
    conn = danh_ba.ket_noi()
    ma = [danh_ba.them_thi_truong(conn, "US", "English"),
          danh_ba.them_thi_truong(conn, "Spain", "Spanish")]
    conn.commit()
    conn.close()
    return ma


def _goi(client_addr, duong="/api/danh-ba/thi-truong"):
    from nen.gateway.main import app as gateway_app

    async def run():
        tr = httpx.ASGITransport(app=gateway_app, client=client_addr)
        async with httpx.AsyncClient(transport=tr, base_url="http://t") as cl:
            return await cl.get(duong)
    return asyncio.run(run())


def test_loopback_thi_truong_tra_danh_muc_va_chan_ngoai(seed_tt):
    r = _goi(("127.0.0.1", 50000))
    assert r.status_code == 200
    ds = r.json()
    # thứ tự đế: ORDER BY tao_luc, ma — cùng giây tạo thì mã quyết, nên so theo mã
    assert sorted(t["ma"] for t in ds) == sorted(seed_tt)
    assert {t["ma"]: (t["ten"], t["ngon_ngu"]) for t in ds} == \
        {"TT-US": ("US", "English"), "TT-SPAIN": ("Spain", "Spanish")}
    # máy LAN gọi thẳng bị chặn — chỉ app phụ cùng máy đọc được
    assert _goi(("192.168.1.50", 50000)).status_code == 403


def test_loopback_ngach_kem_thi_truong_cua_ngach(seed_tt, tmp_path):
    """Tab nhỏ Pool RadarY dựng từ đây: ngách + TẬP THỊ TRƯỜNG user chọn ở
    General (ngach_thi_truong) — ngách mới 0 thị trường, không có mặc định."""
    conn = danh_ba.ket_noi()
    ng = danh_ba.them_ngach(conn, "Life In", trang_thai="khai_thac")
    danh_ba.dat_thi_truong_ngach(conn, ng, [seed_tt[0]])
    conn.commit()
    conn.close()
    r = _goi(("127.0.0.1", 50000), "/api/danh-ba/ngach")
    assert r.status_code == 200
    ds = {n["ma"]: n for n in r.json()}
    assert ds[ng]["ten"] == "Life In" and ds[ng]["thi_truong"] == [seed_tt[0]]
    assert _goi(("10.0.0.9", 50000), "/api/danh-ba/ngach").status_code == 403
