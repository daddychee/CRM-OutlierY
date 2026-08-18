# -*- coding: utf-8 -*-
"""Test trang /niche (dashboard gộp) — danh bạ mock qua monkeypatch, dữ liệu tmp."""
import json

import pytest
from fastapi.testclient import TestClient

from src import dashboard
from src.main import app
from tests.test_niche_bridge import _seed

CLAIMS = {"X-Remote-User": "tester", "X-Remote-Level": "2"}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    project = _seed(tmp_path)                      # snapshot giả 2026-08-18, điểm 58
    monkeypatch.setenv("NICHE_PROJECTS_DIR", str(tmp_path))
    map_path = tmp_path / "niche_projects.json"
    map_path.write_text(json.dumps({"N-TEST": {"TT-US": project}}), encoding="utf-8")
    monkeypatch.setenv("NICHE_PROJECTS_MAP", str(map_path))
    monkeypatch.setattr(dashboard, "_ds_ngach",
                        lambda: [{"ma": "N-TEST", "ten_chuan": "TEST NICHE"}])
    monkeypatch.setattr(dashboard, "_ds_kenh",
                        lambda ma: [{"ma": "K-A", "ten_chuan": "KENH A",
                                     "ngach_ma": ma, "thi_truong_ma": "TT-US"}])
    monkeypatch.setattr(dashboard, "_ten_thi_truong", lambda: {"TT-US": "US"})
    return TestClient(app)


def test_khong_claims_401(client):
    assert client.get("/niche").status_code == 401


def test_overall_hien_tile_va_kenh(client):
    r = client.get("/niche", headers=CLAIMS)
    assert r.status_code == 200
    body = r.text
    assert "TEST NICHE" in body and "KENH A" in body        # rail: niche + kênh
    assert "58" in body and "3.071" in body                  # tile số thật từ snapshot
    assert "VÀO CÓ ĐIỀU KIỆN" in body                        # verdict tiếng Việt
    assert "Read report" in body and "New report" in body    # button tiếng Anh
    assert "hidden" in body and "iraq" in body               # Best & Worst cụm


def test_overall_banner_pills_strip(client):
    """Nội dung báo cáo gộp kéo ra overview (user chốt 18/08): banner phán quyết +
    pill thị trường + dải tổng quan số pipeline."""
    body = client.get("/niche", headers=CLAIMS).text
    assert "PHÁN QUYẾT" in body and "Vào có điều kiện" in body
    assert "Tổng quan số của pipeline" in body and "3.815" in body and "12.869" in body
    assert 'class="nd-pill on"' in body            # pill All active mặc định
    assert "chênh 42× trung vị" in body            # số dẫn xuất PY tính
    b2 = client.get("/niche", headers=CLAIMS,
                    params={"ngach": "N-TEST", "tt": "TT-US"})
    assert b2.status_code == 200 and "TEST NICHE" in b2.text


def test_xem_lai_ngay_cu(client):
    r = client.get("/niche", headers=CLAIMS, params={"ngach": "N-TEST", "ngay": "2026-08-18"})
    assert r.status_code == 200 and "snapshot 2026-08-18" in r.text


def test_doc_va_tai_bao_cao(client):
    ok = client.get("/niche/tai/TestNiche_US/2026-08-18/BAO-CAO-8-PHASE.html",
                    headers=CLAIMS, params={"inline": 1})
    assert ok.status_code == 200 and "text/html" in ok.headers["content-type"]
    assert "content-disposition" not in ok.headers or "attachment" not in ok.headers.get("content-disposition", "")
    tai = client.get("/niche/tai/TestNiche_US/2026-08-18/BAO-CAO-8-PHASE.html", headers=CLAIMS)
    assert "attachment" in tai.headers.get("content-disposition", "")
    # file ngoài sổ snapshot → 404 lặng lẽ
    assert client.get("/niche/tai/TestNiche_US/2026-08-18/decision1.json",
                      headers=CLAIMS).status_code == 404


# ---------- pane KÊNH ----------

