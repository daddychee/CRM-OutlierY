# -*- coding: utf-8 -*-
"""Danh bạ thực thể chung (kênh / ngách) — mảnh ④ tầng nền.

Nguồn sự thật: platform/rules/danh_muc.csv (luật ngoài code — Owner sửa bằng Excel).
Mỗi dòng = một thực thể với tên chuẩn + bí danh + khóa định danh ở từng app
(seo_profile, plannery_project, radary_niche, niche_project, mau_ten_bao_cao).

Mọi mảnh khác (dropdown báo cáo, connector, router hỏi số liệu) tra qua module này —
KHÔNG app nào tự đoán tên thực thể.
"""
from __future__ import annotations

import csv
import os
import re
import unicodedata
from pathlib import Path

DUONG_MAC_DINH = Path(__file__).resolve().parents[1] / "rules" / "danh_muc.csv"


def _duong_hieu_luc(duong: Path | str | None) -> Path:
    """Ưu tiên tham số → env DANH_MUC_CSV (test/cách ly) → file luật thật."""
    if duong:
        return Path(duong)
    return Path(os.environ.get("DANH_MUC_CSV") or DUONG_MAC_DINH)

# Cột khóa ứng dụng hợp lệ (thêm app mới = thêm cột CSV + thêm tên vào đây)
CAC_COT_KHOA = (
    "seo_profile",
    "plannery_project",
    "radary_niche",
    "niche_project",
    "mau_ten_bao_cao",
)


def chuan_hoa_ten(ten: str) -> str:
    """Chuẩn hóa tên để so khớp: thường hóa, bỏ dấu, đ→d, gọn khoảng trắng.

    'đ' (U+0111) KHÔNG phân rã qua NFD nên phải thay riêng — bẫy tiếng Việt
    đã dính ở SEO Optimize 05/08/2026.
    """
    if not ten:
        return ""
    s = ten.casefold()
    s = s.replace("đ", "d").replace("Đ", "d")
    s = unicodedata.normalize("NFD", s)
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def doc_danh_muc(duong: Path | str | None = None) -> list[dict]:
    """Đọc toàn bộ danh mục. utf-8-sig để chịu được file Excel lưu kèm BOM."""
    duong = _duong_hieu_luc(duong)
    if not duong.exists():
        return []
    ket_qua: list[dict] = []
    with open(duong, "r", encoding="utf-8-sig", newline="") as f:
        for dong in csv.DictReader(f):
            if not dong.get("ma") or not (dong.get("ten_chuan") or "").strip():
                continue  # bỏ dòng trống/hỏng, không chết cả danh mục
            ket_qua.append({k: (v or "").strip() for k, v in dong.items() if k})
    return ket_qua


def _cac_ten_khop(thuc_the: dict) -> list[str]:
    ten = [thuc_the.get("ten_chuan", "")]
    ten += [t for t in (thuc_the.get("bi_danh") or "").split(";") if t.strip()]
    return [chuan_hoa_ten(t) for t in ten if t]


def tra_thuc_the(
    ten: str, loai: str | None = None, duong: Path | str | None = None
) -> dict | None:
    """Tra thực thể theo tên chuẩn HOẶC bí danh (đã chuẩn hóa cả hai phía).

    Không khớp → None (người gọi phải hỏi lại người dùng, KHÔNG đoán).
    """
    can = chuan_hoa_ten(ten)
    if not can:
        return None
    for thuc_the in doc_danh_muc(duong):
        if loai and thuc_the.get("loai") != loai:
            continue
        if can in _cac_ten_khop(thuc_the):
            return thuc_the
    return None


def khoa_ung_dung(thuc_the: dict | None, cot: str) -> str | None:
    """Lấy khóa định danh của thực thể ở một app. Trống/chưa điền → None
    (app đó chưa nối được thực thể này — nói thẳng, không đoán)."""
    if not thuc_the or cot not in CAC_COT_KHOA:
        return None
    gia_tri = (thuc_the.get(cot) or "").strip()
    return gia_tri or None


def liet_ke(loai: str | None = None, duong: Path | str | None = None) -> list[dict]:
    """Danh sách thực thể (cho dropdown UI). Giữ nguyên thứ tự file."""
    ds = doc_danh_muc(duong)
    return [t for t in ds if t.get("loai") == loai] if loai else ds
