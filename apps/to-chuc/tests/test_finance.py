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
    assert "CHI-PROXY" in b and k1 in b and ">Đảo<" in b
    bt = tai_chinh.doc_so()[0]
    r2 = c.post("/finance/dao", data={"id": bt["id"], "thang": THANG_NAY},
                follow_redirects=False)
    assert r2.status_code == 303
    assert len(tai_chinh.doc_so()) == 2
    # đảo lần 2 qua route → 422 (sổ chỉ-thêm, không đảo đúp)
    assert c.post("/finance/dao", data={"id": bt["id"]}).status_code == 422
    b2 = c.get(f"/finance?tab=ledger&thang={THANG_NAY}").text
    assert "đã đảo" in b2 and ">Đảo</span>" in b2
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
    assert "THU-ADS" in b and "CHI-LUONG" in b and "100 ₫" in b
    b2 = c.get(f"/finance?tab=pnl&thang={THANG_NAY}").text
    assert k1 in b2 and "Outland Test" in b2
    b3 = c.get("/finance?tab=goals").text
    # B4: tab Ngân sách — mục tiêu chưa đặt hạn mức thì nói thẳng, không đoán
    assert "Vận hành chung" in b3 and "chưa đặt" in b3


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
    assert "Payoneer" in b and "$2,140" in b   # ví USD giữ nguyên tệ
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


# ---------- A3: chứng từ đính kèm ----------

def test_luu_chung_tu_kiem_duoi_kich_thuoc_va_ten():
    with pytest.raises(ValueError):                    # đuôi không cho phép
        tai_chinh.luu_chung_tu("BT-x", [("virus.exe", b"x")])
    with pytest.raises(ValueError):                    # quá 10 MB
        tai_chinh.luu_chung_tu("BT-x", [("to.pdf", b"0" * (10 * 1024 * 1024 + 1))])
    with pytest.raises(ValueError):                    # quá 5 tệp
        tai_chinh.luu_chung_tu("BT-x", [(f"a{i}.png", b"x") for i in range(6)])
    # tên tệp bị dọn: không cho leo thư mục, giữ dấu tiếng Việt
    ten = tai_chinh.luu_chung_tu("BT-y", [("../../hóa đơn .png", b"x")])
    assert ten == ["hóa đơn .png"] or ten == ["hóa đơn.png"]
    assert (tai_chinh.thu_muc_chung_tu("BT-y") / ten[0]).is_file()


def test_dao_ke_thua_chung_tu():
    mt = _seed_muc_tieu()
    goc = tai_chinh.them_but_toan("kt", HOM_NAY, "CHI-PROXY", 86, mt, vi=VI,
                                  tep_dinh_kem=["hoa-don.png"])
    dao = tai_chinh.dao_but_toan("sep", goc["id"])
    assert dao["tep_dinh_kem"] == ["hoa-don.png"]      # dấu vết không đứt


def test_route_upload_chung_tu_va_tai_ve():
    _seed_muc_tieu()
    c = _client()
    r = c.post("/finance/but-toan",
               data={"ngay": HOM_NAY, "danh_muc": "CHI-PROXY", "so_tien": "86",
                     "muc_tieu": "Vận hành chung", "vi": VI},
               files=[("tep", ("hoa-don.png", b"PNG-gia-lap", "image/png"))],
               follow_redirects=False)
    assert r.status_code == 303
    bt = tai_chinh.doc_so()[0]
    assert bt["tep_dinh_kem"] == ["hoa-don.png"]
    # tải về được, nội dung đúng
    r2 = c.get(f"/finance/chung-tu/{bt['id']}/hoa-don.png")
    assert r2.status_code == 200 and r2.content == b"PNG-gia-lap"
    # id lạ / tệp lạ → 404 lặng lẽ
    assert c.get("/finance/chung-tu/BT-khong-co/x.png").status_code == 404
    assert c.get(f"/finance/chung-tu/{bt['id']}/../../secret").status_code == 404
    # người không có cờ finance → không lấy được
    assert _client(apps="to-chuc").get(
        f"/finance/chung-tu/{bt['id']}/hoa-don.png").status_code == 403


