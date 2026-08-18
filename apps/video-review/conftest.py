# -*- coding: utf-8 -*-
"""conftest app video-review — chạy test TỪ THƯ MỤC APP (app tự đủ, Luật 2):
  cd apps/video-review && pytest
Mỗi app một process pytest riêng → package `src` không đụng app khác.
"""
import sys
from pathlib import Path

import pytest

_APP = Path(__file__).resolve().parent
_ROOT = _APP.parents[1]
sys.path.insert(0, str(_APP))    # import src.*
sys.path.insert(0, str(_ROOT))   # import nen.* (ctx_sidebar)


@pytest.fixture(autouse=True)
def _cach_ly_du_lieu(tmp_path, monkeypatch):
    """Mọi test trỏ DB + kho video vào tmp — tuyệt đối không ghi data thật
    (bài học conftest hệ cũ: suite từng ghi bẩn dữ liệu sống)."""
    monkeypatch.setenv("VR_DB_PATH", str(tmp_path / "video_review.db"))
    monkeypatch.setenv("VR_KHO_DIR", str(tmp_path / "kho"))
    from src import kho_video
    kho_video.khoi_tao()
    yield
