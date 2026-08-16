"""Nguồn khóa V3 — KÉT OUTLIERY qua gateway loopback (làm gọn Content Ultimate).

Khuôn radary/khoa_v3.py: lấy khóa MỚI mỗi lần chạy (không cache), gateway chết /
việc chưa được cấp khóa → RuntimeError thông điệp Việt rõ, TUYỆT ĐỐI không rơi
về .env hay admin config (hai nguồn khóa lệch nhau là nguồn lỗi khó lần).

Bật khi CU_TRUST_PROXY=1 (chạy sau cổng OUTLIERY). Tắt → mọi thứ đọc .env như V2.

Ánh xạ VIỆC (khai trong apps.json `viec_api`) → biến env app đang dùng:
  viet_kich_ban  (llm)        → GLM_API_KEY / ANTHROPIC_API_KEY … theo nhà khóa
  phan_tich_outline (llm)     → cùng khuôn (pipeline Outline: beats/label/cluster)
  lay_transcript (transcript) → TRANSCRIPT_API_KEY (transcriptapi.com)
  lay_comment    (youtube)    → YOUTUBE_API_KEY (S1c comment)
"""
from __future__ import annotations

import json
import os
import urllib.request

# nhà LLM (két) → tên biến env mà code app đọc
_ENV_LLM = {"glm": "GLM_API_KEY", "claude": "ANTHROPIC_API_KEY",
            "chatgpt": "OPENAI_API_KEY", "gemini": "GEMINI_API_KEY",
            "deepseek": "DEEPSEEK_API_KEY"}
_ENV_LOAI = {"transcript": "TRANSCRIPT_API_KEY", "youtube": "YOUTUBE_API_KEY"}


def bat() -> bool:
    """V3 mode: chạy sau cổng OUTLIERY → khóa lấy từ két, không đọc .env."""
    return os.environ.get("CU_TRUST_PROXY") == "1"


def _goi_ket() -> dict:
    goc = os.environ.get("GATEWAY_URL", "http://127.0.0.1:9000")
    try:
        with urllib.request.urlopen(
                f"{goc}/api/cau-hinh/api-khoa/content-ultimate", timeout=5) as r:
            return json.load(r) or {}
    except Exception as e:
        raise RuntimeError(
            f"chưa lấy được khóa từ OUTLIERY ({e.__class__.__name__}) — kiểm "
            "gateway 9000 đang chạy + khóa đã cấp phát ở General › API Keys") from None


def env_ket() -> dict[str, str]:
    """Kho khóa dạng dict env-like (thay nội dung .env khi chạy V3).

    Mỗi việc lấy khóa ĐẦU tiên được cấp; việc loại llm còn mang theo model/
    provider/base_url để LLM lớp oe dùng đúng nhà. Không có khóa nào → {} (caller
    tự ném lỗi đúng ngữ cảnh của nó)."""
    ra: dict[str, str] = {}
    for viec, muc in _goi_ket().items():
        khoa = muc.get("khoa") or []
        if not khoa:
            continue
        dau = khoa[0]
        loai, nha = dau.get("loai", ""), dau.get("nha", "")
        if loai == "llm":
            ten = _ENV_LLM.get(nha, "GLM_API_KEY")
            ra.setdefault(ten, dau["key"])
            ra.setdefault("LLM_PROVIDER", nha or "glm")
            if muc.get("model"):
                ra.setdefault("GLM_MODEL" if nha == "glm" else "LLM_MODEL", muc["model"])
        elif loai in _ENV_LOAI:
            ra.setdefault(_ENV_LOAI[loai], dau["key"])
    return ra


def khoa_theo_viec(viec: str) -> list[str]:
    """TẤT CẢ khóa của một việc (S1c comment xoay vòng nhiều khóa YouTube)."""
    muc = _goi_ket().get(viec) or {}
    keys = [k.get("key") for k in muc.get("khoa", []) if k.get("key")]
    if not keys:
        raise RuntimeError(
            f"OUTLIERY chưa cấp khóa cho việc '{viec}' của content-ultimate — "
            "cấp ở General › API Keys (tab Per-app config)")
    return keys
