"""Test quy đổi ngày công → ngày lịch (Thứ 2 – Thứ 7, nghỉ Chủ nhật)."""

from datetime import date

from planner.workcal import (
    date_at,
    nth_workday,
    workday_index,
    workday_number_end,
    workday_number_start,
)

MONDAY = date(2026, 7, 13)  # thứ Hai


def test_moc_la_thu_hai():
    assert MONDAY.weekday() == 0


def test_nth_workday_bo_chu_nhat():
    assert nth_workday(MONDAY, 1) == date(2026, 7, 13)
    assert nth_workday(MONDAY, 6) == date(2026, 7, 18)  # thứ Bảy
    assert nth_workday(MONDAY, 7) == date(2026, 7, 20)  # bỏ CN 19/07 → thứ Hai
    # bắt đầu vào Chủ nhật → ngày làm việc 1 là thứ Hai kế tiếp
    assert nth_workday(date(2026, 7, 19), 1) == date(2026, 7, 20)


def test_workday_number():
    assert workday_number_end(0.5) == 1
    assert workday_number_end(1.0) == 1  # xong đúng cuối ngày 1
    assert workday_number_end(1.5) == 2
    assert workday_number_end(3.0) == 3
    assert workday_number_start(0.0) == 1
    assert workday_number_start(0.5) == 1
    assert workday_number_start(1.0) == 2  # bắt đầu đầu ngày 2


def test_date_at_qua_chu_nhat():
    assert date_at(MONDAY, 6.5) == date(2026, 7, 20)  # nửa ngày thứ 7 rơi sang thứ Hai
    assert date_at(MONDAY, 11.0) == date(2026, 7, 24)  # ngày làm việc 11 = thứ Sáu tuần 2


def test_workday_index():
    assert workday_index(MONDAY, date(2026, 7, 13)) == 1
    assert workday_index(MONDAY, date(2026, 7, 18)) == 6   # thứ Bảy
    assert workday_index(MONDAY, date(2026, 7, 19)) == 6   # CN → tính như thứ Bảy trước đó
    assert workday_index(MONDAY, date(2026, 7, 20)) == 7
    assert workday_index(MONDAY, date(2026, 7, 25)) == 12
    # trước mốc → <= 0 (deadline đã qua từ trước khi bắt đầu)
    assert workday_index(MONDAY, date(2026, 7, 12)) == 0   # CN ngay trước
    assert workday_index(MONDAY, date(2026, 7, 11)) == 0   # thứ Bảy trước
    assert workday_index(MONDAY, date(2026, 7, 10)) == -1  # thứ Sáu trước
