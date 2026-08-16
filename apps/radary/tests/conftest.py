# -*- coding: utf-8 -*-
"""conftest radary V3 — chạy test TỪ THƯ MỤC APP (Luật 2 app tự đủ):
  cd apps/radary && pytest
Radary hệ cũ không có pytest suite — suite này bắt đầu từ adapter SSO V3."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # import radary.*
