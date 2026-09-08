"""Factory: đọc .env để biết VAI nào dùng NHÀ nào + MODEL nào.

Mỗi vai (writer, critic, critic2...) có bộ biến riêng:
  {VAI}_PROVIDER   = anthropic | openai_compatible
  {VAI}_MODEL      = tên model
  {VAI}_API_KEY    = key (vai anthropic có thể bỏ trống → dùng ANTHROPIC_API_KEY)
  {VAI}_BASE_URL   = chỉ cần cho openai_compatible
  {VAI}_MOCK_MODE  = true/false (mặc định true)

Danh sách vai phản biện đọc từ CRITICS (vd "critic,critic2,critic3")
→ sau này nâng lên "hội đồng thẩm phán" chỉ cần thêm dòng vào .env.
"""

import os

# THINKING (Luat 3 Owner chot 08/09) — cung thang muc voi Content Ultimate:
#   "tat"  — khong suy nghi (nhanh/re)   "thap" — suy nghi it
#   "nha"  — de nha cung cap tu quyet
# Mac dinh TAT: do 02/09 tren z.ai, 88%% output token la suy nghi ngam.
THINKING_MAC_DINH = "tat"
THINKING_MUC = ("tat", "thap", "nha")

# Vai noi bo (khuon factory he cu) -> MA VIEC trong hop dong apps.json.
MA_VIEC_THEO_VAI = {"writer": "dien_giai", "critic": "phan_bien",
                    "critic2": "phan_bien", "critic3": "phan_bien"}

from src.llm.anthropic_provider import AnthropicProvider
from src.llm.base import LLMProvider
from src.llm.openai_compatible import OpenAICompatibleProvider


def _env(role: str, key: str, default: str = "") -> str:
    return os.getenv(f"{role.upper()}_{key}", default)


def get_provider(role: str) -> LLMProvider:
    nha = _env(role, "PROVIDER", "anthropic").strip().lower()
    mock = _env(role, "MOCK_MODE", "true").strip().lower() == "true"
    model = _env(role, "MODEL").strip()

    if nha == "anthropic":
        p = AnthropicProvider(
            model=model or "claude-opus-4-8",
            api_key=_env(role, "API_KEY") or os.getenv("ANTHROPIC_API_KEY", ""),
            mock=mock,
        )
    elif nha == "openai_compatible":
        p = OpenAICompatibleProvider(
            model=model,
            api_key=_env(role, "API_KEY"),
            base_url=_env(role, "BASE_URL").strip() or None,
            mock=mock,
            thinking=_env(role, "THINKING", THINKING_MAC_DINH),
        )
    else:
        raise ValueError(f"Vai '{role}': provider '{nha}' chưa hỗ trợ "
                         f"(chọn: anthropic | openai_compatible)")
    p.vai = role   # sổ gọi ghi calls per app·vai (01/09)
    # MA VIEC hop dong (Luat 1, 08/09): so chi phi phai quy ve dung viec da khai
    # trong apps.json — truoc day chi ghi vai NOI BO (writer/critic).
    p.ma_viec = MA_VIEC_THEO_VAI.get(role, "")
    return p


def get_critics() -> list[LLMProvider]:
    roles = [r.strip() for r in os.getenv("CRITICS", "critic").split(",") if r.strip()]
    return [get_provider(r) for r in roles]
