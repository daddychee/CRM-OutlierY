# -*- coding: utf-8 -*-
"""CSRF — token chống giả mạo yêu cầu từ site khác (05/09/2026).

VÌ SAO. Rà soát 05/09 (sổ `docs/bao-mat-internet.md` mục N1): toàn bộ `nen/`
không có một dòng CSRF nào. 38 route POST — tạo/sửa/xóa tài khoản, đặt cấp truy
cập, bật admin ủy quyền, thêm/thu hồi API key, đổi mật khẩu — chỉ được che bởi
`samesite="lax"` của cookie phiên.

VÌ SAO LAX KHÔNG ĐỦ khi ra Internet:
  1. `/nen{duong:path}` (`gateway/main.py`) trả **307 giữ nguyên method + body**
     → bàn đạp để chuyển một điều hướng thành POST.
  2. Cookie đặt ở `.outliery.test` khi vào bằng tên miền → **subdomain khác cùng
     site KHÔNG bị Lax chặn**; một subdomain bị chiếm là POST thay mặt Owner.
  3. Vài trình duyệt/WebView cũ vẫn mặc định `SameSite=None`.

THIẾT KẾ: token = `<hết-hạn>.<chữ-ký HMAC>` ký bằng SESSION_SECRET, **gắn với tên
người dùng** nên token của A không dùng được cho phiên của B. Không cần lưu trạng
thái phía server (hợp với việc chưa có bảng phiên).

DÙNG: nhúng `<input type="hidden" name="_csrf">` vào form; JS gửi header
`X-CSRF-Token`. Route ghi gọi `kiem_token` trước khi làm gì.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import time

TEN_TRUONG = "_csrf"
TEN_HEADER = "X-CSRF-Token"
HAN_GIAY = int(os.getenv("CSRF_HAN_GIAY", str(12 * 3600)))   # 12 giờ


def _bi_mat() -> bytes:
    """Dùng chung SESSION_SECRET — cùng vòng đời với phiên đăng nhập."""
    return (os.getenv("SESSION_SECRET") or "khong-co-secret").encode()


def _ky(ten: str, het: int) -> str:
    thong_diep = f"{ten}|{het}".encode()
    return hmac.new(_bi_mat(), thong_diep, hashlib.sha256).hexdigest()


def sinh_token(ten_user: str) -> str:
    het = int(time.time()) + HAN_GIAY
    return f"{het}.{_ky(ten_user or '', het)}"


def kiem_token(token: str | None, ten_user: str) -> bool:
    """True khi token hợp lệ, chưa hết hạn, và đúng của `ten_user`.

    Mọi trường hợp không chắc chắn đều False — so bằng `compare_digest` để không
    rò thông tin qua thời gian phản hồi.
    """
    if not token or "." not in token:
        return False
    phan_han, _, chu_ky = token.partition(".")
    try:
        het = int(phan_han)
    except ValueError:
        return False
    if het < int(time.time()):
        return False
    return hmac.compare_digest(chu_ky, _ky(ten_user or "", het))
