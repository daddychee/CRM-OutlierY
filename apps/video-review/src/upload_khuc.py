# -*- coding: utf-8 -*-
"""Upload TỪNG KHÚC (chunked) — file 2-10GB qua proxy an toàn (user chốt 18/08).

Proxy gateway buffer TRỌN body mỗi request vào RAM → upload một phát 10GB là bom
RAM máy chủ. Giải ở CLIENT: trình duyệt cắt file thành khúc VR_KHUC_UP_MB (64MB)
gửi TUẦN TỰ; mỗi request qua proxy chỉ nặng một khúc. KHÔNG sửa proxy — bật
chunked transfer ở proxy sẽ vỡ app stdlib phía sau (Content Ultimate).

Phiên upload: registry bộ nhớ (đủ 1 worker, mất khi restart — cùng lệ nap_nas);
phiên bỏ dở >24h (đóng tab giữa chừng, app restart) được quét dọn kèm file .tam
mỗi lần có phiên mới. Ghép xong file mới ghi sổ video — dở dang không có bản ghi.
"""
from __future__ import annotations

import os
import secrets
import threading
import time
from pathlib import Path

from src import kho_video

_PHIEN: dict[str, dict] = {}
_KHOA = threading.Lock()
_HAN_GIAY = 24 * 3600


def tran_bytes() -> int:
    return int(os.environ.get("VR_MAX_MB", "20480")) * 1024 * 1024


def don_phien_cu() -> None:
    """Dọn phiên bỏ dở >24h: registry + file .tam; quét cả .tam mồ côi sau restart."""
    han = time.time() - _HAN_GIAY
    with _KHOA:
        for pid in [p for p, v in _PHIEN.items() if v["luc"] < han]:
            v = _PHIEN.pop(pid)
            try:
                v["tam"].unlink()
            except OSError:
                pass
    try:
        for f in kho_video.kho_dir().glob("up-*.tam"):
            if f.stat().st_mtime < han:
                f.unlink()
    except OSError:
        pass


def bat_dau(ten_file: str, kich_thuoc: int, ten: str, nguoi: str, bo_phan: str) -> str:
    """Kiểm đuôi + trần Ở CỬA rồi mở phiên; trả mã phiên cho client gửi khúc."""
    don_phien_cu()
    duoi = Path(ten_file or "").suffix.lower()
    if duoi not in kho_video.DUOI_CHO_PHEP:
        raise ValueError("Chỉ nhận video mp4 / webm / mov / m4v.")
    kich_thuoc = int(kich_thuoc)
    if kich_thuoc <= 0:
        raise ValueError("Kích thước file lạ.")
    if kich_thuoc > tran_bytes():
        raise OverflowError(f"File quá {tran_bytes() // 1048576}MB (VR_MAX_MB).")
    pid = secrets.token_hex(8)
    tam = kho_video.kho_dir() / f"up-{pid}.tam"
    tam.parent.mkdir(parents=True, exist_ok=True)
    tam.touch()
    with _KHOA:
        _PHIEN[pid] = {"nguoi": nguoi, "bo_phan": bo_phan,
                       "ten": (ten or "").strip() or Path(ten_file).stem,
                       "duoi": duoi, "tong": kich_thuoc, "da_nhan": 0,
                       "tam": tam, "luc": time.time()}
    return pid


def _lay(pid: str, nguoi: str) -> dict | None:
    p = _PHIEN.get(pid)
    return p if p is not None and p["nguoi"] == nguoi else None


def ghi_khuc(pid: str, nguoi: str, offset: int, du_lieu: bytes) -> int:
    """Nối một khúc vào file phiên — offset PHẢI khớp số byte đã nhận (tuần tự,
    chống ghi lệch làm hỏng file). Hàm SYNC — route đẩy threadpool."""
    p = _lay(pid, nguoi)
    if p is None:
        raise KeyError(pid)
    if offset != p["da_nhan"]:
        raise ValueError(f"Lệch khúc: server đã nhận {p['da_nhan']}, client gửi offset {offset}.")
    if p["da_nhan"] + len(du_lieu) > p["tong"]:
        raise OverflowError("Dữ liệu vượt kích thước đã khai.")
    with open(p["tam"], "ab") as f:
        f.write(du_lieu)
    p["da_nhan"] += len(du_lieu)
    p["luc"] = time.time()
    return p["da_nhan"]


def hoan_tat(pid: str, nguoi: str) -> dict:
    """Đủ byte mới ghi sổ + os.replace vào kho — thiếu là từ chối, không ghi sổ."""
    p = _lay(pid, nguoi)
    if p is None:
        raise KeyError(pid)
    if p["da_nhan"] != p["tong"]:
        raise ValueError(f"Chưa đủ dữ liệu: {p['da_nhan']}/{p['tong']} byte.")
    ban_ghi = kho_video.them_video(p["ten"], p["duoi"], p["nguoi"], p["bo_phan"], p["tong"])
    ban_ghi["duong_tuyet_doi"].parent.mkdir(parents=True, exist_ok=True)
    os.replace(p["tam"], ban_ghi["duong_tuyet_doi"])
    with _KHOA:
        _PHIEN.pop(pid, None)
    return ban_ghi


def huy(pid: str, nguoi: str) -> None:
    p = _lay(pid, nguoi)
    if p is None:
        return
    with _KHOA:
        _PHIEN.pop(pid, None)
    try:
        p["tam"].unlink()
    except OSError:
        pass
