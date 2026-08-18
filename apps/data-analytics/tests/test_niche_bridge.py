# -*- coding: utf-8 -*-
"""Test cầu nối snapshot ngách — dữ liệu giả trong tmp, không đụng dự án thật."""
import json

import pytest

from src import niche_bridge


def _seed(tmp_path, project="TestNiche_US", ngay="2026-08-18"):
    snap = tmp_path / project / "snapshots" / ngay
    snap.mkdir(parents=True)
    (snap / "decision1.json").write_text(json.dumps({
        "attractiveness": 58, "decision": "CONDITIONAL",
        "gate_reason": "borderline", "pillars": {"demand": 42}}), encoding="utf-8")
    (snap / "demand.json").write_text(json.dumps({
        "demand_median_views": 3071, "reach_p90_views": 128885,
        "supply_per_month": 264.4, "trend": "FLAT"}), encoding="utf-8")
    (snap / "crackability.json").write_text(json.dumps({
        "newcomer_rate": 0.333, "verdict": "OPEN"}), encoding="utf-8")
    (snap / "monetization.json").write_text(json.dumps({
        "rpm_band_usd": [3, 10]}), encoding="utf-8")
    (snap / "decision2.json").write_text(json.dumps({"ranked": [
        {"anchor": "hidden", "beachhead_score": 114.1, "competition": 0.305,
         "size": 125, "n_channels": 33},
        {"anchor": "laos", "beachhead_score": 111.4, "competition": 0.128,
         "size": 48, "n_channels": 34},
        {"anchor": "x3", "beachhead_score": 87, "competition": 0.4, "size": 45, "n_channels": 23},
        {"anchor": "x4", "beachhead_score": 60, "competition": 0.5, "size": 20, "n_channels": 10},
        {"anchor": "iraq", "beachhead_score": 21.9, "competition": 0.997, "size": 9, "n_channels": 4},
    ]}), encoding="utf-8")
    (snap / "analysis.json").write_text(json.dumps({
        "total_videos": 3815, "n_winners": 648, "n_early_confirmed": 104}), encoding="utf-8")
    (snap / "gaps.json").write_text(json.dumps({
        "total_comments": 12869, "total_questions": 1081}), encoding="utf-8")
    (snap / "channels.json").write_text(json.dumps(
        {f"UC{i}": {} for i in range(75)}), encoding="utf-8")
    (snap / "BAO-CAO-8-PHASE.html").write_text("<title>x</title>", encoding="utf-8")
    (tmp_path / project / "snapshots" / "index.json").write_text(json.dumps([{
        "id": ngay, "tao_luc": ngay + "T00:00:00",
        "artifacts": ["decision1.json", "demand.json", "crackability.json",
                       "monetization.json", "decision2.json", "analysis.json",
                       "gaps.json", "channels.json"],
        "bao_cao": ["BAO-CAO-8-PHASE.html"]}]), encoding="utf-8")
    return project


@pytest.fixture(autouse=True)
def _tro_projects(tmp_path, monkeypatch):
    monkeypatch.setenv("NICHE_PROJECTS_DIR", str(tmp_path))


def test_tom_tat_du_tile(tmp_path):
    project = _seed(tmp_path)
    t = niche_bridge.tom_tat_overall(project)
    assert t["co_bao_cao"] and t["snapshot"] == "2026-08-18"
    assert t["diem_hap_dan"] == 58 and t["phan_quyet"] == "CONDITIONAL"
    assert t["view_trung_vi"] == 3071 and t["moc_trung"] == 128885
    assert t["rpm_band"] == "$3–10" and t["cua_vao_verdict"] == "OPEN"
    assert t["cum_tot"][0]["anchor"] == "hidden"
    assert t["cum_xau"][-1]["anchor"] == "iraq"
    assert len(t["beachhead"]) == 5


def test_pipeline_va_so_dan_xuat(tmp_path):
    """Tổng quan số pipeline + số dẫn xuất (banner/tile) — thiếu nguồn = None."""
    project = _seed(tmp_path)
    t = niche_bridge.tom_tat_overall(project)
    p = t["pipeline"]
    assert p["kenh_resolve"] == 75 and p["video_quet"] == 3815
    assert p["outlier"] == 648 and p["tin_hieu_som"] == 104
    assert p["comment"] == 12869 and p["cau_hoi"] == 1081
    assert p["video_truong_thanh"] is None    # demand giả không có n_matured → không bịa
    assert t["moc_trung_x"] == 42             # 128885/3071 — PY tính, template chỉ in
    assert t["so_cum"] == 5 and t["diem_cum_tb"] == round((114.1 + 111.4 + 87 + 60 + 21.9) / 5)
    # xóa gaps → 2 ô comment/câu hỏi thành None, các ô khác vẫn sống
    (tmp_path / project / "snapshots" / "2026-08-18" / "gaps.json").unlink()
    p2 = niche_bridge.tom_tat_overall(project)["pipeline"]
    assert p2["comment"] is None and p2["video_quet"] == 3815


def test_chua_co_bao_cao_khong_so_gia(tmp_path):
    t = niche_bridge.tom_tat_overall("KhongTonTai_VN")
    assert t["co_bao_cao"] is False and "Chưa có báo cáo" in t["ly_do"]
    assert "diem_hap_dan" not in t  # không được rơi ra số giả


def test_artifact_thieu_thanh_none(tmp_path):
    project = _seed(tmp_path)
    # xóa monetization → tile RPM phải None, các tile khác vẫn sống
    (tmp_path / project / "snapshots" / "2026-08-18" / "monetization.json").unlink()
    t = niche_bridge.tom_tat_overall(project)
    assert t["co_bao_cao"] and t["rpm_band"] is None
    assert t["diem_hap_dan"] == 58


def test_xem_lai_ban_cu_theo_id(tmp_path):
    project = _seed(tmp_path)
    _seed(tmp_path, project="x")  # nhiễu
    # thêm snapshot mới hơn với điểm khác → latest lấy bản mới, id cũ vẫn đọc được
    snap2 = tmp_path / project / "snapshots" / "2026-11-01"
    snap2.mkdir(parents=True)
    (snap2 / "decision1.json").write_text(json.dumps({"attractiveness": 71}), encoding="utf-8")
    idx = tmp_path / project / "snapshots" / "index.json"
    index = json.loads(idx.read_text(encoding="utf-8"))
    index.append({"id": "2026-11-01", "tao_luc": "2026-11-01T00:00:00",
                  "artifacts": ["decision1.json"], "bao_cao": []})
    idx.write_text(json.dumps(index), encoding="utf-8")

    assert niche_bridge.tom_tat_overall(project)["diem_hap_dan"] == 71          # latest
    cu = niche_bridge.tom_tat_overall(project, "2026-08-18")
    assert cu["diem_hap_dan"] == 58 and cu["ds_snapshot"] == ["2026-08-18", "2026-11-01"]


def test_download_chi_file_trong_so(tmp_path):
    project = _seed(tmp_path)
    ok = niche_bridge.duong_bao_cao(project, "2026-08-18", "BAO-CAO-8-PHASE.html")
    assert ok is not None and ok.is_file()
    # file ngoài sổ index → chặn (kể cả khi cố path traversal)
    assert niche_bridge.duong_bao_cao(project, "2026-08-18", "decision1.json") is None
    assert niche_bridge.duong_bao_cao(project, "2026-08-18", "../../x.html") is None
