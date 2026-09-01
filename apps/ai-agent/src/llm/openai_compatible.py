"""Adapter DÙNG CHUNG cho mọi nhà theo chuẩn OpenAI: ChatGPT, GLM, Grok, DeepSeek...

Chỉ khác nhau base_url + api_key + model — tất cả đọc từ .env qua factory.
Khi tắt mock, điền base_url theo nhà (ví dụ cho vai CRITIC):
  - ChatGPT:  CRITIC_BASE_URL=            (bỏ trống = api.openai.com)
  - GLM:      CRITIC_BASE_URL=https://open.bigmodel.cn/api/paas/v4
  - DeepSeek: CRITIC_BASE_URL=https://api.deepseek.com
  - Grok:     CRITIC_BASE_URL=https://api.x.ai/v1
"""

import os

from src.llm.base import LLMProvider


def lay_llm_timeout() -> float:
    """LLM_TIMEOUT (.env, giây — mặc định 60): SDK mặc định chờ tới 600s + tự retry
    → API nghẽn là treo gần vô hạn (bug treo /upload 19/07). Quá giờ SDK ném lỗi,
    nơi gọi tự xử (bản đẹp đã bọc try/except nên chỉ mất bản đẹp, không chặn gì)."""
    return float(os.getenv("LLM_TIMEOUT", "60"))


def lay_llm_retry() -> int:
    """LLM_RETRY (.env — mặc định 0): SDK (cả openai LẪN anthropic) mặc định TỰ THỬ LẠI
    2 lần LẶNG LẼ khi timeout/nghẽn → người dùng nhìn màn hình quay mà không biết gì.
    Bẫy em ruột của LLM_TIMEOUT, dính thật 06/08: flow phân tích nguồn 3 lời gọi ×
    (1+2 retry) × 240s ≈ hơn 30 phút. Mặc định 0 = lỗi NỔI LÊN NGAY với thông điệp rõ,
    người dùng chủ động bấm lại — muốn SDK tự thử thêm thì đặt LLM_RETRY=1."""
    return int(os.getenv("LLM_RETRY", "0"))


class OpenAICompatibleProvider(LLMProvider):
    def __init__(self, model: str = "", api_key: str = "",
                 base_url: str | None = None, mock: bool = True):
        self.model = model
        self.mock = mock
        if not mock:
            if not api_key or not model:
                raise ValueError("Provider openai_compatible thiếu API_KEY hoặc MODEL trong .env")
            from openai import OpenAI  # import tại chỗ — chế độ mock không đụng tới thư viện

            self.client = OpenAI(api_key=api_key, base_url=base_url or None,
                                 timeout=lay_llm_timeout(), max_retries=lay_llm_retry())

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        if self.mock:
            return (f"[MOCK {self.model or 'openai-compatible'}] Trả lời mô phỏng — "
                    f"đặt *_MOCK_MODE=false trong .env để gọi model thật.")
        import time as _t
        _t0 = _t.perf_counter()
        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
        except Exception as e:
            self._ghi_so((_t.perf_counter() - _t0) * 1000, False, str(e))
            raise
        self._ghi_so((_t.perf_counter() - _t0) * 1000, True)
        return resp.choices[0].message.content or ""

    def generate_stream(self, system_prompt: str, user_prompt: str):
        """Stream từng mẩu text (chuẩn OpenAI stream=True). generate() cũ giữ nguyên."""
        if self.mock:
            for tu in self.generate(system_prompt, user_prompt).split():
                yield tu + " "  # mock cũng chảy thành nhiều mẩu để test được luồng
            return
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            stream=True,
        )
        for chunk in resp:
            mau = chunk.choices[0].delta.content if chunk.choices else None
            if mau:  # bỏ mẩu rỗng/None (một số nhà gửi chunk không có nội dung)
                yield mau
