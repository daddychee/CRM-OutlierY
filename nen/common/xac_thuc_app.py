# -*- coding: utf-8 -*-
"""KHUÔN XÁC THỰC APP — app phụ có được tin header danh tính không? (05/09/2026)

VÌ SAO CÓ FILE NÀY. Rà soát bảo mật 05/09 (sổ `docs/bao-mat-internet.md`) phát
hiện hệ chia HAI NỬA rõ rệt:
  - App CŨ ghép SSO (radary, seo-optimize, niche-research, content-ultimate,
    plannery): kiểm CẢ `*_TRUST_PROXY` LẪN loopback → ĐÚNG.
  - App V3 VIẾT MỚI (ai-agent, to-chuc, data-analytics, video-review): đọc thẳng
    `X-Remote-*`, không kiểm gì → chỉ cần cổng app lộ ra là
    `curl -H "X-Remote-Level: 5"` thành Owner tức khắc.

Khuôn dưới đây chép logic từ `apps/seo-optimize/seo/server.py:880-884` (app chắc
nhất trong đợt rà) để 4 app kia dùng CHUNG một nguồn sự thật — sửa luật một chỗ.

HAI ĐIỀU KIỆN, BẮT BUỘC ĐỦ CẢ HAI (không bao giờ nới thành "hoặc"):
  1. `<APP>_TRUST_PROXY=1` — khai trong Arguments tác vụ nền, KHÔNG phải .env.
     Chặn ca app chạy trần (dev/test/container mới) bị tin nhầm.
  2. Client là loopback — app bind 127.0.0.1 nên đường từ xa duy nhất là gateway
     ĐÃ xác thực. Chặn ca cổng app lỡ mở ra LAN/Internet.

FAIL-CLOSED TUYỆT ĐỐI. `request.client` là None (scope ASGI thiếu 'client') →
TỪ CHỐI. Đây chính là bẫy đã tìm thấy ở gateway: viết `if request.client and ...`
làm điều kiện sai khi client None → BỎ QUA kiểm → cho qua. Không lặp lại lỗi đó.
"""
from __future__ import annotations

import os

LOOPBACK = ("127.0.0.1", "::1")


def duoc_tin(request, ten_co: str) -> bool:
    """True khi ĐƯỢC PHÉP tin header danh tính từ proxy.

    request: đối tượng có `.client.host` (Starlette Request).
    ten_co:  tên biến môi trường của app, vd 'VR_TRUST_PROXY'.

    Mọi trường hợp không chắc chắn đều trả False — không biết người gọi là ai
    thì từ chối, đừng đoán.
    """
    if os.getenv(ten_co, "").strip() != "1":
        return False
    client = getattr(request, "client", None)
    if client is None:                      # fail-CLOSED (bẫy gateway 05/09)
        return False
    if getattr(client, "host", None) not in LOOPBACK:
        return False
    # SIẾT 05/09 GĐ7 (phát hiện khi tự tấn công): loopback MỘT MÌNH chưa đủ —
    # gateway VÀ mọi app phụ đều ở loopback, nên một app bị SSRF có thể gọi
    # `127.0.0.1:<cổng app khác>` kèm header X-Remote-* giả và được tin. Đo thật:
    # cờ bật + curl loopback + header giả = 200 (giả được Owner).
    # Nếu cụm đã cấp OUTLIERY_TOKEN_NOI_BO thì header danh tính PHẢI kèm token đó —
    # cùng bí mật gateway dùng cho route phát khóa. Chưa cấp token → giữ hành vi cũ
    # (tương thích ngược, guard loopback vẫn đứng) để không phá lúc chuyển giao.
    from nen.common import token_noi_bo
    if token_noi_bo.dang_bat():
        tok = None
        headers = getattr(request, "headers", None)
        if headers is not None:
            tok = headers.get(token_noi_bo.TEN_HEADER)
        if not token_noi_bo.khop(tok):
            return False
    return True


def ip_goi(request) -> str:
    """IP người gọi để ghi nhật ký — '?' khi không xác định được."""
    client = getattr(request, "client", None)
    return getattr(client, "host", None) or "?" if client else "?"
