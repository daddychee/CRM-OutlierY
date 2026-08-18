# -*- coding: utf-8 -*-
"""Cách ly TRƯỚC khi import package (khuôn apps/radary/tests/conftest.py):
- SEO_DATA_DIR trỏ tmp — seo/common.py chốt ROOT lúc import, đặt sau là muộn.
- SEO_TRUST_PROXY=1 — suite kiểm hành vi V3 (SSO bật) là chính.
- GATEWAY_URL cổng CHẾT — quên mock khóa két là lỗi nổi rõ, không âm thầm gọi
  gateway thật (bài học radary)."""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("SEO_DATA_DIR", tempfile.mkdtemp(prefix="seo-v3-test-"))
os.environ.setdefault("SEO_TRUST_PROXY", "1")
os.environ.setdefault("GATEWAY_URL", "http://127.0.0.1:1")
