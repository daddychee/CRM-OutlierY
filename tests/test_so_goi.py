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
    # gom theo GIỜ — nuôi chart units cộng dồn trong ngày
    from datetime import datetime
    gio = f"{datetime.now():%H}"
    assert tt["youtube"]["theo_gio"][gio] == 102


def test_dong_hong_khong_giet_tom_tat(tmp_path):
    so_goi.ghi("x", "youtube", duoi="abcd", units=1)
    # dòng rác chen vào (app ghi dở/crash giữa dòng) → bỏ qua, không nổ
    f = next((tmp_path / "so-goi").rglob("*.log"))
    with open(f, "a", encoding="utf-8") as fh:
        fh.write("{hong\n")
    tt = so_goi.tom_tat_hom_nay()
    assert tt["youtube"]["tong_units"] == 1


# ---------- kiem_vet: đọc sổ làm bằng chứng kiểm logic (02/09) ----------

def test_kiem_vet_theo_viec_va_xoay_khoa():
    """VẾT cho hệ kiểm logic: theo_viec của MỘT app + kiểm xoay khóa 403 —
    sau 403 key A, call kế cùng dịch vụ trong ≤5s phải OK với key KHÁC."""
    so_goi.ghi("radary", "youtube", duoi="4Yx1", viec="quet", units=1, ok=True)
    so_goi.ghi("radary", "youtube", duoi="4Yx1", viec="quet", units=1, ok=False,
               ma_loi="403 quotaExceeded")
    so_goi.ghi("radary", "youtube", duoi="2Fd3", viec="quet", units=1, ok=True)
    so_goi.ghi("seo-optimize", "youtube", duoi="9Ab0", viec="extract",
               units=100, ok=True)   # app khác — không được lẫn
    v = so_goi.kiem_vet("radary")
    assert v["theo_viec"]["quet"]["calls"] == 3
    assert v["theo_viec"]["quet"]["loi"] == 1
    assert "extract" not in v["theo_viec"]
    xk = v["xoay_khoa"]
    assert xk["so_403"] == 1 and xk["xoay_ok"] is True
    assert "2Fd3" in xk["chi_tiet"]


def test_kiem_vet_khong_403_khong_phan():
    """0 sự kiện 403 → xoay_ok=None (không có gì để phán, không bịa ĐÚNG)."""
    so_goi.ghi("radary", "youtube", duoi="4Yx1", viec="quet", units=1, ok=True)
    v = so_goi.kiem_vet("radary")
    assert v["xoay_khoa"]["so_403"] == 0 and v["xoay_khoa"]["xoay_ok"] is None


def test_kiem_vet_403_khong_xoay_la_fail():
    """403 mà call kế vẫn CÙNG key hoặc vẫn lỗi → xoay_ok=False."""
    so_goi.ghi("radary", "youtube", duoi="4Yx1", viec="quet", ok=False,
               ma_loi="403 quotaExceeded")
    so_goi.ghi("radary", "youtube", duoi="4Yx1", viec="quet", ok=False,
               ma_loi="403 quotaExceeded")
    v = so_goi.kiem_vet("radary")
    assert v["xoay_khoa"]["xoay_ok"] is False


def test_route_vet_loopback():
    from nen.gateway.main import app as gw
    so_goi.ghi("radary", "youtube", duoi="4Yx1", viec="quet", ok=True)

    async def run(addr):
        tr = httpx.ASGITransport(app=gw, client=addr)
        async with httpx.AsyncClient(transport=tr, base_url="http://t") as cl:
            return await cl.get("/api/vet/so-goi/radary")
    r = asyncio.run(run(("127.0.0.1", 50000)))
    assert r.status_code == 200 and r.json()["theo_viec"]["quet"]["calls"] == 1
    assert asyncio.run(run(("192.168.1.9", 1))).status_code == 404


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


def test_kiem_vet_do_TI_LE_khong_de_mot_ca_lat_ket_qua():
    """LỖI THẬT tự bắt 02/09: hệ chạy 990 sự kiện 403, cơ chế xoay khóa hoạt
    động đúng, nhưng phép kiểm cũ để MỘT ca cuối ngày không cứu được lật cả kết
    quả thành SAI — xóa mất 989 ca đúng. Đo tỉ lệ: cứu được ≥90% là ĐẠT; dưới
    ngưỡng (80%) mới là hỏng thật."""
    # 9 ca cứu được + 2 ca không → 9/11 = 82% ≥ 80% → vẫn ĐẠT
    for i in range(9):
        so_goi.ghi("radary", "youtube", duoi="aaaa", ok=False, ma_loi="403 quota")
        so_goi.ghi("radary", "youtube", duoi="bbbb", ok=True)
    so_goi.ghi("radary", "youtube", duoi="aaaa", ok=False, ma_loi="403 quota")
    so_goi.ghi("radary", "youtube", duoi="aaaa", ok=False, ma_loi="403 quota")
    xk = so_goi.kiem_vet("radary")["xoay_khoa"]
    assert xk["so_403"] == 11
    assert xk["so_cuu_duoc"] == 9
    assert xk["xoay_ok"] is True          # 82% ≥ ngưỡng 80%


