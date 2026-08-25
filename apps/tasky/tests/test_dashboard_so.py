# -*- coding: utf-8 -*-
"""B10.6 — số liệu dashboard (lõi, chưa đụng UI)."""
import pytest

from src import dashboard as db
from src import muc_tieu as mt
from src import tuan

MGR = {"ten": "huytq", "level": 4, "bo_phan": "Vận hành"}
MGR_KD = {"ten": "ngocpb", "level": 4, "bo_phan": "Kinh doanh"}
NV = {"ten": "hant", "level": 2, "bo_phan": "Vận hành"}
NV_KD = {"ten": "yenvh", "level": 2, "bo_phan": "Kinh doanh"}
OWNER = {"ten": "bot", "level": 5, "bo_phan": "Ban quản trị"}

SO = [{"ten": "huytq", "level": 4, "bo_phan": "Vận hành", "ho_ten": "Quốc Huy"},
      {"ten": "hant", "level": 2, "bo_phan": "Vận hành", "ho_ten": "Thu Hà"},
      {"ten": "ngocpb", "level": 4, "bo_phan": "Kinh doanh", "ho_ten": "Bảo Ngọc"},
      {"ten": "yenvh", "level": 2, "bo_phan": "Kinh doanh", "ho_ten": "Hải Yến"}]


def _xong(ma, nguoi=NV, giao=MGR, ten="Việc A", mt_id=""):
    v = tuan.them_viec_giao(ma, giao, nguoi, ten, "x", muc_tieu_id=mt_id)
    tuan.nhan_viec(ma, v["id"], nguoi)
    tuan.bao_xong(ma, v["id"], nguoi)
    tuan.xac_nhan_viec(ma, v["id"], giao)
    return v


# ---------- xu hướng ----------

def test_xu_huong_tra_du_so_tuan_va_nhan_dung():
    xh = db.xu_huong(SO, so_tuan=4)
    assert len(xh) == 4
    assert xh[-1]["ma"] == tuan.ma_tuan()          # tuần cuối là tuần này
    assert xh[0]["ma"] == tuan.tuan_lien_ke(tuan.ma_tuan(), -3)


def test_tuan_chua_ai_lam_gi_thi_ti_le_None_khong_phai_0():
    """UI vẽ đứt đoạn ở đó — nối liền 0% là bịa một cú tụt không có thật."""
    xh = db.xu_huong(SO, so_tuan=3)
    assert all(x["ti_le"] is None for x in xh)


def test_xu_huong_dem_dung_ti_le_tuan_co_viec():
    ma = tuan.ma_tuan()
    _xong(ma, ten="Xong")
    tuan.them_viec_giao(ma, MGR, NV, "Chưa xong", "x")
    xh = db.xu_huong(SO, so_tuan=2)
    assert xh[-1]["ti_le"] == 50 and xh[0]["ti_le"] is None


# ---------- theo bộ phận ----------

def test_gom_theo_bo_phan_khong_boc_tung_nguoi():
    ma = tuan.ma_tuan()
    _xong(ma, nguoi=NV, giao=MGR)
    tuan.them_viec_giao(ma, MGR_KD, NV_KD, "Việc KD", "x")
    bp = db.theo_bo_phan(ma, SO)
    ten = [b["bo_phan"] for b in bp]
    assert ten == ["Kinh doanh", "Vận hành"]
    kd = next(b for b in bp if b["bo_phan"] == "Kinh doanh")
    vh = next(b for b in bp if b["bo_phan"] == "Vận hành")
    assert kd["ti_le"] == 0 and vh["ti_le"] == 100
    assert vh["so_nguoi"] == 2 and vh["chua_co_viec"] == 1


def test_bo_phan_chua_ai_co_viec_thi_ti_le_None():
    bp = db.theo_bo_phan(tuan.ma_tuan(), SO)
    assert all(b["ti_le"] is None for b in bp)


# ---------- Goal ----------

def test_tong_hop_goal_tach_cho_chot_khoi_dang_chay():
    """Xong hết việc mà chưa kết luận là 'chờ chốt' — KHÔNG phải 'đã đạt'."""
    ma = tuan.ma_tuan()
    a = mt.tao(MGR, "Goal xong việc", "kết quả A")
    _xong(ma, ten="Việc của A", mt_id=a["id"])
    mt.tao(MGR, "Goal đang chạy", "kết quả B")
    d = mt.tao(MGR, "Goal đã đạt", "kết quả C")
    mt.chot_ket_qua(d["id"], MGR, mt.DAT)

    g = db.tong_hop_goal()
    assert g["cho_chot"] == 1 and g["dang_chay"] == 1 and g["dat"] == 1 and g["tong"] == 3


def test_dem_goal_tre_han():
    from datetime import date, timedelta
    mt.tao(MGR, "Trễ", "x", han=(date.today() - timedelta(days=2)).isoformat())
    mt.tao(MGR, "Còn hạn", "x", han=(date.today() + timedelta(days=5)).isoformat())
    assert db.tong_hop_goal()["tre_han"] == 1


def test_goal_kem_tien_do_dua_viec_can_de_y_len_dau():
    ma = tuan.ma_tuan()
    yen = mt.tao(MGR, "Goal yên", "x")
    _xong(ma, ten="Việc yên", mt_id=yen["id"])
    loan = mt.tao(MGR, "Goal có vấn đề", "x")
    tuan.them_viec_muc_tieu(ma, MGR, "Chưa giao ai", "x", loan["id"])
    ds = db.goal_kem_tien_do(mt.doc_tat_ca())
    assert ds[0]["tieu_de"] == "Goal có vấn đề"


