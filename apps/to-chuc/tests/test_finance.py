# -*- coding: utf-8 -*-
"""Test FINANCE HUB (DE.md mục 10 + luật toàn cục mục 13): gate theo CỜ 'finance'
gateway phát; sổ thu chi JSONL CHỈ-THÊM — sửa = BÚT TOÁN ĐẢO (âm, tham chiếu id
gốc, dòng gốc không đổi một byte); mọi bút toán gắn MỤC TIÊU + kênh TỪ DANH BẠ ĐẾ;
danh mục = rules CSV seed đúng 7 dòng; P&L gộp đúng theo kenh_ma."""

import json
import os
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src import tai_chinh
from src.main import app

THANG_NAY = date.today().strftime("%Y-%m")
HOM_NAY = date.today().isoformat()
VI = "vietcombank"       # A1 — ví VND, khỏi cần tỷ giá cho test cũ
VI_USD = "payoneer"
TY_GIA = 25920.0         # A2 — VCB giá mua chuyển khoản


def _client(apps="to-chuc,hr,finance", ten="ketoan01", level=2):
    return TestClient(app, headers={"X-Remote-User": ten,
                                    "X-Remote-Level": str(level),
                                    "X-Remote-Role": "viewer",
                                    "X-Remote-Dept": "K%E1%BA%BF%20to%C3%A1n",
                                    "X-Remote-Apps": apps})


def _seed_kenh():
    """Danh bạ đế TẠM (env DANH_BA_DB → tmp, conftest lo): 1 ngách + 2 kênh."""
    from nen.common import danh_ba
    conn = danh_ba.ket_noi()
    try:
        ng = danh_ba.them_ngach(conn, "Life In Test")
        k1 = danh_ba.them_kenh(conn, "Outland Test", ng)
        k2 = danh_ba.them_kenh(conn, "Wheel Test", ng)
        return k1, k2
    finally:
        conn.close()


def _seed_ty_gia(gia=TY_GIA, ngay=None):
    tai_chinh.ghi_ty_gia(ngay or HOM_NAY, "USD", gia, "test")


def _seed_muc_tieu():
    tai_chinh.them_muc_tieu("Vận hành chung", 1000)
    return "Vận hành chung"


# ---------- gate ----------

def test_finance_gate_theo_co_gateway():
    assert _client(apps="to-chuc,hr", ten="sep", level=5).get("/finance").status_code == 403
    assert _client().get("/finance").status_code == 200
    assert TestClient(app).get("/finance").status_code == 401


def test_finance_gate_post_cung_bi_chan():
    c = _client(apps="to-chuc")
    assert c.post("/finance/but-toan", data={
        "ngay": HOM_NAY, "danh_muc": "CHI-API", "so_tien": "5",
        "muc_tieu": "x"}).status_code == 403
    assert c.post("/finance/dao", data={"id": "BT-x"}).status_code == 403
    assert c.post("/finance/muc-tieu", data={
        "ten": "x", "ngan_sach": "1"}).status_code == 403


# ---------- danh mục: rules CSV seed 7 dòng ----------

def test_seed_csv_dung_7_dong():
    ds = tai_chinh.doc_danh_muc()
    assert len(ds) == 7
    assert [d["ma"] for d in ds] == ["THU-ADS", "THU-KHAC", "CHI-PROXY", "CHI-TK",
                                     "CHI-API", "CHI-NGOAI", "CHI-LUONG"]
    assert {d["loai"] for d in ds} == {"thu", "chi"}
    assert next(d for d in ds if d["ma"] == "THU-ADS")["loai"] == "thu"


# ---------- sổ chỉ-thêm + bút toán đảo ----------

def test_them_but_toan_ghi_jsonl_chi_them():
    mt = _seed_muc_tieu()
    b1 = tai_chinh.them_but_toan("ketoan01", HOM_NAY, "THU-ADS", 2140, mt, vi=VI)
    b2 = tai_chinh.them_but_toan("ketoan01", HOM_NAY, "CHI-API", 120, mt, vi=VI)
    assert b1["loai"] == "thu" and b2["loai"] == "chi"       # loai suy từ danh mục
    p = Path(os.environ["SO_THU_CHI_DIR"]) / f"{HOM_NAY[:4]}.jsonl"
    dong = p.read_text(encoding="utf-8").splitlines()
    assert len(dong) == 2                                     # append từng dòng
    assert json.loads(dong[0])["id"] == b1["id"]
    assert len(tai_chinh.doc_so()) == 2