def _seed_kenh(monkeypatch, co_report=True):
    from src.bao_cao_lich_su import luu_bao_cao
    monkeypatch.setattr(dashboard, "_kenh_theo_ma",
                        lambda ma: {"ma": "K-A", "ten_chuan": "KENH A", "bi_danh": "kenh-alias",
                                    "ngach_ma": "N-TEST", "thi_truong_ma": "TT-US"}
                        if ma == "K-A" else None)
    if co_report:
        luu_bao_cao("tester", {
            "id": "r-cu", "ten_file_goc": "cu.csv", "ten_bao_cao": "Tuần 33",
            "ten_kenh": "Kenh A", "duong_dan_goc": "/khong/co",
            "kenh": {"tang_vo": "retention", "so_video": 14,
                     "metrics_chinh": {"ctr": 0.046, "retention": 0.24, "views": 412680}},
        }, "2026-08-10T00:00:00")
        luu_bao_cao("tester", {
            "id": "r-moi", "ten_file_goc": "moi.csv", "ten_bao_cao": "Tuần 34",
            "ten_kenh": "KENH  A",                 # lệch hoa/khoảng trắng — phải vẫn khớp
            "duong_dan_goc": "/khong/co",
            "kenh": {"tang_vo": "ctr", "so_video": 15,
                     "metrics_chinh": {"ctr": 0.051, "retention": 0.26, "views": 500000}},
        }, "2026-08-17T00:00:00")


def test_kenh_pane_tile_va_benchmark(client, monkeypatch):
    _seed_kenh(monkeypatch)
    r = client.get("/niche/kenh/K-A", headers=CLAIMS)
    assert r.status_code == 200
    body = r.text
    assert "KENH A" in body and "Tuần 34" in body            # bản mới nhất mặc định
    assert "500.000" in body and "5.1%" in body               # tile từ metrics_chinh
    assert "Full analysis" in body
    assert "3.071" in body and "128.885" in body              # dải so-ngách từ snapshot niche
    assert "chỉ hiện số tóm tắt" in body                      # file gốc không có → lý do, không vỡ
    assert "— 💰" in body or "chưa bật kiếm tiền" in body     # tile doanh thu van chống bịa


def test_kenh_pane_xem_report_cu(client, monkeypatch):
    _seed_kenh(monkeypatch)
    r = client.get("/niche/kenh/K-A", headers=CLAIMS, params={"id": "r-cu"})
    assert r.status_code == 200 and "Tuần 33" in r.text and "412.680" in r.text


def test_kenh_chua_co_report(client, monkeypatch):
    _seed_kenh(monkeypatch, co_report=False)
    r = client.get("/niche/kenh/K-A", headers=CLAIMS)
    assert r.status_code == 200 and "Chưa có report nào gắn tên kênh" in r.text


def test_kenh_khong_ton_tai_404(client, monkeypatch):
    _seed_kenh(monkeypatch, co_report=False)
    assert client.get("/niche/kenh/K-XYZ", headers=CLAIMS).status_code == 404


# ---------- PA2: một mặt tiền ----------

def test_chan_doan_phuc_vu_thang_dashboard(client):
    # Alias cấp-1 của gateway /data-analytics trỏ 'chan-doan' — /niche KHÔNG tồn tại
    # ở cấp gốc gateway, nên GET /chan-doan phải phục vụ THẲNG dashboard (không 303).
    r = client.get("/chan-doan", headers=CLAIMS)
    assert r.status_code == 200
    assert 'id="nrk-kenh"' in r.text and "TEST NICHE" in r.text


def test_modal_co_form_kenh_tu_danh_ba(client):
    body = client.get("/niche", headers=CLAIMS).text
    assert 'id="nrk-kenh"' in body and "KENH A" in body       # select kênh từ danh bạ
    assert 'id="nrk-file"' in body and "Diagnose" in body     # form nạp trong modal
    assert 'href="/chan-doan"' not in body                     # hết link sang trang cũ


def test_dieu_huong_tren_dau_khong_con_rail(client):
    # User chốt 18/08: bỏ rail trong, điều hướng để TRÊN ĐẦU như tab General.
    body = client.get("/niche", headers=CLAIMS).text
    assert 'class="nd-top"' in body and "nd-rail" not in body
    assert 'class="nd-tab on"' in body                         # tab Overall đang active


def test_niche_chua_gan_project(client, tmp_path, monkeypatch):
    monkeypatch.setattr(dashboard, "_ds_ngach",
                        lambda: [{"ma": "N-KHAC", "ten_chuan": "NICHE TRỐNG"}])
    r = client.get("/niche", headers=CLAIMS, params={"ngach": "N-KHAC"})
    assert r.status_code == 200 and "chưa gán dự án" in r.text
