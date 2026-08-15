"""Test CẬP NHẬT NỘI DUNG tài liệu bằng file mới (Kho tài liệu bước 2B — chỉ Owner, chạm truy xuất).
Van chống lệch: Qdrant TRƯỚC (xóa sạch chunk cũ theo doc_code rồi nạp mới — chống chunk mồ côi),
catalog SAU (chỉ khi Qdrant OK). File cũ chuyển vào 99_Luu-tru, KHÔNG xóa. doc_code BẤT BIẾN.
Mock lớp Qdrant (như test dự án); .txt để _cat_doan đếm chunk không cần API."""

import csv
import os

os.environ["MOCK_MODE"] = "true"

from pathlib import Path

from fastapi.testclient import TestClient

from src.main import CATALOG_HEADER, app, client, doc_catalog


def _setup(tmp_path, monkeypatch):
    client._mock_chunks.clear()                       # reset store chunk mock của client toàn cục
    # V2: không còn USERS_FILE — claims thay đăng nhập (giữ chữ ký call-site)
    kho = Path(os.environ["KHO_TAI_LIEU"])
    ngan = kho / "05_Kinh-doanh"; ngan.mkdir(parents=True, exist_ok=True)
    old = ngan / "2026-07-01_Kinh-doanh_Tai-lieu_v1.txt"
    old.write_text("noi dung cu. cau hai cu.", encoding="utf-8")
    with (kho / "_catalog.csv").open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh); w.writerow(CATALOG_HEADER)
        w.writerow(["KD-DOC", "2026-07-01", "Tai lieu", "Kinh doanh", "Quy trình", "Còn hiệu lực",
                    "v1", "Giới hạn theo bộ phận", "2", "tu-khoa", "An", old.name, "05_Kinh-doanh",
                    "False", "KD-DOC", ""])
    return kho, ngan, old


from claims_v2 import client_claims

HO_SO = {"sep": ("Kinh doanh", 5), "nv": ("Kinh doanh", 2)}


def _login(ten):
    return client_claims(app, ten, *HO_SO[ten])


def _dong(code):
    return next((d for d in doc_catalog() if d["Mã tài liệu"] == code), None)


def test_owner_cap_nhat_tang_phien_ban_doc_code_bat_bien(tmp_path, monkeypatch):
    kho, ngan, old = _setup(tmp_path, monkeypatch)
    r = _login("sep").post("/kho-tai-lieu/cap-nhat-noi-dung",
                           files={"file": ("moi.txt", b"noi dung moi hoan toan. cau hai moi.")},
                           data={"doc_code": "KD-DOC"})
    assert r.status_code == 200 and r.json()["ok"]
    row = _dong("KD-DOC")
    assert row["Phiên bản"] == "v2"                   # v1 → v2
    assert row["Mã tài liệu"] == "KD-DOC" and row["document_id"] == "KD-DOC"   # doc_code BẤT BIẾN
    assert "v2" in row["Tên file mới"]                # tên file mới phản ánh phiên bản


def test_file_cu_vao_luu_tru_khong_bi_xoa(tmp_path, monkeypatch):
    kho, ngan, old = _setup(tmp_path, monkeypatch)
    noi_dung_cu = old.read_bytes()
    _login("sep").post("/kho-tai-lieu/cap-nhat-noi-dung",
                       files={"file": ("moi.txt", b"abc mot. def hai.")}, data={"doc_code": "KD-DOC"})
    archived = [p for p in (kho / "99_Luu-tru").glob("*") if "KD-DOC" in p.name and "v1" in p.name]
    assert archived, "file cũ phải nằm trong 99_Luu-tru"
    assert archived[0].read_bytes() == noi_dung_cu    # bản cũ CÒN NGUYÊN, không bị xóa/hỏng
    assert not old.exists()                           # đã chuyển khỏi ngăn (vào lưu trữ)


