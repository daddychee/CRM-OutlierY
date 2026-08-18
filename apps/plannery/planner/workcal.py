"""Quy đổi "ngày công" (số thực) sang ngày lịch.

Lịch làm việc đã chốt 13/07/2026: Thứ 2 – Thứ 7, nghỉ Chủ nhật.
Thời gian trong engine tính bằng ngày công liên tục: t = 0 là ĐẦU ngày làm việc
thứ nhất của dự án; t = 2.5 nghĩa là đã trôi qua 2 ngày rưỡi làm việc.
"""

from __future__ import annotations

import math
from datetime import date, timedelta

_EPS = 1e-9

SUNDAY = 6  # date.weekday(): Thứ 2 = 0 ... Chủ nhật = 6
WORKDAYS_PER_WEEK = 6


def is_workday(d: date) -> bool:
    return d.weekday() != SUNDAY


def nth_workday(start: date, n: int) -> date:
    """Ngày làm việc thứ n (n >= 1) kể từ `start`; `start` là ngày 1 nếu là ngày làm việc."""
    if n < 1:
        raise ValueError(f"n phải >= 1, nhận {n}")
    d = start
    count = 0
    while True:
        if is_workday(d):
            count += 1
            if count == n:
                return d
        d += timedelta(days=1)


def workday_number_end(t: float) -> int:
    """Ngày làm việc (1-based) chứa thời điểm HOÀN THÀNH t — t = 2.0 xong cuối ngày 2."""
    return max(1, math.ceil(t - _EPS))


def workday_number_start(t: float) -> int:
    """Ngày làm việc (1-based) chứa thời điểm BẮT ĐẦU t — t = 2.0 bắt đầu đầu ngày 3."""
    return math.floor(t + _EPS) + 1


def date_at(start: date, t: float) -> date:
    """Ngày lịch mà việc hoàn thành, nếu ngày làm việc thứ nhất của dự án là `start`."""
    return nth_workday(start, workday_number_end(t))


def _workdays_upto(d: date) -> int:
    # số ngày không-phải-Chủ-nhật từ mốc lịch tới hết ngày d
    o = d.toordinal()  # ordinal 7 = một Chủ nhật → các ordinal chia hết cho 7 là CN
    return o - o // 7


def workday_index(anchor: date, d: date) -> int:
    """Số thứ tự ngày làm việc của ngày d so với mốc anchor (anchor = ngày 1).

    d là Chủ nhật → tính như ngày làm việc gần nhất TRƯỚC đó (deadline rơi vào CN
    nghĩa là phải xong trong tuần). d trước anchor cho kết quả <= 0.
    """
    return _workdays_upto(d) - _workdays_upto(anchor) + 1
