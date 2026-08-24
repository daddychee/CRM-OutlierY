# -*- coding: utf-8 -*-
"""conftest app tasky — chạy test TỪ THƯ MỤC APP (app tự đủ, Luật 2):
  cd apps/tasky && pytest
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
    """Mọi test ghi vào tmp — tuyệt đối không đụng data thật (bài học conftest hệ
    cũ: suite từng ghi bẩn dữ liệu sống, và test duyệt nhân sự từng ghi vào
    PlannerY thật)."""
    monkeypatch.setenv("TASKY_DIR", str(tmp_path / "db"))
    yield
