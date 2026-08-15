# -*- coding: utf-8 -*-
"""conftest app data-analytics — chạy test TỪ THƯ MỤC APP (app tự đủ, Luật 2):
  cd apps/data-analytics && pytest
Mỗi app một process pytest riêng → package `src` không đụng app khác.
"""
import os
import sys
from pathlib import Path

import pytest

_APP = Path(__file__).resolve().parent
_ROOT = _APP.parents[1]
sys.path.insert(0, str(_APP))    # import src.*
sys.path.insert(0, str(_ROOT))   # import nen.* (danh bạ)

os.environ["MOCK_MODE"] = "true"          # không gọi model thật trong test
os.environ["WRITER_MOCK_MODE"] = "true"
os.environ["CRITIC_MOCK_MODE"] = "true"
os.environ["GATEWAY_URL"] = "http://127.0.0.1:1"   # két: đứt ngay → env/mock (test không phụ thuộc gateway)


@pytest.fixture(autouse=True)
def _cach_ly_du_lieu(tmp_path, monkeypatch):
    """Mọi test trỏ dữ liệu vào tmp — không ghi rác data thật (bài học conftest hệ cũ)."""
    monkeypatch.setenv("BAO_CAO_DIR", str(tmp_path / "bao-cao-lich-su"))
    monkeypatch.setenv("BAO_CAO_GOC_DIR", str(tmp_path / "bao-cao-goc"))
    # danh bạ trỏ file không tồn tại → gợi ý kênh chỉ còn nguồn lịch sử (test cũ giữ nghĩa);
    # test danh bạ+gộp có file CSV tmp riêng
    monkeypatch.setenv("DANH_MUC_CSV", str(tmp_path / "danh-muc-khong-co.csv"))
