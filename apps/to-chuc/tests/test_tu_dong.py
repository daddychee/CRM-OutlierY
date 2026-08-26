# -*- coding: utf-8 -*-
"""Test tab Tự động: B5 đối soát AdSense · C3 tiền API từ quota log · C2 luật gợi ý.

Bất biến xuyên suốt: máy chỉ ĐỀ NGHỊ, người CHỐT — không bút toán nào do máy tự
ghi vào sổ tiền; nguồn thiếu thì nói thẳng chứ không nặn số.
"""
import json
import os
from pathlib import Path

import pytest

from src import tai_chinh, tu_dong

THANG = "2026-08"
VI = "vietcombank"
VI_USD = "payoneer"


def _seed():
    from nen.common import danh_ba
    conn = danh_ba.ket_noi()
    try:
        ng = danh_ba.them_ngach(conn, "Life In")
        k1 = danh_ba.them_kenh(conn, "OUTLAND", ng)
        k2 = danh_ba.them_kenh(conn, "TIME VAULT", ng)
    finally:
        conn.close()
    tai_chinh.them_muc_tieu("Vận hành chung", 0)
    tai_chinh.ghi_ty_gia("2026-08-01", "USD", 25920, "test")
    return k1, k2


def _ghi_quota(ngay, api, app, viec, luot=1, quota=0):
    p = Path(os.environ["LOGS_DIR"]) / "quota" / ngay[:4] / ngay[5:7] / f"{ngay}.log"
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"luc": f"{ngay}T09:00:00", "api": api, "khoa_duoi": "1234",
                            "app": app, "viec": viec, "luot": luot,
                            "quota_tieu": quota}, ensure_ascii=False) + "\n")


# ---------- B5: đối soát chi trả AdSense ----------

CSV_ADSENSE = """Channel,Amount
OUTLAND,2140.00
TIME VAULT,1954.00
The Space Archive,312.00
"""


def test_doi_soat_khop_kenh_va_chi_ra_chenh_lech():
    k1, k2 = _seed()
    # đã ghi doanh thu ƯỚC TÍNH cho 2 kênh
    tai_chinh.them_but_toan("kt", "2026-08-05", "THU-ADS", 2140, "Vận hành chung",
                            kenh_ma=k1, vi=VI_USD, trang_thai_thu="uoc_tinh")
    tai_chinh.them_but_toan("kt", "2026-08-05", "THU-ADS", 1980, "Vận hành chung",
                            kenh_ma=k2, vi=VI_USD, trang_thai_thu="uoc_tinh")
    kq = tu_dong.doi_soat_adsense(CSV_ADSENSE, THANG)
    d = {x["ten_trong_tep"]: x for x in kq["dong"]}
    assert d["OUTLAND"]["kenh_ma"] == k1 and d["OUTLAND"]["chac_chan"] is True
    assert d["OUTLAND"]["chenh"] == 0
    assert d["TIME VAULT"]["chenh"] == -26.0        # 1954 thật vs 1980 ước tính
    # tên không khớp kênh nào → để người chọn, KHÔNG đoán bừa
    assert d["The Space Archive"]["kenh_ma"] == "" and d["The Space Archive"]["chac_chan"] is False


def test_doi_soat_khong_tu_ghi_so():
    """Máy dựng bút toán NHÁP; sổ không nhận dòng nào cho tới khi người duyệt."""
    _seed()
    truoc = len(tai_chinh.doc_so())
    tu_dong.doi_soat_adsense(CSV_ADSENSE, THANG)
    assert len(tai_chinh.doc_so()) == truoc


def test_duyet_doi_soat_sinh_but_toan_va_chenh_lech():
    k1, _ = _seed()
    b = tu_dong.duyet_doi_soat("lanne", [
        {"kenh_ma": k1, "tien_that": 2140, "chenh": 0}], THANG, "Vận hành chung",
        VI_USD)
    assert len(b) == 1
    bt = tai_chinh.doc_so()[0]
    assert bt["nguon"] == "adsense" and bt["trang_thai_thu"] == "da_ve_vi"
    assert bt["so_tien"] == 2140.0 and bt["kenh_ma"] == k1


def test_csv_hong_thi_bao_loi_khong_nuot():
    _seed()
    with pytest.raises(ValueError):
        tu_dong.doi_soat_adsense("khong,phai,csv,adsense\n1,2,3,4", THANG)


# ---------- C3: tiền API từ quota log ----------

