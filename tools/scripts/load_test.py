# -*- coding: utf-8 -*-
"""Load test P7.1 — 50 phiên giả lập bấm đồng thời vào gateway (đo, không đoán).

Mô phỏng nhịp dùng thật: mỗi phiên login → trang chủ → mở app qua proxy →
health → hỏi số liệu. Chạy: python tools/scripts/load_test.py [so_phien]
Yêu cầu hệ đang bật (start-all) + user test đã tạo.
"""
import asyncio
import statistics
import sys
import time

import httpx

GOC = "http://127.0.0.1:9000"


CHI_TIET: dict[str, list] = {}


async def _do(c, ten, fn):
    t0 = time.perf_counter()
    r = await fn()
    CHI_TIET.setdefault(ten, []).append(time.perf_counter() - t0)
    return r


_transport = None   # pool TCP DÙNG CHUNG — 50 client riêng trên 1 loop Windows dồn
                    # TCP connect là nghẽn CLIENT giả tạo (đo 16/08: 6.6s vs 0.7s);
                    # người thật là 50 máy khác nhau. Cookie mỗi phiên vẫn riêng.


async def mot_phien(i: int, ket_qua: list):
    async with httpx.AsyncClient(base_url=GOC, timeout=60,
                                 transport=_transport) as c:
        t0 = time.perf_counter()
        loi = None
        try:
            r = await _do(c, "login", lambda: c.post(
                "/login", data={"ten": "quanly", "mat_khau": "test123"}))
            assert r.status_code == 303, f"login {r.status_code}"
            for duong in ("/", "/app/app-mau/", "/app/data-analytics/health",
                          "/suc-khoe"):
                r = await _do(c, duong, lambda d=duong: c.get(d))
                assert r.status_code == 200, f"{duong} -> {r.status_code}"
            r = await _do(c, "cau-noi", lambda: c.post(
                "/api/cau-noi/hoi-so-lieu",
                data={"cau_hoi": "kenh outland tuan roi the nao"}))
            assert r.status_code == 200, f"cau-noi {r.status_code}"
        except Exception as e:  # noqa: BLE001
            loi = str(e)
        ket_qua.append({"phien": i, "giay": time.perf_counter() - t0, "loi": loi})


async def chay(so_phien: int):
    global _transport
    _transport = httpx.AsyncHTTPTransport(
        limits=httpx.Limits(max_connections=100, max_keepalive_connections=60))
    ket_qua: list = []
    t0 = time.perf_counter()
    await asyncio.gather(*(mot_phien(i, ket_qua) for i in range(so_phien)))
    tong = time.perf_counter() - t0
    hong = [k for k in ket_qua if k["loi"]]
    tg = sorted(k["giay"] for k in ket_qua)
    print(f"Phiên: {so_phien} | lỗi: {len(hong)} | tổng: {tong:.1f}s")
    print(f"Thời gian/phiên (6 request): trung vị {statistics.median(tg):.2f}s | "
          f"p95 {tg[int(len(tg)*0.95)-1]:.2f}s | max {tg[-1]:.2f}s")
    for k in hong[:5]:
        print("  LỖI:", k["phien"], k["loi"])
    for ten, ds in CHI_TIET.items():
        ds = sorted(ds)
        print(f"  {ten:28} trung vị {statistics.median(ds):6.2f}s | "
              f"max {ds[-1]:6.2f}s | n={len(ds)}")
    return len(hong)


if __name__ == "__main__":
    so = int(sys.argv[1]) if len(sys.argv) > 1 else 50
    sys.exit(1 if asyncio.run(chay(so)) else 0)