def test_route_tep_sai_duoi_thi_422_va_so_khong_nhan_dong_rac():
    _seed_muc_tieu()
    c = _client()
    r = c.post("/finance/but-toan",
               data={"ngay": HOM_NAY, "danh_muc": "CHI-PROXY", "so_tien": "86",
                     "muc_tieu": "Vận hành chung", "vi": VI},
               files=[("tep", ("virus.exe", b"MZ", "application/octet-stream"))])
    assert r.status_code == 422
    assert tai_chinh.doc_so() == []                    # validate TRƯỚC khi ghi sổ


# ---------- A4: lọc + xuất ----------

def _seed_vai_but_toan():
    k1, k2 = _seed_kenh()
    _seed_muc_tieu()
    _seed_ty_gia(ngay="2026-08-01")      # tỷ giá phải có TRƯỚC ngày bút toán
    tai_chinh.them_muc_tieu("Nuôi kênh SPACE", 500)
    tai_chinh.them_but_toan("lanne", "2026-08-05", "THU-ADS", 100, "Vận hành chung",
                            kenh_ma=k1, vi=VI_USD, ghi_chu="kỳ 07 AdSense")
    tai_chinh.them_but_toan("lanne", "2026-08-13", "CHI-PROXY", 2_261_800, "Nuôi kênh SPACE",
                            kenh_ma=k2, vi=VI, ghi_chu="proxy 911 gói tháng")
    tai_chinh.them_but_toan("kt2", "2026-09-02", "CHI-API", 500_000, "Vận hành chung", vi=VI)
    return k1, k2


def test_loc_so_theo_tung_tieu_chi():
    k1, k2 = _seed_vai_but_toan()
    assert len(tai_chinh.loc_so()) == 3
    assert len(tai_chinh.loc_so(thang="2026-08")) == 2
    assert len(tai_chinh.loc_so(tu="2026-08-10", den="2026-09-01")) == 1
    assert len(tai_chinh.loc_so(loai="thu")) == 1
    assert len(tai_chinh.loc_so(vi=VI)) == 2
    assert len(tai_chinh.loc_so(kenh=k1)) == 1
    assert len(tai_chinh.loc_so(muc_tieu="Nuôi kênh SPACE")) == 1
    assert len(tai_chinh.loc_so(danh_muc="CHI-API")) == 1
    assert len(tai_chinh.loc_so(nguoi="lanne")) == 2
    assert len(tai_chinh.loc_so(q="proxy 911")) == 1        # tìm trong ghi chú
    assert len(tai_chinh.loc_so(q="PROXY")) == 1            # không phân biệt hoa thường
    # kết hợp nhiều điều kiện
    assert len(tai_chinh.loc_so(thang="2026-08", loai="chi", vi=VI)) == 1


def test_xuat_csv_du_cot_va_quy_vnd():
    _seed_vai_but_toan()
    csv_txt = tai_chinh.xuat_csv(tai_chinh.loc_so(thang="2026-08"))
    dong = csv_txt.strip().splitlines()
    assert dong[0].startswith("id,ngay,loai,danh_muc,so_tien,tien_te,ty_gia,quy_vnd")
    assert len(dong) == 3                                    # 1 header + 2 bút toán
    assert "2592000" in csv_txt                              # 100 USD × 25920


def test_xuat_beancount_dung_khuon():
    _seed_vai_but_toan()
    txt = tai_chinh.xuat_beancount(tai_chinh.loc_so(thang="2026-08"))
    assert 'option "operating_currency" "VND"' in txt
    assert "1900-01-01 open Assets:PAYONEER" in txt
    assert "1900-01-01 open Income:THU-ADS" in txt
    # dòng thu: tài sản DƯƠNG, income ÂM (đúng quy ước bút toán kép)
    assert '2026-08-05 * "kỳ 07 AdSense"' in txt
    assert "Assets:PAYONEER      100.00 USD @ 25920.00 VND" in txt
    assert "Income:THU-ADS      -100.00 USD @ 25920.00 VND" in txt
    # dòng chi VND: không có tỷ giá bám đuôi
    assert "Expenses:CHI-PROXY      2261800.00 VND" in txt
    assert "kenh:" in txt and "muc-tieu:" in txt


