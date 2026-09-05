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

def header() -> dict:
    """Header để app phụ gửi kèm khi gọi 2 route phát khóa của gateway.

    Chưa đặt biến môi trường → trả dict RỖNG (giai đoạn chuyển, xem docstring
    module). Nhờ vậy có thể sửa hết caller TRƯỚC, đặt biến SAU — không có khoảnh
    khắc nào cụm mất khóa.
    """
    t = os.getenv(TEN_BIEN, "").strip()
    return {TEN_HEADER: t} if t else {}

def _duong_file() -> str:
    """File giữ token — mọi tiến trình (gateway + 7 app) đọc CÙNG một giá trị.

    SỰ CỐ 05/09: token sinh động `[Guid]::NewGuid()` trong start-all → mỗi lần
    restart LẺ một app, app đó có token MỚI lệch với gateway → 403 khi xin khóa +
    401 danh tính (cả cụm loạn). Token nội bộ phải ỔN ĐỊNH như SESSION_SECRET.
    """
    import os as _os
    goc = _os.environ.get("OUTLIERY_ROOT") or _os.getcwd()
    return _os.path.join(goc, "data", "nen", "token_noi_bo.txt")


def lay_hoac_sinh() -> str:
    """Đọc token từ file; chưa có thì sinh + lưu (ghi nguyên tử). Trả token để
    start-all bơm vào env cho cả cụm. Ổn định qua mọi lần restart."""
    import os as _os
    p = _duong_file()
    if _os.path.isfile(p):
        t = open(p, encoding="utf-8").read().strip()
        if t:
            return t
    _os.makedirs(_os.path.dirname(p), exist_ok=True)
    t = secrets.token_urlsafe(48)
    tam = p + ".tmp"
    with open(tam, "w", encoding="utf-8") as f:
        f.write(t)
    _os.replace(tam, p)
    return t

