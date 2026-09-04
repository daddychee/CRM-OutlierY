# -*- coding: utf-8 -*-
"""Test tầng mạch dựng: hồ sơ ngoài code, đo thô, và dịch số thành CÂU BỆNH."""
import pytest

from src import mach_dung


@pytest.fixture()
def ho_so():
    return mach_dung.doc_ho_so("life-in")


def test_ho_so_doc_tu_file_ngoai_code(ho_so):
    assert ho_so["cat_phut"] == 10.8
    assert ho_so["than_p50"] == 4.2
    assert ho_so["hook_p50"] == 1.0
    assert ho_so["hook_chop"] == 0.70
    assert ho_so["std_san"] == 1.55
    assert mach_dung.doc_ho_so("khong-co-niche-nay")["niche"] == "_mac_dinh"


def test_hook_cham_ra_cau_benh_co_loi_giai_thich(ho_so):
    so = {"hook_p50": 2.4, "hook_chop": 0.38, "shot_p50": 3.8, "shot_std": 1.9,
          "cat_phut": 9.1, "shot_dai_nhat": 5.0, "tin_cay": True, "duong_cong": []}
    cd = mach_dung.chan_doan(so, ho_so)
    hook = [c for c in cd if "Mở đầu" in c["benh"]]
    assert len(hook) == 1
    c = hook[0]
    assert c["muc"] == "nang" and c["ts"] == 0.0
    assert "2,4" in c["loi"].replace(".", ",") or "2.4" in c["loi"]
    assert c["nen_lam"] and c["so_lieu"]


def test_canh_giu_qua_lau_va_nhip_deu(ho_so):
    so = {"hook_p50": 1.0, "hook_chop": 0.72, "shot_p50": 3.8, "shot_std": 1.2,
          "cat_phut": 10.0, "shot_dai_nhat": 9.2, "tin_cay": True, "duong_cong": []}
    ten = [c["benh"] for c in mach_dung.chan_doan(so, ho_so)]
    assert "Một cảnh bị giữ quá lâu" in ten
    assert "Nhịp đều đều — thiếu tương phản" in ten
    assert not any("Mở đầu" in t for t in ten)


def test_ban_dat_chuan_thi_khong_bia_ra_benh(ho_so):
    so = {"hook_p50": 0.9, "hook_chop": 0.75, "shot_p50": 4.2, "shot_std": 2.4,
          "cat_phut": 10.8, "shot_dai_nhat": 8.0, "tin_cay": True, "duong_cong": []}
    assert mach_dung.chan_doan(so, ho_so) == []
    assert mach_dung.dat_dat(so, ho_so) == "chưa đo được"


def test_hai_thuoc_lech_thi_noi_khong_dang_tin(ho_so):
    so = {"hook_p50": 2.4, "hook_chop": 0.38, "shot_p50": 3.8, "shot_std": 1.9,
          "cat_phut": 9.1, "shot_dai_nhat": 5.0, "tin_cay": False, "duong_cong": []}
    assert mach_dung.chan_doan(so, ho_so)[0]["benh"] == "Số đo không đáng tin"


def test_tut_nhip_gop_quang_lien_nhau(ho_so):
    so = {"hook_p50": 1.0, "hook_chop": 0.72, "shot_p50": 4.2, "shot_std": 2.0,
          "cat_phut": 10.8, "shot_dai_nhat": 8.0, "tin_cay": True,
          "duong_cong": [(0, 11), (15, 12), (360, 4.9), (375, 4.5), (390, 4.8),
                         (600, 11), (900, 3.9)]}
    tut = [c for c in mach_dung.chan_doan(so, ho_so) if "Nhịp tụt" in c["benh"]]
    assert len(tut) == 2                      # 3 cửa sổ liền nhau gộp làm 1
    assert tut[0]["ts"] == 360 and "06:00" in tut[0]["loi"]


def test_khong_co_so_do_thi_khong_ket_luan(ho_so):
    assert mach_dung.chan_doan({}, ho_so) == []
    assert mach_dung.chan_doan({"cat_phut": 9}, {}) == []
