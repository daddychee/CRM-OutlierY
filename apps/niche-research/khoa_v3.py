"""Nguồn khóa V3 — KÉT OUTLIERY qua gateway loopback (làm gọn Niche Research).

Khuôn radary/content khoa_v3: lấy khóa MỚI mỗi lần chạy (không cache), gateway
chết / việc chưa được cấp khóa → RuntimeError thông điệp Việt rõ, TUYỆT ĐỐI
không rơi về .env hay Settings nội bộ (hai nguồn khóa lệch nhau là nguồn lỗi
khó lần). Bật khi NICHE_TRUST_PROXY=1; tắt → V2 đọc .env như cũ.

Ánh xạ VIỆC (khai trong apps.json `viec_api`) → chỗ pipeline đang đọc:
  quet_kenh     (youtube)    → BƠM vào competitors.txt của run (scripts/_common
                               load_input regex AIza… từ CHÍNH file input — V2
                               vốn bắt user dán key vào file; V3 két bơm thay)
  phan_tich     (llm)        → env LLM_PROVIDER + <NHÀ>_API_KEY/_MODEL đúng
                               danh pháp scripts/llm_provider.py
  lay_transcript(transcript) → env TRANSCRIPT_API_KEY (15_fetch_transcripts)
"""
from __future__ import annotations

import json
import os
import urllib.request

# nhà LLM (két) → (giá trị LLM_PROVIDER của llm_provider.py, biến key, biến model)
_NHA_LLM = {
    "claude": ("anthropic", "ANTHROPIC_API_KEY", "ANTHROPIC_MODEL"),
    "glm": ("glm", "GLM_API_KEY", "GLM_MODEL"),
    "chatgpt": ("openai", "OPENAI_API_KEY", "OPENAI_MODEL"),
    # gemini/deepseek đi nhánh provider=custom (OpenAI-compatible) của llm_provider
    "gemini": ("custom", "CUSTOM_API_KEY", "CUSTOM_MODEL"),
    "deepseek": ("custom", "CUSTOM_API_KEY", "CUSTOM_MODEL"),
}
_BASE_CUSTOM = {
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai",
    "deepseek": "https://api.deepseek.com",
}


def bat() -> bool:
    """V3 mode: chạy sau cổng OUTLIERY → khóa lấy từ két, không đọc .env."""
    return os.environ.get("NICHE_TRUST_PROXY") == "1"


def _goi_ket() -> dict:
    goc = os.environ.get("GATEWAY_URL", "http://127.0.0.1:9000")
    try:
        with urllib.request.urlopen(
                f"{goc}/api/cau-hinh/api-khoa/niche-research", timeout=5) as r:
            return json.load(r) or {}
    except Exception as e:
        raise RuntimeError(
            f"chưa lấy được khóa từ OUTLIERY ({e.__class__.__name__}) — kiểm "
            "gateway 9000 đang chạy + khóa đã cấp phát ở General › API Keys") from None


def khoa_theo_viec(viec: str, cap_phat: dict | None = None) -> list[str]:
    """TẤT CẢ khóa của một việc (quet_kenh xoay vòng nhiều khóa YouTube)."""
    muc = (cap_phat if cap_phat is not None else _goi_ket()).get(viec) or {}
    keys = [k.get("key") for k in muc.get("khoa", []) if k.get("key")]
    if not keys:
        raise RuntimeError(
            f"OUTLIERY chưa cấp khóa cho việc '{viec}' của niche-research — "
            "cấp ở General › API Keys (tab Per-app config)")
    return keys


def env_llm(cap_phat: dict | None = None) -> dict[str, str]:
    """Env overlay cho các stage LLM (việc phan_tich) đúng danh pháp
    llm_provider.py. Việc chưa cấp khóa → RuntimeError rõ (caller quyết
    bắt buộc hay tùy chọn theo cờ run)."""
    muc = (cap_phat if cap_phat is not None else _goi_ket()).get("phan_tich") or {}
    khoa = muc.get("khoa") or []
    if not khoa:
        raise RuntimeError(
            "OUTLIERY chưa cấp khóa LLM cho việc 'phan_tich' của niche-research"
            " — cấp ở General › API Keys (tab Per-app config)")
    dau = khoa[0]
    nha = dau.get("nha", "")
    provider, bien_key, bien_model = _NHA_LLM.get(nha, ("glm", "GLM_API_KEY",
                                                        "GLM_MODEL"))
    ra = {"LLM_PROVIDER": provider, bien_key: dau["key"]}
    if muc.get("model"):
        ra[bien_model] = muc["model"]
    if provider == "custom":
        ra["CUSTOM_BASE_URL"] = _BASE_CUSTOM.get(nha, "")
    return ra


def env_transcript(cap_phat: dict | None = None) -> dict[str, str]:
    """Env overlay cho deepdive S15 (việc lay_transcript, transcriptapi.com)."""
    keys = khoa_theo_viec("lay_transcript", cap_phat)
    return {"TRANSCRIPT_API_KEY": keys[0]}
