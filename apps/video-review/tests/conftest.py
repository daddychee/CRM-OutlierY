# -*- coding: utf-8 -*-
"""Fixture chung cho test video-review (05/09/2026).

VÌ SAO CÓ FILE NÀY. Siết bảo mật 05/09 bắt `lay_user` đòi ĐỦ CẢ HAI:
`VR_TRUST_PROXY=1` VÀ client là loopback (xem `nen/common/xac_thuc_app.py`).

Nhưng `TestClient` mặc định gửi với `client.host == "testclient"` — KHÔNG phải
loopback — nên mọi test cũ nhận 401. Cách xử lý ĐÚNG là cho test giả lập ĐÚNG
môi trường chạy thật (gateway gọi app qua 127.0.0.1), TUYỆT ĐỐI KHÔNG nới bản vá
để test xanh — nới là mở lại đúng lỗ vừa bịt.

Hai fixture autouse dưới đây làm test chạy như hệ thật:
  - `_bat_trust_proxy`: đặt cờ như Arguments của tác vụ nền.
  - `_testclient_loopback`: ép TestClient khai địa chỉ 127.0.0.1.
"""
import pytest
from starlette.testclient import TestClient


@pytest.fixture(autouse=True)
def _bat_trust_proxy(monkeypatch):
    """Như tác vụ nền thật: VR_TRUST_PROXY=1 trong Arguments."""
    monkeypatch.setenv("VR_TRUST_PROXY", "1")


@pytest.fixture(autouse=True)
def _testclient_loopback(monkeypatch):
    """TestClient khai client.host = 127.0.0.1 (mặc định là 'testclient').

    TÔN TRỌNG test tự khai địa chỉ: `TestClient(app, client=("192.168.1.9", 1))`
    dùng để kiểm "gọi từ LAN thì bị chặn" — fixture KHÔNG được ghi đè ca đó, nếu
    không thì chính test bảo vệ lại bị vô hiệu.
    Chỉ thay khi địa chỉ đang là mặc định 'testclient'.
    """
    from starlette.testclient import _TestClientTransport
    goc_handle = _TestClientTransport.handle_request

    def handle_loopback(self, request):
        if getattr(self, "client", None) in (None, ("testclient", 50000)):
            self.client = ("127.0.0.1", 50000)
        return goc_handle(self, request)

    monkeypatch.setattr(_TestClientTransport, "handle_request", handle_loopback)