# ---------- nhiệm vụ đã giao (khối riêng của Owner) ----------

def test_nhiem_vu_giao_cho_manager_ma_chua_dung_goal():
    ma = tuan.ma_tuan()
    tuan.them_viec_giao(ma, OWNER, MGR, "Nâng chất lượng giữ chân", "Định hướng")
    ds = db.nhiem_vu_da_giao(OWNER)
    assert len(ds) == 1 and ds[0]["goal"] is None and ds[0]["tien_do"] is None


def test_nhiem_vu_da_dung_goal_thi_kem_tien_do():
    ma = tuan.ma_tuan()
    nv = tuan.them_viec_giao(ma, OWNER, MGR, "Nhiệm vụ A", "Định hướng")
    g = mt.tao(MGR, "Goal từ nhiệm vụ A", "kết quả", tu_nhiem_vu=nv["id"])
    _xong(ma, ten="Việc con", mt_id=g["id"])
    ds = db.nhiem_vu_da_giao(OWNER)
    assert ds[0]["goal"]["id"] == g["id"] and ds[0]["tien_do"]["phan_tram"] == 100


def test_viec_thuong_da_nghiem_thu_khong_ke_la_nhiem_vu_treo():
    """Owner giao việc vặt rồi nghiệm thu xong thì không nằm mãi trong bảng."""
    ma = tuan.ma_tuan()
    _xong(ma, nguoi=MGR, giao=OWNER, ten="Việc vặt")
    assert db.nhiem_vu_da_giao(OWNER) == []


def test_chi_hien_nhiem_vu_CUA_MINH_giao():
    ma = tuan.ma_tuan()
    tuan.them_viec_giao(ma, OWNER, MGR, "Của Owner", "x")
    tuan.them_viec_giao(ma, MGR, NV, "Của Manager", "x")
    assert [x["viec"]["tieu_de"] for x in db.nhiem_vu_da_giao(OWNER)] == ["Của Owner"]


# ---------- trang dashboard ----------

from fastapi.testclient import TestClient          # noqa: E402
from src import main                               # noqa: E402

_c = TestClient(main.app)
H_MGR = {"X-Remote-User": "huytq", "X-Remote-Level": "4", "X-Remote-Dept": "V%E1%BA%ADn%20h%C3%A0nh",
         "X-Remote-Actions": "vao,giao_viec,xac_nhan_ket_qua,bao_cao_bo_phan,bao_cao_cong_ty",
         "X-Remote-Apps": "tasky"}
H_LEADER = {"X-Remote-User": "vh3", "X-Remote-Level": "3", "X-Remote-Dept": "V%E1%BA%ADn%20h%C3%A0nh",
            "X-Remote-Actions": "vao,giao_viec,xac_nhan_ket_qua,bao_cao_bo_phan",
            "X-Remote-Apps": "tasky"}


@pytest.fixture()
def _so(monkeypatch):
    monkeypatch.setattr(main.nhan_su, "ds_nguoi", lambda: (list(SO), ""))


def test_dashboard_nap_vendor_bieu_do(_so):
    r = _c.get("/bao-cao-tuan", headers=H_MGR)
    assert r.status_code == 200
    assert "/tasky-static/vendor/frappe-charts.min.umd.js" in r.text


def test_manager_mac_dinh_thay_toan_cong_ty(_so):
    """Giữ luật 24/08 — không đổi mặc định khi làm dashboard."""
    ma = tuan.ma_tuan()
    _xong(ma, nguoi=NV_KD, giao=MGR_KD, ten="Việc KD")
    r = _c.get("/bao-cao-tuan", headers=H_MGR)
    assert "Bảo Ngọc" in r.text and "Theo bộ phận" in r.text


def test_chuyen_ve_bo_phan_minh(_so):
    ma = tuan.ma_tuan()
    _xong(ma, nguoi=NV_KD, giao=MGR_KD, ten="Việc KD")
    r = _c.get("/bao-cao-tuan?pham_vi=bo-phan", headers=H_MGR)
    assert "Hải Yến" not in r.text and "Theo bộ phận" not in r.text


def test_leader_khong_co_nut_toan_cong_ty(_so):
    r = _c.get("/bao-cao-tuan", headers=H_LEADER)
    assert "Toàn công ty" not in r.text and "Nhiệm vụ tôi giao" not in r.text


def test_dashboard_hien_goal_va_canh_bao(_so):
    ma = tuan.ma_tuan()
    g = mt.tao(MGR, "Tăng AVD", "AVD ≥ 45%")
    tuan.them_viec_muc_tieu(ma, MGR, "Chưa giao ai", "x", g["id"])
    r = _c.get("/bao-cao-tuan", headers=H_MGR)
    assert "Tăng AVD" in r.text and "1 chưa giao" in r.text


def test_khoi_nhiem_vu_chi_o_pham_vi_cong_ty(_so):
    ma = tuan.ma_tuan()
    tuan.them_viec_giao(ma, MGR, {"ten": "vh3", "level": 3, "bo_phan": "Vận hành"},
                        "Nhiệm vụ cho leader", "x")
    assert "Nhiệm vụ tôi giao" in _c.get("/bao-cao-tuan", headers=H_MGR).text
    assert "Nhiệm vụ tôi giao" not in _c.get("/bao-cao-tuan?pham_vi=bo-phan", headers=H_MGR).text