def test_route_xuat_va_loc_qua_url():
    k1, _ = _seed_vai_but_toan()
    c = _client()
    r = c.get("/finance/xuat.csv?thang=2026-08")
    assert r.status_code == 200 and "text/csv" in r.headers["content-type"]
    assert r.text.startswith("\ufeff") or r.content.startswith(b"\xef\xbb\xbf")  # BOM cho Excel
    r2 = c.get("/finance/xuat.beancount?thang=2026-08")
    assert r2.status_code == 200 and "Assets:PAYONEER" in r2.text
    # lọc trên trang: chỉ còn bút toán của kênh k1
    b = c.get(f"/finance?tab=ledger&thang=2026-08&kenh={k1}").text
    assert "kỳ 07 AdSense" in b and "proxy 911" not in b
    # lọc theo chữ trong ghi chú
    b2 = c.get("/finance?tab=ledger&thang=2026-08&q=proxy").text
    assert "proxy 911" in b2 and "kỳ 07 AdSense" not in b2


# ---------- D2: dịch vụ trả phí (gộp C1 khoản định kỳ) ----------

def _seed_dich_vu(**kw):
    d = dict(ten="Proxy 911", nha_cung_cap="911proxy.com", nhom="proxy",
             phi=86, tien_te="USD", chu_ky="thang", ngay_gia_han="2026-09-13",
             tu_dong_gia_han=True, trang_thai="dang_dung", danh_muc="CHI-PROXY",
             vi=VI_USD, kenh_ma="", vault_id="3f9a1c22", ghi_chu="")
    d.update(kw)
    return tai_chinh.luu_dich_vu("lanne", **d)


def test_dich_vu_validate_va_ghi_nguyen_tu():
    dv = _seed_dich_vu()
    assert dv["id"].startswith("DV-") and dv["ten"] == "Proxy 911"
    assert len(tai_chinh.doc_dich_vu()) == 1
    with pytest.raises(ValueError):
        _seed_dich_vu(nhom="nhom-la")
    with pytest.raises(ValueError):
        _seed_dich_vu(chu_ky="tuan")
    with pytest.raises(ValueError):
        _seed_dich_vu(trang_thai="lung-tung")
    with pytest.raises(ValueError):
        _seed_dich_vu(danh_muc="CHI-KHONG-CO")      # mã khoản phải có trong CSV
    with pytest.raises(ValueError):
        _seed_dich_vu(vi="vi-la")
    with pytest.raises(ValueError):
        _seed_dich_vu(ten="")
    assert len(tai_chinh.doc_dich_vu()) == 1        # không bản ghi hỏng nào lọt vào


def test_dich_vu_khong_bao_gio_co_truong_mat_khau():
    """Vault giữ bí mật, Finance giữ lịch — hai kho, hai vai."""
    dv = _seed_dich_vu()
    assert "mat_khau" not in dv and "tai_khoan" not in dv
    assert dv["vault_id"] == "3f9a1c22"             # chỉ id trỏ sang két


def test_dich_vu_sua_giu_id():
    dv = _seed_dich_vu()
    sua = tai_chinh.luu_dich_vu("lanne", id=dv["id"], ten="Proxy 911",
                                nha_cung_cap="911proxy.com", nhom="proxy", phi=99,
                                tien_te="USD", chu_ky="thang",
                                ngay_gia_han="2026-09-13", tu_dong_gia_han=True,
                                trang_thai="sap_bo", danh_muc="CHI-PROXY", vi=VI_USD)
    assert sua["id"] == dv["id"] and sua["phi"] == 99.0
    assert sua["trang_thai"] == "sap_bo" and len(tai_chinh.doc_dich_vu()) == 1


def test_den_han_va_qua_han():
    _seed_dich_vu(ten="Sắp tới", ngay_gia_han="2026-09-01")
    _seed_dich_vu(ten="Còn xa", ngay_gia_han="2026-12-01")
    _seed_dich_vu(ten="Quá hạn", ngay_gia_han="2026-08-20")
    _seed_dich_vu(ten="Đã hủy", ngay_gia_han="2026-09-01", trang_thai="da_huy")
    ds = tai_chinh.den_han("2026-08-26", trong_ngay=14)
    ten = [d["ten"] for d in ds]
    assert "Sắp tới" in ten and "Quá hạn" in ten      # quá hạn vẫn phải hiện
    assert "Còn xa" not in ten and "Đã hủy" not in ten
    assert next(d for d in ds if d["ten"] == "Quá hạn")["qua_han"] is True


