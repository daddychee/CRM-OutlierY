# -*- coding: utf-8 -*-
"""B10.2 — lõi mục tiêu (FLOW-v3 §12).

Hai luật ghim ở đây: tiến độ đếm việc đã NGHIỆM THU (không trọng số), và xong hết
việc KHÔNG tự thành "đạt" — Manager phải kết luận.
"""
import pytest

from src import muc_tieu as mt
from src import tuan

MGR = {"ten": "huytq", "level": 4, "bo_phan": "Vận hành"}
MGR_KD = {"ten": "ngocpb", "level": 4, "bo_phan": "Kinh doanh"}
LEADER = {"ten": "vh3", "level": 3, "bo_phan": "Vận hành"}
NV = {"ten": "hant", "level": 2, "bo_phan": "Vận hành"}
OWNER = {"ten": "bot", "level": 5, "bo_phan": "Ban quản trị"}


def _mt(user=MGR, tieu_de="Tăng AVD kênh Life In", kq="AVD ≥ 45%", han="", tu=""):
    return mt.tao(user, tieu_de, kq, han, tu)


def _viec_xong(ma, m, tieu_de="Việc A"):
    """Một việc đi trọn vòng tới nghiệm thu, gắn vào mục tiêu."""
    v = tuan.them_viec_giao(ma, MGR, NV, tieu_de, "Dựng video", muc_tieu_id=m["id"])
    tuan.nhan_viec(ma, v["id"], NV)
    tuan.bao_xong(ma, v["id"], NV)
    tuan.xac_nhan_viec(ma, v["id"], MGR)
    return v


# ---------- ai được đặt mục tiêu ----------

def test_manager_dat_duoc_muc_tieu():
    m = _mt()
    assert m["trang_thai"] == mt.DANG_CHAY and m["bo_phan"] == "Vận hành"


def test_leader_khong_dat_duoc_muc_tieu():
    """Owner chốt: công việc bắt đầu từ Manager. Leader vẫn giao việc lẻ như cũ."""
    with pytest.raises(PermissionError):
        _mt(user=LEADER)


def test_nhan_vien_khong_dat_duoc():
    with pytest.raises(PermissionError):
        _mt(user=NV)


def test_thieu_ket_qua_can_dat_thi_bi_chan():
    """Mục tiêu không nêu kết quả thì sau này không chốt được — chặn ngay từ cửa."""
    with pytest.raises(ValueError):
        mt.tao(MGR, "Làm cho tốt hơn", "   ")


def test_thieu_ten_bi_chan():
    with pytest.raises(ValueError):
        mt.tao(MGR, "  ", "AVD ≥ 45%")


def test_han_sai_dinh_dang_bao_loi():
    with pytest.raises(ValueError):
        _mt(han="cuối tháng")


# ---------- tiến độ đếm theo việc nghiệm thu ----------

def test_chua_co_viec_thi_tien_do_la_None_khong_phai_0():
    m = _mt()
    t = mt.tien_do(m["id"])
    assert t["phan_tram"] is None and t["tong"] == 0 and t["xong_het"] is False


def test_tien_do_dem_viec_da_nghiem_thu(monkeypatch):
    ma = tuan.ma_tuan()
    m = _mt()
    _viec_xong(ma, m, "Việc 1")
    tuan.them_viec_giao(ma, MGR, NV, "Việc 2", "Dựng video", muc_tieu_id=m["id"])
    t = mt.tien_do(m["id"])
    assert (t["xong"], t["tong"], t["phan_tram"]) == (1, 2, 50)


def test_bao_xong_chua_lam_tien_do_nhuc_nhich():
    """Nấc 2 giữ nguyên: báo xong khác nghiệm thu."""
    ma = tuan.ma_tuan()
    m = _mt()
    v = tuan.them_viec_giao(ma, MGR, NV, "Việc A", "Dựng video", muc_tieu_id=m["id"])
    tuan.nhan_viec(ma, v["id"], NV)
    tuan.bao_xong(ma, v["id"], NV)
    assert mt.tien_do(m["id"])["phan_tram"] == 0


def test_viec_bi_huy_khong_lam_hong_mau_so():
    ma = tuan.ma_tuan()
    m = _mt()
    _viec_xong(ma, m, "Việc 1")
    bo = tuan.them_viec_giao(ma, MGR, NV, "Việc bỏ", "Dựng video", muc_tieu_id=m["id"])
    tuan.huy_viec(ma, bo["id"], MGR, "không cần nữa")
    assert mt.tien_do(m["id"])["phan_tram"] == 100


def test_viec_gom_qua_NHIEU_TUAN(monkeypatch):
    """Mục tiêu sống xuyên tuần — việc rải ở hai tuần vẫn gom về một cây."""
    ma = tuan.ma_tuan()
    sau = tuan.tuan_lien_ke(ma, 1)
    m = _mt()
    _viec_xong(ma, m, "Việc tuần này")
    tuan.them_viec_giao(sau, MGR, NV, "Việc tuần sau", "Dựng video", muc_tieu_id=m["id"])
    t = mt.tien_do(m["id"])
    assert t["tong"] == 2 and t["xong"] == 1


# ---------- xong hết việc KHÔNG tự thành đạt ----------

