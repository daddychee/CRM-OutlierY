"""Test SỬA METADATA NGUY HIỂM (Kho tài liệu bước 2C — chỉ Owner): đổi quyền truy xuất
(bộ phận/mức truy cập/level/hiệu lực) có ĐỒNG BỘ payload Qdrant. Van chống lệch: Qdrant TRƯỚC +
KIỂM CHỨNG sau đồng bộ, catalog SAU (chỉ khi Qdrant OK + kiểm chứng đạt). Mock lớp Qdrant."""

import csv
import os

os.environ["MOCK_MODE"] = "true"

from pathlib import Path

from fastapi.testclient import TestClient

from src.main import CATALOG_HEADER, app, client, doc_catalog

# 04/08/2026: "IT" hết là bộ phận (mô hình 3 trục) → ca đổi-bộ-phận dùng HCNS
_QUYEN_MOI = {"doc_code": "KD-DOC", "department": "Hành chính Nhân sự", "access_level": "Mật",
              "effective_status": "Hết hiệu lực", "min_level": "5"}


def _setup(tmp_path, monkeypatch):
    client._mock_chunks.clear(); client._mock_payload.clear()
    pass  # V2: không còn USERS_FILE — claims thay đăng nhập (giữ chữ ký call-site)
    kho = Path(os.environ["KHO_TAI_LIEU"]); kho.mkdir(parents=True, exist_ok=True)
    with (kho / "_catalog.csv").open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh); w.writerow(CATALOG_HEADER)
        w.writerow(["KD-DOC", "2026-07-01", "Tai lieu", "Kinh doanh", "Quy trình", "Còn hiệu lực",
                    "v1", "Giới hạn theo bộ phận", "2", "kw", "An", "f.txt", "05_Kinh-doanh",
                    "False", "KD-DOC", ""])
    # payload quyền hiện tại của doc (như đã upload trước đó)
    client._mock_payload["KD-DOC"] = {"department": "Kinh doanh", "effective_status": "Còn hiệu lực",
                                      "access_level": "Giới hạn theo bộ phận", "min_level": 2}
    return kho


from claims_v2 import client_claims

HO_SO = {"sep": ("Kinh doanh", 5), "nv": ("Kinh doanh", 2)}


def _login(ten):
    return client_claims(app, ten, *HO_SO[ten])


def _dong(code):
    return next((d for d in doc_catalog() if d["Mã tài liệu"] == code), None)


def test_owner_sua_quyen_dong_bo_ca_payload_va_catalog(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    r = _login("sep").post("/kho-tai-lieu/sua-quyen", data=_QUYEN_MOI)
    assert r.status_code == 200 and r.json()["ok"]
    pl = client.doc_payload_mau("KD-DOC")             # payload Qdrant đã đổi đúng
    assert pl == {"department": "Hành chính Nhân sự", "access_level": "Mật",
                  "effective_status": "Hết hiệu lực", "min_level": 5}
    row = _dong("KD-DOC")                             # catalog đồng bộ (chỉ khi Qdrant OK)
    assert row["Bộ phận"] == "Hành chính Nhân sự" and row["Mức truy cập"] == "Mật"
    assert row["Hiệu lực"] == "Hết hiệu lực" and row["Level tối thiểu"] == "5"
    assert row["Mã tài liệu"] == "KD-DOC" and row["document_id"] == "KD-DOC"   # doc_code BẤT BIẾN


def test_kiem_chung_phat_hien_payload_khong_khop(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    # set_payload KHÔNG thực sự đổi (mô phỏng đồng bộ hỏng) → kiểm chứng đọc lại phải phát hiện lệch
    monkeypatch.setattr(client, "cap_nhat_payload_doc_code", lambda dc, pm: None)
    r = _login("sep").post("/kho-tai-lieu/sua-quyen", data=_QUYEN_MOI)
    assert r.status_code == 500                       # kiểm chứng sau đồng bộ BẮT được, không im lặng
    assert _dong("KD-DOC")["Bộ phận"] == "Kinh doanh"  # catalog KHÔNG đổi (chống lệch)


def test_qdrant_loi_thi_catalog_khong_doi(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    def no(*a, **k):
        raise RuntimeError("Qdrant sập")
    monkeypatch.setattr(client, "cap_nhat_payload_doc_code", no)
    r = _login("sep").post("/kho-tai-lieu/sua-quyen", data=_QUYEN_MOI)
    assert r.status_code == 500                       # Qdrant lỗi → báo lỗi rõ
    row = _dong("KD-DOC")
    assert row["Bộ phận"] == "Kinh doanh" and row["Level tối thiểu"] == "2"   # catalog giữ cũ


def test_non_owner_bi_route_tu_choi(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    r = _login("nv").post("/kho-tai-lieu/sua-quyen", data=_QUYEN_MOI)
    assert r.status_code == 403                        # yeu_cau_owner chặn ở SERVER
    assert _dong("KD-DOC")["Bộ phận"] == "Kinh doanh"


def test_gia_tri_ngoai_dropdown_bi_chan(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    r = _login("sep").post("/kho-tai-lieu/sua-quyen",
                           data={**_QUYEN_MOI, "department": "Phòng Ma"})
    assert r.status_code == 422                        # giá trị ngoài dropdown bị chặn (như nhập liệu)
    assert _dong("KD-DOC")["Bộ phận"] == "Kinh doanh"