def test_dao_but_toan_am_tham_chieu_khong_sua_goc():
    mt = _seed_muc_tieu()
    goc = tai_chinh.them_but_toan("ketoan01", HOM_NAY, "CHI-PROXY", 43, mt, vi=VI)
    dao = tai_chinh.dao_but_toan("sep", goc["id"])
    assert dao["loai"] == "dao" and dao["so_tien"] == -43.0
    assert dao["tham_chieu"] == goc["id"]
    assert dao["danh_muc"] == "CHI-PROXY" and dao["muc_tieu"] == mt
    # dòng GỐC không đổi một byte — sổ chỉ-thêm
    dong = (Path(os.environ["SO_THU_CHI_DIR"]) / f"{HOM_NAY[:4]}.jsonl") \
        .read_text(encoding="utf-8").splitlines()
    assert len(dong) == 2 and json.loads(dong[0]) == goc
    # đảo ĐÚP bị chặn; đảo-của-đảo bị chặn; id lạ bị chặn
    with pytest.raises(ValueError):
        tai_chinh.dao_but_toan("sep", goc["id"])
    with pytest.raises(ValueError):
        tai_chinh.dao_but_toan("sep", dao["id"])
    with pytest.raises(ValueError):
        tai_chinh.dao_but_toan("sep", "BT-khong-co")
    # tổng tháng: 43 - 43 = 0 chi (bút toán đảo trừ đúng bên CHI)
    assert tai_chinh.tong_thang(THANG_NAY) == {"thu": 0.0, "chi": 0.0}


def test_but_toan_validate_chat():
    mt = _seed_muc_tieu()
    with pytest.raises(ValueError):        # danh mục ngoài CSV
        tai_chinh.them_but_toan("kt", HOM_NAY, "CHI-LA", 5, mt, vi=VI)
    with pytest.raises(ValueError):        # mục tiêu chưa có trong sổ
        tai_chinh.them_but_toan("kt", HOM_NAY, "CHI-API", 5, "Mục tiêu lạ", vi=VI)
    with pytest.raises(ValueError):        # kênh không có trong danh bạ đế
        tai_chinh.them_but_toan("kt", HOM_NAY, "CHI-API", 5, mt, kenh_ma="K-LA", vi=VI)
    with pytest.raises(ValueError):        # số tiền âm chỉ dành cho bút toán đảo
        tai_chinh.them_but_toan("kt", HOM_NAY, "CHI-API", -5, mt, vi=VI)
    with pytest.raises(ValueError):        # ngày sai dạng
        tai_chinh.them_but_toan("kt", "16/08/2026", "CHI-API", 5, mt, vi=VI)
    assert tai_chinh.doc_so() == []        # không dòng rác nào lọt vào sổ


# ---------- mục tiêu ----------

def test_muc_tieu_ghi_nguyen_tu_va_tong_hop():
    tai_chinh.them_muc_tieu("Nuôi kênh KR", 600)
    with pytest.raises(ValueError):
        tai_chinh.them_muc_tieu("Nuôi kênh KR", 900)          # trùng tên
    tai_chinh.them_but_toan("kt", HOM_NAY, "CHI-PROXY", 86, "Nuôi kênh KR", vi=VI)
    tai_chinh.them_but_toan("kt", HOM_NAY, "THU-ADS", 40, "Nuôi kênh KR", vi=VI)
    t = tai_chinh.tong_hop_muc_tieu()["Nuôi kênh KR"]
    assert t == {"da_chi": 86.0, "da_thu": 40.0}


# ---------- P&L theo kênh ----------