def test_chi_phi_thue_bao_thang_quy_ve_thang():
    _seed_ty_gia()
    _seed_dich_vu(ten="Tháng USD", phi=100, tien_te="USD", chu_ky="thang")
    _seed_dich_vu(ten="Năm VND", phi=12_000_000, tien_te="VND", chu_ky="nam", vi=VI)
    _seed_dich_vu(ten="Quý VND", phi=3_000_000, tien_te="VND", chu_ky="quy", vi=VI)
    _seed_dich_vu(ten="Một lần", phi=9_000_000, tien_te="VND", chu_ky="mot_lan", vi=VI)
    _seed_dich_vu(ten="Đã hủy", phi=5_000_000, tien_te="VND", chu_ky="thang",
                  vi=VI, trang_thai="da_huy")
    # 100 USD × 25920 + 12tr/12 + 3tr/3 = 2.592.000 + 1.000.000 + 1.000.000
    assert tai_chinh.chi_phi_thue_bao_thang() == 4_592_000.0
    _seed_dich_vu(ten="Sắp bỏ", phi=1_000_000, tien_te="VND", chu_ky="thang",
                  vi=VI, trang_thai="sap_bo")
    assert tai_chinh.tiet_kiem_neu_bo() == 1_000_000.0


def test_day_gia_han_sau_khi_ghi():
    dv = _seed_dich_vu(ngay_gia_han="2026-09-13", chu_ky="thang")
    moi = tai_chinh.day_gia_han(dv["id"])
    assert moi["ngay_gia_han"] == "2026-10-13"
    nam = _seed_dich_vu(ten="Gói năm", chu_ky="nam", ngay_gia_han="2027-02-02")
    assert tai_chinh.day_gia_han(nam["id"])["ngay_gia_han"] == "2028-02-02"


def test_route_thue_bao_them_va_ghi_but_toan():
    _seed_muc_tieu()
    _seed_ty_gia()
    c = _client()
    r = c.post("/finance/dich-vu", data={
        "ten": "Z.ai quota", "nha_cung_cap": "api.z.ai", "nhom": "api",
        "phi": "200", "tien_te": "USD", "chu_ky": "thang",
        "ngay_gia_han": "2026-09-01", "tu_dong_gia_han": "1",
        "trang_thai": "dang_dung", "danh_muc": "CHI-API", "vi": VI_USD},
        follow_redirects=False)
    assert r.status_code == 303
    dv = tai_chinh.doc_dich_vu()[0]
    b = c.get("/finance?tab=subs").text
    assert "Z.ai quota" in b and "api.z.ai" in b
    # ghi bút toán từ hàng chờ: sinh bút toán ĐÚNG dịch vụ + đẩy hạn sang kỳ sau
    r2 = c.post("/finance/dich-vu/ghi", data={"id": dv["id"], "muc_tieu": "Vận hành chung"},
                follow_redirects=False)
    assert r2.status_code == 303
    bt = tai_chinh.doc_so()[0]
    assert bt["danh_muc"] == "CHI-API" and bt["so_tien"] == 200.0
    assert bt["nguon"] == "thue_bao" and bt["vi"] == VI_USD
    assert tai_chinh.doc_dich_vu()[0]["ngay_gia_han"] == "2026-10-01"


# ---------- UI-final: dashboard + tab ngách ----------

def test_route_dashboard_va_bieu_do():
    _seed_vai_but_toan()
    c = _client()
    b = c.get("/finance?tab=dashboard&thang=2026-08").text
    assert "Lịch tài chính" in b and "10…" in b or "2026-09-10" in b
    assert "frappe-charts.min.umd.js" in b        # vendor, KHÔNG CDN
    assert "bd-dong-tien" in b
    # tệp vendor phục vụ được
    assert c.get("/to-chuc-static/vendor/frappe-charts.min.umd.js").status_code == 200


def test_dashboard_kho_rong_thi_khong_ve_truc_rong():
    c = _client()
    b = c.get("/finance?tab=dashboard").text
    assert "Chưa có bút toán nào" in b and "bd-dong-tien" not in b


def test_route_tab_ngach_render():
    _seed_vai_but_toan()
    b = _client().get("/finance?tab=ngach&ky_luong=2026-08").text
    assert "Chi phí sản xuất theo ngách" in b


# ---------- B3: mức đốt & thời gian còn sống ----------

def test_muc_dot_chua_co_du_lieu_thi_khong_bia():
    m = tai_chinh.muc_dot(THANG_NAY)
    assert m["chi_tb"] == 0 and m["thu_tb"] == 0
    assert m["dot_rong"] is None and m["so_thang_con"] is None


