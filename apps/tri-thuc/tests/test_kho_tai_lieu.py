"""Test trang KHO TÀI LIỆU (chỉ đọc — bước 1/3). RBAC tái dùng client._duoc_xem:
Owner (level 5) thấy toàn bộ catalog; người khác chỉ thấy tài liệu đủ quyền (công khai nội bộ
HOẶC đúng bộ phận + đủ level). Lọc Ở SERVER: tài liệu vượt quyền KHÔNG lọt vào HTML.
Mock LLM/Qdrant qua conftest; KHO_TAI_LIEU + USERS_FILE trỏ tmp (conftest kho_tam)."""

import csv
import os

os.environ["MOCK_MODE"] = "true"

from pathlib import Path

from fastapi.testclient import TestClient

from src.main import CATALOG_HEADER, app, doc_catalog


def _row(ma, tieu_de, bo_phan, hieu_luc, muc, level, phu_trach="An", keywords=""):
    """1 dòng catalog 16 cột đúng khuôn CATALOG_HEADER."""
    return [ma, "2026-07-01", tieu_de, bo_phan, "Quy trình", hieu_luc, "v1", muc,
            level, keywords, phu_trach, f"{ma}.pdf", "01", "False", f"doc-{ma}", ""]


CAC_DONG = [
    _row("KD-PUB", "So tay chung",     "Kinh doanh", "Còn hiệu lực", "Công khai nội bộ",      ""),   # công khai → mọi người
    _row("KD-L2",  "Quy dinh KD",      "Kinh doanh", "Còn hiệu lực", "Giới hạn theo bộ phận", "2",
         keywords="marketing, quang cao"),                                                            # KD, cần level 2
    _row("KD-L4",  "Chien luoc mat",   "Kinh doanh", "Còn hiệu lực", "Mật",                   "4"),  # KD, cần level 4
    _row("IT-L1",  "Huong dan IT",     "IT",         "Còn hiệu lực", "Giới hạn theo bộ phận", "1"),  # bộ phận IT
    _row("KD-OLD", "Bang gia cu",      "Kinh doanh", "Hết hiệu lực", "Giới hạn theo bộ phận", "2"),  # KD lv2, HẾT hiệu lực
]


# V2: claims từ gateway thay users.txt — bảng bộ phận×level giữ nguyên ý cũ.
from claims_v2 import client_claims

HO_SO = {"sep": ("Kinh doanh", 5), "nv": ("Kinh doanh", 2), "itnv": ("IT", 2)}


def _setup(tmp_path, monkeypatch):
    # _catalog.csv trong KHO_TAI_LIEU (conftest đã trỏ tmp) — ghi utf-8-sig như app đọc
    kho = Path(os.environ["KHO_TAI_LIEU"]); kho.mkdir(parents=True, exist_ok=True)
    with (kho / "_catalog.csv").open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh); w.writerow(CATALOG_HEADER); w.writerows(CAC_DONG)


def _login(ten):
    return client_claims(app, ten, *HO_SO[ten])