def test_pnl_gop_dung_theo_kenh():
    k1, k2 = _seed_kenh()
    mt = _seed_muc_tieu()
    tai_chinh.them_but_toan("kt", HOM_NAY, "THU-ADS", 2140, mt, kenh_ma=k1, vi=VI)
    tai_chinh.them_but_toan("kt", HOM_NAY, "CHI-PROXY", 310, mt, kenh_ma=k1, vi=VI)
    tai_chinh.them_but_toan("kt", HOM_NAY, "THU-ADS", 50, mt, kenh_ma=k2, vi=VI)
    chi_chung = tai_chinh.them_but_toan("kt", HOM_NAY, "CHI-API", 120, mt, vi=VI)  # chung hệ
    tai_chinh.dao_but_toan("kt", chi_chung["id"])            # đảo → chung hệ về 0
    pnl = tai_chinh.pnl_theo_kenh(THANG_NAY)
    assert pnl[k1] == {"thu": 2140.0, "chi": 310.0}
    assert pnl[k2] == {"thu": 50.0, "chi": 0.0}
    assert pnl[""] == {"thu": 0.0, "chi": 0.0}
    # tổng tháng danh mục: lũy kế = tháng (sổ mới chỉ có tháng này)
    dm = tai_chinh.tong_hop_danh_muc(THANG_NAY)
    assert dm["THU-ADS"] == {"thang": 2190.0, "luy_ke": 2190.0}
    assert dm["CHI-API"] == {"thang": 0.0, "luy_ke": 0.0}     # 120 - 120 (đảo)


# ---------- route đầu-cuối qua form ----------

def test_route_ledger_dao_va_render():
    k1, _ = _seed_kenh()
    _seed_muc_tieu()
    c = _client()
    r = c.post("/finance/but-toan", data={
        "ngay": HOM_NAY, "danh_muc": "CHI-PROXY", "so_tien": "86",
        "muc_tieu": "Vận hành chung", "kenh_ma": k1, "chung_tu": "hóa đơn",
        "ghi_chu": "gói tháng", "vi": VI}, follow_redirects=False)
    assert r.status_code == 303
    b = c.get(f"/finance?tab=ledger&thang={THANG_NAY}").text
    assert "CHI-PROXY" in b and k1 in b and "Reverse" in b
    bt = tai_chinh.doc_so()[0]
    r2 = c.post("/finance/dao", data={"id": bt["id"], "thang": THANG_NAY},
                follow_redirects=False)
    assert r2.status_code == 303
    assert len(tai_chinh.doc_so()) == 2
    # đảo lần 2 qua route → 422 (sổ chỉ-thêm, không đảo đúp)
    assert c.post("/finance/dao", data={"id": bt["id"]}).status_code == 422
    b2 = c.get(f"/finance?tab=ledger&thang={THANG_NAY}").text
    assert "reversed" in b2 and "Reversal" in b2
    # bút toán sai danh mục qua route → 422, sổ không nhận dòng rác
    assert c.post("/finance/but-toan", data={
        "ngay": HOM_NAY, "danh_muc": "XXX", "so_tien": "5",
        "muc_tieu": "Vận hành chung", "vi": VI}).status_code == 422
    assert len(tai_chinh.doc_so()) == 2


def test_route_categories_va_pnl_render():
    k1, _ = _seed_kenh()
    _seed_muc_tieu()
    tai_chinh.them_but_toan("kt", HOM_NAY, "THU-ADS", 100, "Vận hành chung", kenh_ma=k1, vi=VI)
    c = _client()
    b = c.get(f"/finance?tab=categories&thang={THANG_NAY}").text
    assert "THU-ADS" in b and "CHI-LUONG" in b and "$100" in b
    b2 = c.get(f"/finance?tab=pnl&thang={THANG_NAY}").text
    assert k1 in b2 and "Outland Test" in b2
    b3 = c.get("/finance?tab=goals").text
    assert "Vận hành chung" in b3 and "$1,000" in b3


# ---------- A1: ví tiền (rules/danh_muc_vi.csv) ----------

def test_danh_muc_vi_doc_csv():
    ds = tai_chinh.doc_danh_muc_vi()
    assert [d["ma"] for d in ds] == ["payoneer", "vietcombank", "tien-mat", "adsense-cho"]
    assert next(d for d in ds if d["ma"] == "payoneer")["tien_te"] == "USD"
    assert next(d for d in ds if d["ma"] == "adsense-cho")["loai"] == "phai_thu"


def test_but_toan_bat_buoc_vi_hop_le():
    mt = _seed_muc_tieu()
    with pytest.raises(ValueError):          # thiếu ví — tiền phải biết nằm ở đâu
        tai_chinh.them_but_toan("kt", HOM_NAY, "CHI-API", 5, mt, vi="")
    with pytest.raises(ValueError):          # ví ngoài CSV
        tai_chinh.them_but_toan("kt", HOM_NAY, "CHI-API", 5, mt, vi="vi-la")
    assert tai_chinh.doc_so() == []          # không dòng rác nào lọt vào sổ


