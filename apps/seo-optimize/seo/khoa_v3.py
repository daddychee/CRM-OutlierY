"""Nguồn khóa V3 — KÉT OUTLIERY qua gateway loopback (đưa SEO Optimize vào V3, APPS.md app 4).

Khi SEO_TRUST_PROXY=1 (chạy sau gateway V3), MỌI khóa lấy từ trang API Keys theo
VIỆC đã khai trong hợp đồng app (nen/rules/apps.json → viec_api):
  - trich_kenh    (youtube) — pool key xoay vòng, extract profile/format
  - sinh_metadata (llm)     — sinh title/description/tags/CTA

Mỗi lần dùng lấy danh sách MỚI (không cache qua đêm) — Owner đổi khóa/cấp phát là
lượt sau ăn ngay. Gateway chết / việc chưa cấp khóa → DỪNG với thông điệp rõ,
TUYỆT ĐỐI không rơi về .env / api.txt (chống hai nguồn khóa lệch nhau — khuôn
radary/niche). Tab quản trị key trong app đã đóng khi SSO (server._CUA_QUAN_TRI).
"""
import json
import os
import urllib.request

APP = "seo-optimize"

# nhà trong két → danh pháp provider của seo/llm.py (anthropic | glm | openai).
# Nhà khác (gemini/deepseek/custom) app này chưa nói chuyện được — báo rõ thay vì
# đoán base URL. ponytail: đủ cho 3 nhà đang dùng thật; cần nhà mới thì thêm dòng.
_NHA_LLM = {"claude": "anthropic", "anthropic": "anthropic",
            "glm": "glm", "chatgpt": "openai", "openai": "openai"}


def bat() -> bool:
    return os.environ.get("SEO_TRUST_PROXY") == "1"


def _cap_phat() -> dict:
    goc = os.environ.get("GATEWAY_URL", "http://127.0.0.1:9000")
    url = f"{goc}/api/cau-hinh/api-khoa/{APP}"
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            return json.load(r) or {}
    except Exception as e:
        raise RuntimeError(
            f"chưa lấy được khóa từ OUTLIERY ({e.__class__.__name__}) — kiểm "
            "gateway 9000 đang chạy + khóa đã cấp phát ở General › API Keys") from None


def khoa_youtube() -> list[str]:
    """Pool key YouTube cho việc trich_kenh — thứ tự như cấp phát, app tự xoay
    (common.yt_get giữ nguyên cơ chế con trỏ)."""
    muc = _cap_phat().get("trich_kenh") or {}
    keys = [k.get("key") for k in muc.get("khoa", []) if k.get("key")]
    if not keys:
        raise RuntimeError(
            f"OUTLIERY chưa cấp khóa YouTube cho việc 'trich_kenh' của {APP} — "
            "cấp ở General › API Keys (tab Per-app config)")
    return keys


def llm_viec() -> tuple[str, str, str]:
    """(provider, key, model) cho việc sinh_metadata — danh pháp seo/llm.py."""
    muc = _cap_phat().get("sinh_metadata") or {}
    khoa = [k for k in muc.get("khoa", []) if k.get("key")]
    if not khoa:
        raise RuntimeError(
            f"OUTLIERY chưa cấp khóa LLM cho việc 'sinh_metadata' của {APP} — "
            "cấp ở General › API Keys (tab Per-app config)")
    k = khoa[0]
    nha = (k.get("nha") or "").strip().lower()
    provider = _NHA_LLM.get(nha)
    if not provider:
        raise RuntimeError(
            f"nhà LLM '{nha}' chưa hỗ trợ trong SEO Optimize — cấp khóa "
            "glm / claude / chatgpt cho việc 'sinh_metadata'")
    return provider, k["key"], (muc.get("model") or "").strip()