def test_kiem_vet_hong_that_khi_hau_het_khong_cuu_duoc():
    """Đa số 403 không được cứu = cơ chế xoay khóa hỏng thật → phải báo SAI."""
    for _ in range(8):
        so_goi.ghi("radary", "youtube", duoi="aaaa", ok=False, ma_loi="403 quota")
    so_goi.ghi("radary", "youtube", duoi="bbbb", ok=True)
    xk = so_goi.kiem_vet("radary")["xoay_khoa"]
    assert xk["xoay_ok"] is False and xk["so_cuu_duoc"] < xk["so_403"]


def test_theo_gio_calls_dem_ca_dich_vu_KHONG_tinh_units(monkeypatch):
    """Owner 02/09: "ngoài YouTube cũng cần thấy lưu lượng các API khác".

    `theo_gio` chỉ cộng UNITS, nên dịch vụ không tính units ra đường phẳng 0 —
    đo thật hôm đó: LLM 132 call mà units toàn 0 (chưa ghi token), vẽ theo units
    là thấy "không dùng" trong khi đang chạy. Thêm theo_gio_calls (+ theo_gio_loi)
    để mọi dịch vụ vẽ được nhịp bằng thước của chính nó.

    Ghim: dịch vụ units=0 vẫn phải đếm được call và lỗi theo giờ."""
    from datetime import datetime

    so_goi.ghi("content-ultimate", "llm", viec="viet", model="glm-5", ok=True)
    so_goi.ghi("content-ultimate", "llm", viec="viet", model="glm-5", ok=True)
    so_goi.ghi("content-ultimate", "llm", viec="viet", model="glm-5", ok=False,
               ma_loi="429")
    tt = so_goi.tom_tat_hom_nay()
    gio = f"{datetime.now():%H}"

    assert tt["llm"]["tong_units"] == 0, "ca này cố ý không có units"
    assert tt["llm"]["theo_gio"].get(gio, 0) == 0, (
        "theo_gio (units) bằng 0 — chính là lý do phải có theo_gio_calls")
    assert tt["llm"]["theo_gio_calls"][gio] == 3
    assert tt["llm"]["theo_gio_loi"][gio] == 1


def test_moi_call_chi_kem_dich_vu_thua_va_co_tran(monkeypatch):
    """Owner 02/09: "hiển thị theo từng lần call là cột được không?" → "chỉ dùng
    cho LLM và serp".

    Hai dịch vụ này thưa (đo thật 132 và 58 call/ngày) nên vẽ mỗi call một cột
    được. YouTube 29.704 call thì KHÔNG — vừa không vẽ nổi (0,03px/cột) vừa bơm
    cả vạn dòng qua mạng mỗi 15s, mà nó đã có biểu đồ units cộng dồn riêng.

    Ghim: chỉ dịch vụ trong VE_TUNG_CALL được kèm moi_call, và có trần chống
    ngày bất thường."""
    for _ in range(3):
        so_goi.ghi("radary", "youtube", duoi="k1", units=1, ok=True)
    so_goi.ghi("content-ultimate", "llm", model="glm-5", ms=5800, ok=True)
    so_goi.ghi("radary", "serp", duoi="66c7", ok=False, ma_loi="het quota")
    tt = so_goi.tom_tat_hom_nay()

    assert "moi_call" not in tt["youtube"], (
        "YouTube KHÔNG được kèm từng call — 29k dòng/ngày qua mạng mỗi 15s")
    assert len(tt["llm"]["moi_call"]) == 1
    assert len(tt["serp"]["moi_call"]) == 1
    c = tt["llm"]["moi_call"][0]
    assert c["ms"] == 5800 and c["ok"] is True and c["nhan"] == "glm-5"
    assert len(c["luc"]) == 8, f"cần HH:MM:SS để vẽ đúng mốc giờ, có {c['luc']!r}"
    assert tt["serp"]["moi_call"][0]["ok"] is False


def test_moi_call_co_tran_va_dem_phan_bi_cat(monkeypatch):
    """Trần TOI_DA_CALL: ngày bất thường không bơm cả vạn dòng — và phần bị cắt
    phải ĐẾM ĐƯỢC để UI nói thật "N call cũ không vẽ", không im lặng giấu."""
    monkeypatch.setattr(so_goi, "TOI_DA_CALL", 5)
    for _ in range(8):
        so_goi.ghi("radary", "serp", duoi="k", ok=True)
    tt = so_goi.tom_tat_hom_nay()
    assert len(tt["serp"]["moi_call"]) == 5
    assert tt["serp"]["moi_call_cat"] == 3
    assert tt["serp"]["calls"] == 8, "tổng calls vẫn phải đếm đủ, không bị trần cắt"


