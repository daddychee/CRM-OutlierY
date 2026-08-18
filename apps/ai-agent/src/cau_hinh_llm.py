# -*- coding: utf-8 -*-
"""Nạp cấu hình LLM (writer/critic) từ KÉT qua gateway loopback — bắt chước
dien_giai.nap_cau_hinh_llm của data-analytics (Luật 4: không import chéo app).

Đổ vào env đúng khuôn {VAI}_* mà src/llm/factory hệ cũ đã đọc — factory + provider
GIỮ NGUYÊN KHÔNG SỬA. Gateway chết / vai chưa khai (provider rỗng) → env giữ nguyên
(mock mặc định), app vẫn sống. Trả True nếu nạp được ÍT NHẤT một vai — main dùng cờ
này để dựng lại qa.writer/qa.critics (QAPipeline đã khởi tạo từ env lúc import)."""
from __future__ import annotations

import logging
import os

import httpx

GATEWAY_URL = os.environ.get("GATEWAY_URL", "http://127.0.0.1:9000")


def nap_cau_hinh_llm() -> bool:
    da_nap = False
    try:
        with httpx.Client(timeout=3) as c:
            for vai in ("writer", "critic"):
                # app=ai-agent TƯỜNG MINH (dù trùng mặc định gateway) — chống
                # lệch ngầm khi có app thứ 3 dùng chung tên vai (bug 18/08).
                ch = c.get(f"{GATEWAY_URL}/api/cau-hinh/llm/{vai}",
                           params={"app": "ai-agent"}).json()
                if not ch.get("provider"):
                    continue
                v = vai.upper()
                os.environ[f"{v}_PROVIDER"] = ch["provider"]
                os.environ[f"{v}_MODEL"] = ch["model"]
                os.environ[f"{v}_BASE_URL"] = ch["base_url"]
                os.environ[f"{v}_API_KEY"] = ch["api_key"]
                os.environ[f"{v}_MOCK_MODE"] = "false"
                os.environ.setdefault("LLM_TIMEOUT", str(ch["timeout"]))
                os.environ.setdefault("LLM_RETRY", str(ch["retry"]))
                da_nap = True
    except httpx.HTTPError as e:
        logging.warning("Không nạp được cấu hình LLM từ gateway (%s) — dùng env/mock.", e)
    return da_nap