def test_muc_dot_tinh_tu_3_thang_gan_nhat():
    _seed_muc_tieu()
    for t, thu, chi in [("2026-06", 30_000_000, 60_000_000),
                        ("2026-07", 30_000_000, 60_000_000),
                        ("2026-08", 30_000_000, 60_000_000)]:
        tai_chinh.them_but_toan("kt", f"{t}-10", "THU-ADS", thu, "Vận hành chung", vi=VI)
        tai_chinh.them_but_toan("kt", f"{t}-11", "CHI-API", chi, "Vận hành chung", vi=VI)
    m = tai_chinh.muc_dot("2026-08")
    assert m["chi_tb"] == 60_000_000 and m["thu_tb"] == 30_000_000
    assert m["dot_rong"] == 30_000_000
    # số dư ví: 3 tháng thu 90tr, chi 180tr → âm; runway âm thì báo None
    assert m["so_thang_con"] is None and m["het_tien"] is True


def test_thu_lon_hon_chi_thi_khong_co_runway():
    _seed_muc_tieu()
    tai_chinh.them_but_toan("kt", "2026-08-10", "THU-ADS", 90_000_000, "Vận hành chung", vi=VI)
    tai_chinh.them_but_toan("kt", "2026-08-11", "CHI-API", 10_000_000, "Vận hành chung", vi=VI)
    m = tai_chinh.muc_dot("2026-08")
    assert m["dot_rong"] is None and m["so_thang_con"] is None
    assert m["duong"] is True          # đang lãi — không có khái niệm "còn sống mấy tháng"


def test_route_doi_trang_thai_dich_vu():
    dv = _seed_dich_vu()
    c = _client()
    r = c.post("/finance/dich-vu/trang-thai",
               data={"id": dv["id"], "trang_thai": "sap_bo"}, follow_redirects=False)
    assert r.status_code == 303
    assert tai_chinh.doc_dich_vu()[0]["trang_thai"] == "sap_bo"
    assert len(tai_chinh.doc_dich_vu()) == 1          # sửa tại chỗ, không đẻ bản mới
    assert c.post("/finance/dich-vu/trang-thai",
                  data={"id": "DV-khong-co", "trang_thai": "sap_bo"}).status_code == 404


def test_ledger_co_modal_va_thanh_loc_mot_hang():
    _seed_muc_tieu()
    b = _client().get("/finance?tab=ledger").text
    assert 'id="mb-bt"' in b and "moModal(1)" in b     # bút toán mới là MODAL
    assert 'id="bt-quy-vnd"' in b                      # ô Quy VND tự tính
    assert "Kéo ảnh hóa đơn vào đây" in b
    assert "Loại: tất cả" in b and "Ví: tất cả" in b    # nhãn nằm trong dropdown


# ---------- B1: phân bổ chi phí chung xuống kênh ----------

def _seed_pnl_co_chung_he():
    k1, k2 = _seed_kenh()
    _seed_muc_tieu()
    tai_chinh.them_but_toan("kt", HOM_NAY, "THU-ADS", 60_000_000, "Vận hành chung",
                            kenh_ma=k1, vi=VI)
    tai_chinh.them_but_toan("kt", HOM_NAY, "THU-ADS", 20_000_000, "Vận hành chung",
                            kenh_ma=k2, vi=VI)
    tai_chinh.them_but_toan("kt", HOM_NAY, "CHI-PROXY", 5_000_000, "Vận hành chung",
                            kenh_ma=k1, vi=VI)
    # chi CHUNG HỆ — thứ mà bản v1 để nguyên một dòng, làm mọi kênh trông có lãi
    tai_chinh.them_but_toan("kt", HOM_NAY, "CHI-API", 8_000_000, "Vận hành chung", vi=VI)
    return k1, k2


def test_phan_bo_theo_doanh_thu():
    k1, k2 = _seed_pnl_co_chung_he()
    kq = tai_chinh.pnl_phan_bo(THANG_NAY, "doanh_thu")
    d = {x["kenh_ma"]: x for x in kq["dong"]}
    # 8tr chia theo tỷ lệ thu 60:20 → 6tr : 2tr
    assert d[k1]["phan_bo"] == 6_000_000.0 and d[k2]["phan_bo"] == 2_000_000.0
    assert d[k1]["lai_lo_sau"] == 60_000_000 - 5_000_000 - 6_000_000
    assert kq["chung_he_con_lai"] == 0.0          # đã rải hết, không còn dòng lận