def test_owner_thay_toan_bo_catalog(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    r = _login("sep").get("/kho-tai-lieu")
    assert r.status_code == 200
    for ma in ("KD-PUB", "KD-L2", "KD-L4", "IT-L1", "KD-OLD"):
        assert ma in r.text                       # Owner thấy TẤT CẢ 5 tài liệu
    assert "toàn bộ kho" in r.text                # ghi chú chế độ Owner


def test_nhan_vien_kd_chi_thay_dung_quyen(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    r = _login("nv").get("/kho-tai-lieu")         # KD, level 2
    assert r.status_code == 200
    assert "KD-PUB" in r.text                     # công khai nội bộ
    assert "KD-L2" in r.text and "KD-OLD" in r.text  # đúng bộ phận + đủ level (kể cả hết hiệu lực)
    assert "KD-L4" not in r.text                  # cần level 4 > 2 → SERVER không gửi
    assert "IT-L1" not in r.text                  # khác bộ phận → không thấy
    # chặn ở SERVER, không chỉ ẩn UI: tiêu đề tài liệu vượt quyền KHÔNG lọt vào HTML
    assert "Chien luoc mat" not in r.text and "Huong dan IT" not in r.text


def test_nhan_vien_bo_phan_khac(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    r = _login("itnv").get("/kho-tai-lieu")       # IT, level 2
    assert "KD-PUB" in r.text and "IT-L1" in r.text          # công khai + đúng bộ phận IT
    for ma in ("KD-L2", "KD-L4", "KD-OLD"):
        assert ma not in r.text                   # tài liệu Kinh doanh → không thấy


def test_danh_dau_het_hieu_luc(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    r = _login("nv").get("/kho-tai-lieu")
    assert 'class="het"' in r.text                # dòng hết hiệu lực có đánh dấu thị giác
    assert "Hết hiệu lực" in r.text


# ═══ Bước 2A: popup xem chi tiết + sửa metadata AN TOÀN (chỉ Owner) ═══

def _dong(code):
    return next((d for d in doc_catalog() if d["Mã tài liệu"] == code), None)


def test_popup_tra_dung_du_lieu_day_du(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    html = _login("sep").get("/kho-tai-lieu").text
    # dữ liệu popup nhúng đầy đủ (KT_DOCS) — kể cả cột KHÔNG hiện ở bảng: từ khóa + tên file
    assert "KT_DOCS" in html
    assert "marketing, quang cao" in html         # Chủ đề/Từ khóa của KD-L2 (không có ở cột bảng)
    assert "KD-L2.pdf" in html                    # Tên file mới (không có ở cột bảng)
    assert 'data-i=' in html                      # dòng bấm được để mở popup


def test_owner_co_nut_sua_nguoi_khac_khong(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    assert "Sửa thông tin" in _login("sep").get("/kho-tai-lieu").text   # Owner thấy nút Sửa
    assert "Sửa thông tin" not in _login("nv").get("/kho-tai-lieu").text  # nhân viên KHÔNG có nút


def test_owner_sua_metadata_an_toan_catalog_dung(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    truoc = _dong("KD-L2")
    r = _login("sep").post("/kho-tai-lieu/sua", data={
        "doc_code": "KD-L2", "title": "Tieu de MOI", "doc_type": "Bao cao",
        "version": "v2", "keywords": "seo, moi", "owner": "Binh"})
    assert r.status_code in (200, 303)            # 303 redirect về trang kho
    sau = _dong("KD-L2")
    # các TRƯỜNG AN TOÀN đã đổi đúng
    assert sau["Tiêu đề"] == "Tieu de MOI" and sau["Loại tài liệu"] == "Bao cao"
    assert sau["Phiên bản"] == "v2" and sau["Chủ đề/Từ khóa"] == "seo, moi" and sau["Phụ trách"] == "Binh"
    # doc_code BẤT BIẾN + các trường ẢNH HƯỞNG TRUY XUẤT KHÔNG bị đụng
    assert sau["Mã tài liệu"] == "KD-L2" and sau["document_id"] == truoc["document_id"]
    assert sau["Bộ phận"] == truoc["Bộ phận"] == "Kinh doanh"
    assert sau["Mức truy cập"] == truoc["Mức truy cập"] and sau["Level tối thiểu"] == truoc["Level tối thiểu"]
    assert sau["Hiệu lực"] == truoc["Hiệu lực"] == "Còn hiệu lực"
    # tài liệu KHÁC không bị ảnh hưởng
    assert _dong("KD-PUB")["Tiêu đề"] == "So tay chung"


def test_non_owner_bi_route_tu_choi_sua(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    r = _login("nv").post("/kho-tai-lieu/sua", data={
        "doc_code": "KD-L2", "title": "Hack", "doc_type": "", "version": "",
        "keywords": "", "owner": ""})
    assert r.status_code == 403                    # yeu_cau_owner chặn ở SERVER
    assert _dong("KD-L2")["Tiêu đề"] == "Quy dinh KD"   # catalog KHÔNG đổi


def test_sua_doc_code_khong_ton_tai_404(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    r = _login("sep").post("/kho-tai-lieu/sua", data={
        "doc_code": "KHONG-CO", "title": "X", "doc_type": "", "version": "",
        "keywords": "", "owner": ""})
    assert r.status_code == 404                    # không có doc_code → không ghi gì


# ═══ Lưới cảnh báo kho rỗng / Qdrant không nối được (31/07/2026) ═══
# Bài học thật: kho 0 point suốt 29-31/07 mà không ai hay — hỏi-đáp chết lặng lẽ.

def _gia_lap_kho_that(monkeypatch, so_point):
    """Giả lập chế độ Qdrant thật: mock=False + dem_point_kho trả so_point (None = mất kết nối)."""
    from src.main import client
    monkeypatch.setattr(client, "mock", False)
    monkeypatch.setattr(client, "dem_point_kho", lambda: so_point)


def test_canh_bao_kho_rong(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    _gia_lap_kho_that(monkeypatch, 0)
    r = _login("sep").get("/kho-tai-lieu")
    assert "RỖNG" in r.text and "nap_lai_kho" in r.text   # chỉ đường sửa ngay trong banner


def test_canh_bao_qdrant_mat_ket_noi(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    _gia_lap_kho_that(monkeypatch, None)
    r = _login("sep").get("/kho-tai-lieu")
    assert "Không kết nối được kho tìm kiếm" in r.text


def test_khong_canh_bao_khi_kho_co_du_lieu_va_voi_nhan_vien(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    _gia_lap_kho_that(monkeypatch, 53)
    assert "RỖNG" not in _login("sep").get("/kho-tai-lieu").text   # kho có dữ liệu → im lặng
    _gia_lap_kho_that(monkeypatch, 0)
    r = _login("nv").get("/kho-tai-lieu")                          # nhân viên lv2: không phải người xử lý
    assert "RỖNG" not in r.text

# ─────────────── 📖 Xem nội dung trực tiếp trong popup (06/08) ───────────────

def test_xem_noi_dung_truc_tiep_va_rbac(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    kho = Path(os.environ["KHO_TAI_LIEU"])
    (kho / "01").mkdir(parents=True, exist_ok=True)
    # thêm 1 tài liệu .md (đọc thẳng được) cùng quyền KD level 2 + file thật trên đĩa
    with (kho / "_catalog.csv").open("a", newline="", encoding="utf-8-sig") as fh:
        csv.writer(fh).writerow(["KD-MD", "2026-08-06", "Quy trinh md", "Kinh doanh",
                                 "Quy trình", "Còn hiệu lực", "v1", "Giới hạn theo bộ phận",
                                 "2", "", "An", "KD-MD.md", "01", "False", "doc-KD-MD", ""])
    (kho / "01" / "KD-MD.md").write_text("nội dung quy trình bán hàng", encoding="utf-8")
    (kho / "01" / "KD-L2.pdf").write_bytes(b"%PDF fake")

    # đúng quyền + file chữ → đọc thẳng nội dung
    r = _login("nv").get("/kho-tai-lieu/xem/KD-MD")
    assert r.status_code == 200 and "quy trình bán hàng" in r.json()["noi_dung"]
    # file nhị phân (.pdf) → noi_dung None, UI chỉ sang nút tải bản gốc
    r2 = _login("nv").get("/kho-tai-lieu/xem/KD-L2")
    assert r2.status_code == 200 and r2.json()["noi_dung"] is None
    # vượt level → 404 LẶNG LẼ (không lộ tài liệu tồn tại)
    assert _login("nv").get("/kho-tai-lieu/xem/KD-L4").status_code == 404
    # khác bộ phận → 404; Owner → thấy
    assert _login("itnv").get("/kho-tai-lieu/xem/KD-MD").status_code == 404
    assert _login("sep").get("/kho-tai-lieu/xem/KD-MD").status_code == 200


def test_ghep_ban_phan_tich_duoi_goc_het_duplicate():
    """06/08: -PT phải vào NHÓM dưới tài liệu gốc như -QA — trước đó đứng dòng riêng
    nhìn như tài liệu trùng."""
    from src.main import ghep_goc_qa
    rows = [{"Mã tài liệu": "YT-a", "Tiêu đề": "Nguồn"},
            {"Mã tài liệu": "YT-a-PT", "Tiêu đề": "Bài học kinh nghiệm — Nguồn"},
            {"Mã tài liệu": "YT-a-QA", "Tiêu đề": "Q&A"},
            {"Mã tài liệu": "KD-1", "Tiêu đề": "SOP"}]
    kq = ghep_goc_qa(rows)
    assert [r["Mã tài liệu"] for r in kq] == ["YT-a", "YT-a-PT", "YT-a-QA", "KD-1"]
    assert kq[1]["la_pt"] is True and kq[1]["la_qa"] is False
    assert kq[2]["la_qa"] is True and kq[0]["la_pt"] is False
