# -*- coding: utf-8 -*-
"""conftest app ai-agent — chạy test TỪ THƯ MỤC APP (app tự đủ, Luật 2):
  cd apps/ai-agent && pytest
Mỗi app một process pytest riêng → package `src` không đụng app khác.
"""
import os
import sys
from pathlib import Path

import pytest

_APP = Path(__file__).resolve().parent
_ROOT = _APP.parents[1]
sys.path.insert(0, str(_APP))    # import src.*
sys.path.insert(0, str(_ROOT))   # import nen.* (nếu cần về sau)

# Test KHÔNG BAO GIỜ gọi API thật/Qdrant thật — ép mọi công tắc mock TRƯỚC khi
# test import app (đặt ở đây thắng .env vì load_dotenv không ghi đè biến có sẵn).
os.environ["MOCK_MODE"] = "true"
os.environ["WRITER_MOCK_MODE"] = "true"
os.environ["CRITIC_MOCK_MODE"] = "true"
os.environ["GATEWAY_URL"] = "http://127.0.0.1:1"   # két: đứt ngay → env/mock
# Qdrant TEST — mock không đụng tới nhưng ghim sẵn cho chắc (kho thật :6333 cấm)
os.environ["QDRANT_URL"] = "http://127.0.0.1:6343"
# Gợi ý câu hỏi (Ý 3) TẮT mặc định trong test — các test cũ đếm chính xác số lần
# gọi model để canh "không có lời gọi ẩn"; test_goi_y tự bật lại qua fixture riêng.
os.environ["GOI_Y_CAU_HOI"] = "false"
# Bản đẹp PDF (Ý 4) cũng TẮT mặc định — upload test không render PDF cho nhanh;
# test_remake_dep tự bật lại qua fixture riêng.
os.environ["REMAKE_DEP"] = "false"


@pytest.fixture(autouse=True)
def kho_tam(tmp_path, monkeypatch):
    """Mỗi test một kho tài liệu + lịch sử tạm riêng — không đụng data thật
    (bài học conftest hệ cũ + lệ 'không nghiệm thu ghi/xóa trên hệ thật').
    Mọi sổ vận hành (phan_hoi.csv, nhom_kho_thieu.json, nhap-phan-tich/,
    youtube_cookies.txt...) đều treo dưới KHO_TAI_LIEU nên cách ly 2 env là đủ."""
    monkeypatch.setenv("KHO_TAI_LIEU", str(tmp_path / "kho-tai-lieu"))
    monkeypatch.setenv("LICH_SU_DIR", str(tmp_path / "lich-su"))


# ── SIẾT BẢO MẬT 05/09/2026 ────────────────────────────────────────────────────
# lay_user đòi ĐỦ CẢ HAI: AA_TRUST_PROXY=1 VÀ client loopback
# (nen/common/xac_thuc_app.py). TestClient mặc định báo host='testclient' nên test
# cũ sẽ nhận 401 — 2 fixture dưới cho test chạy ĐÚNG như hệ thật.
# TUYỆT ĐỐI không nới bản vá để test xanh.

@pytest.fixture(autouse=True)
def _bat_trust_proxy_bm(monkeypatch):
    monkeypatch.setenv("AA_TRUST_PROXY", "1")


@pytest.fixture(autouse=True)
def _testclient_loopback_bm(monkeypatch):
    """Tôn trọng test tự khai địa chỉ (ca 'gọi từ LAN bị chặn' giữ tác dụng)."""
    from starlette.testclient import _TestClientTransport
    goc = _TestClientTransport.handle_request

    def handle(self, request):
        if getattr(self, "client", None) in (None, ("testclient", 50000)):
            self.client = ("127.0.0.1", 50000)
        return goc(self, request)

    monkeypatch.setattr(_TestClientTransport, "handle_request", handle)
