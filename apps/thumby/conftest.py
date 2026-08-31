# -*- coding: utf-8 -*-
"""conftest app thumby — chạy test TỪ THƯ MỤC APP (app tự đủ, Luật 2):
  cd apps/thumby && pytest
App không có dữ liệu server (ảnh chỉ nằm trong trình duyệt) nên không cần
fixture cách ly dữ liệu — nhưng test PHẢI GHIM điều đó (test_khong_endpoint_nhan_file).
"""
import sys
from pathlib import Path

_APP = Path(__file__).resolve().parent
_ROOT = _APP.parents[1]
sys.path.insert(0, str(_APP))    # import src.*
sys.path.insert(0, str(_ROOT))   # import nen.* (ctx_sidebar)
