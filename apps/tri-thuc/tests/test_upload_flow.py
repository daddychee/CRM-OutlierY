"""Test luồng nhập liệu đầy đủ: scan → đổi tên → chép ngăn → catalog (chế độ mock)."""

import csv
import io
import os
from datetime import date
from pathlib import Path

os.environ["MOCK_MODE"] = "true"  # ép mock TRƯỚC khi import app

from fastapi.testclient import TestClient
from pypdf import PdfWriter

from src.main import app

tc = TestClient(app)


def _form(**thay):
    d = {
        "title": "Quy trình đăng video",
        "keywords": "đăng video",
        "owner": "Thành",
        "version": "v1",
        "department": "Kinh doanh",
        "doc_type": "Quy trình",
        "effective_status": "Còn hiệu lực",
        "access_level": "Công khai nội bộ",
        "min_level": "2",
    }
    d.update(thay)
    return d


def _kho():
    return Path(os.environ["KHO_TAI_LIEU"])  # conftest trỏ vào thư mục tạm riêng mỗi test


def test_txt_nhap_ok_dung_ngan_va_co_dong_catalog():
    r = tc.post("/upload", data=_form(),
                files={"file": ("ghi-chu.txt", "nội dung thử".encode())})
    assert r.status_code == 200
    body = r.json()

    ten_mong_doi = f"{date.today():%Y-%m-%d}_KinhDoanh_Quy-Trinh-Dang-Video_v1.txt"
    assert body["new_filename"] == ten_mong_doi
    assert body["folder"] == "05_Kinh-doanh"
    assert body["warning"] is None
    assert (_kho() / "05_Kinh-doanh" / ten_mong_doi).is_file()

    with (_kho() / "_catalog.csv").open(encoding="utf-8-sig") as f:
        dong = list(csv.reader(f))
    assert len(dong) == 2  # header + đúng 1 dòng
    assert body["doc_code"] in dong[1] and body["document_id"] in dong[1]


def test_trung_ten_khong_ghi_de():
    r1 = tc.post("/upload", data=_form(), files={"file": ("a.txt", b"ban 1")})
    r2 = tc.post("/upload", data=_form(), files={"file": ("a.txt", b"ban 2")})
    ten1, ten2 = r1.json()["new_filename"], r2.json()["new_filename"]
    assert ten1 != ten2 and ten2.endswith("-2.txt")
    ngan = _kho() / "05_Kinh-doanh"
    assert (ngan / ten1).read_bytes() == b"ban 1"  # ban dau con nguyen
    assert (ngan / ten2).read_bytes() == b"ban 2"


def test_pdf_scan_van_nhap_nhung_co_canh_bao():
    buf = io.BytesIO()
    w = PdfWriter()
    w.add_blank_page(width=200, height=200)  # PDF không có lớp chữ = scan
    w.write(buf)
    r = tc.post("/upload", data=_form(title="Báo cáo scan"),
                files={"file": ("scan.pdf", buf.getvalue())})
    assert r.status_code == 200
    body = r.json()
    assert body["warning"] and "scan" in body["warning"].lower()

    with (_kho() / "_catalog.csv").open(encoding="utf-8-sig") as f:
        dong_cuoi = list(csv.reader(f))[-1]
    assert "true" in dong_cuoi  # cột "PDF scan"


def test_ten_bo_dau_dung_khuon():
    r = tc.post("/upload",
                data=_form(title="Hướng dẫn xuất video",
                           department="Vận hành - Sản xuất", version="v2"),
                files={"file": ("hd.docx", b"x")})
    body = r.json()
    assert body["new_filename"] == \
        f"{date.today():%Y-%m-%d}_VanHanhSanXuat_Huong-Dan-Xuat-Video_v2.docx"
    assert body["folder"] == "04_Van-hanh-San-xuat"
