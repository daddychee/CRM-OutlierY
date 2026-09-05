# -*- coding: utf-8 -*-
"""GĐ1 — TOKEN NỘI BỘ cho 2 route phát API key (05/09/2026).

LỖ (rà 05/09, sổ `docs/bao-mat-internet.md` mục N5/A1): hai route
  GET /api/cau-hinh/llm/{vai}
  GET /api/cau-hinh/api-khoa/{app_slug}
trả **API key dạng thô** của cả công ty, và xác thực DUY NHẤT là kiểm IP loopback.
Không session, không token. Ghi chú `ponytail:` ngay trong code đã nêu trần bảo vệ
này và đề xuất "token nội bộ khi tách nhiều máy".

Ra Internet thì kiểm IP là chưa đủ: bất kỳ SSRF nào trong hệ (app tự gọi URL do
người dùng nhập) đều phát request TỪ loopback → vượt qua guard.

Lớp thứ hai: header `X-Noi-Bo` khớp bí mật chung. Bí mật sinh lúc khởi động và
truyền cho app qua env, không nằm trong file cấu hình nào.
"""
import os

import pytest

from nen.common import token_noi_bo


def test_sinh_token_du_dai_va_ngau_nhien():
    a, b = token_noi_bo.sinh(), token_noi_bo.sinh()
    assert len(a) >= 32 and a != b


def test_khop_dung(monkeypatch):
    monkeypatch.setenv("OUTLIERY_TOKEN_NOI_BO", "bi-mat-test-1234567890abcdef")
    assert token_noi_bo.khop("bi-mat-test-1234567890abcdef") is True


def test_khop_sai_thi_tu_choi(monkeypatch):
    monkeypatch.setenv("OUTLIERY_TOKEN_NOI_BO", "bi-mat-test-1234567890abcdef")
    assert token_noi_bo.khop("sai") is False
    assert token_noi_bo.khop("") is False
    assert token_noi_bo.khop(None) is False


def test_chua_dat_token_thi_KHONG_chan(monkeypatch):
    """TƯƠNG THÍCH NGƯỢC CÓ CHỦ ĐÍCH.

    Hệ đang chạy chưa có biến này; bật kiểm cứng ngay là cả 7 app mất khóa LLM
    giữa giờ làm việc. Nên: chưa đặt token → bỏ qua lớp 2, guard loopback (đã
    fail-closed) vẫn giữ. Đặt token → bắt buộc khớp.
    GĐ6 sẽ đặt token trong start-all.ps1 rồi siết thành bắt buộc.
    """
    monkeypatch.delenv("OUTLIERY_TOKEN_NOI_BO", raising=False)
    assert token_noi_bo.khop(None) is True
    assert token_noi_bo.khop("bat-ky") is True


def test_so_sanh_hang_thoi_gian():
    """Dùng compare_digest — chống dò token qua đo thời gian phản hồi."""
    import inspect
    ma = inspect.getsource(token_noi_bo.khop)
    assert "compare_digest" in ma, "phải so bằng hmac.compare_digest"