def test_so_du_vi_cong_tru_dung_va_dao_ke_thua_vi():
    mt = _seed_muc_tieu()
    _seed_ty_gia()
    tai_chinh.them_but_toan("kt", HOM_NAY, "THU-ADS", 2140, mt, vi="payoneer")
    chi = tai_chinh.them_but_toan("kt", HOM_NAY, "CHI-PROXY", 140, mt, vi="payoneer")
    tai_chinh.them_but_toan("kt", HOM_NAY, "THU-ADS", 500, mt, vi="adsense-cho")
    tai_chinh.them_but_toan("kt", HOM_NAY, "CHI-NGOAI", 4500000, mt, vi="vietcombank")
    dao = tai_chinh.dao_but_toan("sep", chi["id"])
    assert dao["vi"] == "payoneer"           # đảo kế thừa ví của dòng gốc

    sd = tai_chinh.so_du_vi()
    assert sd["payoneer"]["nguyen_te"] == 2140.0     # 2140 − 140 + 140 (đảo)
    assert sd["payoneer"]["tien_te"] == "USD"
    assert sd["payoneer"]["but_toan_cuoi"] == HOM_NAY
    assert sd["adsense-cho"]["nguyen_te"] == 500.0
    assert sd["vietcombank"]["nguyen_te"] == -4500000.0
    assert "tien-mat" not in sd                      # ví chưa phát sinh thì không hiện


def test_tien_kha_dung_bo_qua_vi_phai_thu():
    mt = _seed_muc_tieu()
    _seed_ty_gia()
    tai_chinh.them_but_toan("kt", HOM_NAY, "THU-ADS", 2140, mt, vi="payoneer")
    tai_chinh.them_but_toan("kt", HOM_NAY, "THU-ADS", 2980, mt, vi="adsense-cho")
    tai_chinh.them_but_toan("kt", HOM_NAY, "THU-KHAC", 58400000, mt, vi="vietcombank")
    # AdSense chờ chi trả CHƯA phải tiền của mình → không vào khả dụng
    assert tai_chinh.tien_kha_dung() == {"USD": 2140.0, "VND": 58400000.0}


def test_route_wallets_render_va_form_co_o_vi():
    _seed_muc_tieu()
    _seed_ty_gia()
    tai_chinh.them_but_toan("kt", HOM_NAY, "THU-ADS", 2140, "Vận hành chung", vi=VI_USD)
    c = _client()
    b = c.get("/finance?tab=wallets").text
    assert "Payoneer" in b and "$2,140" in b
    assert "không tính vào tiền khả dụng" in b      # ví phải thu gắn nhãn rõ
    assert 'name="vi"' in c.get("/finance?tab=ledger").text   # form bắt chọn ví


# ---------- A2: hai đồng tiền + sổ tỷ giá ----------

def test_so_ty_gia_chi_them_va_lay_dong_gan_nhat():
    tai_chinh.ghi_ty_gia("2026-08-20", "USD", 25800, "vcb_transfer")
    tai_chinh.ghi_ty_gia("2026-08-26", "USD", 25920, "vcb_transfer")
    dung = tai_chinh.ty_gia_ngay("2026-08-26")
    assert dung["gia"] == 25920.0 and dung["cu"] is False
    # ngày chưa có tỷ giá → lấy dòng GẦN NHẤT TRƯỚC đó, gắn cờ cu (không bịa số mới)
    cu = tai_chinh.ty_gia_ngay("2026-08-28")
    assert cu["gia"] == 25920.0 and cu["cu"] is True and cu["ngay"] == "2026-08-26"
    # trước mọi dòng trong sổ → None, tuyệt đối không suy ngược
    assert tai_chinh.ty_gia_ngay("2026-08-01") is None


def test_but_toan_ngoai_te_can_ty_gia_va_chot_cung():
    mt = _seed_muc_tieu()
    with pytest.raises(ValueError):        # ví USD mà sổ chưa có tỷ giá
        tai_chinh.them_but_toan("kt", HOM_NAY, "CHI-PROXY", 86, mt, vi=VI_USD)
    assert tai_chinh.doc_so() == []
    _seed_ty_gia()
    b = tai_chinh.them_but_toan("kt", HOM_NAY, "CHI-PROXY", 86, mt, vi=VI_USD)
    assert b["tien_te"] == "USD" and b["ty_gia"] == TY_GIA      # tiền tệ suy từ VÍ
    assert b["nguon_ty_gia"] == "test"
    # tỷ giá đổi về sau KHÔNG đụng bút toán đã chốt
    tai_chinh.ghi_ty_gia(HOM_NAY, "USD", 30000, "test")
    assert tai_chinh.doc_so()[0]["ty_gia"] == TY_GIA


