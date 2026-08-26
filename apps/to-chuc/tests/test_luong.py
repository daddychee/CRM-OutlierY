# -*- coding: utf-8 -*-
"""Test D1 (bảng lương) + D6 (cảnh báo đi muộn) — Owner chốt 26/08:

- chấm công CHỈ đo giờ CÓ MẶT (mở CRM); trong phiên không đo;
- đi muộn chỉ CẢNH BÁO, **máy không tự trừ lương** — đường duy nhất ảnh hưởng
  lương là ô "điều chỉnh HR" có lý do bắt buộc;
- ngày làm việc = ngày trong tháng − chủ nhật − lễ (lễ trùng CN không trừ 2 lần).
"""
import json
import os
from pathlib import Path

import pytest

from src import cham_cong, kpi_danh_gia, luong, tai_chinh

KY = "2026-08"
NGUOI = [{"ten": "ngocth", "ho_ten": "Trần Hồng Ngọc", "ma": "NS-005",
          "bo_phan": "Vận hành", "vi_tri": "content"},
         {"ten": "thiennc", "ho_ten": "Nguyễn Chu Thiện", "ma": "NS-006",
          "bo_phan": "Vận hành", "vi_tri": "editor"}]


def _cham(ten, ngay, vao):
    """Ghi thẳng file chấm công (mô phỏng người mở CRM lúc <vao>)."""
    p = Path(os.environ["CHAM_CONG_DIR"]) / f"{ngay[:7]}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    du = json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}
    du.setdefault(ngay, {})[ten] = {"vao": vao, "ra": "17:30:00", "nguon_ra": "dang_xuat"}
    p.write_text(json.dumps(du, ensure_ascii=False), encoding="utf-8")


def _seed_cong():
    for i, ngay in enumerate(["2026-08-03", "2026-08-04", "2026-08-05"]):
        _cham("ngocth", ngay, "08:25:00")
    _cham("thiennc", "2026-08-03", "09:14:00")     # muộn 44'
    _cham("thiennc", "2026-08-04", "08:52:00")     # muộn 22'
    _cham("thiennc", "2026-08-05", "08:35:00")     # trong dung sai 10' → không muộn


# ---------- ngày làm việc ----------

def test_ngay_lam_viec_tru_chu_nhat_va_le():
    assert luong.ngay_lam_viec("2026-08") == 26     # 31 ngày − 5 chủ nhật
    assert luong.ngay_lam_viec("2026-07") == 27
    assert luong.ngay_lam_viec("2026-02") == 24


def test_le_trung_chu_nhat_khong_tru_hai_lan(tmp_path, monkeypatch):
    p = tmp_path / "le.csv"
    # 2026-08-02 là CHỦ NHẬT; 2026-08-03 là thứ hai
    p.write_text("ngay,ten,ghi_chu\n2026-08-02,Lễ trùng CN,\n2026-08-03,Lễ thường,\n",
                 encoding="utf-8")
    monkeypatch.setenv("NGAY_NGHI_LE", str(p))
    assert luong.ngay_lam_viec("2026-08") == 25     # chỉ trừ thêm ngày 03


# ---------- D6: đi muộn ----------

def test_di_muon_chi_dem_lan_mo_crm_dau_ngay():
    _seed_cong()
    dm = luong.di_muon_thang(KY)
    assert dm["thiennc"]["so_buoi"] == 2 and dm["thiennc"]["tong_phut"] == 66
    assert dm["thiennc"]["muon_nhat"] == "09:14:00"
    assert "ngocth" not in dm                       # đi sớm hơn giờ chuẩn
    # ngày KHÔNG mở CRM là VẮNG, không phải muộn
    assert all(c["ngay"] != "2026-08-06" for c in dm["thiennc"]["chi_tiet"])


def test_di_muon_qua_nguong_thi_gan_co():
    for ngay in ["2026-08-03", "2026-08-04", "2026-08-05", "2026-08-06",
                 "2026-08-07", "2026-08-10"]:
        _cham("namnt", ngay, "09:05:00")
    dm = luong.di_muon_thang(KY)
    assert dm["namnt"]["so_buoi"] == 6 and dm["namnt"]["qua_nguong"] is True


