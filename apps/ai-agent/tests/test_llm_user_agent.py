# -*- coding: utf-8 -*-
"""USER-AGENT ở điểm-ra LLM (sự cố 12/09).

Cửa của mwapi (Cloudflare đứng trước) TỪ CHỐI theo User-Agent:
  - SDK openai gửi UA 'OpenAI/Python 3.1.0'  -> 403 {"message": "All available
    accounts exhausted"}  ← THÔNG ĐIỆP ĐÁNH LỪA: khóa vẫn tốt, tài khoản vẫn còn.
  - SDK anthropic gửi UA 'Anthropic/Python'  -> 502 Cloudflare.
  - urllib không đặt UA                      -> 403 'error code: 1010'.
Đo đối chứng cùng khóa + cùng model claude-opus-5 + cùng thời điểm: đặt một UA
thường thì CẢ HAI SDK trả 200 OK.

Cùng họ vết cũ "urllib bị Cloudflare chặn 1010" (08/09) — tái diễn ở tầng SDK.
Nhà nào KÉT khai mà đứng sau một cửa lọc UA đều dính, nên van đặt ở điểm-ra
chung của app chứ không vá lẻ theo nhà.

Test KHÔNG gọi mạng: chỉ ghim rằng client dựng ra có mang User-Agent riêng.
"""
import pytest

from src.llm.anthropic_provider import AnthropicProvider
from src.llm.openai_compatible import OpenAICompatibleProvider

_MWAPI = "https://api.mwapi.dev/v1"


class _ClientGia:
    """Client giả — chỉ giữ tham số khởi tạo, không đụng mạng."""

    def __init__(self, **kw):
        self.kw = kw


@pytest.fixture
def bat_kwargs(monkeypatch):
    """Bắt kwargs truyền vào constructor SDK (provider import TẠI CHỖ nên
    monkeypatch trên module gốc ăn)."""
    bat = {}

    def gia(**kw):
        bat.update(kw)
        return _ClientGia(**kw)

    monkeypatch.setattr("openai.OpenAI", gia)
    monkeypatch.setattr("anthropic.Anthropic", gia)
    return bat


def _ua(kw) -> str:
    return (kw.get("default_headers") or {}).get("User-Agent", "")


def test_client_openai_mang_user_agent_rieng(bat_kwargs):
    OpenAICompatibleProvider(model="claude-opus-5", api_key="k",
                             base_url=_MWAPI, mock=False)
    ua = _ua(bat_kwargs)
    assert ua, ("client openai dựng KHÔNG đặt User-Agent → SDK tự gửi "
                "'OpenAI/Python ...' → mwapi trả 403 'All available accounts "
                "exhausted' (khóa vẫn tốt) → hỏi–đáp/phản biện chết lặng lẽ")
    assert "OpenAI/Python" not in ua


def test_client_anthropic_mang_user_agent_rieng(bat_kwargs, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://api.mwapi.dev")
    AnthropicProvider(model="claude-opus-5", api_key="k", mock=False)
    ua = _ua(bat_kwargs)
    assert ua, ("client anthropic dựng KHÔNG đặt User-Agent → SDK tự gửi "
                "'Anthropic/Python ...' → mwapi/Cloudflare trả 502")
    assert "Anthropic/Python" not in ua
