# -*- coding: utf-8 -*-
"""GĐ3 — RBAC tài liệu phải FAIL-CLOSED khi bộ phận rỗng (05/09/2026).

LỖ A2 (rà 05/09, sổ `docs/bao-mat-internet.md`):
    ap_quyen = bool(user and user.get("bo_phan")) and user.get("level", 0) < 5
Bộ phận rỗng → `ap_quyen` False → **KHÔNG lọc quyền gì cả**. Đây là di sản "chế
độ mở" thời chưa có auth.

Cột cho phép rỗng (`nen/iam/migrations/001_khoi_tao.sql:16` DEFAULT '') và
`iam.tao_tai_khoan` KHÔNG kiểm rỗng; gateway chỉ gửi header khi giá trị truthy.
→ Một Intern level 1 bộ phận rỗng đọc TOÀN BỘ kho mọi bộ phận, gồm tài liệu Mật.

ĐÃ KIỂM DỮ LIỆU THẬT 05/09: 20 tài khoản, 0 cái bộ phận rỗng → chưa bị khai thác.
Nhưng là MÌN: Owner tạo một tài khoản bỏ trống ô bộ phận là nổ.

Luật đúng: **không có bộ phận = không thấy gì** (trừ Owner level 5 và tài liệu
công khai). Ngược hẳn hành vi cũ.
"""
import pytest

from src import vector_client

_duoc_xem = vector_client.QdrantClientWrapper._duoc_xem


def _u(bo_phan, level):
    return {"ten": "x", "bo_phan": bo_phan, "level": level}


def test_bo_phan_rong_KHONG_duoc_xem_tai_lieu_bo_phan_khac():
    """Trọng tâm của lỗ: trước đây trả True cho MỌI tài liệu."""
    tai_lieu = {"department": "Kinh doanh", "access_level": "Nội bộ", "min_level": 1}
    assert _duoc_xem(tai_lieu, _u("", 1)) is False
    assert _duoc_xem(tai_lieu, _u(None, 1)) is False


def test_bo_phan_rong_van_xem_duoc_tai_lieu_cong_khai():
    """Không siết quá tay: tài liệu công khai vẫn phải xem được."""
    tl = {"department": "Kinh doanh", "access_level": "Công khai nội bộ", "min_level": 1}
    assert _duoc_xem(tl, _u("", 1)) is True


def test_owner_van_xem_duoc_het():
    tl = {"department": "Kinh doanh", "access_level": "Mật", "min_level": 5}
    assert _duoc_xem(tl, _u("", 5)) is True


def test_dung_bo_phan_du_level_van_xem_duoc():
    """KHÔNG được phá hành vi đúng đang chạy."""
    tl = {"department": "Kinh doanh", "access_level": "Nội bộ", "min_level": 2}
    assert _duoc_xem(tl, _u("Kinh doanh", 3)) is True


def test_dung_bo_phan_thieu_level_thi_chan():
    tl = {"department": "Kinh doanh", "access_level": "Nội bộ", "min_level": 4}
    assert _duoc_xem(tl, _u("Kinh doanh", 2)) is False


# ── ĐO CHÍNH ĐIỂM ĐÃ SỬA: quyết định CÓ ÁP bộ lọc hay không ───────────────────
# `_duoc_xem` vốn đã đúng; lỗ nằm ở chỗ quyết định có GỌI nó hay không (`ap_quyen`
# trong `tim_kiem`). Test dưới đo qua đường search thật ở chế độ mock.

def _client_mock(monkeypatch):
    monkeypatch.setenv("MOCK_MODE", "true")
    return vector_client.QdrantClientWrapper()


def test_search_bo_phan_rong_khong_thay_tai_lieu_bo_phan_khac(monkeypatch):
    c = _client_mock(monkeypatch)
    monkeypatch.setattr(vector_client, "_MOCK_CHUNKS", [
        {"content": "bi mat KD", "document_metadata": {
            "department": "Kinh doanh", "access_level": "Nội bộ", "min_level": 1}},
    ], raising=False)
    ra = c.search("x", user={"ten": "nv", "bo_phan": "", "level": 1})
    assert ra == [], "bộ phận rỗng vẫn thấy tài liệu bộ phận khác"


def test_search_user_None_van_la_che_do_mo(monkeypatch):
    """Chế độ mở cho script/job nền là CÓ CHỦ ĐÍCH — không được siết nhầm."""
    c = _client_mock(monkeypatch)
    monkeypatch.setattr(vector_client, "_MOCK_CHUNKS", [
        {"content": "tai lieu", "document_metadata": {
            "department": "Kinh doanh", "access_level": "Nội bộ", "min_level": 1}},
    ], raising=False)
    assert len(c.search("x", user=None)) == 1