def test_chi_phi_theo_app_ba_van_chong_bia_so_tien(monkeypatch, tmp_path):
    """Owner 03/09: "hiện số token đã tiêu tốn của từng API để tính chi phí cho
    từng app". Tiền là số người ta ĐỐI CHIẾU HOÁ ĐƠN — sai kiểu im lặng ở đây
    tệ hơn không có tính năng. Ba van:

    1. Call CHƯA ĐO token không được thành "0 token" — 0 giả làm hoá đơn rẻ hơn
       thật. calls_co_token/calls cho biết đang phủ bao nhiêu phần.
    2. Model chưa khai giá → vào `thieu_gia`, KHÔNG đoán giá.
    3. usd chốt LÚC GHI (kèm tỉ giá lúc đó) nên tổng tháng trước không nhảy số
       khi giá/tỉ giá hôm nay đổi."""
    so_goi.ghi("app-x", "llm", model="glm-5", token_vao=1_000_000, token_ra=1_000_000)
    so_goi.ghi("app-x", "llm", model="glm-5")                      # chưa đo token
    so_goi.ghi("app-x", "llm", model="model-chua-khai", token_vao=1000, token_ra=1000)
    so_goi.ghi("app-x", "youtube", duoi="k1", units=100)           # không phải LLM
    cp = so_goi.chi_phi_theo_app()["app-x"]

    assert cp["calls"] == 3, "chỉ đếm call LLM, không lẫn YouTube"
    assert cp["calls_co_token"] == 2, "call chưa đo token KHÔNG được tính là đã đo"
    # 1M vào × $0.6 + 1M ra × $2.2 = $2.8 — model chưa khai giá KHÔNG cộng thêm
    assert abs(cp["usd"] - 2.8) < 1e-6, cp["usd"]
    assert cp["thieu_gia"] == ["model-chua-khai"], cp["thieu_gia"]
    assert cp["token_vao"] == 1_001_000 and cp["token_ra"] == 1_001_000


def test_usd_chot_luc_ghi_khong_tinh_lai_khi_gia_doi(monkeypatch, tmp_path):
    """Đổi bảng giá KHÔNG được làm số tiền đã ghi nhảy — nếu không, hoá đơn
    tháng trước tự đổi mỗi lần nhà cung cấp tăng giá."""
    so_goi.ghi("app-y", "llm", model="glm-5", token_vao=1_000_000, token_ra=0)
    truoc = so_goi.chi_phi_theo_app()["app-y"]["usd"]

    gia_moi = tmp_path / "gia.csv"
    gia_moi.write_text("model,gia_vao_usd_1m,gia_ra_usd_1m\nglm-5,99,99\n",
                       encoding="utf-8")
    monkeypatch.setenv("GIA_LLM", str(gia_moi))
    so_goi._gia_cache.clear()
    assert so_goi.tinh_usd("glm-5", 1_000_000, 0) == 99, "bảng giá mới phải có hiệu lực"
    assert so_goi.chi_phi_theo_app()["app-y"]["usd"] == truoc, (
        "số tiền ĐÃ GHI bị tính lại theo giá mới — hoá đơn cũ sẽ nhảy số")


def test_model_chua_khai_gia_tra_None_khong_doan(monkeypatch):
    assert so_goi.tinh_usd("model-hoan-toan-la", 1000, 1000) is None


def test_self_test_cua_app_khong_duoc_ghi_so_that():
    """LỖI TỰ BẮT 03/09: nối token vào sổ xong, self-test của seo-optimize
    (model giả "m", token 1-10) và test của content-ultimate ghi 52 DÒNG RÁC
    vào sổ THẬT — làm bảng chi phí hiện app "44/44 call đo được mà $0.0000".

    Cùng họ bẫy phép-kiểm-ghi-bẩn-sổ đã dính hai lần trong tuần. Ghim: hai hàm
    gửi sổ của app phải im lặng khi đang pytest/self-test."""
    import os

    from pathlib import Path
    goc = Path(__file__).resolve().parents[1]

    seo = (goc / "apps" / "seo-optimize" / "seo" / "common.py").read_text(encoding="utf-8")
    assert "PYTEST_CURRENT_TEST" in seo and "SEO_SELFTEST" in seo, (
        "_ghi_so_goi_llm của seo-optimize thiếu chặn self-test")

    cu = (goc / "apps" / "content-ultimate" / "src" / "voiceprofile"
          / "usage.py").read_text(encoding="utf-8")
    assert "PYTEST_CURRENT_TEST" in cu, (
        "_ghi_so_goi_nen của content-ultimate thiếu chặn pytest")

    # chính test này đang chạy dưới pytest → biến phải có mặt, tức chặn hiệu lực
    assert os.environ.get("PYTEST_CURRENT_TEST"), "pytest phải đặt biến này"
