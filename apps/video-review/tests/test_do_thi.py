# -*- coding: utf-8 -*-
"""Test đọc đường cong giữ chân từ ảnh chụp Studio + neo bằng số thật."""
import numpy as np
import pytest
from PIL import Image, ImageDraw

from src import do_thi


def _anh_studio(tmp_path, tut_tai=None, w=900, h=300):
    """Ảnh giả đúng kiểu Studio: nền tối, dải xám 'thông thường', đường xanh."""
    im = Image.new("RGB", (w, h), (15, 15, 15))
    d = ImageDraw.Draw(im)
    xs = np.arange(w)
    y = 0.86 * np.exp(-xs / (w * 0.16)) + 0.10
    if tut_tai:
        for pt in tut_tai:
            y[int(w * pt):] -= 0.06
    y = np.clip(y, 0.02, 1.0)
    for x in xs:                                   # dải xám phải KHÔNG bị nhầm
        yy = int(h - (0.80 * np.exp(-x / (w * 0.16)) + 0.13) * h * 0.9)
        d.line([(int(x), yy - 6), (int(x), yy + 6)], fill=(70, 70, 70))
    d.line([(int(x), int(h - y[x] * h * 0.9)) for x in xs], fill=(62, 166, 255), width=3)
    p = tmp_path / "studio.png"
    im.save(p)
    return p, y


def test_doc_duoc_duong_xanh_khong_nham_dai_xam(tmp_path):
    p, that = _anh_studio(tmp_path)
    cong = do_thi.doc_duong_cong(p)
    assert cong and len(cong) == do_thi.SO_DIEM
    assert cong[0] > 90                            # đầu video gần 100%
    assert cong[-1] < 25                           # cuối video thấp
    assert all(cong[i] >= cong[i + 1] - 3 for i in range(len(cong) - 1))


def test_anh_khong_co_duong_thi_tra_None(tmp_path):
    p = tmp_path / "trang.png"
    Image.new("RGB", (400, 200), (240, 240, 240)).save(p)
    assert do_thi.doc_duong_cong(p) is None


def test_neo_dat_khi_khop_so_that(tmp_path):
    p, _ = _anh_studio(tmp_path)
    cong = do_thi.doc_duong_cong(p)
    doc = do_thi._diem_tai(cong, 30.0 / 600 * 100)
    kq = do_thi.neo_bang_so_that(cong, doc, 600)
    assert kq["dat"] is True and abs(kq["lech"]) < 0.01
    assert len(kq["cong"]) == do_thi.SO_DIEM


def test_neo_lech_qua_thi_TU_CHOI_chu_khong_dung_so_sai(tmp_path):
    p, _ = _anh_studio(tmp_path)
    cong = do_thi.doc_duong_cong(p)
    kq = do_thi.neo_bang_so_that(cong, 20.0, 600)   # số thật khác hẳn ảnh
    assert kq["dat"] is False
    assert "lệch" in kq["ly_do"] and "cong" not in kq


def test_tim_cho_tut_theo_chinh_video_khong_dung_nguong_cung(tmp_path):
    p, _ = _anh_studio(tmp_path, tut_tai=[0.45])
    cong = do_thi.doc_duong_cong(p)
    tut = do_thi.tim_cho_tut(cong, 1800)
    assert tut, "phải thấy ít nhất chỗ rơi dựng đứng ở đầu"
    assert tut[0]["tu_giay"] < 300                  # chỗ nặng nhất là mở đầu
    assert tut[0]["mat_diem"] > 10
    assert all("con_lai" in t for t in tut)


def test_khong_du_du_lieu_thi_khong_ket_luan():
    assert do_thi.tim_cho_tut([], 600) == []
    assert do_thi.tim_cho_tut([90, 80], 600) == []
    assert do_thi.neo_bang_so_that([], 59, 600)["dat"] is False
    assert do_thi.neo_bang_so_that([90] * 100, 59, 0)["dat"] is False


def test_dong_goi_mo_goi_giu_nguyen_so():
    cong = [99.5, 80.25, 13.9]
    assert do_thi.mo_goi(do_thi.dong_goi(cong)) == cong
    assert do_thi.mo_goi("hong") == []
