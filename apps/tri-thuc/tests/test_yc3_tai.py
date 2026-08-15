"""Test YC3 — điểm liên quan + cờ bản đẹp trên nguồn, lọc ngưỡng gợi-ý-tải."""

import os

os.environ["MOCK_MODE"] = "true"

import csv
from pathlib import Path

from src.qa_pipeline import QAPipeline


def _chunk(ma, doc_id, similarity, rerank=None):
    c = {"content": "x", "document_id": doc_id, "document_keyword": f"{ma}.docx",
         "similarity": similarity,
         "document_metadata": {"doc_code": ma, "title": f"Tài liệu {ma}"}}
    if rerank is not None:
        c["rerank_score"] = rerank
    return c


def _ghi_catalog_ban_dep(ma, ten_pdf):
    kho = Path(os.environ["KHO_TAI_LIEU"])
    kho.mkdir(parents=True, exist_ok=True)
    with (kho / "_catalog.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["h"] * 16)
        w.writerow([ma] + [""] * 14 + [ten_pdf])


def test_diem_lien_quan_max_theo_tai_lieu_va_loc_nguong(monkeypatch):
    monkeypatch.setenv("NGUONG_GOI_Y_TAI", "0.7")
    nguon = QAPipeline._gom_nguon([
        _chunk("KD-1", "d1", 0.55),
        _chunk("KD-1", "d1", 0.92),          # cùng tài liệu — lấy MAX
        _chunk("KD-2", "d2", 0.40),          # dưới ngưỡng → không gợi ý tải
    ])
    theo_ma = {n["doc_code"]: n for n in nguon}
    assert theo_ma["KD-1"]["diem_lien_quan"] == 0.92
    assert theo_ma["KD-1"]["goi_y_tai"] is True
    assert theo_ma["KD-2"]["goi_y_tai"] is False
    assert len(nguon) == 2                    # vẫn đủ nguồn cho cơ chế ngầm


def test_uu_tien_rerank_score_khi_co(monkeypatch):
    monkeypatch.setenv("NGUONG_GOI_Y_TAI", "0.5")
    nguon = QAPipeline._gom_nguon([_chunk("KD-1", "d1", 0.2, rerank=0.9)])
    assert nguon[0]["diem_lien_quan"] == 0.9 and nguon[0]["goi_y_tai"] is True


def test_co_ban_dep_tra_tu_catalog():
    _ghi_catalog_ban_dep("KD-1", "a_ban-dep.pdf")
    nguon = QAPipeline._gom_nguon([_chunk("KD-1", "d1", 0.9), _chunk("KD-2", "d2", 0.9)])
    theo_ma = {n["doc_code"]: n for n in nguon}
    assert theo_ma["KD-1"]["co_ban_dep"] is True
    assert theo_ma["KD-2"]["co_ban_dep"] is False   # không có dòng catalog


def test_khong_catalog_khong_vo():
    nguon = QAPipeline._gom_nguon([_chunk("KD-1", "d1", 0.9)])
    assert nguon[0]["co_ban_dep"] is False           # thiếu catalog → coi như chưa có


# ---- route GET /tai-ban-goc/{doc_code} — RBAC y hệt /tai-ban-dep, 404 lặng lẽ ----

from fastapi.testclient import TestClient

from src.main import app, ghi_catalog


def _users_file(tmp_path, monkeypatch):
    f = tmp_path / "users.txt"
    f.write_text("ql:mk:Kinh doanh:4\nnv:mk:Kinh doanh:2\n", encoding="utf-8")
    monkeypatch.setenv("USERS_FILE", str(f))


def _dang_nhap(ten):
    c = TestClient(app)
    c.post("/dang-nhap", data={"ten": ten, "mat_khau": "mk"})
    return c


def _chuan_bi_ban_goc(doc_code="KD-2026-0099", ngan="05_Kinh-doanh"):
    kho = Path(os.environ["KHO_TAI_LIEU"])
    (kho / ngan).mkdir(parents=True, exist_ok=True)
    (kho / ngan / "goc.docx").write_bytes(b"GOC-DOCX")
    ghi_catalog(kho, [doc_code] + [""] * 10 + ["goc.docx", ngan, "", "", ""])


def test_tai_ban_goc_dung_quyen(tmp_path, monkeypatch):
    _users_file(tmp_path, monkeypatch)
    _chuan_bi_ban_goc()                                      # 0099 = Mật min4 (kho mock)
    r = _dang_nhap("ql").get("/tai-ban-goc/KD-2026-0099")    # Manager KD → được
    assert r.status_code == 200 and r.content == b"GOC-DOCX"


def test_tai_ban_goc_thieu_level_404(tmp_path, monkeypatch):
    _users_file(tmp_path, monkeypatch)
    _chuan_bi_ban_goc()
    assert _dang_nhap("nv").get("/tai-ban-goc/KD-2026-0099").status_code == 404


def test_tai_ban_goc_khong_file_404(tmp_path, monkeypatch):
    _users_file(tmp_path, monkeypatch)                       # có quyền nhưng không catalog/file
    assert _dang_nhap("nv").get("/tai-ban-goc/KD-2026-0042").status_code == 404
    assert _dang_nhap("nv").get("/tai-ban-goc/XX-LA").status_code == 404
