# -*- coding: utf-8 -*-
"""GĐ1 — GATEWAY: mọi guard loopback phải FAIL-CLOSED (05/09/2026).

BẪY ĐÃ TÌM THẤY khi rà 05/09: 13 chỗ trong `nen/gateway/main.py` viết

    if request.client and request.client.host not in ("127.0.0.1", "::1"):
        return 403

Khi `request.client is None` (scope ASGI thiếu khóa 'client' — xảy ra với một số
ASGI server/adapter, hoặc khi chạy sau Unix socket) thì vế trái SAI → cả điều kiện
SAI → KHÔNG chặn → CHO QUA. Đây là lưới an toàn cuối của route
`/api/cau-hinh/api-khoa/{app_slug}` — route trả API KEY PLAINTEXT của cả công ty.

Test này QUÉT MÃ NGUỒN thay vì gọi từng route: khuôn sai có thể được chép sang
route mới bất cứ lúc nào, nên phải chặn ở dạng khuôn. Cùng tinh thần test quét cả
cây đã dùng cho theme 22/08.
"""
import re
from pathlib import Path

GOC = Path(__file__).resolve().parents[1]

# Khuôn SAI: `request.client and` đứng ngay trước phép so host.
KHUON_SAI = re.compile(r"if\s+request\.client\s+and\s+request\.client\.host\s+not\s+in")


def _cac_file_py():
    for thu_muc in ("nen", "apps"):
        for p in (GOC / thu_muc).rglob("*.py"):
            if ".venv" in p.parts or "node_modules" in p.parts:
                continue
            yield p


def test_khong_con_guard_loopback_fail_open():
    """Không file nào được dùng khuôn `if request.client and ... not in (...)`.

    Cách viết ĐÚNG: `if not request.client or request.client.host not in (...)`
    hoặc dùng `nen.common.xac_thuc_app.duoc_tin()`.
    """
    pham = []
    for p in _cac_file_py():
        try:
            noi_dung = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for so, dong in enumerate(noi_dung.splitlines(), 1):
            if KHUON_SAI.search(dong):
                pham.append(f"{p.relative_to(GOC)}:{so}")
    assert not pham, (
        "Guard loopback FAIL-OPEN (client=None thì lọt) tại:\n  "
        + "\n  ".join(pham)
        + "\nSửa thành: if not request.client or request.client.host not in (...)"
    )


def test_helper_xac_thuc_fail_closed_khi_client_none():
    """Chốt lại hành vi của helper dùng chung (phòng ai đó nới về sau)."""
    import os
    from nen.common import xac_thuc_app

    class _R:
        client = None

    os.environ["TEST_CO_TAM"] = "1"
    try:
        assert xac_thuc_app.duoc_tin(_R(), "TEST_CO_TAM") is False
    finally:
        os.environ.pop("TEST_CO_TAM", None)
