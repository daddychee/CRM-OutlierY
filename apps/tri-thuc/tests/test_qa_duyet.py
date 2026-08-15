"""Test khép Q&A bổ sung: route DUYỆT ghi kho (them_cap_qa) + hàm ghép gốc/Q&A ở kho tài liệu.
Mock hết (MOCK_MODE). Chỉ Owner; chặn ghi rác (rỗng / 'KHÔNG ĐỦ CƠ SỞ')."""

import csv
import os

os.environ["MOCK_MODE"] = "true"

from pathlib import Path

from fastapi.testclient import TestClient

from src.main import CATALOG_HEADER, app, client, doc_catalog, ghep_goc_qa


def _setup(tmp_path, monkeypatch):
    client._mock_chunks.clear(); client._mock_payload.clear()
    f = tmp_path / "users.txt"
    f.write_text("chu:mk:Kinh doanh:5\nnv:mk:Kinh doanh:2\n", encoding="utf-8")
    monkeypatch.setenv("USERS_FILE", str(f))
    kho = Path(os.environ["KHO_TAI_LIEU"])
    (kho / "05_Kinh-doanh").mkdir(parents=True, exist_ok=True)
    with (kho / "_catalog.csv").open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh); w.writerow(CATALOG_HEADER)
        w.writerow(["KD-1", "2026-07-01", "Quy trình bán hàng", "Kinh doanh", "Quy trình",
                    "Còn hiệu lực", "v1", "Giới hạn theo bộ phận", "3", "bán hàng", "An",
                    "goc.txt", "05_Kinh-doanh", "False", "KD-1", ""])
    return kho


def _login(ten):
    c = TestClient(app); c.post("/dang-nhap", data={"ten": ten, "mat_khau": "mk"}); return c


def _co_qa():
    return [d for d in doc_catalog() if d["Mã tài liệu"] == "KD-1-QA"]


# ─────────────── route DUYỆT ───────────────

def test_duyet_owner_ghi_qa_vao_kho(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    r = _login("chu").post("/kho-thieu/duyet-qa", data={
        "cau_hoi": "GA là gì?", "doc_code_goc": "KD-1",
        "cau_tra_loi": "GA là Google Analytics, dùng để đo lưu lượng."})
    assert r.status_code == 200
    j = r.json()
    assert j["ok"] and j["ma_qa"] == "KD-1-QA" and j["lan_dau"] is True
    assert len(_co_qa()) == 1                       # them_cap_qa ĐÃ chạy: dòng catalog Q&A xuất hiện
    assert client.dem_chunk_doc_code("KD-1-QA") >= 1


def test_duyet_cau_tra_loi_rong_422_khong_ghi(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    r = _login("chu").post("/kho-thieu/duyet-qa", data={
        "cau_hoi": "x?", "doc_code_goc": "KD-1", "cau_tra_loi": "   "})
    assert r.status_code == 422 and _co_qa() == []   # KHÔNG ghi Q&A rỗng


def test_duyet_khong_du_co_so_422_khong_ghi(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    r = _login("chu").post("/kho-thieu/duyet-qa", data={
        "cau_hoi": "x?", "doc_code_goc": "KD-1", "cau_tra_loi": "KHÔNG ĐỦ CƠ SỞ"})
    assert r.status_code == 422 and _co_qa() == []   # chặn ghi nháp vô nghĩa


def test_duyet_goc_khong_ton_tai_404(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    r = _login("chu").post("/kho-thieu/duyet-qa", data={
        "cau_hoi": "x?", "doc_code_goc": "KHONG-CO", "cau_tra_loi": "trả lời hợp lệ"})
    assert r.status_code == 404                       # them_cap_qa raise ValueError → 404


def test_duyet_non_owner_403(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    r = _login("nv").post("/kho-thieu/duyet-qa", data={
        "cau_hoi": "x?", "doc_code_goc": "KD-1", "cau_tra_loi": "trả lời hợp lệ"})
    assert r.status_code == 403 and _co_qa() == []    # yeu_cau_owner chặn ở SERVER


# ─────────────── ghép gốc + Q&A ở kho tài liệu ───────────────

def test_ghep_goc_qa_xep_qa_duoi_goc():
    rows = [{"Mã tài liệu": "KD-1", "Tiêu đề": "A"},
            {"Mã tài liệu": "KD-2", "Tiêu đề": "B"},
            {"Mã tài liệu": "KD-1-QA", "Tiêu đề": "Q&A A"}]
    out = ghep_goc_qa(rows)
    assert [(r["Mã tài liệu"], r["la_qa"]) for r in out] == [
        ("KD-1", False), ("KD-1-QA", True), ("KD-2", False)]   # Q&A ngay dưới gốc


def test_ghep_goc_qa_bo_qua_qa_mo_coi():
    rows = [{"Mã tài liệu": "KD-2", "Tiêu đề": "B"},
            {"Mã tài liệu": "KD-9-QA", "Tiêu đề": "Q&A mồ côi"}]
    out = ghep_goc_qa(rows)
    assert [r["Mã tài liệu"] for r in out] == ["KD-2"]         # gốc ngoài quyền → Q&A cũng ẩn
