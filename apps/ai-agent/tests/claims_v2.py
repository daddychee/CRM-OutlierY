# -*- coding: utf-8 -*-
"""Helper V2 dùng chung cho tests: app nhận CLAIMS từ gateway thay vì tự đăng nhập.

Khuôn chuyển fixture login→claims theo apps/data-analytics/tests/test_bao_cao_lich_su.py:
- _users*/users.txt hệ cũ → NO-OP (giữ chữ ký call-site);
- _login/_dang_nhap(ten) → TestClient(app, headers={claims}) — X-Remote-Dept đi
  URL-ENCODED (header không chở UTF-8 thô 'Vận hành - Sản xuất');
- 'chế độ mở/khách' hệ cũ không còn — ca tương đương là claims THIẾU bộ phận
  (gateway không phát X-Remote-Dept) → app không ghi lịch sử/sổ, không lọc quyền.
"""
from urllib.parse import quote

from fastapi.testclient import TestClient


def client_claims(app, ten: str, bo_phan: str = "", level: int = 1,
                  vai: str = "viewer") -> TestClient:
    headers = {"X-Remote-User": ten, "X-Remote-Level": str(level),
               "X-Remote-Role": vai}
    if bo_phan:
        headers["X-Remote-Dept"] = quote(bo_phan)
    return TestClient(app, headers=headers)


def client_khach(app) -> TestClient:
    """Claims đủ danh tính + level cao nhưng THIẾU bộ phận — tương đương 'khách/chế
    độ mở' hệ cũ ở các nhánh `if user.get("bo_phan")` (không ghi lịch sử/sổ)."""
    return TestClient(app, headers={"X-Remote-User": "khach", "X-Remote-Level": "5",
                                    "X-Remote-Role": "viewer"})
