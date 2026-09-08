"""Adapter DÙNG CHUNG cho mọi nhà theo chuẩn OpenAI: ChatGPT, GLM, Grok, DeepSeek...

Chỉ khác nhau base_url + api_key + model — tất cả đọc từ .env qua factory.
Khi tắt mock, điền base_url theo nhà (ví dụ cho vai CRITIC):
  - ChatGPT:  CRITIC_BASE_URL=            (bỏ trống = api.openai.com)
  - GLM:      CRITIC_BASE_URL=https://open.bigmodel.cn/api/paas/v4
  - DeepSeek: CRITIC_BASE_URL=https://api.deepseek.com
  - Grok:     CRITIC_BASE_URL=https://api.x.ai/v1
"""

import os

from src.llm.base import LLMProvider, kiem_host_diem_ra


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
                 base_url: str | None = None, mock: bool = True,
                 thinking: str = ""):
        self.model = model
        self.mock = mock
        # Luat 3 (Owner 08/09): muc suy nghi do NGUOI DUNG chon, khong de nha
        # cung cap tu quyet ngam (z.ai bat thinking mac dinh — do that 02/09).
        from src.llm import factory as _f
        self.thinking = (thinking or _f.THINKING_MAC_DINH).lower()
        if not mock:
            if not api_key or not model:
                raise ValueError("Provider openai_compatible thiếu API_KEY hoặc MODEL trong .env")
            kiem_host_diem_ra(base_url)   # van phòng thủ: host lạ chết từ cửa (05/09)
            from openai import OpenAI  # import tại chỗ — chế độ mock không đụng tới thư viện

            self.client = OpenAI(api_key=api_key, base_url=base_url or None,
                                 timeout=lay_llm_timeout(), max_retries=lay_llm_retry())

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        if self.mock:
            return (f"[MOCK {self.model or 'openai-compatible'}] Trả lời mô phỏng — "
                    f"đặt *_MOCK_MODE=false trong .env để gọi model thật.")
        self._kiem_truoc_goi(system_prompt, user_prompt)
        import time as _t
        _t0 = _t.perf_counter()
        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                **self._them_thinking(),
            )
        except Exception as e:
            self._ghi_so((_t.perf_counter() - _t0) * 1000, False, str(e))
            raise
        self._ghi_so((_t.perf_counter() - _t0) * 1000, True, resp=resp)
        return resp.choices[0].message.content or ""

    def _them_thinking(self) -> dict:
        """Tham so suy nghi gui kem lenh goi (Luat 3).

        SDK openai khong biet truong rieng cua z.ai nen di qua `extra_body`.
        "tat"  -> thinking disabled (glm-5/5.2 nhan)
        "thap" -> reasoning_effort low (glm-5.3 CAM tat han, chi nhan muc nay)
        "nha"  -> khong dong gi, de nha cung cap tu quyet.
        """
        if self.thinking == "tat":
            return {"extra_body": {"thinking": {"type": "disabled"}}}
        if self.thinking == "thap":
            return {"extra_body": {"reasoning_effort": "low"}}
        return {}

    def generate_stream(self, system_prompt: str, user_prompt: str):
        """Stream từng mẩu text (chuẩn OpenAI stream=True). generate() cũ giữ nguyên."""
        if self.mock:
            for tu in self.generate(system_prompt, user_prompt).split():
                yield tu + " "  # mock cũng chảy thành nhiều mẩu để test được luồng
            return
        self._kiem_truoc_goi(system_prompt, user_prompt)
        # GHI SỔ cả đường stream (05/09): trước đây stream — đường tiêu CHÍNH của
        # hỏi–đáp — không ghi dòng nào → trần/ngày + Command Center mù. Token
        # stream chưa đo (cần stream_options include_usage, GLM chưa chắc hỗ trợ)
        # → giữ None = "chưa đo", trần CALL vẫn đếm đủ.
        import time as _t
        _t0 = _t.perf_counter()
        try:
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
        except Exception as e:
            self._ghi_so((_t.perf_counter() - _t0) * 1000, False, str(e))
            raise
        self._ghi_so((_t.perf_counter() - _t0) * 1000, True)