def test_but_toan_vnd_khong_can_ty_gia():
    mt = _seed_muc_tieu()
    b = tai_chinh.them_but_toan("kt", HOM_NAY, "CHI-NGOAI", 4500000, mt, vi=VI)
    assert b["tien_te"] == "VND" and b["ty_gia"] == 1.0


def test_tong_hop_quy_ve_vnd():
    mt = _seed_muc_tieu()
    _seed_ty_gia()
    tai_chinh.them_but_toan("kt", HOM_NAY, "THU-ADS", 100, mt, vi=VI_USD)      # 2.592.000 ₫
    tai_chinh.them_but_toan("kt", HOM_NAY, "CHI-NGOAI", 592_000, mt, vi=VI)    # 592.000 ₫
    assert tai_chinh.tong_thang(THANG_NAY) == {"thu": 2_592_000.0, "chi": 592_000.0}
    assert tai_chinh.tong_hop_danh_muc(THANG_NAY)["THU-ADS"]["thang"] == 2_592_000.0
    assert tai_chinh.tong_hop_muc_tieu()[mt]["da_thu"] == 2_592_000.0


def test_so_du_vi_co_quy_vnd():
    mt = _seed_muc_tieu()
    _seed_ty_gia()
    tai_chinh.them_but_toan("kt", HOM_NAY, "THU-ADS", 100, mt, vi=VI_USD)
    tai_chinh.them_but_toan("kt", HOM_NAY, "THU-KHAC", 500_000, mt, vi=VI)
    sd = tai_chinh.so_du_vi()
    assert sd[VI_USD]["nguyen_te"] == 100.0 and sd[VI_USD]["quy_vnd"] == 2_592_000.0
    assert sd[VI]["quy_vnd"] == 500_000.0
    assert tai_chinh.tien_kha_dung() == {"USD": 100.0, "VND": 500_000.0}
    assert tai_chinh.tien_kha_dung_vnd() == 3_092_000.0


def test_lay_ty_gia_online_hong_thi_tra_none(monkeypatch):
    """Mọi nguồn chết → None để form bắt nhập tay. KHÔNG bịa một con số nào."""
    def _no(*a, **k):
        raise OSError("mạng chết")
    monkeypatch.setattr(tai_chinh, "_doc_url", _no)
    assert tai_chinh.lay_ty_gia_online("USD") is None


def test_lay_ty_gia_online_doc_dung_vcb(monkeypatch):
    mau = ('{"Count":1,"Data":[{"currencyCode":"USD","cash":"25890.00",'
           '"transfer":"25920.00","sell":"26300.00"}]}')
    monkeypatch.setattr(tai_chinh, "_doc_url", lambda url, **k: mau)
    kq = tai_chinh.lay_ty_gia_online("USD")
    assert kq == {"gia": 25920.0, "nguon": "vcb_transfer"}   # giá MUA chuyển khoản


def test_route_lay_ty_gia_ghi_so_va_hong_thi_422(monkeypatch):
    c = _client()
    monkeypatch.setattr(tai_chinh, "_doc_url",
                        lambda url, **k: '{"Data":[{"currencyCode":"USD","transfer":"25920.00"}]}')
    r = c.post("/finance/ty-gia/lay", data={"tien_te": "USD"}, follow_redirects=False)
    assert r.status_code == 303
    assert tai_chinh.ty_gia_ngay(HOM_NAY)["gia"] == 25920.0
    b = c.get("/finance?tab=wallets").text
    assert "25920" in b and "vcb_transfer" in b
    # mọi nguồn chết → 422, KHÔNG ghi số bịa
    def _no(*a, **k):
        raise OSError("mạng chết")
    monkeypatch.setattr(tai_chinh, "_doc_url", _no)
    assert c.post("/finance/ty-gia/lay", data={"tien_te": "EUR"}).status_code == 422
    assert tai_chinh.ty_gia_ngay(HOM_NAY, "EUR") is None
