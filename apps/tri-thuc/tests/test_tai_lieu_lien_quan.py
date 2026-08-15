"""Test TÀI LIỆU LIÊN QUAN — bản rẻ (user chốt 07/08): vector similarity thuần, tính lúc
nạp tài liệu mới, lưu BỀN vào tai_lieu_lien_quan.json (khác quan hệ nhất thời lúc trả lời
câu hỏi). Không gọi LLM — dùng GiaClient giả lập search() để kiểm định soát ngưỡng/loại trừ
CHÍNH XÁC, độc lập với dữ liệu mock của vector_client."""

import json
import os

os.environ["MOCK_MODE"] = "true"

from pathlib import Path

from fastapi.testclient import TestClient

import src.tai_lieu_lien_quan as L
from src.main import CATALOG_HEADER, app, client, doc_catalog


class GiaClient:
    """Client giả: search() trả đúng danh sách chunk được cấu hình, bất kể query/filters —
    để test threshold/loại trừ tách bạch khỏi nội dung _MOCK_CHUNKS thật."""

    def __init__(self, chunks):
        self._chunks = chunks

    def search(self, query, filters=None, user=None):
        return self._chunks


def _chunk(ma, diem, title="T"):
    return {"similarity": diem, "document_id": ma,
            "document_metadata": {"doc_code": ma, "title": title}}


def test_tinh_va_luu_giu_dung_nguong_va_top_k(tmp_path, monkeypatch):
    monkeypatch.setenv("NGUONG_LIEN_QUAN_TAI_LIEU", "0.3")
    gc = GiaClient([_chunk("KD-1", 0.9, "Cao nhất"), _chunk("KD-2", 0.5, "Vừa"),
                    _chunk("KD-3", 0.2, "Dưới ngưỡng — loại")])
    ds = L.tinh_va_luu_lien_quan("KD-MOI", "Chủ đề", "tu khoa", gc, kho=tmp_path, so_luong=5)
    assert [d["ma"] for d in ds] == ["KD-1", "KD-2"]         # dưới ngưỡng bị loại
    assert L.doc_lien_quan("KD-MOI", kho=tmp_path) == ds     # đọc lại đúng đã ghi


def test_tinh_va_luu_top_k_gioi_han_so_luong(tmp_path):
    gc = GiaClient([_chunk(f"KD-{i}", 0.9 - i * 0.01) for i in range(10)])
    ds = L.tinh_va_luu_lien_quan("KD-MOI", "Chủ đề", "", gc, kho=tmp_path, so_luong=3)
    assert len(ds) == 3 and ds[0]["ma"] == "KD-0"            # điểm cao nhất đứng đầu


def test_tinh_va_luu_loai_tru_chinh_no_va_ho_qa_pt(tmp_path):
    """Không 'phát hiện lại' quan hệ đã TƯỜNG MINH qua cấu trúc cha-con (-QA/-PT của
    chính tài liệu đang tính) — tránh liệt kê thứ đã biết rồi."""
    gc = GiaClient([_chunk("KD-1", 0.9), _chunk("KD-1-QA", 0.85), _chunk("KD-1-PT", 0.8),
                    _chunk("KD-2", 0.7)])
    ds = L.tinh_va_luu_lien_quan("KD-1", "Chủ đề", "", gc, kho=tmp_path)
    assert [d["ma"] for d in ds] == ["KD-2"]


def test_tinh_va_luu_query_rong_khong_goi_search_ghi_rong(tmp_path):
    class NoCall(GiaClient):
        def search(self, *a, **k):
            raise AssertionError("Query rỗng thì KHÔNG được gọi search")
    ds = L.tinh_va_luu_lien_quan("KD-MOI", "  ", "  ", NoCall([]), kho=tmp_path)
    assert ds == [] and L.doc_lien_quan("KD-MOI", kho=tmp_path) == []


def test_tinh_va_luu_ghi_de_khong_noi_dong(tmp_path):
    gc1 = GiaClient([_chunk("KD-1", 0.9)])
    L.tinh_va_luu_lien_quan("KD-MOI", "A", "", gc1, kho=tmp_path)
    gc2 = GiaClient([_chunk("KD-2", 0.9)])
    ds = L.tinh_va_luu_lien_quan("KD-MOI", "A", "", gc2, kho=tmp_path)
    assert [d["ma"] for d in ds] == ["KD-2"]                 # lần tính mới THAY, không cộng dồn


