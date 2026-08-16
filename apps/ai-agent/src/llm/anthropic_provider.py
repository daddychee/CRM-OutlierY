"""Adapter riêng cho Claude — dùng thư viện `anthropic` chính thức.

Khi tắt mock: điền vào .env
  WRITER_PROVIDER=anthropic
  WRITER_MODEL=claude-opus-4-8   (hoặc claude-sonnet-5, claude-haiku-4-5)
  ANTHROPIC_API_KEY=sk-ant-...
"""

from src.llm.base import LLMProvider


class AnthropicProvider(LLMProvider):
    def __init__(self, model: str = "claude-opus-4-8", api_key: str = "", mock: bool = True):
        self.model = model
        self.mock = mock
        if not mock:
            import anthropic  # import tại chỗ — chế độ mock không đụng tới thư viện

            from src.llm.openai_compatible import lay_llm_retry, lay_llm_timeout

            # api_key rỗng → thư viện tự đọc ANTHROPIC_API_KEY từ môi trường
            # max_retries: SDK mặc định tự thử lại 2 lần lặng lẽ — cùng bẫy với timeout (06/08)
            self.client = anthropic.Anthropic(api_key=api_key or None,
                                              timeout=lay_llm_timeout(),
                                              max_retries=lay_llm_retry())

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        if self.mock:
            return (f"[MOCK {self.model}] Trả lời mô phỏng — "
                    f"đặt *_MOCK_MODE=false trong .env để gọi model thật.")
        resp = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return "".join(b.text for b in resp.content if b.type == "text")

    def generate_stream(self, system_prompt: str, user_prompt: str):
        """Stream từng mẩu text qua SDK anthropic. generate() cũ giữ nguyên."""
        if self.mock:
            for tu in self.generate(system_prompt, user_prompt).split():
                yield tu + " "  # mock cũng chảy thành nhiều mẩu để test được luồng
            return
        with self.client.messages.stream(
            model=self.model,
            max_tokens=4096,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        ) as stream:
            for text in stream.text_stream:
                if text:
                    yield text
