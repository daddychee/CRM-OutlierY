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
    assert avail["glm"]["model"] == "glm-5.2"
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