def test_khong_du_nguong_xoa_khoi_file_khong_de_lai_rac(tmp_path):
    gc_co = GiaClient([_chunk("KD-1", 0.9)])
    L.tinh_va_luu_lien_quan("KD-MOI", "A", "", gc_co, kho=tmp_path)
    assert L._doc_toan_bo(tmp_path) == {"KD-MOI": [{"ma": "KD-1", "tieu_de": "T", "diem": 0.9}]}
    gc_rong = GiaClient([_chunk("KD-1", 0.1)])               # giờ dưới ngưỡng hết
    L.tinh_va_luu_lien_quan("KD-MOI", "A", "", gc_rong, kho=tmp_path)
    assert "KD-MOI" not in L._doc_toan_bo(tmp_path)           # không để lại mục rỗng


# ─────────────── tích hợp: /upload tính + lưu, /kho-tai-lieu hiển thị có lọc RBAC ───────────────

def _login(tmp_path, monkeypatch, dong):
    # V2: claims thay users.txt — 'dong' giữ khuôn cũ ten:mk:bo_phan:level, parse ra claims
    from claims_v2 import client_claims
    ten, _, bo_phan, level = dong.strip().splitlines()[0].split(":")
    return client_claims(app, ten, bo_phan, int(level))


def test_upload_tinh_lien_quan_va_ghi_file(tmp_path, monkeypatch):
    c = _login(tmp_path, monkeypatch, "sep:mk:Kinh doanh:5\n")
    r = c.post("/upload", data={
        "title": "Tài liệu mới", "keywords": "quy trình", "department": "Kinh doanh",
        "doc_type": "Quy trình", "effective_status": "Còn hiệu lực",
        "access_level": "Công khai nội bộ", "min_level": "1"},
        files={"file": ("t.txt", b"noi dung")})
    assert r.status_code == 200
    doc_code = r.json()["doc_code"]
    f = Path(os.environ["KHO_TAI_LIEU"]) / "tai_lieu_lien_quan.json"
    assert f.is_file()
    du_lieu = json.loads(f.read_text(encoding="utf-8"))
    # mock chunk trả về khớp filter effective_status="Còn hiệu lực" → có liên quan (mock có sẵn)
    assert doc_code in du_lieu and du_lieu[doc_code]


def test_kho_tai_lieu_hien_lien_quan_loc_theo_rbac(tmp_path, monkeypatch):
    """Tài liệu liên quan CHỈ hiện những mã mà NGƯỜI ĐANG XEM cũng thấy được — không lộ
    tài liệu vượt quyền qua đường 'liên quan' dù quan hệ được TÍNH không lọc quyền."""
    import csv

    # V2: không còn USERS_FILE — _login parse 'dong' ra claims
    kho = Path(os.environ["KHO_TAI_LIEU"])
    kho.mkdir(parents=True, exist_ok=True)
    with (kho / "_catalog.csv").open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh); w.writerow(CATALOG_HEADER)
        w.writerow(["KD-A", "2026-08-07", "Tài liệu A", "Kinh doanh", "Quy trình",
                    "Còn hiệu lực", "v1", "Công khai nội bộ", "1", "", "An",
                    "KD-A.md", "05_Kinh-doanh", "false", "KD-A", "", "noi_bo", "Official"])
        w.writerow(["KD-B", "2026-08-07", "Tài liệu B — chỉ Manager", "Kinh doanh", "Quy trình",
                    "Còn hiệu lực", "v1", "Mật", "4", "", "An",
                    "KD-B.md", "05_Kinh-doanh", "false", "KD-B", "", "noi_bo", "Official"])
    d = json.dumps({"KD-A": [{"ma": "KD-B", "tieu_de": "Tài liệu B — chỉ Manager", "diem": 0.9}]},
                   ensure_ascii=False)
    (kho / "tai_lieu_lien_quan.json").write_text(d, encoding="utf-8")

    r_owner = _login(tmp_path, monkeypatch, "sep:mk:Kinh doanh:5\n").get("/kho-tai-lieu")
    assert "Tài liệu B" in r_owner.text                      # Owner thấy quan hệ đủ quyền
    r_nv = _login(tmp_path, monkeypatch, "nv:mk:Kinh doanh:2\n").get("/kho-tai-lieu")
    assert "chỉ Manager" not in r_nv.text                    # NV level 2 không thấy KD-B → ẩn luôn quan hệ
