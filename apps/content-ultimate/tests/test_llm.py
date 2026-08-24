import pytest

from voiceprofile.llm import (
    PROVIDERS,
    available_providers,
    load_env_file,
    parse_json_text,
    provider_config,
)


def test_load_env_file_ignores_comments_and_blank_lines(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "# comment\n"
        "\n"
        "ANTHROPIC_API_KEY=sk-ant-abc\n"
        "# GLM_API_KEY=glm-secret\n"
        "GLM_MODEL = 'glm-5.2'\n",
        encoding="utf-8",
    )
    env = load_env_file(env_file)
    assert env == {"ANTHROPIC_API_KEY": "sk-ant-abc", "GLM_MODEL": "glm-5.2"}
    assert "GLM_API_KEY" not in env  # dong bi # = an provider


def test_available_providers_lists_only_those_with_keys():
    env = {"GLM_API_KEY": "glm-secret", "OPENAI_API_KEY": "sk-oa"}
    avail = available_providers(env)
    assert set(avail) == {"glm", "openai"}
    # ghim theo giá trị HIỆN HÀNH của catalog, không ghim mặt chữ —
    # đổi bản GLM (5.2 → 5.3 …) không được làm test tự vỡ.
    assert avail["glm"]["model"] == PROVIDERS["glm"]["default_model"]
    assert avail["glm"]["base_url"].startswith("https://")
    assert avail["glm"]["openai_compatible"] is True


def test_provider_config_reads_model_override_and_errors_without_key():
    env = {"GLM_API_KEY": "k", "GLM_MODEL": "glm-4.6"}
    cfg = provider_config("glm", env)
    assert cfg["model"] == "glm-4.6"
    assert cfg["provider"] == "glm"
    with pytest.raises(RuntimeError, match="chua co key"):
        provider_config("anthropic", env)
    with pytest.raises(RuntimeError, match="khong ho tro"):
        provider_config("bogus", env)


def test_anthropic_is_not_openai_compatible():
    env = {"ANTHROPIC_API_KEY": "sk-ant"}
    cfg = provider_config("anthropic", env)
    assert cfg["openai_compatible"] is False
    assert "base_url" not in cfg


def test_all_four_providers_declared():
    assert set(PROVIDERS) == {"anthropic", "glm", "openai", "gemini"}


def test_parse_json_text_handles_plain_and_fenced_json():
    assert parse_json_text('{"a": 1}') == {"a": 1}
    assert parse_json_text('```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json_text('```\n{"a": 1}\n```') == {"a": 1}
    with pytest.raises(RuntimeError, match="JSON khong hop le"):
        parse_json_text("not json at all")


# --- 429 cua z.ai: nghen toc do HAY het tien? (do that 2026-07-15) ------------------

def test_429_het_tien_khong_bao_nham_thanh_nghen_toc_do():
    """z.ai tra 429 cho CA HAI viec. Body that khi het tien (probe key that 2026-07-15):
    {"error":{"code":"1113","message":"Insufficient balance or no resource package."}}
    Bao "cho mot chut roi chay lai" luc nay = ca team ngoi cho vo ich."""
    from voiceprofile.llm import _explain_429

    real_body = ('{"error":{"code":"1113","message":"Insufficient balance or no '
                 'resource package. Please recharge."}}')
    msg = _explain_429(real_body)
    assert "HET TIEN" in msg
    assert "cho mot chut" not in msg          # KHONG duoc khuyen cho doi

    # 429 that su do nghen toc do -> van khuyen cho roi thu lai
    rate = _explain_429('{"error":{"code":"1302","message":"Too many requests"}}')
    assert "gioi han toc do" in rate and "HET TIEN" not in rate


def test_oe_llm_nhan_dien_het_tien():
    from oe.llm import _no_balance

    assert _no_balance('{"error":{"code":"1113","message":"Insufficient balance"}}')
    assert _no_balance("Please recharge your account")
    assert not _no_balance('{"error":{"code":"1302","message":"Too many requests"}}')
    assert not _no_balance("")

def test_oe_llm_cong_tac_suy_luan_theo_doi_model(tmp_path):
    """GLM 5.3 KHÔNG tắt được thinking (z.ai 1210) và có field `thinking` là 400 →
    body phải mang reasoning_effort thay. Bản 5.2 thì ngược lại: reasoning_effort
    KHÔNG cắt được reasoning nên vẫn phải thinking:disabled. Đo thật 23/08."""
    from oe.llm import LLM, _luon_thinking

    assert _luon_thinking("glm-5.3") and _luon_thinking("GLM-5.3")
    assert not _luon_thinking("glm-5.2") and not _luon_thinking("")

    def body_cua(model):
        env = tmp_path / f"{model}.env"
        env.write_text(chr(10).join(["LLM_PROVIDER=glm", "GLM_API_KEY=k",
                                     f"GLM_MODEL={model}", ""]),
                       encoding="utf-8")
        llm = LLM(env)
        ghi = {}
        llm._stream = lambda body, timeout: ghi.update(body) or "x"   # noqa: ARG005
        llm.complete("s", "u")
        return ghi

    b = body_cua("glm-5.2")
    assert b["thinking"] == {"type": "disabled"} and "reasoning_effort" not in b
    b = body_cua("glm-5.3")
    assert "thinking" not in b and b["reasoning_effort"] == "low"