def test_tien_api_quy_tu_quota_log():
    _seed()
    tu_dong.dat_don_gia("llm_glm", 0.0002)          # $/lượt
    tu_dong.dat_don_gia("youtube_v3", 0.000005)
    for i in range(3):
        _ghi_quota(f"2026-08-0{i + 1}", "llm_glm", "content-ultimate", "viết kịch bản",
                   luot=100)
    _ghi_quota("2026-08-05", "youtube_v3", "radary", "quét pool", luot=10_000)
    kq = tu_dong.tien_api_thang(THANG)
    d = {x["app"]: x for x in kq["dong"]}
    assert d["content-ultimate"]["luot"] == 300
    assert d["content-ultimate"]["thanh_tien_usd"] == 0.06     # 300 × 0.0002
    assert d["radary"]["thanh_tien_usd"] == 0.05
    assert kq["tong_usd"] == 0.11


def test_api_chua_co_don_gia_thi_khong_doan():
    _seed()
    _ghi_quota("2026-08-03", "api_la", "app-x", "việc gì đó", luot=500)
    kq = tu_dong.tien_api_thang(THANG)
    d = {x["app"]: x for x in kq["dong"]}
    assert d["app-x"]["thanh_tien_usd"] is None
    assert "chưa có đơn giá" in d["app-x"]["thieu"]
    assert kq["tong_usd"] == 0.0                      # không cộng số không biết


def test_tao_but_toan_tong_hop_api():
    _seed()
    tu_dong.dat_don_gia("llm_glm", 0.001)
    _ghi_quota("2026-08-02", "llm_glm", "ai-agent", "hỏi đáp", luot=1000)
    bt = tu_dong.ghi_tien_api("Bot", THANG, "Vận hành chung", VI_USD)
    assert bt["danh_muc"] == "CHI-API" and bt["nguon"] == "quota"
    assert bt["so_tien"] == 1.0 and bt["tien_te"] == "USD"
    with pytest.raises(ValueError):                   # ghi hai lần cùng kỳ → chặn
        tu_dong.ghi_tien_api("Bot", THANG, "Vận hành chung", VI_USD)


# ---------- C2: luật gợi ý phân loại ----------

def test_goi_y_tu_luat_csv(tmp_path, monkeypatch):
    p = tmp_path / "luat.csv"
    p.write_text("khop,danh_muc,vi,kenh_ma\nproxy;911,CHI-PROXY,payoneer,\n"
                 "z.ai;glm,CHI-API,payoneer,\n", encoding="utf-8")
    monkeypatch.setenv("LUAT_GOI_Y", str(p))
    g = tu_dong.goi_y("proxy 911 gói tháng")
    assert g["danh_muc"] == "CHI-PROXY" and g["vi"] == "payoneer"
    assert tu_dong.goi_y("nạp quota Z.AI")["danh_muc"] == "CHI-API"   # không phân biệt hoa thường
    assert tu_dong.goi_y("mua bàn phím") == {}       # không khớp → im lặng, không áp bừa


# ---------- route tab Tự động ----------

def _client():
    from fastapi.testclient import TestClient
    from src.main import app
    return TestClient(app, headers={"X-Remote-User": "lanne", "X-Remote-Level": "2",
                                    "X-Remote-Role": "viewer",
                                    "X-Remote-Dept": "K%E1%BA%BF%20to%C3%A1n",
                                    "X-Remote-Apps": "to-chuc,finance"})


def test_route_tab_auto_render():
    _seed()
    b = _client().get(f"/finance?tab=auto&thang={THANG}").text
    assert "Đối soát chi trả AdSense" in b
    assert "Tiền API từ nhật ký quota" in b
    assert "Luật gợi ý phân loại" in b
    assert "CHI-PROXY" in b          # luật seed từ rules/luat_goi_y.csv


def test_route_doi_soat_tra_bang_nhap_va_duyet_moi_ghi_so():
    k1, _ = _seed()
    c = _client()
    r = c.post("/finance/doi-soat", data={"thang": THANG},
               files=[("tep", ("chi-tra.csv", CSV_ADSENSE.encode(), "text/csv"))])
    assert r.status_code == 200 and "OUTLAND" in r.text
    assert tai_chinh.doc_so() == []              # bảng nháp — CHƯA ghi sổ
    r2 = c.post("/finance/doi-soat/duyet",
                data={"thang": THANG, "muc_tieu": "Vận hành chung", "vi": VI_USD,
                      "kenh_0": k1, "tien_0": "2140.00"}, follow_redirects=False)
    assert r2.status_code == 303
    bt = tai_chinh.doc_so()
    assert len(bt) == 1 and bt[0]["nguon"] == "adsense"


def test_route_csv_hong_tra_422():
    _seed()
    r = _client().post("/finance/doi-soat", data={"thang": THANG},
                       files=[("tep", ("x.csv", b"a,b\n1,2", "text/csv"))])
    assert r.status_code == 422


def test_modal_but_toan_co_goi_y_c2():
    _seed()
    b = _client().get(f"/finance?tab=ledger&thang={THANG}").text
    assert "apGoiY()" in b and "var LUAT =" in b
    assert "CHI-PROXY" in b            # luật đã nhúng để JS gợi ý ngay khi gõ