# ---------- D1: bảng lương ----------

def test_bang_luong_khong_tu_tru_theo_cham_cong():
    _seed_cong()
    luong.dat_luong_co_ban("hr", "ngocth", 12_000_000)
    luong.dat_luong_co_ban("hr", "thiennc", 15_000_000)
    kpi_danh_gia.them_danh_gia("ngocth", KY, "A", "giữ nhịp tốt", "sep")
    kpi_danh_gia.them_danh_gia("thiennc", KY, "B", "", "sep")
    bang = luong.bang_luong(KY, NGUOI)
    d = {x["ten"]: x for x in bang["dong"]}
    # công 3/26 ngày nhưng KHÔNG bị cắt: lương = cơ bản × hệ số
    assert d["ngocth"]["cong_chot"] == 3
    assert d["ngocth"]["he_so"] == 1.10
    assert d["ngocth"]["thuc_nhan"] == 13_200_000.0
    assert d["thiennc"]["thuc_nhan"] == 15_000_000.0
    assert d["thiennc"]["di_muon"]["so_buoi"] == 2
    assert bang["tong"] == 28_200_000.0


def test_thieu_xep_loai_thi_de_trong_kem_ly_do():
    _seed_cong()
    luong.dat_luong_co_ban("hr", "ngocth", 12_000_000)
    luong.dat_luong_co_ban("hr", "thiennc", 15_000_000)
    kpi_danh_gia.them_danh_gia("ngocth", KY, "A", "", "sep")
    bang = luong.bang_luong(KY, NGUOI)
    d = {x["ten"]: x for x in bang["dong"]}
    assert d["thiennc"]["thuc_nhan"] is None
    assert "xếp loại" in d["thiennc"]["thieu"].lower()
    assert bang["tong"] == 13_200_000.0             # người thiếu KHÔNG vào tổng
    # chấm xếp loại xong thì vào tổng
    kpi_danh_gia.them_danh_gia("thiennc", KY, "B", "", "sep")
    assert luong.bang_luong(KY, NGUOI)["tong"] == 28_200_000.0


def test_dieu_chinh_hr_bat_buoc_ly_do():
    _seed_cong()
    luong.dat_luong_co_ban("hr", "thiennc", 15_000_000)
    kpi_danh_gia.them_danh_gia("thiennc", KY, "B", "", "sep")
    with pytest.raises(ValueError):
        luong.them_dieu_chinh("hr", KY, "thiennc", -500_000, "")
    luong.them_dieu_chinh("hr", KY, "thiennc", -500_000, "nghỉ 2 ngày không phép")
    d = {x["ten"]: x for x in luong.bang_luong(KY, NGUOI)["dong"]}
    assert d["thiennc"]["dieu_chinh"] == -500_000.0
    assert d["thiennc"]["ly_do_dieu_chinh"] == "nghỉ 2 ngày không phép"
    assert d["thiennc"]["thuc_nhan"] == 14_500_000.0


# ---------- duyệt + sinh bút toán ----------

def _seed_de_duyet():
    _seed_cong()
    luong.dat_luong_co_ban("hr", "ngocth", 12_000_000)
    kpi_danh_gia.them_danh_gia("ngocth", KY, "A", "", "sep")
    tai_chinh.them_muc_tieu("Vận hành chung", 100_000_000)


def test_duyet_can_chot_cong_truoc():
    _seed_de_duyet()
    with pytest.raises(ValueError):                  # công kỳ này chưa chốt
        luong.duyet_bang_luong("Bot", KY, NGUOI, "Vận hành chung", "vietcombank")
    cham_cong.chot_ky(KY, "hr")
    kq = luong.duyet_bang_luong("Bot", KY, NGUOI, "Vận hành chung", "vietcombank")
    assert kq["tong"] == 13_200_000.0
    bt = tai_chinh.doc_so()
    assert len(bt) == 1 and bt[0]["danh_muc"] == "CHI-LUONG"
    assert bt[0]["so_tien"] == 13_200_000.0 and bt[0]["nguon"] == "luong"
    assert "NS-005" in bt[0]["ghi_chu"]
    # duyệt lần hai bị chặn — không chi đôi
    with pytest.raises(ValueError):
        luong.duyet_bang_luong("Bot", KY, NGUOI, "Vận hành chung", "vietcombank")


