# -*- coding: utf-8 -*-
"""B2 — lõi sổ tuần + luật nghiệp vụ (FLOW-v3 §4, §9.2, §9.3)."""
import json
from datetime import date

import pytest

from src import tuan

MA = "2026-W35"

LEADER = {"ten": "huytq", "level": 3, "bo_phan": "Vận hành - Sản xuất"}
NHANVIEN = {"ten": "hant", "level": 2, "bo_phan": "Vận hành - Sản xuất"}
NV_KHAC_BP = {"ten": "ngocpb", "level": 2, "bo_phan": "Kinh doanh"}
LEADER_KHAC = {"ten": "lannh", "level": 3, "bo_phan": "Hành chính Nhân sự"}
MANAGER = {"ten": "ducl", "level": 4, "bo_phan": "Vận hành - Sản xuất"}
OWNER = {"ten": "bot", "level": 5, "bo_phan": "Ban quản trị"}


def _giao(tieu_de="Dựng 6 video kênh Hidden Laos", loai="Dựng video",
          giao=LEADER, nhan=NHANVIEN, ma=MA):
    return tuan.them_viec_giao(ma, giao, nhan, tieu_de, loai)


# ---------- tuần ----------

def test_ma_tuan_va_khoang_theo_lich_iso_thu_hai_den_chu_nhat():
    assert tuan.ma_tuan(date(2026, 8, 27)) == "2026-W35"
    assert tuan.khoang_tuan("2026-W35") == ("2026-08-24", "2026-08-30")


def test_tuan_ke_tiep_qua_nam_khong_lech():
    """Năm ISO có năm 52 tuần có năm 53 — cộng ngày rồi hỏi lại lịch, không cộng số tuần."""
    assert tuan.tuan_ke_tiep("2026-W52") == "2026-W53"
    assert tuan.tuan_ke_tiep("2026-W53") == "2027-W01"


def test_tuan_chua_ai_khai_gi_tra_so_rong_hop_le():
    so = tuan.doc_tuan("2026-W40")
    assert so["viec"] == [] and so["tu"] == "2026-09-28"


def test_ma_tuan_sai_thi_bao_loi_ro_rang():
    with pytest.raises(ValueError):
        tuan.khoang_tuan("thang 8")


# ---------- luật giao việc (§9.2) ----------

def test_leader_giao_cho_nhan_vien_cung_bo_phan():
    v = _giao()
    assert v["trang_thai"] == tuan.CHO_NHAN and v["nguon"] == "giao"
    assert v["nguoi"] == "hant" and v["nguoi_giao"] == "huytq"


def test_ngang_cap_khong_giao_duoc_cho_nhau():
    with pytest.raises(PermissionError):
        _giao(giao=LEADER, nhan={"ten": "x", "level": 3,
                                 "bo_phan": "Vận hành - Sản xuất"})


def test_cap_duoi_khong_giao_nguoc_len_cap_tren():
    with pytest.raises(PermissionError):
        _giao(giao=NHANVIEN, nhan=LEADER)


def test_leader_khong_giao_sang_bo_phan_khac():
    with pytest.raises(PermissionError):
        _giao(giao=LEADER_KHAC, nhan=NHANVIEN)


def test_owner_giao_duoc_moi_bo_phan():
    v = _giao(giao=OWNER, nhan=NV_KHAC_BP)
    assert v["nguoi"] == "ngocpb"


def test_thieu_loai_viec_thi_khong_giao_duoc():
    """Loại việc là khóa gom checklist thành quy trình sau này (§5) — thiếu thì
    sau không cứu được bằng migration, nên chặn ngay từ cửa."""
    with pytest.raises(ValueError):
        _giao(loai="")


# ---------- nhận / từ chối (§9.3) ----------

def test_chua_nhan_viec_thi_chua_viet_duoc_checklist():
    v = _giao()
    with pytest.raises(ValueError):
        tuan.them_buoc(MA, v["id"], NHANVIEN, "Rà transcript")


def test_nhan_roi_moi_viet_duoc_buoc():
    v = _giao()
    tuan.nhan_viec(MA, v["id"], NHANVIEN)
    b = tuan.them_buoc(MA, v["id"], NHANVIEN, "Rà transcript")
    assert b["xong"] is False
    assert tuan.viec_cua(MA, "hant")[0]["trang_thai"] == tuan.DANG_LAM


def test_nguoi_khac_khong_nhan_ho_khong_tick_ho():
    v = _giao()
    with pytest.raises(PermissionError):
        tuan.nhan_viec(MA, v["id"], NV_KHAC_BP)


