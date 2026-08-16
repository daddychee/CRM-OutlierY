"""Test gợi ý từ khóa nhất quán (Ý 2 Đợt 3) — gom từ payload + endpoint phân quyền."""

import os

os.environ["MOCK_MODE"] = "true"  # ép mock TRƯỚC khi import app

from types import SimpleNamespace

from fastapi.testclient import TestClient

from src.main import app
from src.tu_khoa import TU_KHOA_MAU, lay_tu_khoa_da_co

# V2: claims từ gateway thay users.txt — bảng bộ phận×level giữ nguyên ý cũ.
from claims_v2 import client_claims

HO_SO = {"ql": ("Kinh doanh", 4), "nv": ("Kinh doanh", 2)}


def _users_file(tmp_path, monkeypatch):
    """V2: không còn USERS_FILE — giữ chữ ký để call-site cũ nguyên vẹn (no-op)."""


def _dang_nhap(ten):
    return client_claims(app, ten, *HO_SO[ten])


def test_lay_tu_khoa_gom_tach_dedup_xep_tan_suat():
    """Tách chuỗi phẩy/chấm phẩy; chunk cùng tài liệu không đếm thêm; bỏ trùng
    hoa-thường nhưng giữ cách viết phổ biến nhất; từ hay dùng lên đầu."""
    diem = [
        SimpleNamespace(payload={"doc_code": "D1", "keywords": "Ngâm kênh, AdSense"}),
        SimpleNamespace(payload={"doc_code": "D1", "keywords": "Ngâm kênh, AdSense"}),
        SimpleNamespace(payload={"doc_code": "D2", "keywords": "ngâm kênh; kiếm tiền"}),
        SimpleNamespace(payload={"doc_code": "D3", "keywords": " ngâm kênh "}),
        SimpleNamespace(payload={"doc_code": "D4", "keywords": ""}),      # rỗng — bỏ qua
        SimpleNamespace(payload={"doc_code": "D5"}),                       # thiếu keywords
    ]
    rag = SimpleNamespace(mock=False,
                          client=SimpleNamespace(scroll=lambda *a, **k: (diem, None)))
    kq = lay_tu_khoa_da_co(rag)
    assert kq[0] == "ngâm kênh"                    # 3 tài liệu dùng; "ngâm kênh" 2 doc > "Ngâm kênh" 1
    assert set(kq) == {"ngâm kênh", "AdSense", "kiếm tiền"}   # dedup hoa-thường, 3 từ riêng


def test_tu_khoa_mock_tra_mau():
    assert lay_tu_khoa_da_co(SimpleNamespace(mock=True)) == TU_KHOA_MAU


def test_endpoint_goi_y_chi_manager(tmp_path, monkeypatch):
    _users_file(tmp_path, monkeypatch)
    r = _dang_nhap("ql").get("/tu-khoa-goi-y")     # Manager 4 → 200, app mock → list mẫu
    assert r.status_code == 200 and r.json() == TU_KHOA_MAU
    assert _dang_nhap("nv").get("/tu-khoa-goi-y").status_code == 403   # level 2 → chặn


def test_upload_van_nhan_keywords_chuoi():
    """Backward-compat: tag input chỉ là UI — /upload vẫn nhận chuỗi 'a, b' như cũ."""
    r = client_claims(app, "ql", *HO_SO["ql"]).post("/upload", data={
        "title": "t", "keywords": "đăng video, SEO", "owner": "", "version": "v1",
        "department": "Kinh doanh", "doc_type": "Quy trình",
        "effective_status": "Còn hiệu lực", "access_level": "Công khai nội bộ",
        "min_level": "1"}, files={"file": ("a.txt", b"x")})
    assert r.status_code == 200
