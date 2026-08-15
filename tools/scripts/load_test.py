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


async def mot_phien(i: int, ket_qua: list):
    async with httpx.AsyncClient(base_url=GOC, timeout=30) as c:
        t0 = time.perf_counter()
        loi = None
        try:
            r = await c.post("/login", data={"ten": "quanly", "mat_khau": "test123"})
            assert r.status_code == 303, f"login {r.status_code}"
            for duong in ("/", "/app/app-mau/", "/app/data-analytics/health",
                          "/suc-khoe"):
                r = await c.get(duong)
                assert r.status_code == 200, f"{duong} -> {r.status_code}"
            r = await c.post("/api/cau-noi/hoi-so-lieu",
                             data={"cau_hoi": "kenh outland tuan roi the nao"})
            assert r.status_code == 200, f"cau-noi {r.status_code}"
        except Exception as e:  # noqa: BLE001
            loi = str(e)
        ket_qua.append({"phien": i, "giay": time.perf_counter() - t0, "loi": loi})


async def chay(so_phien: int):
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
    return len(hong)


if __name__ == "__main__":
    so = int(sys.argv[1]) if len(sys.argv) > 1 else 50
    sys.exit(1 if asyncio.run(chay(so)) else 0)
