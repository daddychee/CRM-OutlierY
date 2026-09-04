# -*- coding: utf-8 -*-
"""Nhận xét của MÁY về một bản dựng: đo mạch dựng → câu bệnh → lưu vào sổ.

Nhận xét máy nằm chung danh sách với note người (bảng riêng nhưng cùng trục thời
gian, giao diện trộn lại theo mốc). Máy KHÔNG chấm điểm và KHÔNG chặn Approve.

Đo một video 37 phút mất khoảng 4 phút nên chạy NỀN theo khuôn tác vụ của
Data Analytics: tạo tác vụ → trả ngay → poll trạng thái.
"""
from __future__ import annotations

import json
import secrets
import threading
from datetime import datetime

from src import kho_video, mach_dung

_TAC_VU: dict[str, dict] = {}
_KHOA = threading.Lock()


def ds_nhan_xet(video_ma: str) -> list[dict]:
    conn = kho_video.ket_noi()
    try:
        hang = conn.execute(
            "SELECT * FROM nhan_xet_may WHERE video_ma=?"
            " ORDER BY ts_giay IS NULL, ts_giay, id", (video_ma,)).fetchall()
        return [dict(h) for h in hang]
    finally:
        conn.close()


def xoa_nhan_xet(video_ma: str) -> None:
    conn = kho_video.ket_noi()
    try:
        conn.execute("DELETE FROM nhan_xet_may WHERE video_ma=?", (video_ma,))
        conn.commit()
    finally:
        conn.close()


def luu_nhan_xet(video_ma: str, cac: list[dict]) -> int:
    """Ghi đè toàn bộ nhận xét của video — chạy lại là thay bộ cũ, không cộng dồn."""
    xoa_nhan_xet(video_ma)
    luc = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = kho_video.ket_noi()
    try:
        for c in cac:
            conn.execute(
                "INSERT INTO nhan_xet_may (video_ma, ts_giay, ts_het, benh, muc, loi,"
                " so_lieu, nen_lam, trich_kb, phan, tao_luc)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (video_ma, c.get("ts"), c.get("ts_het"), c["benh"], c.get("muc", "nhe"),
                 c.get("loi", ""), c.get("so_lieu", ""), c.get("nen_lam", ""),
                 c.get("trich_kb", ""), c.get("phan", ""), luc))
        conn.commit()
    finally:
        conn.close()
    return len(cac)


def danh_dau_da_doc(nx_id: int) -> None:
    conn = kho_video.ket_noi()
    try:
        cur = conn.execute("UPDATE nhan_xet_may SET da_doc=1 WHERE id=?", (nx_id,))
        if cur.rowcount == 0:
            raise KeyError(nx_id)
        conn.commit()
    finally:
        conn.close()


def sua_phan(nx_id: int, phan_nguoi: str) -> None:
    """Người sửa phán quyết của máy (luồng 2) — giữ cả phán gốc để đối chiếu."""
    conn = kho_video.ket_noi()
    try:
        cur = conn.execute("UPDATE nhan_xet_may SET phan_nguoi=? WHERE id=?",
                           (phan_nguoi.strip(), nx_id))
        if cur.rowcount == 0:
            raise KeyError(nx_id)
        conn.commit()
    finally:
        conn.close()


def tao_tac_vu(video_ma: str, nguoi: str) -> str:
    tid = secrets.token_hex(8)
    with _KHOA:
        _TAC_VU[tid] = {"nguoi": nguoi, "video_ma": video_ma, "trang_thai": "dang_chay",
                        "so": 0, "loi": ""}
    return tid


def chay_danh_gia(tid: str) -> None:
    """Thân tác vụ — SYNC, route đẩy threadpool (bài học khóa event loop)."""
    tv = _TAC_VU.get(tid)
    if tv is None:
        return
    try:
        video = kho_video.lay_video(tv["video_ma"])
        if video is None:
            raise KeyError(tv["video_ma"])
        p = kho_video.duong_video(video)
        if p is None or not p.is_file():
            raise FileNotFoundError("File gốc không còn ở nơi đã liên kết")
        so = mach_dung.do_video(p)
        if not so:
            raise RuntimeError("Không đo được mạch dựng (thiếu ffmpeg hoặc file lạ)")
        ho_so = mach_dung.doc_ho_so(_niche_cua(video))
        cac = mach_dung.chan_doan(so, ho_so)
        _luu_so_do(tv["video_ma"], so)
        tv["so"] = luu_nhan_xet(tv["video_ma"], cac)
        tv["trang_thai"] = "xong"
    except Exception as e:                       # lỗi nền chỉ ghi vào tác vụ
        tv["trang_thai"] = "loi"
        tv["loi"] = str(e)


def _niche_cua(video: dict) -> str:
    """Niche suy từ đường NAS: 'Life In/US/...' → life-in. Không nhận ra → mặc định."""
    dau = (video.get("duong") or "").split("/")[0].strip().lower().replace(" ", "-")
    return dau or "_mac_dinh"


def _luu_so_do(video_ma: str, so: dict) -> None:
    """Số đo thô cất cùng bản ghi để giao diện hiện 'xem số liệu thô'."""
    gon = {k: v for k, v in so.items() if k not in ("moc_cat", "duong_cong")}
    gon["duong_cong"] = [[round(t, 1), round(v, 2)] for t, v in so.get("duong_cong", [])]
    gon["moc_cat"] = [round(m, 2) for m in so.get("moc_cat", [])]
    conn = kho_video.ket_noi()
    try:
        conn.execute("UPDATE video SET so_do_nhip=? WHERE ma=?",
                     (json.dumps(gon, ensure_ascii=False), video_ma))
        conn.commit()
    finally:
        conn.close()


def so_do_cua(video: dict) -> dict:
    try:
        return json.loads(video.get("so_do_nhip") or "{}")
    except (json.JSONDecodeError, TypeError):
        return {}


def trang_thai(tid: str, nguoi: str) -> dict | None:
    """RBAC như lệ tác vụ nền: chỉ CHỦ tác vụ xem, khác người → None (404 lặng lẽ)."""
    tv = _TAC_VU.get(tid)
    if tv is None or tv["nguoi"] != nguoi:
        return None
    return {"trang_thai": tv["trang_thai"], "so": tv["so"], "loi": tv["loi"]}
