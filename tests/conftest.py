# -*- coding: utf-8 -*-
"""Fixture chung cho bộ test tầng nền (05/09/2026).

VÌ SAO CÓ FILE NÀY. Siết bảo mật 05/09 thêm middleware CSRF (`_chan_csrf`): mọi
phương thức GHI có phiên phải mang token, không thì 403. Trình duyệt thật lấy
token từ ô ẩn `{{ o_csrf(request) }}` mà `o_csrf` đã chèn vào 27 form; test dùng
`TestClient` gọi thẳng nên không đi qua form.

Fixture dưới cho `TestClient` cư xử như trình duyệt thật: **có phiên thì tự gắn
`X-CSRF-Token`**. TUYỆT ĐỐI KHÔNG tắt middleware để test xanh — tắt là bỏ luôn
lớp phòng thủ vừa dựng, và test sẽ không còn chứng minh được điều gì.

Test nào muốn kiểm CHÍNH cơ chế CSRF thì gửi token sai/thiếu tường minh — header
tự gắn chỉ bù khi lời gọi CHƯA có header đó.
"""
import pytest


@pytest.fixture(autouse=True)
def _tu_gan_csrf(monkeypatch):
    from starlette.testclient import TestClient

    from nen.common import csrf
    from nen.gateway.main import COOKIE_TEN, _ky

    goc = TestClient.request

    def request(self, method, url, **kw):
        if str(method).upper() in ("POST", "PUT", "PATCH", "DELETE"):
            headers = dict(kw.get("headers") or {})
            if csrf.TEN_HEADER not in headers:
                ma = self.cookies.get(COOKIE_TEN)
                if ma:
                    try:
                        ten = _ky.loads(ma)
                        headers[csrf.TEN_HEADER] = csrf.sinh_token(ten)
                        kw["headers"] = headers
                    except Exception:
                        pass
        return goc(self, method, url, **kw)

    monkeypatch.setattr(TestClient, "request", request)
