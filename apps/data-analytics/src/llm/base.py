"""Interface chung cho mọi nhà cung cấp LLM.

Mọi adapter (Claude, ChatGPT, GLM, Grok, DeepSeek...) đều tuân theo interface này
→ vỏ chỉ gọi generate(), đổi nhà/model chỉ cần sửa .env, không sửa code.
"""

from abc import ABC, abstractmethod
from collections.abc import Iterator


def kiem_host_diem_ra(base_url) -> None:
    """VAN PHÒNG THỦ (05/09, spec docs/phong-thu-api-ngoai.md): BASE_URL phải là
    https + host trong allowlist — .env bị sửa/gõ nhầm trỏ prompt + key sang
    server lạ là chặn NGAY lúc dựng client. Thiếu nen (bản đóng gói chạy độc
    lập) → van tự tắt, hành vi cũ không đổi."""
    try:
        from nen.common import phong_thu
    except ImportError:
        return
    phong_thu.kiem_host(base_url)


class LLMProvider(ABC):
    APP_SO_GOI = "data-analytics"   # bản sao — hằng app riêng

    def _ghi_so(self, ms: float, ok: bool, ma_loi: str = "", resp=None) -> None:
        """SỔ GỌI nền (01/09): 1 dòng mỗi call LLM THẬT (mock không ghi) —
        Command Center đếm calls/lỗi per app·vai. Sổ chết không hỏng call.

        TOKEN (03/09, Owner: "tính chi phí sử dụng cho từng app"): truyền `resp`
        thì lấy usage TỪ CHÍNH BODY nhà cung cấp trả về — không ước lượng, không
        đếm chữ. Nhà nào không trả usage → giữ None = "chưa đo", khác hẳn 0.
        Đặt ở base nên MỌI provider (và cả bản sao ở data-analytics) hưởng chung.
        """
        tv = tr = None
        u = getattr(resp, "usage", None) if resp is not None else None
        if u is not None:
            # OpenAI/GLM: prompt_tokens/completion_tokens · Anthropic: input/output_tokens
            tv = getattr(u, "prompt_tokens", None)
            tr = getattr(u, "completion_tokens", None)
            if tv is None and tr is None:
                tv = getattr(u, "input_tokens", None)
                tr = getattr(u, "output_tokens", None)
        try:
            from nen.common import so_goi
            so_goi.ghi(self.APP_SO_GOI, "llm", viec=getattr(self, "vai", ""),
                       model=getattr(self, "model", ""), ms=ms, ok=ok,
                       ma_loi=ma_loi[:120], token_vao=tv, token_ra=tr)
        except Exception:  # noqa: BLE001
            pass

    def _kiem_truoc_goi(self, system_prompt: str, user_prompt: str) -> None:
        """VAN PHÒNG THỦ trước MỌI call thật (05/09): secret lọt prompt / vượt
        trần LLM ngày → LoiPhongThu NỔI LÊN chặn call (không lặng lẽ); mock
        không qua đây. Thiếu nen (bản chạy độc lập) → van tự tắt."""
        try:
            from nen.common import phong_thu
        except ImportError:
            return
        phong_thu.kiem_truoc_goi(system_prompt, user_prompt)

    @abstractmethod
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Gửi 1 lượt hỏi (system + user), trả về text."""

    def generate_stream(self, system_prompt: str, user_prompt: str) -> Iterator[str]:
        """Bản stream: yield từng mẩu text. Mặc định (provider chưa hỗ trợ stream):
        trả cả câu thành 1 mẩu — adapter nào stream được thì override."""
        yield self.generate(system_prompt, user_prompt)
