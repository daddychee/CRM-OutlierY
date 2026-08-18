# -*- coding: utf-8 -*-
"""Cách ly test niche-research: dữ liệu (projects/data) về thư mục TẠM trước khi
import server (server.py đọc NICHE_DATA_DIR + mkdir ngay lúc import) — suite
không bao giờ ghi vào apps/ hay data/ thật. Chạy: cd apps/niche-research && pytest."""
import os
import tempfile

os.environ.setdefault("NICHE_DATA_DIR", tempfile.mkdtemp(prefix="niche-test-"))
