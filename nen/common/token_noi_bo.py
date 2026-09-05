# -*- coding: utf-8 -*-
"""TOKEN NỘI BỘ — lớp thứ hai cho các route chỉ dành cho app phụ (05/09/2026).

VÌ SAO. Hai route của gateway trả **API key dạng thô** của cả công ty:
    GET /api/cau-hinh/llm/{vai}
    GET /api/cau-hinh/api-khoa/{app_slug}
Xác thực duy nhất của chúng là kiểm IP loopback — không session, không token.
Ghi chú `ponytail:` ngay trong code đã nêu đúng trần này và đề xuất token nội bộ.

Kiểm IP là chưa đủ khi ra Internet: **mọi SSRF trong hệ đều phát request TỪ
loopback**. App nào nhận URL người dùng rồi gọi đi (nạp nguồn ngoài của ai-agent,
niche-research…) đều thành đường vòng để đọc hai route này.

CÁCH DÙNG: gateway sinh bí mật lúc khởi động, truyền cho app qua biến môi trường
`OUTLIERY_TOKEN_NOI_BO`; app gửi kèm header `X-Noi-Bo` khi gọi hai route trên.

TƯƠNG THÍCH NGƯỢC CÓ CHỦ ĐÍCH: chưa đặt biến → `khop()` luôn True (bỏ qua lớp 2,
guard loopback đã fail-closed vẫn giữ). Bật kiểm cứng ngay sẽ làm cả 7 app mất
khóa LLM giữa giờ làm việc. GĐ6 đặt token trong start-all.ps1 rồi siết bắt buộc.
"""
from __future__ import annotations

import hmac
import os
import secrets

TEN_BIEN = "OUTLIERY_TOKEN_NOI_BO"
TEN_HEADER = "X-Noi-Bo"


def sinh() -> str:
    """Bí mật mới cho một lần khởi động cụm."""
    return secrets.token_urlsafe(32)


def dang_bat() -> bool:
    return bool(os.getenv(TEN_BIEN, "").strip())


def khop(token: str | None) -> bool:
    """True khi được phép đi tiếp.

    Chưa đặt biến môi trường → True (giai đoạn chuyển, xem docstring module).
    Đã đặt → phải khớp tuyệt đối, so bằng `compare_digest` để không rò độ dài
    hay nội dung token qua thời gian phản hồi.
    """
    that = os.getenv(TEN_BIEN, "").strip()
    if not that:
        return True
    return hmac.compare_digest(that, (token or "").strip())
