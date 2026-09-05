# -*- coding: utf-8 -*-
"""GĐ1 — KHUÔN XÁC THỰC APP (05/09/2026).

BỐI CẢNH: rà soát 05/09 phát hiện hệ chia HAI NỬA — app cũ ghép SSO (radary,
seo-optimize, niche-research, content-ultimate, plannery) kiểm CẢ `*_TRUST_PROXY`
LẪN loopback; app V3 viết mới (ai-agent, to-chuc, data-analytics, video-review)
tin header VÔ ĐIỀU KIỆN. Cổng 9103 lộ ra là `curl -H "X-Remote-Level: 5"` thành
Owner tức khắc.

Khuôn này chép từ `apps/seo-optimize/seo/server.py:880-884` (app chắc nhất đợt rà):
tin header CHỈ KHI đủ CẢ HAI điều kiện, thiếu bất kỳ điều nào → fail-closed.

TUYỆT ĐỐI KHÔNG nới thành "hoặc" — mỗi điều kiện chặn một lớp khác nhau:
- TRUST_PROXY: chặn app chạy trần (dev/test/container) bị tin nhầm.
- loopback:    chặn kẻ trong LAN gọi thẳng cổng app nếu cổng lỡ mở.
"""
import pytest

from nen.common import xac_thuc_app


class _Client:
    def __init__(self, host): self.host = host


class _Req:
    """Giả Request của Starlette — chỉ cần .client (khuôn thật chỉ đọc chỗ này)."""
    def __init__(self, host="127.0.0.1"):
        self.client = _Client(host) if host is not None else None


def test_du_hai_dieu_kien_thi_tin(monkeypatch):
    monkeypatch.setenv("VR_TRUST_PROXY", "1")
    assert xac_thuc_app.duoc_tin(_Req("127.0.0.1"), "VR_TRUST_PROXY") is True
    assert xac_thuc_app.duoc_tin(_Req("::1"), "VR_TRUST_PROXY") is True


def test_thieu_trust_proxy_thi_tu_choi(monkeypatch):
    """Loopback đúng nhưng KHÔNG bật cờ → vẫn từ chối."""
    monkeypatch.delenv("VR_TRUST_PROXY", raising=False)
    assert xac_thuc_app.duoc_tin(_Req("127.0.0.1"), "VR_TRUST_PROXY") is False


def test_khong_loopback_thi_tu_choi(monkeypatch):
    """Cờ bật nhưng gọi từ LAN → từ chối. Đây là ca `curl` từ máy khác."""
    monkeypatch.setenv("VR_TRUST_PROXY", "1")
    assert xac_thuc_app.duoc_tin(_Req("192.168.1.50"), "VR_TRUST_PROXY") is False


def test_client_none_thi_tu_choi_FAIL_CLOSED(monkeypatch):
    """BẪY CHÍNH đợt rà 05/09: gateway viết `if request.client and ...` nên khi
    scope ASGI thiếu 'client' thì vế trái sai → BỎ QUA kiểm → cho đi tiếp.
    Khuôn mới phải fail-CLOSED: không biết người gọi là ai thì từ chối."""
    monkeypatch.setenv("VR_TRUST_PROXY", "1")
    assert xac_thuc_app.duoc_tin(_Req(None), "VR_TRUST_PROXY") is False


def test_co_bat_bang_gia_tri_khac_1_thi_tu_choi(monkeypatch):
    """Chỉ '1' mới bật — '0'/'true'/rỗng đều là tắt (tránh bật nhầm do gõ)."""
    monkeypatch.setenv("VR_TRUST_PROXY", "0")
    assert xac_thuc_app.duoc_tin(_Req("127.0.0.1"), "VR_TRUST_PROXY") is False
    monkeypatch.setenv("VR_TRUST_PROXY", "true")
    assert xac_thuc_app.duoc_tin(_Req("127.0.0.1"), "VR_TRUST_PROXY") is False


def test_moi_app_mot_co_rieng(monkeypatch):
    """Cờ của app này bật KHÔNG được làm app kia tin theo."""
    monkeypatch.setenv("VR_TRUST_PROXY", "1")
    monkeypatch.delenv("DA_TRUST_PROXY", raising=False)
    assert xac_thuc_app.duoc_tin(_Req("127.0.0.1"), "VR_TRUST_PROXY") is True
    assert xac_thuc_app.duoc_tin(_Req("127.0.0.1"), "DA_TRUST_PROXY") is False


# ── GĐ7 (phát hiện khi tự tấn công 05/09): loopback + token nội bộ ─────────────
def test_co_token_bat_thi_doi_token_dung(monkeypatch):
    """Khi cụm đã cấp OUTLIERY_TOKEN_NOI_BO, header danh tính PHẢI kèm token —
    chống một app bị SSRF gọi loopback giả gateway. Đo thật GĐ7: cờ bật + loopback
    + header giả (không token) = 200 (giả được Owner) TRƯỚC bản vá này."""
    monkeypatch.setenv("VR_TRUST_PROXY", "1")
    monkeypatch.setenv("OUTLIERY_TOKEN_NOI_BO", "bi-mat-cum")

    class _R:
        def __init__(self, tok):
            self.client = type("C", (), {"host": "127.0.0.1"})()
            self.headers = {"X-Noi-Bo": tok} if tok else {}

    assert xac_thuc_app.duoc_tin(_R("bi-mat-cum"), "VR_TRUST_PROXY") is True
    assert xac_thuc_app.duoc_tin(_R("sai"), "VR_TRUST_PROXY") is False
    assert xac_thuc_app.duoc_tin(_R(None), "VR_TRUST_PROXY") is False


def test_chua_cap_token_thi_giu_hanh_vi_cu(monkeypatch):
    """Tương thích ngược: chưa đặt token → chỉ cần loopback (guard vẫn đứng)."""
    monkeypatch.setenv("VR_TRUST_PROXY", "1")
    monkeypatch.delenv("OUTLIERY_TOKEN_NOI_BO", raising=False)

    class _R:
        client = type("C", (), {"host": "127.0.0.1"})()
        headers = {}

    assert xac_thuc_app.duoc_tin(_R(), "VR_TRUST_PROXY") is True
