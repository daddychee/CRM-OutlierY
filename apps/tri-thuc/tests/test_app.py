"""Test module nhập liệu FastAPI (chế độ mock) — chạy: pytest"""

import os

os.environ["MOCK_MODE"] = "true"  # ép mock TRƯỚC khi import app

from fastapi.testclient import TestClient

from src.main import app
from claims_v2 import client_claims

# V2: '/' + /upload cần claims Manager+ (hệ cũ chạy chế độ mở khi chưa có users.txt)
tc = client_claims(app, "sep", "Kinh doanh", 5)


def _form_hop_le():
    return {
        "title": "Quy trình đăng video test",
        "keywords": "đăng video, SEO",
        "owner": "Thành",
        "version": "v1",
        "department": "Kinh doanh",
        "doc_type": "Quy trình",
        "effective_status": "Còn hiệu lực",
        "access_level": "Công khai nội bộ",
        "min_level": "2",
    }


def test_trang_chu_tra_ve_200_va_co_dropdown():
    r = tc.get("/")
    assert r.status_code == 200
    assert "Department" in r.text and "Kinh doanh" in r.text


def test_upload_mock_tra_ve_document_id():
    r = tc.post("/upload", data=_form_hop_le(),
                files={"file": ("test.docx", b"noi dung thu")})
    assert r.status_code == 200
    body = r.json()
    assert body["document_id"].startswith("doc-mock-")
    assert body["doc_code"].startswith("KD-")
    assert "message" in body


def test_upload_chan_gia_tri_ngoai_dropdown():
    data = _form_hop_le() | {"department": "Phòng không tồn tại"}
    r = tc.post("/upload", data=data, files={"file": ("t.docx", b"x")})
    assert r.status_code == 422


def test_upload_thieu_file_bi_chan():
    r = tc.post("/upload", data=_form_hop_le())
    assert r.status_code == 422