def test_chunk_cu_xoa_sach_khong_mo_coi(tmp_path, monkeypatch):
    kho, ngan, old = _setup(tmp_path, monkeypatch)
    client._mock_chunks["KD-DOC"] = {0, 1, 2, 3, 4}   # giả lập tài liệu cũ có 5 chunk trong Qdrant
    _login("sep").post("/kho-tai-lieu/cap-nhat-noi-dung",
                       files={"file": ("moi.txt", b"mot cau ngan thoi.")},  # file mới CHỈ 1 chunk
                       data={"doc_code": "KD-DOC"})
    # xóa sạch 5 chunk cũ theo doc_code TRƯỚC → chỉ còn 1 chunk mới, KHÔNG còn 4 chunk mồ côi
    assert client.dem_chunk_doc_code("KD-DOC") == 1


def test_payload_chunk_moi_giu_dung_quyen_cu(tmp_path, monkeypatch):
    kho, ngan, old = _setup(tmp_path, monkeypatch)
    cap = {}
    orig = client.upload_document
    monkeypatch.setattr(client, "upload_document", lambda fp, md: (cap.update(md), orig(fp, md))[1])
    _login("sep").post("/kho-tai-lieu/cap-nhat-noi-dung",
                       files={"file": ("moi.txt", b"noi dung moi. cau hai.")}, data={"doc_code": "KD-DOC"})
    # cập nhật nội dung KHÔNG đổi quyền: payload chunk mới giữ đúng bộ phận/level/hiệu lực/mức truy cập cũ
    assert cap["department"] == "Kinh doanh" and cap["min_level"] == 2
    assert cap["effective_status"] == "Còn hiệu lực" and cap["access_level"] == "Giới hạn theo bộ phận"
    assert cap["doc_code"] == "KD-DOC" and cap["version"] == "v2"   # doc_code cũ + version mới


def test_qdrant_loi_thi_catalog_khong_cap_nhat(tmp_path, monkeypatch):
    kho, ngan, old = _setup(tmp_path, monkeypatch)
    def no(*a, **k):
        raise RuntimeError("Qdrant sập")
    monkeypatch.setattr(client, "cap_nhat_noi_dung", no)
    r = _login("sep").post("/kho-tai-lieu/cap-nhat-noi-dung",
                           files={"file": ("moi.txt", b"abc. def.")}, data={"doc_code": "KD-DOC"})
    assert r.status_code == 422
    assert _dong("KD-DOC")["Phiên bản"] == "v1"       # Qdrant lỗi → CHƯA đổi catalog (chống lệch)
    assert old.exists()                               # file cũ vẫn còn (không mất dữ liệu)


def test_non_owner_bi_route_tu_choi(tmp_path, monkeypatch):
    kho, ngan, old = _setup(tmp_path, monkeypatch)
    r = _login("nv").post("/kho-tai-lieu/cap-nhat-noi-dung",
                          files={"file": ("moi.txt", b"abc. def.")}, data={"doc_code": "KD-DOC"})
    assert r.status_code == 403                        # yeu_cau_owner chặn ở SERVER
    assert _dong("KD-DOC")["Phiên bản"] == "v1" and old.exists()   # không đổi gì


def test_scan_khong_co_chu_khong_xoa_noi_dung_cu(tmp_path, monkeypatch):
    kho, ngan, old = _setup(tmp_path, monkeypatch)
    client._mock_chunks["KD-DOC"] = {0, 1, 2}         # có nội dung cũ
    r = _login("sep").post("/kho-tai-lieu/cap-nhat-noi-dung",
                           files={"file": ("moi.txt", b"   ")},   # file rỗng chữ → 0 chunk
                           data={"doc_code": "KD-DOC"})
    assert r.status_code == 422                        # van an toàn: raise TRƯỚC khi xóa
    assert client.dem_chunk_doc_code("KD-DOC") == 3    # chunk cũ KHÔNG bị xóa
    assert _dong("KD-DOC")["Phiên bản"] == "v1"        # catalog không đổi
