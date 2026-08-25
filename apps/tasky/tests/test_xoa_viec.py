# -*- coding: utf-8 -*-
"""Xóa việc (Owner yêu cầu 25/08) — gỡ mềm trước, xóa hẳn chỉ ở ca an toàn."""
import json

import pytest

from src import tuan

LEADER = {"ten": "huytq", "level": 3, "bo_phan": "Vận hành"}
NV = {"ten": "hant", "level": 2, "bo_phan": "Vận hành"}
NV2 = {"ten": "ducm", "level": 2, "bo_phan": "Vận hành"}
OWNER = {"ten": "bot", "level": 5, "bo_phan": "Ban quản trị"}


@pytest.fixture()
def ma():
    return tuan.ma_tuan()


def _giao(ma, ten="Việc A"):
    return tuan.them_viec_giao(ma, LEADER, NV, ten, "x")


# ---------- ca xóa được ----------

def test_xoa_viec_vua_giao_chua_ai_nhan(ma):
    v = _giao(ma)
    tuan.xoa_viec(ma, v["id"], LEADER)
    assert tuan.viec_cua(ma, "hant") == []


def test_nhan_su_xoa_duoc_viec_minh_tu_them(ma):
    v = tuan.them_viec_tu(ma, NV, "Việc tôi tự nhận", "x")
    tuan.xoa_viec(ma, v["id"], NV)
    assert tuan.viec_cua(ma, "hant") == []


def test_xoa_duoc_viec_da_bi_tu_choi(ma):
    v = _giao(ma)
    tuan.tu_choi_viec(ma, v["id"], NV, "Đang quá tải")
    tuan.xoa_viec(ma, v["id"], LEADER)
    assert tuan.viec_cua(ma, "hant") == []


def test_xoa_duoc_viec_da_huy(ma):
    v = _giao(ma)
    tuan.huy_viec(ma, v["id"], LEADER, "giao nhầm")
    tuan.xoa_viec(ma, v["id"], LEADER)
    assert tuan.viec_cua(ma, "hant") == []


def test_nguoi_nhan_xoa_duoc_viec_chua_nhan_cua_minh(ma):
    v = _giao(ma)
    tuan.xoa_viec(ma, v["id"], NV)
    assert tuan.viec_cua(ma, "hant") == []


# ---------- ca KHÔNG xóa ----------

def test_viec_dang_lam_thi_khong_xoa_trang(ma):
    """Người ta đã bỏ công — dùng Hủy kèm lý do, đừng xóa cả dấu vết."""
    v = _giao(ma)
    tuan.nhan_viec(ma, v["id"], NV)
    with pytest.raises(ValueError) as e:
        tuan.xoa_viec(ma, v["id"], LEADER)
    assert "Hủy kèm lý do" in str(e.value)


def test_viec_bao_xong_cung_khong_xoa(ma):
    v = _giao(ma)
    tuan.nhan_viec(ma, v["id"], NV)
    tuan.bao_xong(ma, v["id"], NV)
    with pytest.raises(ValueError):
        tuan.xoa_viec(ma, v["id"], LEADER)


def test_viec_da_nghiem_thu_chi_owner_xoa_duoc(ma):
    v = _giao(ma)
    tuan.nhan_viec(ma, v["id"], NV)
    tuan.bao_xong(ma, v["id"], NV)
    tuan.xac_nhan_viec(ma, v["id"], LEADER)
    with pytest.raises(PermissionError) as e:
        tuan.xoa_viec(ma, v["id"], LEADER)
    assert "báo cáo" in str(e.value)
    tuan.xoa_viec(ma, v["id"], OWNER)          # Owner dọn được
    assert tuan.viec_cua(ma, "hant") == []


def test_nguoi_ngoai_cuoc_khong_xoa_duoc(ma):
    v = _giao(ma)
    with pytest.raises(PermissionError):
        tuan.xoa_viec(ma, v["id"], NV2)


def test_viec_da_doi_khong_xoa_tuy_tien(ma):
    """Đã dời thì tuần sau đã có việc con — xóa bừa là bỏ mồ côi."""
    v = _giao(ma)
    tuan.doi_sang_tuan_sau(ma, v["id"], LEADER, "chờ editor")
    with pytest.raises(PermissionError):
        tuan.xoa_viec(ma, v["id"], LEADER)


# ---------- chống mất dữ liệu ----------

def test_nhat_ky_giu_nguyen_ban_viec_bi_xoa(ma, tmp_path):
    v = _giao(ma, "Việc quý giá")
    tuan.xoa_viec(ma, v["id"], LEADER)
    dong = [json.loads(d) for d in
            (tmp_path / "db" / "nhat-ky.jsonl").read_text(encoding="utf-8").splitlines()]
    cuoi = dong[-1]
    assert cuoi["hanh_dong"] == "xoa_viec"
    assert cuoi["ban_goc"]["tieu_de"] == "Việc quý giá"      # dựng lại tay được


def test_xoa_khong_dung_toi_viec_khac(ma):
    a, b = _giao(ma, "Giữ lại"), _giao(ma, "Xóa đi")
    tuan.xoa_viec(ma, b["id"], LEADER)
    assert [x["tieu_de"] for x in tuan.viec_cua(ma, "hant")] == ["Giữ lại"]