def test_tu_choi_bat_buoc_ghi_ly_do():
    v = _giao()
    with pytest.raises(ValueError):
        tuan.tu_choi_viec(MA, v["id"], NHANVIEN, "   ")
    d = tuan.tu_choi_viec(MA, v["id"], NHANVIEN, "Đang gánh 3 việc gấp tuần này")
    assert d["trang_thai"] == tuan.TU_CHOI and "3 việc" in d["ly_do"]


def test_viec_bi_tu_choi_khong_vao_mau_so_ti_le():
    a, b = _giao("Việc A"), _giao("Việc B")
    tuan.tu_choi_viec(MA, b["id"], NHANVIEN, "Không đúng chuyên môn")
    tuan.nhan_viec(MA, a["id"], NHANVIEN)
    tuan.bao_xong(MA, a["id"], NHANVIEN)
    tuan.xac_nhan_viec(MA, a["id"], LEADER)
    t = tuan.thong_ke_nguoi(MA, "hant")
    assert t["so_viec"] == 1 and t["ti_le"] == 100 and t["bi_tu_choi"] == 1


# ---------- việc tự thêm ----------

def test_tu_them_viec_vao_thang_dang_lam_khong_qua_luat_giao():
    v = tuan.them_viec_tu(MA, NHANVIEN, "Dựng lại intro sau feedback", "Dựng video")
    assert v["trang_thai"] == tuan.DANG_LAM and v["nguon"] == "tu_them"
    assert v["nguoi_giao"] is None


def test_viec_khong_co_ten_bi_chan():
    with pytest.raises(ValueError):
        tuan.them_viec_tu(MA, NHANVIEN, "   ", "Dựng video")


# ---------- hai nấc xác nhận (§4) ----------

def test_bao_xong_chua_phai_la_xong_phai_co_leader_xac_nhan():
    v = _giao()
    tuan.nhan_viec(MA, v["id"], NHANVIEN)
    tuan.bao_xong(MA, v["id"], NHANVIEN)
    t = tuan.thong_ke_nguoi(MA, "hant")
    assert t["xong"] == 0 and t["cho_xac_nhan"] == 1 and t["ti_le"] == 0

    tuan.xac_nhan_viec(MA, v["id"], LEADER)
    t2 = tuan.thong_ke_nguoi(MA, "hant")
    assert t2["xong"] == 1 and t2["ti_le"] == 100


def test_nhan_su_khong_tu_xac_nhan_viec_leader_giao():
    v = _giao()
    tuan.nhan_viec(MA, v["id"], NHANVIEN)
    tuan.bao_xong(MA, v["id"], NHANVIEN)
    with pytest.raises(PermissionError):
        tuan.xac_nhan_viec(MA, v["id"], NHANVIEN)


def test_leader_tu_lam_thi_tu_xac_nhan_va_bi_dan_nhan():
    v = tuan.them_viec_tu(MA, LEADER, "Soát lại quy trình QC", "Quy trình nội bộ")
    tuan.bao_xong(MA, v["id"], LEADER)
    tuan.xac_nhan_viec(MA, v["id"], LEADER)
    t = tuan.thong_ke_nguoi(MA, "huytq")
    assert t["ti_le"] == 100 and t["tu_xac_nhan"] is True


def test_owner_xac_nhan_duoc_viec_cua_bo_phan_khac():
    v = _giao()
    tuan.nhan_viec(MA, v["id"], NHANVIEN)
    tuan.bao_xong(MA, v["id"], NHANVIEN)
    assert tuan.xac_nhan_viec(MA, v["id"], OWNER)["trang_thai"] == tuan.XAC_NHAN


def test_tra_lai_viec_ve_dang_lam():
    v = _giao()
    tuan.nhan_viec(MA, v["id"], NHANVIEN)
    tuan.bao_xong(MA, v["id"], NHANVIEN)
    tuan.tra_lai_viec(MA, v["id"], LEADER, "Thiếu bước QC")
    assert tuan.viec_cua(MA, "hant")[0]["trang_thai"] == tuan.DANG_LAM


# ---------- dời / hủy / việc kẹt (§4) ----------

def test_doi_sang_tuan_sau_giu_goc_va_dem_so_lan_doi():
    v = _giao()
    tuan.nhan_viec(MA, v["id"], NHANVIEN)
    tuan.them_buoc(MA, v["id"], NHANVIEN, "Bước chưa làm")
    moi = tuan.doi_sang_tuan_sau(MA, v["id"], LEADER, "Chờ bản dựng của editor")

    assert tuan.viec_cua(MA, "hant")[0]["trang_thai"] == tuan.DOI
    assert moi["so_lan_doi"] == 1 and moi["goc_id"] == v["id"]
    assert [b["noi_dung"] for b in moi["checklist"]] == ["Bước chưa làm"]
    assert tuan.viec_cua("2026-W36", "hant")[0]["id"] == moi["id"]


