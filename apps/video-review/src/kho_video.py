# -*- coding: utf-8 -*-
"""Tầng dữ liệu Video Review — SQLite (migration có phiên bản) + LIÊN KẾT file NAS.

Từ 20/08/2026 app KHÔNG chép video vào kho nữa (user chốt): quy trình công ty là
anh em up bản dựng lên NAS rồi chọn file đó vào app, nên sổ chỉ giữ ĐƯỜNG TƯƠNG ĐỐI
trong VR_NAS_DIR (nguon='nas'). Bản ghi đời cũ nguon='kho' vẫn đọc được từ kho app.

- NAS là CHỈ ĐỌC tuyệt đối: app không ghi/xóa/đổi tên bất cứ thứ gì trong VR_NAS_DIR,
  kể cả khi người dùng xóa video (xóa vẫn là GỠ MỀM — bất biến hệ cũ).
- Vân tay (kich_thuoc + nas_mtime) chụp lúc liên kết → phát hiện file bị GHI ĐÈ bản
  mới cùng tên, vì bình luận gắn mốc giây của bản cũ sẽ lệch.
- Mọi hàm đọc env LÚC GỌI (không cache lúc import) để test đè đường bằng monkeypatch.
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
    """Kho app — giờ chỉ còn giữ phụ đề gắn từ app + bản sao video đời cũ."""
    return Path(os.environ.get("VR_KHO_DIR", str(ROOT / "data" / "video-review" / "kho")))


def nas_dir() -> Path | None:
    """Gốc NAS được phép duyệt (env VR_NAS_DIR). CHƯA khai → None (tính năng ẩn)."""
    d = os.environ.get("VR_NAS_DIR", "").strip()
    if not d:
        return None
    p = Path(d)
    return p if p.is_dir() else None


def duong_nas_an_toan(goc: Path, tuong_doi: str) -> Path:
    """Đường client gửi → đường tuyệt đối TRONG gốc; ngoài gốc → PermissionError.
    Đường tuyệt đối/ổ đĩa client nhét vào cũng bị resolve rồi rơi ngoài gốc.
    Kiểm LẠI cả lúc phát video (không chỉ lúc liên kết) — sổ có thể bị sửa tay."""
    td = (tuong_doi or "").replace("\\", "/").strip("/")
    goc_rs = goc.resolve()
    if not td:
        return goc_rs
    con = (goc / td).resolve()
    if con != goc_rs and goc_rs not in con.parents:
        raise PermissionError("Đường ngoài gốc NAS")
    return con


def duong_video(video: dict) -> Path | None:
    """Đường file thật của một bản ghi — None khi không resolve nổi (NAS chưa khai
    / sổ trỏ ra ngoài gốc). Caller vẫn phải tự kiểm .is_file()."""
    if (video.get("nguon") or "kho") == "nas":
        goc = nas_dir()
        if goc is None:
            return None
        try:
            return duong_nas_an_toan(goc, video["duong"])
        except (PermissionError, OSError):
            return None
    return kho_dir() / video["duong"]


def tinh_trang_file(video: dict) -> dict:
    """Vân tay file lúc liên kết so với hiện tại — dữ liệu cho cảnh báo trên UI.
    'mat' = file không còn (bị xóa/đổi tên/di chuyển trên NAS, hoặc NAS chưa khai);
    'doi' = còn nhưng dung lượng/ngày sửa đã khác → bình luận gắn mốc giây có thể
    lệch (editor ghi đè bản mới cùng tên). CHỈ báo, không tự sửa sổ."""
    p = duong_video(video)
    if p is None or not p.is_file():
        return {"co": False, "doi": False, "duong_hien": str(p) if p else ""}
    st = p.stat()
    doi = False
    if (video.get("nguon") or "kho") == "nas":
        cu_mt = video.get("nas_mtime")
        doi = (bool(video.get("kich_thuoc")) and st.st_size != video["kich_thuoc"]) or (
            cu_mt is not None and abs(st.st_mtime - float(cu_mt)) > 2)
    return {"co": True, "doi": doi, "duong_hien": str(p),
            "kich_thuoc_hien": st.st_size}


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


def them_video_nas(ten: str, duong_nas: str, nguoi_tao: str, bo_phan: str,
                   kich_thuoc: int, mtime: float, luc: datetime | None = None) -> dict:
    """Ghi sổ 1 video LIÊN KẾT tới file có sẵn trên NAS — không chép byte nào.
    Mã VR-xxxx sinh từ rowid trong CÙNG transaction (không đua giữa 2 lượt thêm);
    ten_file = tên file thật trên NAS để hiện/tải về đúng tên anh em đặt."""
    duong_nas = (duong_nas or "").replace("\\", "/").strip("/")
    if not duong_nas:
        raise ValueError("Thiếu đường file trên NAS")
    ten_file = duong_nas.rsplit("/", 1)[-1]
    duoi = ("." + ten_file.rsplit(".", 1)[-1]).lower() if "." in ten_file else ""
    if duoi not in DUOI_CHO_PHEP:
        raise ValueError(f"Đuôi {duoi} không hỗ trợ (nhận: {', '.join(sorted(DUOI_CHO_PHEP))})")
    luc = luc or datetime.now()
    conn = ket_noi()
    try:
        cur = conn.execute(
            "INSERT INTO video (ma, ten, ten_file, duong, mime, kich_thuoc, nguoi_tao,"
            " bo_phan, tao_luc, nguon, nas_mtime)"
            " VALUES ('', ?, ?, ?, ?, ?, ?, ?, ?, 'nas', ?)",
            (ten or ten_file, ten_file, duong_nas, DUOI_CHO_PHEP[duoi], kich_thuoc,
             nguoi_tao, bo_phan, luc.strftime("%Y-%m-%d %H:%M:%S"), mtime))
        ma = f"VR-{cur.lastrowid:04d}"
        conn.execute("UPDATE video SET ma=? WHERE id=?", (ma, cur.lastrowid))
        conn.commit()
    finally:
        conn.close()
    return {"ma": ma, "ten": ten or ten_file, "ten_file": ten_file,
            "duong": duong_nas, "nguon": "nas"}


def da_lien_ket(duong_nas: str) -> dict | None:
    """Bản ghi CÒN SỐNG đang trỏ đúng file NAS này (chống thêm trùng một bản dựng)."""
    duong_nas = (duong_nas or "").replace("\\", "/").strip("/")
    conn = ket_noi()
    try:
        hang = conn.execute(
            "SELECT * FROM video WHERE nguon='nas' AND duong=? AND trang_thai != 'da_xoa'"
            " ORDER BY id DESC", (duong_nas,)).fetchone()
        return dict(hang) if hang else None
    finally:
        conn.close()


def lay_video(ma: str) -> dict | None:
    conn = ket_noi()
    try:
        hang = conn.execute("SELECT * FROM video WHERE ma=?", (ma,)).fetchone()
        return dict(hang) if hang else None
    finally:
        conn.close()


def cac_duong_nas_dang_dung() -> set[str]:
    """Đường NAS đã có bản ghi CÒN SỐNG — để danh sách NAS đánh dấu 'đã trong app'."""
    conn = ket_noi()
    try:
        return {h["duong"] for h in conn.execute(
            "SELECT duong FROM video WHERE nguon='nas' AND trang_thai != 'da_xoa'")}
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


# ---------- phụ đề (.srt/.vtt — mỗi video tối đa MỘT phụ đề) ----------
# Hai nguồn: (1) bản gắn TỪ APP nằm trong kho app (kho/phu-de/<ma>.srt) — app sở hữu,
# gỡ được; (2) file .srt anh em để CẠNH video trên NAS — app chỉ ĐỌC, không bao giờ
# ghi/xóa. Bản gắn từ app thắng (người dùng vừa gắn thì phải thấy bản mới).

DUOI_PHU_DE = (".srt", ".vtt")


def _phu_de_app(video: dict, duoi: str) -> Path:
    return kho_dir() / "phu-de" / f"{video['ma']}{duoi}"


def phu_de_tim(video: dict) -> tuple[Path | None, str]:
    """(đường, nguồn) với nguồn ∈ 'app' | 'nas' | 'kho' (sidecar đời cũ) | ''."""
    for d in DUOI_PHU_DE:
        p = _phu_de_app(video, d)
        if p.is_file():
            return p, "app"
    goc = duong_video(video)
    if goc is None:
        return None, ""
    canh = "nas" if (video.get("nguon") or "kho") == "nas" else "kho"
    for d in DUOI_PHU_DE:
        # hai lối đặt tên ngoài đời: "phim.mp4.srt" (kho app đời cũ) và "phim.srt"
        for ung in (goc.with_name(goc.name + d), goc.with_name(goc.stem + d)):
            if ung.is_file():
                return ung, canh
    return None, ""


def duong_phu_de(video: dict) -> Path | None:
    return phu_de_tim(video)[0]


def doc_phu_de_bytes(b: bytes) -> str:
    """SRT ngoài đời đủ kiểu encoding (CapCut/Premiere UTF-8, tool cũ UTF-16) —
    thử lần lượt, bí quá thay ký tự hỏng chứ không nổ."""
    for enc in ("utf-8-sig", "utf-16"):
        try:
            return b.decode(enc)
        except UnicodeDecodeError:
            pass
    return b.decode("utf-8", errors="replace")


def srt_sang_vtt(chu: str) -> str:
    """SRT → WebVTT (thứ DUY NHẤT <track> trình duyệt chịu đọc): thêm header +
    đổi dấu phẩy mili-giây thành chấm. Dòng số thứ tự SRT giữ nguyên — VTT coi
    là cue identifier hợp lệ. File đã là VTT → trả nguyên."""
    chu = chu.lstrip("﻿")
    if chu.lstrip().upper().startswith("WEBVTT"):
        return chu
    chu = re.sub(r"(\d{2}:\d{2}:\d{2}),(\d{3})", r"\1.\2", chu)
    return "WEBVTT\n\n" + chu


def ghi_phu_de(video: dict, chu: str, duoi: str) -> Path:
    """Ghi phụ đề vào KHO APP (nguyên tử) — TUYỆT ĐỐI không ghi lên NAS.
    Gắn bản mới thì gỡ bản app cũ khác đuôi."""
    dich = _phu_de_app(video, duoi)
    dich.parent.mkdir(parents=True, exist_ok=True)
    for d in DUOI_PHU_DE:
        cu = _phu_de_app(video, d)
        if d != duoi and cu.is_file():
            cu.unlink()
    tam = dich.with_name(dich.name + ".tam")
    tam.write_text(chu, encoding="utf-8", newline="")
    os.replace(tam, dich)
    return dich


def xoa_phu_de(video: dict) -> bool:
    """Gỡ phụ đề APP SỞ HỮU (kho app). Trả False khi phụ đề đang đọc từ file cạnh
    video trên NAS — app chỉ đọc, muốn bỏ thì gỡ file đó trên NAS."""
    p, nguon = phu_de_tim(video)
    if p is None or nguon == "nas":
        return False
    p.unlink()
    return True
