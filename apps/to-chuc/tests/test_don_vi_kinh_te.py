# -*- coding: utf-8 -*-
"""Test B2 — đơn vị kinh tế: chi phí/video, chi phí/1K view, biên lãi.

Van chống bịa của engine chẩn đoán giữ nguyên: dưới ngưỡng mẫu thì ghi
"chưa đủ dữ liệu", KHÔNG tính bừa ra một con số trông hợp lý.
"""
import json
import os
from pathlib import Path

from src import don_vi_kinh_te, tai_chinh

THANG = "2026-08"
VI = "vietcombank"


def _seed_kenh():
    from nen.common import danh_ba
    conn = danh_ba.ket_noi()
    try:
        ng = danh_ba.them_ngach(conn, "Life In")
        return danh_ba.them_kenh(conn, "Outland", ng), danh_ba.them_kenh(conn, "Mới toanh", ng)
    finally:
        conn.close()


def _seed_plannery(kenh_ma, so_video):
    """PlannerY: videos đã xuất bản của kênh trong kỳ."""
    plan = {"people": [], "assignments": [], "projects": [
        {"id": "pr1", "name": "Life In", "ngach_ma": "N-LIFE-IN", "channels": [
            {"id": "ch1", "name": "Outland", "kenh_ma": kenh_ma,
             "videos": [{"publish_date": f"2026-08-{i + 1:02d}"} for i in range(so_video)]}]}]}
    Path(os.environ["PLANNERY_PLAN"]).write_text(json.dumps(plan), encoding="utf-8")


def test_chi_phi_moi_video_va_bien_lai():
    k1, _ = _seed_kenh()
    _seed_plannery(k1, 10)
    tai_chinh.them_muc_tieu("Vận hành chung", 0)
    tai_chinh.them_but_toan("kt", "2026-08-10", "THU-ADS", 50_000_000,
                            "Vận hành chung", kenh_ma=k1, vi=VI)
    tai_chinh.them_but_toan("kt", "2026-08-11", "CHI-NGOAI", 20_000_000,
                            "Vận hành chung", kenh_ma=k1, vi=VI)
    d = {x["kenh_ma"]: x for x in don_vi_kinh_te.don_vi_kinh_te(THANG)["dong"]}
    assert d[k1]["so_video"] == 10
    assert d[k1]["chi_moi_video"] == 2_000_000       # 20tr ÷ 10 video
    assert d[k1]["bien_lai"] == 60                   # (50−20)/50
    assert d[k1]["luot_xem"] is None                 # chưa nối báo cáo → không đoán
    assert d[k1]["chi_moi_1k_view"] is None


def test_khong_du_mau_thi_noi_thang():
    k1, k2 = _seed_kenh()
    _seed_plannery(k1, 10)                            # k2 KHÔNG có video nào
    tai_chinh.them_muc_tieu("Vận hành chung", 0)
    tai_chinh.them_but_toan("kt", "2026-08-11", "CHI-TK", 6_000_000,
                            "Vận hành chung", kenh_ma=k2, vi=VI)
    d = {x["kenh_ma"]: x for x in don_vi_kinh_te.don_vi_kinh_te(THANG)["dong"]}
    assert d[k2]["so_video"] == 0
    assert d[k2]["chi_moi_video"] is None             # chia cho 0 → không tính
    assert d[k2]["thieu"] != ""


def test_chua_monetize_thi_khong_co_bien_lai():
    k1, _ = _seed_kenh()
    _seed_plannery(k1, 5)
    tai_chinh.them_muc_tieu("Vận hành chung", 0)
    tai_chinh.them_but_toan("kt", "2026-08-11", "CHI-NGOAI", 5_000_000,
                            "Vận hành chung", kenh_ma=k1, vi=VI)
    d = {x["kenh_ma"]: x for x in don_vi_kinh_te.don_vi_kinh_te(THANG)["dong"]}
    assert d[k1]["bien_lai"] is None                  # thu = 0 → không chia được


def test_plannery_chet_thi_bao_thieu_nguon():
    _seed_kenh()
    kq = don_vi_kinh_te.don_vi_kinh_te(THANG)         # không seed plan.json
    assert kq["thieu_nguon"] is True and kq["dong"] == []
