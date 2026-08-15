"""Test XÓA tài liệu (Kho tài liệu bước 2D — chỉ Owner): GỠ MỀM ưu tiên (đổi hiệu lực cả catalog +
Qdrant → hỏi-đáp bỏ qua) và XÓA CỨNG đường riêng xác nhận 2 lớp (xóa chunk Qdrant TRƯỚC → catalog →
chuyển file 99_Luu-tru). Qdrant lỗi khi xóa cứng → không xóa catalog (tránh tài liệu ma). Mock Qdrant."""

import csv
import os

os.environ["MOCK_MODE"] = "true"

from pathlib import Path

from fastapi.testclient import TestClient

from src.main import CATALOG_HEADER, app, client, doc_catalog


def _setup(tmp_path, monkeypatch):
    client._mock_chunks.clear(); client._mock_payload.clear()
    f = tmp_path / "users.txt"
    f.write_text("sep:mk:Kinh doanh:5\nnv:mk:Kinh doanh:2\n", encoding="utf-8")
    monkeypatch.setenv("USERS_FILE", str(f))
    kho = Path(os.environ["KHO_TAI_LIEU"])
    ngan = kho / "05_Kinh-doanh"; ngan.mkdir(parents=True, exist_ok=True)
    fpath = ngan / "2026-07-01_Kinh-doanh_Tai-lieu_v1.txt"
    fpath.write_text("noi dung tai lieu", encoding="utf-8")
    with (kho / "_catalog.csv").open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh); w.writerow(CATALOG_HEADER)
        w.writerow(["KD-DOC", "2026-07-01", "Tai lieu", "Kinh doanh", "Quy trình", "Còn hiệu lực",
                    "v1", "Giới hạn theo bộ phận", "2", "kw", "An", fpath.name, "05_Kinh-doanh",
                    "False", "KD-DOC", ""])
        w.writerow(["KD-KHAC", "2026-07-02", "Khac", "Kinh doanh", "Quy trình", "Còn hiệu lực",
                    "v1", "Giới hạn theo bộ phận", "2", "", "An", "khac.txt", "05_Kinh-doanh",
                    "False", "KD-KHAC", ""])   # tài liệu KHÁC — không bị đụng
    client._mock_chunks["KD-DOC"] = {0, 1, 2}
    client._mock_payload["KD-DOC"] = {"department": "Kinh doanh", "effective_status": "Còn hiệu lực",
                                      "access_level": "Giới hạn theo bộ phận", "min_level": 2}
    return kho, ngan, fpath


def _login(ten):
    c = TestClient(app); c.post("/dang-nhap", data={"ten": ten, "mat_khau": "mk"}); return c


def _dong(code):
    return next((d for d in doc_catalog() if d["Mã tài liệu"] == code), None)


# ─────────────── GỠ MỀM ───────────────

def test_go_mem_doi_hieu_luc_ca_catalog_va_qdrant(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    r = _login("sep").post("/kho-tai-lieu/go-mem", data={"doc_code": "KD-DOC"})
    assert r.status_code == 200 and r.json()["ok"]
    assert _dong("KD-DOC")["Hiệu lực"] == "Hết hiệu lực"                       # catalog
    assert client.doc_payload_mau("KD-DOC")["effective_status"] == "Hết hiệu lực"  # Qdrant payload
    # → hỏi-đáp lọc mặc định {"effective_status":"Còn hiệu lực"} sẽ bỏ qua; dữ liệu VẪN CÒN
    assert client.dem_chunk_doc_code("KD-DOC") == 3                            # chunk chưa bị xóa (khôi phục được)


def test_go_mem_non_owner_bi_tu_choi(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    r = _login("nv").post("/kho-tai-lieu/go-mem", data={"doc_code": "KD-DOC"})
    assert r.status_code == 403 and _dong("KD-DOC")["Hiệu lực"] == "Còn hiệu lực"


# ─────────────── XÓA CỨNG ───────────────

def test_xoa_cung_xoa_chunk_truoc_roi_catalog_roi_file(tmp_path, monkeypatch):
    kho, ngan, fpath = _setup(tmp_path, monkeypatch)
    r = _login("sep").post("/kho-tai-lieu/xoa-cung",
                           data={"doc_code": "KD-DOC", "xac_nhan_ma": "KD-DOC"})
    assert r.status_code == 200 and r.json()["ok"]
    assert client.dem_chunk_doc_code("KD-DOC") == 0        # chunk Qdrant đã xóa sạch
    assert _dong("KD-DOC") is None                          # dòng catalog đã xóa
    assert _dong("KD-KHAC") is not None                     # tài liệu KHÁC còn nguyên
    assert not fpath.exists()                               # file gốc đã rời ngăn
    daxoa = [p for p in (kho / "99_Luu-tru").glob("*") if p.name.startswith("DAXOA_KD-DOC")]
    assert daxoa and daxoa[0].read_text() == "noi dung tai lieu"   # file chuyển vào lưu trữ, còn nguyên


def test_xoa_cung_xac_nhan_sai_bi_chan_o_server(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    r = _login("sep").post("/kho-tai-lieu/xoa-cung",
                           data={"doc_code": "KD-DOC", "xac_nhan_ma": "SAI-MA"})
    assert r.status_code == 400                             # lớp 2 xác nhận kiểm ở server
    assert _dong("KD-DOC") is not None                      # KHÔNG xóa gì
    assert client.dem_chunk_doc_code("KD-DOC") == 3


def test_xoa_cung_qdrant_loi_thi_khong_xoa_catalog(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    def no(dc):
        raise RuntimeError("Qdrant sập")
    monkeypatch.setattr(client, "xoa_chunk_doc_code", no)
    r = _login("sep").post("/kho-tai-lieu/xoa-cung",
                           data={"doc_code": "KD-DOC", "xac_nhan_ma": "KD-DOC"})
    assert r.status_code == 500
    assert _dong("KD-DOC") is not None                      # Qdrant lỗi → DỪNG, catalog còn (tránh tài liệu ma)


def test_xoa_cung_non_owner_bi_tu_choi(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    r = _login("nv").post("/kho-tai-lieu/xoa-cung",
                          data={"doc_code": "KD-DOC", "xac_nhan_ma": "KD-DOC"})
    assert r.status_code == 403 and _dong("KD-DOC") is not None
