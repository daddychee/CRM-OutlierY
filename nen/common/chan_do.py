# -*- coding: utf-8 -*-
"""CHẶN DÒ — khóa tạm sau nhiều lần đăng nhập sai (05/09/2026).

VÌ SAO. Rà soát 05/09 (sổ `docs/bao-mat-internet.md` mục N2): `/login` không đếm
lần sai, không khóa tạm, không delay, không CAPTCHA. Cộng với chính sách mật khẩu
tối thiểu 6 ký tự = tài khoản bị dò trong thời gian ngắn khi ra Internet.

KÈM RỦI RO DoS: `/login` chạy bcrypt SYNC trong threadpool (có chủ đích — bcrypt
CPU-bound, để async là block event loop; đo thật 16/08 trung vị 44,6s/phiên).
Bắn vài trăm request/giây làm CẠN THREADPOOL → **cả cổng đứng**, không riêng
đăng nhập. Vì vậy phải chặn TRƯỚC khi chạy bcrypt.

KHÓA THEO (tên, IP), không theo tên đơn lẻ: kẻ tấn công dò 'owneruser' từ máy nó
KHÔNG được khóa lây Owner thật đang ngồi ở văn phòng.

Trạng thái trong BỘ NHỚ — đủ cho LAN một tiến trình (cùng lệ registry _TAC_VU).
Giới hạn đã biết: mất khi restart, không chia sẻ giữa nhiều worker. Khi ra
Internet nhiều worker thì chuyển sang SQLite/Redis — ghi trong sổ GĐ6.
"""
from __future__ import annotations

import os
import threading
from time import monotonic

SO_LAN_TOI_DA = int(os.getenv("LOGIN_SO_LAN_SAI", "8"))
KHOA_GIAY = int(os.getenv("LOGIN_KHOA_GIAY", "300"))        # 5 phút

_KHOA = threading.Lock()
_SO: dict[tuple[str, str], list] = {}        # (ten, ip) -> [so_lan, het_khoa]


def _key(ten: str, ip: str) -> tuple[str, str]:
    return ((ten or "").strip().lower(), (ip or "?").strip())


def bi_chan(ten: str, ip: str) -> bool:
    with _KHOA:
        so, het = _SO.get(_key(ten, ip), [0, 0.0])
        return so >= SO_LAN_TOI_DA and monotonic() < het


def con_lai(ten: str, ip: str) -> int:
    """Giây còn phải chờ (0 nếu không bị chặn) — để hiện thông báo tử tế."""
    with _KHOA:
        so, het = _SO.get(_key(ten, ip), [0, 0.0])
        if so < SO_LAN_TOI_DA:
            return 0
        return max(0, int(het - monotonic()))


def ghi_that_bai(ten: str, ip: str) -> None:
    with _KHOA:
        k = _key(ten, ip)
        so, _ = _SO.get(k, [0, 0.0])
        so += 1
        # tăng dần: mỗi lần vượt thêm một bội SO_LAN_TOI_DA thì thời gian nhân đôi
        boi = max(0, so - SO_LAN_TOI_DA) // max(1, SO_LAN_TOI_DA)
        _SO[k] = [so, monotonic() + KHOA_GIAY * (2 ** boi)]


def ghi_thanh_cong(ten: str, ip: str) -> None:
    with _KHOA:
        _SO.pop(_key(ten, ip), None)


def xoa_het() -> None:
    """Chỉ dùng trong test."""
    with _KHOA:
        _SO.clear()