def test_phan_bo_chia_deu_va_khong_phan_bo():
    k1, k2 = _seed_pnl_co_chung_he()
    d = {x["kenh_ma"]: x for x in tai_chinh.pnl_phan_bo(THANG_NAY, "chia_deu")["dong"]}
    assert d[k1]["phan_bo"] == d[k2]["phan_bo"] == 4_000_000.0
    kq = tai_chinh.pnl_phan_bo(THANG_NAY, "khong")
    assert all(x["phan_bo"] == 0 for x in kq["dong"])
    assert kq["chung_he_con_lai"] == 8_000_000.0   # giữ nguyên hàng chung hệ


def test_phan_bo_khong_sinh_but_toan():
    """Phân bổ tính LÚC ĐỌC — sổ gốc không được đụng một dòng."""
    _seed_pnl_co_chung_he()
    truoc = len(tai_chinh.doc_so())
    tai_chinh.pnl_phan_bo(THANG_NAY, "doanh_thu")
    tai_chinh.pnl_phan_bo(THANG_NAY, "chia_deu")
    assert len(tai_chinh.doc_so()) == truoc


def test_khong_co_kenh_nao_thi_khong_chia():
    _seed_muc_tieu()
    tai_chinh.them_but_toan("kt", HOM_NAY, "CHI-API", 8_000_000, "Vận hành chung", vi=VI)
    kq = tai_chinh.pnl_phan_bo(THANG_NAY, "doanh_thu")
    assert kq["dong"] == [] and kq["chung_he_con_lai"] == 8_000_000.0


# ---------- B4: ngân sách theo kỳ + chuyển tiếp ----------

def test_ngan_sach_ky_va_chuyen_tiep():
    tai_chinh.them_muc_tieu("Nuôi kênh SPACE", 0)
    tai_chinh.dat_han_muc("Bot", "Nuôi kênh SPACE", 30_000_000, chuyen_tiep=True)
    tai_chinh.them_but_toan("kt", "2026-07-05", "CHI-API", 22_000_000,
                            "Nuôi kênh SPACE", vi=VI)
    b7 = {x["muc_tieu"]: x for x in tai_chinh.ngan_sach_ky("2026-07")["dong"]}
    assert b7["Nuôi kênh SPACE"]["han_muc"] == 30_000_000
    assert b7["Nuôi kênh SPACE"]["da_chi"] == 22_000_000
    assert b7["Nuôi kênh SPACE"]["ti_le"] == 73
    # tháng sau: phần chưa tiêu 8tr chuyển tiếp
    b8 = {x["muc_tieu"]: x for x in tai_chinh.ngan_sach_ky("2026-08")["dong"]}
    assert b8["Nuôi kênh SPACE"]["chuyen_tiep"] == 8_000_000


def test_vuot_han_muc_chi_canh_bao_khong_chan():
    tai_chinh.them_muc_tieu("Hồi sinh OLD", 0)
    tai_chinh.dat_han_muc("Bot", "Hồi sinh OLD", 12_000_000)
    b = tai_chinh.them_but_toan("kt", "2026-08-05", "CHI-NGOAI", 13_200_000,
                                "Hồi sinh OLD", vi=VI)
    assert b["id"]                                   # KHÔNG chặn — tiền đã tiêu thì sổ phải ghi
    d = {x["muc_tieu"]: x for x in tai_chinh.ngan_sach_ky("2026-08")["dong"]}
    assert d["Hồi sinh OLD"]["ti_le"] == 110 and d["Hồi sinh OLD"]["vuot"] is True
    assert d["Hồi sinh OLD"]["con_lai"] == -1_200_000


def test_muc_tieu_chua_dat_han_muc_thi_khong_doan():
    tai_chinh.them_muc_tieu("Chưa đặt", 0)
    d = {x["muc_tieu"]: x for x in tai_chinh.ngan_sach_ky(THANG_NAY)["dong"]}
    assert d["Chưa đặt"]["han_muc"] is None and d["Chưa đặt"]["ti_le"] is None


# ---------- C5: chốt kỳ + đối chiếu số dư ví ----------

