# -*- coding: utf-8 -*-
"""Tầng dữ liệu Video Review — SQLite (migration có phiên bản) + kho file năm/tháng.

Luật 6: DB sống ở data/video-review/db, file video ở data/video-review/kho
(năm/tháng, khuôn tên YYYY-MM-DD_<ma>_<ten>.ext — Luật 5). Mọi hàm đọc env LÚC GỌI
(không cache lúc import) để conftest test đè đường bằng monkeypatch được.
Xóa video là GỠ MỀM (trang_thai='da_xoa', file giữ nguyên) — bất biến hệ cũ.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import unicodedata
from datetime import datetime
from pathlib import Path

_APP_DIR = Path(__file__).resolve().parents[1]           # apps/video-review
ROOT = _APP_DIR.parents[1]                                # D:\AI AGENT OUTLIERY

TRANG_THAI_VIDEO = ("dang_duyet", "can_sua", "da_duyet", "da_xoa")
# .mov để được nhưng cảnh báo ở UI (tùy codec trình duyệt mới phát) — mp4/webm chắc ăn.
DUOI_CHO_PHEP = {".mp4": "video/mp4", ".m4v": "video/mp4",
                 ".webm": "video/webm", ".mov": "video/quicktime"}


def _db_path() -> Path:
    return Path(os.environ.get("VR_DB_PATH",
                               str(ROOT / "data" / "video-review" / "db" / "video_review.db")))


def kho_dir() -> Path:
    return Path(os.environ.get("VR_KHO_DIR", str(ROOT / "data" / "video-review" / "kho")))


def ket_noi() -> sqlite3.Connection:
    p = _db_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(p, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def khoi_tao() -> None:
    """Chạy migration còn thiếu (bảng schema_version = số file .sql đã áp)."""
    conn = ket_noi()
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS schema_version (v INTEGER NOT NULL)")
        hang = conn.execute("SELECT v FROM schema_version").fetchone()
        hien_tai = hang["v"] if hang else 0
        cac_file = sorted((_APP_DIR / "migrations").glob("*.sql"))
        for f in cac_file:
            so = int(f.name.split("_")[0])
            if so <= hien_tai:
                continue
            conn.executescript(f.read_text(encoding="utf-8"))
            hien_tai = so
        if hang:
            conn.execute("UPDATE schema_version SET v=?", (hien_tai,))
        else:
            conn.execute("INSERT INTO schema_version (v) VALUES (?)", (hien_tai,))
        conn.commit()
    finally:
        conn.close()


def _slug_ten(ten: str) -> str:
    """Tên hiển thị → mảnh tên file ASCII (bẫy 'đ' không phân rã qua NFD)."""
    s = ten.strip().lower().replace("đ", "d")
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:60] or "video"


def them_video(ten: str, duoi: str, nguoi_tao: str, bo_phan: str,
               kich_thuoc: int, luc: datetime | None = None) -> dict:
    """Ghi sổ 1 video mới, trả bản ghi kèm đường tuyệt đối để caller đặt file vào.
    Mã VR-xxxx sinh từ rowid trong CÙNG transaction — không đua giữa 2 upload."""
    duoi = duoi.lower()
    if duoi not in DUOI_CHO_PHEP:
        raise ValueError(f"Đuôi {duoi} không hỗ trợ (nhận: {', '.join(sorted(DUOI_CHO_PHEP))})")
    luc = luc or datetime.now()
    conn = ket_noi()
    try:
        cur = conn.execute(
            "INSERT INTO video (ma, ten, ten_file, duong, mime, kich_thuoc, nguoi_tao,"
            " bo_phan, tao_luc) VALUES ('', ?, '', '', ?, ?, ?, ?, ?)",
            (ten, DUOI_CHO_PHEP[duoi], kich_thuoc, nguoi_tao, bo_phan,
             luc.strftime("%Y-%m-%d %H:%M:%S")))
        ma = f"VR-{cur.lastrowid:04d}"
        ten_file = f"{luc:%Y-%m-%d}_{ma}_{_slug_ten(ten)}{duoi}"
        duong = f"{luc:%Y}/{luc:%m}/{ten_file}"
        conn.execute("UPDATE video SET ma=?, ten_file=?, duong=? WHERE id=?",
                     (ma, ten_file, duong, cur.lastrowid))
        conn.commit()
    finally:
        conn.close()
    return {"ma": ma, "ten": ten, "ten_file": ten_file, "duong": duong,
            "duong_tuyet_doi": kho_dir() / duong}


def lay_video(ma: str) -> dict | None:
    conn = ket_noi()
    try:
        hang = conn.execute("SELECT * FROM video WHERE ma=?", (ma,)).fetchone()
        return dict(hang) if hang else None
    finally:
        conn.close()


def danh_sach_video() -> list[dict]:
    """Danh sách chưa-gỡ, mới nhất trước, kèm số bình luận còn mở + TỔNG bình luận
    (so_tong = 0 là dấu hiệu 'chưa ai review' — logic hiển thị Awaiting review)."""
    conn = ket_noi()
    try:
        hang = conn.execute(
            "SELECT v.*, (SELECT COUNT(*) FROM binh_luan b WHERE b.video_ma = v.ma"
            "  AND b.trang_thai = 'mo') AS so_mo,"
            " (SELECT COUNT(*) FROM binh_luan b2 WHERE b2.video_ma = v.ma) AS so_tong"
            " FROM video v WHERE v.trang_thai != 'da_xoa' ORDER BY v.id DESC").fetchall()
        return [dict(h) for h in hang]
    finally:
        conn.close()


def doi_trang_thai(ma: str, trang_thai: str) -> None:
    if trang_thai not in TRANG_THAI_VIDEO:
        raise ValueError(f"Trạng thái lạ: {trang_thai}")
    conn = ket_noi()
    try:
        cur = conn.execute("UPDATE video SET trang_thai=? WHERE ma=?", (trang_thai, ma))
        if cur.rowcount == 0:
            raise KeyError(ma)
        conn.commit()
    finally:
        conn.close()


# ---------- bình luận ----------

def them_binh_luan(video_ma: str, nguoi: str, noi_dung: str,
                   ts_giay: float | None = None, ve_json: str | None = None) -> dict:
    noi_dung = (noi_dung or "").strip()
    if not noi_dung:
        raise ValueError("Bình luận rỗng")
    if ve_json:
        json.loads(ve_json)  # phải là JSON hợp lệ — hỏng thì ValueError nổ ngay tại cửa
    if lay_video(video_ma) is None:
        raise KeyError(video_ma)
    conn = ket_noi()
    try:
        cur = conn.execute(
            "INSERT INTO binh_luan (video_ma, nguoi, noi_dung, ts_giay, ve_json, tao_luc)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (video_ma, nguoi, noi_dung, ts_giay, ve_json,
             datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        hang = conn.execute("SELECT * FROM binh_luan WHERE id=?", (cur.lastrowid,)).fetchone()
        return dict(hang)
    finally:
        conn.close()


def ds_binh_luan(video_ma: str) -> list[dict]:
    """Bình luận theo mốc thời gian tăng dần; bình luận chung (không mốc) xuống cuối."""
    conn = ket_noi()
    try:
        hang = conn.execute(
            "SELECT * FROM binh_luan WHERE video_ma=?"
            " ORDER BY ts_giay IS NULL, ts_giay, id", (video_ma,)).fetchall()
        return [dict(h) for h in hang]
    finally:
        conn.close()


def _sua_binh_luan(bl_id: int, nguoi: str, la_duyet: bool, cau_sql: str) -> None:
    """Khuôn chung giải/xóa: chỉ CHÍNH CHỦ hoặc người có quyền duyệt (Leader+)."""
    conn = ket_noi()
    try:
        hang = conn.execute("SELECT nguoi FROM binh_luan WHERE id=?", (bl_id,)).fetchone()
        if hang is None:
            raise KeyError(bl_id)
        if hang["nguoi"] != nguoi and not la_duyet:
            raise PermissionError("Chỉ người viết hoặc Leader+ được thao tác")
        conn.execute(cau_sql, (bl_id,))
        conn.commit()
    finally:
        conn.close()


def giai_binh_luan(bl_id: int, nguoi: str, la_duyet: bool) -> None:
    _sua_binh_luan(bl_id, nguoi, la_duyet,
                   "UPDATE binh_luan SET trang_thai='da_giai' WHERE id=?")


def mo_lai_binh_luan(bl_id: int, nguoi: str, la_duyet: bool) -> None:
    _sua_binh_luan(bl_id, nguoi, la_duyet,
                   "UPDATE binh_luan SET trang_thai='mo' WHERE id=?")


def xoa_binh_luan(bl_id: int, nguoi: str, la_duyet: bool) -> None:
    _sua_binh_luan(bl_id, nguoi, la_duyet, "DELETE FROM binh_luan WHERE id=?")