def test_don_gia_ngay_tu_ky_da_duyet():
    _seed_de_duyet()
    cham_cong.chot_ky(KY, "hr")
    luong.duyet_bang_luong("Bot", KY, NGUOI, "Vận hành chung", "vietcombank")
    # 13.200.000 ÷ 3 ngày công = 4.400.000/ngày
    assert luong.don_gia_ngay(KY) == {"ngocth": 4_400_000.0}
    assert luong.don_gia_ngay("2026-07") == {}       # kỳ chưa duyệt → rỗng, không đoán


# ---------- route ----------

def test_route_payroll_render_va_duyet_chi_owner():
    from fastapi.testclient import TestClient
    from src.main import app

    def _c(ten="lanne", level=2):
        return TestClient(app, headers={"X-Remote-User": ten, "X-Remote-Level": str(level),
                                        "X-Remote-Role": "viewer",
                                        "X-Remote-Dept": "K%E1%BA%BF%20to%C3%A1n",
                                        "X-Remote-Apps": "to-chuc,finance"})
    c = _c()
    b = c.get(f"/finance?tab=payroll&ky_luong={KY}").text
    assert "Bảng lương kỳ 2026-08" in b and "ngày làm việc của tháng: 26" in b
    assert "Máy không tự trừ tiền của ai" in b
    # điều chỉnh thiếu lý do → 422 (lý do bắt buộc)
    assert c.post("/finance/luong/dieu-chinh",
                  data={"ten": "thiennc", "ky": KY, "so_tien": "-500000",
                        "ly_do": ""}).status_code == 422
    # duyệt chi: kế toán L2 KHÔNG được, dù có cờ finance
    assert c.post("/finance/luong/duyet",
                  data={"ky": KY, "muc_tieu": "x", "vi": "vietcombank"}).status_code == 403


# ---------- D5: phiếu lương ----------

def test_phieu_luong_chi_co_khi_ky_da_duyet():
    from fastapi.testclient import TestClient
    from src.main import app
    c = TestClient(app, headers={"X-Remote-User": "hr1", "X-Remote-Level": "3",
                                 "X-Remote-Role": "viewer",
                                 "X-Remote-Dept": "HR", "X-Remote-Apps": "to-chuc,hr,finance"})
    _seed_de_duyet()
    # kỳ chưa duyệt → không có phiếu nháp nào trôi ra ngoài
    assert c.get(f"/finance/luong/phieu/{KY}/ngocth").status_code == 404
    cham_cong.chot_ky(KY, "hr")
    luong.duyet_bang_luong("Bot", KY, NGUOI, "Vận hành chung", "vietcombank")
    r = c.get(f"/finance/luong/phieu/{KY}/ngocth")
    assert r.status_code == 200
    b = r.text
    assert "Trần Hồng Ngọc" in b and "NS-005" in b
    assert "13.200.000" in b                       # thực nhận
    assert "3 / 26" in b                           # công / ngày làm việc
    assert "không trừ lương" in b                  # nhãn đi muộn nói rõ
    assert "@media print" in b                     # trang IN được, không cần WeasyPrint
    # người không có trong bảng → 404 lặng lẽ
    assert c.get(f"/finance/luong/phieu/{KY}/khong-co-ai").status_code == 404


def test_tai_ca_ky_dang_zip():
    from fastapi.testclient import TestClient
    from src.main import app
    c = TestClient(app, headers={"X-Remote-User": "hr1", "X-Remote-Level": "3",
                                 "X-Remote-Role": "viewer",
                                 "X-Remote-Dept": "HR", "X-Remote-Apps": "to-chuc,hr,finance"})
    _seed_de_duyet()
    cham_cong.chot_ky(KY, "hr")
    luong.duyet_bang_luong("Bot", KY, NGUOI, "Vận hành chung", "vietcombank")
    r = c.get(f"/finance/luong/phieu.zip?ky={KY}")
    assert r.status_code == 200 and r.content[:2] == b"PK"
