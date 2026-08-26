# -*- coding: utf-8 -*-
"""Test D3 — chi phí sản xuất theo NGÁCH, quy từ ngày công.

Owner: "Chi phí sản xuất cho niche được tính bằng số lượng ngày công làm cho
niche đó." Nguồn phân công là PlannerY (projects[].ngach_ma + assignments[]),
đơn giá ngày từ bảng lương ĐÃ DUYỆT (D1).
"""
import json
import os
from pathlib import Path

from src import cham_cong, chi_phi_ngach, kpi_danh_gia, luong, tai_chinh

KY = "2026-08"
NGUOI = [{"ten": "ngocth", "ho_ten": "Trần Hồng Ngọc", "ma": "NS-005",
          "planner_id": "ns_ns005", "bo_phan": "Vận hành"},
         {"ten": "thiennc", "ho_ten": "Nguyễn Chu Thiện", "ma": "NS-006",
          "planner_id": "ns_ns006", "bo_phan": "Vận hành"},
         {"ten": "namnt", "ho_ten": "Nghiêm Trường Nam", "ma": "NS-018",
          "planner_id": "ns_ns018", "bo_phan": "Vận hành"}]


def _seed_plannery(kenh_life="", kenh_space=""):
    """plan.json giả — đúng khuôn thật: project mang ngach_ma, channel mang kenh_ma."""
    plan = {
        "people": [{"id": "ns_ns005", "name": "Trần Hồng Ngọc", "role": "content"},
                   {"id": "ns_ns006", "name": "Nguyễn Chu Thiện", "role": "editor"},
                   {"id": "ns_ns018", "name": "Nghiêm Trường Nam", "role": "content"}],
        "projects": [
            {"id": "pr_life", "name": "Life In", "ngach_ma": "N-LIFE-IN",
             "channels": [{"id": "ch1", "name": "LIFE DECODED", "kenh_ma": kenh_life}]},
            {"id": "pr_space", "name": "SPACE", "ngach_ma": "N-SPACE",
             "channels": [{"id": "ch2", "name": "Cosmic Depth", "kenh_ma": kenh_space}]},
        ],
        "assignments": [{"person_id": "ns_ns005", "project_id": "pr_life"},
                        {"person_id": "ns_ns005", "project_id": "pr_space"},
                        {"person_id": "ns_ns006", "project_id": "pr_life"}],
    }
    Path(os.environ["PLANNERY_PLAN"]).write_text(
        json.dumps(plan, ensure_ascii=False), encoding="utf-8")


def _cham(ten, ngay, vao="08:15:00"):
    p = Path(os.environ["CHAM_CONG_DIR"]) / f"{ngay[:7]}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    du = json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}
    du.setdefault(ngay, {})[ten] = {"vao": vao, "ra": "17:30:00", "nguon_ra": "dang_xuat"}
    p.write_text(json.dumps(du, ensure_ascii=False), encoding="utf-8")


def _seed_luong_da_duyet():
    """2 người có lương duyệt (10 và 5 ngày công), 1 người KHÔNG (namnt)."""
    for i in range(10):
        _cham("ngocth", f"2026-08-{i + 3:02d}")
    for i in range(5):
        _cham("thiennc", f"2026-08-{i + 3:02d}")
    for i in range(4):
        _cham("namnt", f"2026-08-{i + 3:02d}")
    luong.dat_luong_co_ban("hr", "ngocth", 10_000_000)
    luong.dat_luong_co_ban("hr", "thiennc", 5_000_000)
    kpi_danh_gia.them_danh_gia("ngocth", KY, "B", "", "sep")     # hệ số 1.00
    kpi_danh_gia.them_danh_gia("thiennc", KY, "B", "", "sep")
    tai_chinh.them_muc_tieu("Vận hành chung", 100_000_000)
    cham_cong.chot_ky(KY, "hr")
    luong.duyet_bang_luong("Bot", KY, NGUOI, "Vận hành chung", "vietcombank")


def test_chia_deu_ngay_cong_cho_cac_ngach_duoc_phan_cong():
    _seed_plannery()
    _seed_luong_da_duyet()
    kq = chi_phi_ngach.chi_phi_ngach(KY, NGUOI)
    ng = {x["ngach_ma"]: x for x in kq["dong"]}
    # ngocth: 10 ngày công, 2 ngách → 5 ngày mỗi ngách; đơn giá 1.000.000/ngày
    # thiennc: 5 ngày công, 1 ngách LIFE IN; đơn giá 1.000.000/ngày
    assert ng["N-LIFE-IN"]["ngay_cong"] == 10.0
    assert ng["N-LIFE-IN"]["nhan_cong"] == 10_000_000.0
    assert ng["N-SPACE"]["ngay_cong"] == 5.0
    assert ng["N-SPACE"]["nhan_cong"] == 5_000_000.0


def test_tong_nhan_cong_bang_dung_tong_bang_luong_da_duyet():
    """Đẳng thức ghim: không được đẻ thêm hay đánh rơi đồng nào."""
    _seed_plannery()
    _seed_luong_da_duyet()
    kq = chi_phi_ngach.chi_phi_ngach(KY, NGUOI)
    assert kq["tong_nhan_cong"] == luong.doc_bang_luong(KY)["tong"] == 15_000_000.0


def test_nguoi_khong_phan_cong_ve_hang_chua_phan_cong():
    _seed_plannery()
    _seed_luong_da_duyet()
    luong.dat_luong_co_ban("hr", "namnt", 8_000_000)   # có lương nhưng chưa duyệt kỳ
    kq = chi_phi_ngach.chi_phi_ngach(KY, NGUOI)
    chua = kq["chua_phan_cong"]
    assert chua["ngay_cong"] == 4.0                    # ngày công của namnt
    assert chua["nhan_cong"] is None                   # lương chưa duyệt → KHÔNG tính
    assert "chưa duyệt" in chua["ghi_chu"].lower()


def test_plannery_chet_thi_noi_thang_khong_dung_so():
    _seed_luong_da_duyet()                             # KHÔNG seed plan.json
    kq = chi_phi_ngach.chi_phi_ngach(KY, NGUOI)
    assert kq["dong"] == [] and kq["thieu_nguon"] is True
    assert kq["tong_nhan_cong"] is None


def test_tien_mat_theo_ngach_gop_tu_kenh():
    from nen.common import danh_ba
    conn = danh_ba.ket_noi()
    try:
        ng = danh_ba.them_ngach(conn, "Life In")
        k1 = danh_ba.them_kenh(conn, "Life Decoded", ng)
    finally:
        conn.close()
    _seed_plannery(kenh_life=k1)
    _seed_luong_da_duyet()
    tai_chinh.them_but_toan("kt", "2026-08-10", "CHI-PROXY", 2_000_000,
                            "Vận hành chung", kenh_ma=k1, vi="vietcombank")
    kq = chi_phi_ngach.chi_phi_ngach(KY, NGUOI)
    ng_row = {x["ngach_ma"]: x for x in kq["dong"]}
    assert ng_row[ng]["tien_mat"] == 2_000_000.0
    assert ng_row[ng]["tong"] == ng_row[ng]["nhan_cong"] + 2_000_000.0