def test_xong_het_viec_van_chua_phai_dat():
    ma = tuan.ma_tuan()
    m = _mt()
    _viec_xong(ma, m)
    t = mt.tien_do(m["id"])
    assert t["xong_het"] is True and t["phan_tram"] == 100
    assert mt.doc_tat_ca()[0]["trang_thai"] == mt.DANG_CHAY   # máy KHÔNG tự phán đạt


def test_manager_chot_dat():
    m = _mt()
    d = mt.chot_ket_qua(m["id"], MGR, mt.DAT)
    assert d["trang_thai"] == mt.DAT and d["nguoi_chot"] == "huytq"


def test_chua_dat_tron_thi_bat_ghi_nhan_xet():
    """Số liệu không nói được vì sao — người chốt phải nói."""
    m = _mt()
    with pytest.raises(ValueError):
        mt.chot_ket_qua(m["id"], MGR, mt.MOT_PHAN, "")
    d = mt.chot_ket_qua(m["id"], MGR, mt.MOT_PHAN, "Làm đủ việc nhưng AVD chỉ lên 41%")
    assert d["trang_thai"] == mt.MOT_PHAN and "41%" in d["ket_luan"]


def test_ket_qua_ngoai_tap_bi_chan():
    m = _mt()
    with pytest.raises(ValueError):
        mt.chot_ket_qua(m["id"], MGR, "gan_dat", "x")


def test_manager_bo_phan_khac_khong_chot_duoc():
    m = _mt()
    with pytest.raises(PermissionError):
        mt.chot_ket_qua(m["id"], MGR_KD, mt.DAT)


def test_owner_chot_duoc_moi_muc_tieu():
    m = _mt()
    assert mt.chot_ket_qua(m["id"], OWNER, mt.DAT)["trang_thai"] == mt.DAT


def test_chot_hai_lan_bi_chan():
    m = _mt()
    mt.chot_ket_qua(m["id"], MGR, mt.DAT)
    with pytest.raises(ValueError):
        mt.chot_ket_qua(m["id"], MGR, mt.KHONG_DAT, "đổi ý")


def test_chot_nham_thi_mo_lai_duoc():
    m = _mt()
    mt.chot_ket_qua(m["id"], MGR, mt.DAT)
    mt.mo_lai(m["id"], MGR)
    assert mt.doc_tat_ca()[0]["trang_thai"] == mt.DANG_CHAY


def test_dang_chay_thi_khong_mo_lai():
    m = _mt()
    with pytest.raises(ValueError):
        mt.mo_lai(m["id"], MGR)


# ---------- nhiệm vụ Owner → mục tiêu Manager ----------

def test_muc_tieu_dung_tu_nhiem_vu_giu_lien_ket_nguoc():
    """Owner giao nhiệm vụ → Manager dựng thành mục tiêu; Owner theo dõi được."""
    ma = tuan.ma_tuan()
    nv = tuan.them_viec_giao(ma, OWNER, MGR, "Nâng chất lượng giữ chân video Mỹ", "Định hướng")
    m = _mt(tu=nv["id"])
    assert m["tu_nhiem_vu"] == nv["id"]
    assert [x["id"] for x in mt.doc_tat_ca() if x["tu_nhiem_vu"] == nv["id"]] == [m["id"]]


# ---------- phạm vi xem ----------

def test_manager_chi_thay_muc_tieu_bo_phan_minh():
    _mt()
    mt.tao(MGR_KD, "Chốt 3 ngách mới", "3 ngách vào pool US")
    assert [m["tieu_de"] for m in mt.trong_pham_vi(MGR)] == ["Tăng AVD kênh Life In"]
    assert len(mt.trong_pham_vi(MGR_KD)) == 1


def test_owner_thay_tat_ca():
    _mt()
    mt.tao(MGR_KD, "Chốt 3 ngách mới", "3 ngách vào pool US")
    assert len(mt.trong_pham_vi(OWNER)) == 2


def test_co_quyen_toan_cong_ty_thi_thay_tat():
    _mt()
    mt.tao(MGR_KD, "Chốt 3 ngách", "3 ngách")
    assert len(mt.trong_pham_vi(MGR, toan_cong_ty=True)) == 2


# ---------- hạn ----------

def test_con_han_am_la_qua_han():
    from datetime import date, timedelta
    m = _mt(han=(date.today() - timedelta(days=3)).isoformat())
    assert mt.con_han(m) == -3


def test_khong_dat_han_thi_None():
    assert mt.con_han(_mt()) is None


# ---------- sổ ----------

def test_so_hong_khong_lam_vo_app(tmp_path):
    (tmp_path / "db").mkdir(exist_ok=True)
    (tmp_path / "db" / "muc-tieu.json").write_text("{hỏng", encoding="utf-8")
    assert mt.doc_tat_ca() == []


def test_moi_thao_tac_de_lai_vet(tmp_path):
    import json
    m = _mt()
    mt.chot_ket_qua(m["id"], MGR, mt.DAT)
    dong = [json.loads(d) for d in
            (tmp_path / "db" / "nhat-ky.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [d["hanh_dong"] for d in dong] == ["tao_muc_tieu", "chot_muc_tieu"]
