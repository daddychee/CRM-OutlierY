# -*- coding: utf-8 -*-
"""Công tắc suy luận theo ĐỜI model GLM (đo thật 23/08/2026 trên key công ty).

glm-5.3 KHÔNG tắt được thinking: gửi kèm field `thinking` là 400 ngay (z.ai code
1210 "always engages in thinking ... use low, high, or max"). Chiều ngược lại
cũng đúng — glm-5.2 KHÔNG giảm reasoning theo `reasoning_effort` (vẫn 178-205
token) nên bản cũ vẫn phải dùng thinking:disabled. Hai đời, hai công tắc.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))  # scripts/ chạy độc lập, không phải package

import llm_provider as lp  # noqa: E402


def _extra(monkeypatch, model):
    """Chạy call() tới ngay trước lúc ra mạng, bắt lấy extra_body đã dựng."""
    bat = {}

    def gia(base_url, key_env, model_env, default_model, system, user, **kw):
        bat.update(kw.get("extra_body") or {})
        bat["_model"] = kw.get("model_override") or model
        return "x"

    monkeypatch.setattr(lp, "_openai_compatible_call", gia)
    monkeypatch.setenv("LLM_PROVIDER", "glm")
    monkeypatch.setenv("GLM_API_KEY", "k")
    monkeypatch.setenv("GLM_MODEL", model)
    lp.call("glm", "s", "u", work=None)
    return bat


def test_glm_5_3_ha_muc_thay_vi_tat_thinking(monkeypatch):
    assert lp._always_thinking("glm-5.3") and lp._always_thinking("GLM-5.3")
    assert not lp._always_thinking("glm-5.2") and not lp._always_thinking("")

    cu = _extra(monkeypatch, "glm-5.2")
    assert cu["thinking"] == {"type": "disabled"} and "reasoning_effort" not in cu

    moi = _extra(monkeypatch, "glm-5.3")
    # 5.3: KHÔNG được có field thinking (có là 400), chỉ hạ MỨC suy luận
    assert "thinking" not in moi and moi["reasoning_effort"] == "low"
