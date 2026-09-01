"""Interface chung cho mọi nhà cung cấp LLM.

Mọi adapter (Claude, ChatGPT, GLM, Grok, DeepSeek...) đều tuân theo interface này
→ vỏ chỉ gọi generate(), đổi nhà/model chỉ cần sửa .env, không sửa code.
"""

from abc import ABC, abstractmethod
from collections.abc import Iterator


class LLMProvider(ABC):
    APP_SO_GOI = "data-analytics"   # bản sao — hằng app riêng

    def _ghi_so(self, ms: float, ok: bool, ma_loi: str = "") -> None:
        """SỔ GỌI nền (01/09): 1 dòng mỗi call LLM THẬT (mock không ghi) —
        Command Center đếm calls/lỗi per app·vai. Sổ chết không hỏng call."""
        try:
            from nen.common import so_goi
            so_goi.ghi(self.APP_SO_GOI, "llm", viec=getattr(self, "vai", ""),
                       model=getattr(self, "model", ""), ms=ms, ok=ok,
                       ma_loi=ma_loi[:120])
        except Exception:  # noqa: BLE001
            pass

    @abstractmethod
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Gửi 1 lượt hỏi (system + user), trả về text."""

    def generate_stream(self, system_prompt: str, user_prompt: str) -> Iterator[str]:
        """Bản stream: yield từng mẩu text. Mặc định (provider chưa hỗ trợ stream):
        trả cả câu thành 1 mẩu — adapter nào stream được thì override."""
        yield self.generate(system_prompt, user_prompt)