def test_chot_ky_khoa_khi_vi_lech():
    _seed_muc_tieu()
    tai_chinh.them_but_toan("kt", "2026-08-05", "THU-KHAC", 10_000_000,
                            "Vận hành chung", vi=VI)
    # khai số dư thật LỆCH so với sổ → không cho chốt
    with pytest.raises(ValueError):
        tai_chinh.chot_ky_tien("Bot", "2026-08", {VI: 9_800_000})
    assert tai_chinh.doc_chot_ky("2026-08") is None
    # khớp thì chốt được, và chốt hai lần bị chặn
    ban = tai_chinh.chot_ky_tien("Bot", "2026-08", {VI: 10_000_000})
    assert ban["ky"] == "2026-08" and ban["nguoi_chot"] == "Bot"
    with pytest.raises(ValueError):
        tai_chinh.chot_ky_tien("Bot", "2026-08", {VI: 10_000_000})


def test_doi_chieu_vi_chi_ra_lech():
    _seed_muc_tieu()
    tai_chinh.them_but_toan("kt", "2026-08-05", "THU-KHAC", 5_000_000,
                            "Vận hành chung", vi=VI)
    dc = tai_chinh.doi_chieu_vi("2026-08", {VI: 4_800_000})
    d = {x["vi"]: x for x in dc}
    assert d[VI]["so_so"] == 5_000_000 and d[VI]["khai"] == 4_800_000
    assert d[VI]["lech"] == -200_000 and d[VI]["khop"] is False


def test_but_toan_vao_ky_da_chot_bi_danh_dau_dieu_chinh():
    _seed_muc_tieu()
    tai_chinh.them_but_toan("kt", "2026-08-05", "THU-KHAC", 1_000_000,
                            "Vận hành chung", vi=VI)
    tai_chinh.chot_ky_tien("Bot", "2026-08", {VI: 1_000_000})
    # vẫn GHI ĐƯỢC (không sửa lịch sử, không giấu chênh lệch) nhưng có dấu
    b = tai_chinh.them_but_toan("kt", "2026-08-20", "CHI-API", 500_000,
                                "Vận hành chung", vi=VI)
    assert b["dieu_chinh_ky_truoc"] is True
    b2 = tai_chinh.them_but_toan("kt", "2026-09-02", "CHI-API", 500_000,
                                 "Vận hành chung", vi=VI)
    assert b2["dieu_chinh_ky_truoc"] is False


def test_co_cau_chi_chi_lay_ben_CHI():
    _seed_muc_tieu()
    tai_chinh.them_but_toan("kt", HOM_NAY, "THU-ADS", 60_000_000, "Vận hành chung", vi=VI)
    tai_chinh.them_but_toan("kt", HOM_NAY, "CHI-API", 20_000_000, "Vận hành chung", vi=VI)
    bd = tai_chinh.du_lieu_bieu_do(THANG_NAY)
    assert "THU-ADS" not in bd["co_cau_nhan"]     # biểu đồ CƠ CẤU CHI, không phải mọi khoản
    assert bd["co_cau_nhan"] == ["CHI-API"]


def test_so_du_vi_khong_am_khi_chi_tu_vi_khac():
    """Chi từ ví VND không được làm ví đó âm nếu tiền vào cũng ở ví đó — nhưng
    nếu CHỈ có chi thì âm là ĐÚNG (sổ phản ánh thật). Ghim để không ai 'sửa' cho đẹp."""
    _seed_muc_tieu()
    tai_chinh.them_but_toan("kt", HOM_NAY, "CHI-LUONG", 27_700_000, "Vận hành chung", vi=VI)
    assert tai_chinh.so_du_vi()[VI]["nguyen_te"] == -27_700_000.0


def test_muc_dot_khong_lay_thang_hien_tai_lam_chuan_khi_thieu_ky():
    """3 tháng gần nhất phải là 3 kỳ CÓ THẬT; kỳ chưa phát sinh không kéo trung
    bình xuống thành số vô nghĩa."""
    _seed_muc_tieu()
    tai_chinh.them_but_toan("kt", "2026-08-10", "CHI-API", 30_000_000, "Vận hành chung", vi=VI)
    m = tai_chinh.muc_dot("2026-08")
    assert m["chi_tb"] == 10_000_000        # 30tr ÷ 3 tháng — trung bình đúng nghĩa
    assert m["so_ky_co_phat_sinh"] == 1     # nhưng phải nói rõ chỉ 1 kỳ có số


def test_trang_finance_go_tran_900px_cua_base():
    """base.html khóa .noi-dung{max-width:900px} cho mọi trang con; Finance là
    bảng nhiều cột nên phải gỡ trần — ghim để không ai vô tình bỏ."""
    b = _client().get("/finance?tab=ledger").text
    assert ".noi-dung{max-width:none" in b.replace(" ", "")