def test_doi_hai_lan_thi_len_co_viec_ket():
    v = _giao()
    m1 = tuan.doi_sang_tuan_sau(MA, v["id"], LEADER, "lần 1")
    m2 = tuan.doi_sang_tuan_sau("2026-W36", m1["id"], LEADER, "lần 2")
    assert m2["so_lan_doi"] == 2
    assert tuan.thong_ke_nguoi("2026-W37", "hant")["ket"] == 1


def test_doi_kem_doi_nguoi_van_phai_qua_luat_giao():
    v = _giao()
    with pytest.raises(PermissionError):
        tuan.doi_sang_tuan_sau(MA, v["id"], LEADER, "đổi người", nguoi_moi=NV_KHAC_BP)
    moi = tuan.doi_sang_tuan_sau(MA, v["id"], LEADER, "đổi người",
                                 nguoi_moi={"ten": "ducm", "level": 2,
                                            "bo_phan": "Vận hành - Sản xuất"})
    assert moi["nguoi"] == "ducm"


def test_huy_bat_buoc_ly_do_va_khong_xoa_khoi_so():
    v = _giao()
    with pytest.raises(ValueError):
        tuan.huy_viec(MA, v["id"], LEADER, "")
    tuan.huy_viec(MA, v["id"], LEADER, "RadarY đã có dữ liệu, không cần làm tay")
    ds = tuan.viec_cua(MA, "hant")
    assert len(ds) == 1 and ds[0]["trang_thai"] == tuan.HUY
    assert tuan.thong_ke_nguoi(MA, "hant")["so_viec"] == 0


# ---------- đóng tuần ----------

def test_con_viec_treo_thi_chua_dong_duoc_tuan():
    v = _giao()
    with pytest.raises(ValueError):
        tuan.dong_tuan(MA, "hant", LEADER)
    tuan.huy_viec(MA, v["id"], LEADER, "giao nhầm người")
    tuan.dong_tuan(MA, "hant", LEADER)
    assert tuan.thong_ke_nguoi(MA, "hant")["da_dong"] is True


# ---------- van chống bịa (§3) ----------

def test_nguoi_chua_co_viec_nao_thi_ti_le_la_None_khong_phai_0():
    t = tuan.thong_ke_nguoi(MA, "chuaai")
    assert t["ti_le"] is None and t["so_viec"] == 0


def test_bang_bao_cao_giu_None_cho_nguoi_chua_co_viec():
    _giao()
    bang = tuan.bang_bao_cao(MA, [{"ten": "hant", "ho_ten": "Nguyễn Thu Hà"},
                                  {"ten": "yenvh", "ho_ten": "Vũ Hải Yến"}])
    assert bang[0]["ti_le"] == 0 and bang[1]["ti_le"] is None


# ---------- khối lượng + vết ----------

def test_dem_khoi_luong_theo_viec_va_buoc():
    a = _giao("Việc A")
    tuan.nhan_viec(MA, a["id"], NHANVIEN)
    b1 = tuan.them_buoc(MA, a["id"], NHANVIEN, "b1")
    tuan.them_buoc(MA, a["id"], NHANVIEN, "b2")
    tuan.tick_buoc(MA, a["id"], b1["id"], NHANVIEN)
    tuan.them_viec_tu(MA, NHANVIEN, "Việc tự nhận", "Dựng video")
    t = tuan.thong_ke_nguoi(MA, "hant")
    assert (t["so_viec"], t["giao"], t["tu_them"]) == (2, 1, 1)
    assert (t["buoc_tong"], t["buoc_xong"]) == (2, 1)


def test_moi_thao_tac_deu_de_lai_vet_chi_them(tmp_path):
    v = _giao()
    tuan.nhan_viec(MA, v["id"], NHANVIEN)
    tuan.bao_xong(MA, v["id"], NHANVIEN)
    tuan.xac_nhan_viec(MA, v["id"], LEADER)
    dong = [json.loads(d) for d in
            (tmp_path / "db" / "nhat-ky.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [d["hanh_dong"] for d in dong] == ["giao_viec", "nhan_viec", "bao_xong", "xac_nhan"]


def test_ghi_so_la_nguyen_tu_khong_de_lai_file_tam(tmp_path):
    _giao()
    assert list((tmp_path / "db" / "tuan").glob("*.tmp")) == []
    assert (tmp_path / "db" / "tuan" / f"{MA}.json").is_file()
