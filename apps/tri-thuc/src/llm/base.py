"""Interface chung cho mọi nhà cung cấp LLM.

Mọi adapter (Claude, ChatGPT, GLM, Grok, DeepSeek...) đều tuân theo interface này
→ vỏ chỉ gọi generate(), đổi nhà/model chỉ cần sửa .env, không sửa code.
"""

from abc import ABC, abstractmethod
from collections.abc import Iterator


class LLMProvider(ABC):
    @abstractmethod
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Gửi 1 lượt hỏi (system + user), trả về text."""

    def generate_stream(self, system_prompt: str, user_prompt: str) -> Iterator[str]:
        """Bản stream: yield từng mẩu text. Mặc định (provider chưa hỗ trợ stream):
        trả cả câu thành 1 mẩu — adapter nào stream được thì override."""
        yield self.generate(system_prompt, user_prompt)
