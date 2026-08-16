"""Cau noi LLM cho cac module can LLM (Module 3 rhetoric, Module 5 generator).

Ho tro 4 provider: Anthropic Claude (SDK rieng) va GLM / OpenAI / Gemini (chung mot
endpoint OpenAI-compatible). File `.env` o goc repo la KHO KEY: dien key cua nhung
provider ban co (nhieu cai cung luc deu duoc); dau `#` de an han mot provider. Chon
provider nao de dung la viec cua nguoi goi (dropdown UI / tham so CLI), khong phai
cua .env.

Lop vo mong duy nhat duoc phep goi API: logic domain (rhetoric.py, generator.py)
nhan callback dang ham nen test duoc offline; file nay cung cap callback that.
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

from . import usage

_REPO_ROOT = Path(os.environ.get("CU_DATA_DIR") or Path(__file__).resolve().parents[2])  # V3: CU_DATA_DIR tro kho du lieu ra data/content-ultimate (Luat 6); mac dinh giu canh repo nhu V2

# Dinh nghia provider: key/model doc tu .env, base_url cho cac provider OpenAI-compatible.
PROVIDERS: dict[str, dict] = {
    "anthropic": {
        "label": "Claude",
        "key_env": "ANTHROPIC_API_KEY",
        "model_env": "ANTHROPIC_MODEL",
        "default_model": "claude-opus-4-8",
        "openai_compatible": False,
    },
    "glm": {
        "label": "GLM",
        "key_env": "GLM_API_KEY",
        "model_env": "GLM_MODEL",
        "base_env": "GLM_BASE_URL",
        "default_model": "glm-5.2",
        "default_base": "https://api.z.ai/api/paas/v4",
        "openai_compatible": True,
    },
    "openai": {
        "label": "ChatGPT",
        "key_env": "OPENAI_API_KEY",
        "model_env": "OPENAI_MODEL",
        "base_env": "OPENAI_BASE_URL",
        "default_model": "gpt-4o",
        "default_base": "https://api.openai.com/v1",
        "openai_compatible": True,
    },
    "gemini": {
        "label": "Gemini",
        "key_env": "GEMINI_API_KEY",
        "model_env": "GEMINI_MODEL",
        "base_env": "GEMINI_BASE_URL",
        "default_model": "gemini-1.5-flash",
        "default_base": "https://generativelanguage.googleapis.com/v1beta/openai",
        "openai_compatible": True,
    },
}


# Lua chon model cho dropdown UI (yeu cau team 2026-07-08): user chon 1 trong 4 —
# Claude Sonnet / Claude Opus / GLM 5.0 / GLM 5.2; chi hien model co key trong .env.
# Id that tren z.ai cua "GLM 5.0" la "glm-5" (do bang endpoint /models, 2026-07-08).
MODEL_CHOICES: list[dict] = [
    {"id": "anthropic:claude-sonnet-5", "provider": "anthropic",
     "model": "claude-sonnet-5", "label": "Claude Sonnet"},
    {"id": "anthropic:claude-opus-4-8", "provider": "anthropic",
     "model": "claude-opus-4-8", "label": "Claude Opus"},
    {"id": "glm:glm-5", "provider": "glm", "model": "glm-5", "label": "GLM 5.0"},
    {"id": "glm:glm-5.2", "provider": "glm", "model": "glm-5.2", "label": "GLM 5.2"},
]


def available_model_choices(env: dict[str, str] | None = None) -> list[dict]:
    """Cac lua chon model da co key provider trong kho .env (cho dropdown UI)."""
    env = _load_env(env)
    return [dict(m) for m in MODEL_CHOICES
            if env.get(PROVIDERS[m["provider"]]["key_env"])]


def load_env_file(path: str | Path) -> dict[str, str]:
    """Parse file .env don gian: KEY=VALUE moi dong; dong bat dau bang # bi bo qua."""
    env: dict[str, str] = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        env[key.strip()] = value.strip().strip("'\"")
    return env


def find_env_file() -> Path | None:
    for candidate in (Path.cwd() / ".env", _REPO_ROOT / ".env"):
        if candidate.is_file():
            return candidate
    return None


def _load_env(env: dict[str, str] | None) -> dict[str, str]:
    if env is not None:
        return env
    # V3: khoa tu KET OUTLIERY (khong doc .env) khi chay sau cong — xem khoa_v3.
    from contentultimate import khoa_v3
    if khoa_v3.bat():
        return khoa_v3.env_ket()
    env_path = find_env_file()
    return load_env_file(env_path) if env_path else dict(os.environ)


def provider_config(name: str, env: dict[str, str] | None = None) -> dict:
    """Config cua 1 provider (api_key/model/base_url) doc tu kho key .env.

    Nem RuntimeError neu provider chua co key — thong diep huong dan sua .env.
    """
    if name not in PROVIDERS:
        raise RuntimeError(f"Provider khong ho tro: {name} (co: {', '.join(PROVIDERS)})")
    env = _load_env(env)
    spec = PROVIDERS[name]
    key = env.get(spec["key_env"])
    if not key:
        raise RuntimeError(
            f"Provider '{name}' chua co key. Dien {spec['key_env']}=... vao .env "
            "(bo dau # o dong do)."
        )
    cfg = {
        "provider": name,
        "api_key": key,
        "model": env.get(spec["model_env"], spec["default_model"]),
        "openai_compatible": spec["openai_compatible"],
    }
    if spec["openai_compatible"]:
        cfg["base_url"] = env.get(spec["base_env"], spec["default_base"])
    return cfg


def available_providers(env: dict[str, str] | None = None) -> dict[str, dict]:
    """Cac provider da co key trong kho .env -> {ten: config}."""
    env = _load_env(env)
    out = {}
    for name in PROVIDERS:
        if env.get(PROVIDERS[name]["key_env"]):
            out[name] = provider_config(name, env)
    return out


# --- Transport --------------------------------------------------------------------

# Tran max_tokens khi tu-tang do reasoning (GLM) dot het budget -> rong. z.ai cho phep lon.
_MAX_TOKENS_CAP = 65536

# z.ai dung 429 cho CA HAI viec: nghen toc do VA het tien (code 1113). Do that
# 2026-07-15 tren key that:
#   {"error":{"code":"1113","message":"Insufficient balance or no resource package."}}
# Bao "cho mot chut roi chay lai" khi thuc te la het tien = ca team ngoi cho vo ich.
_NO_BALANCE = ("1113", "insufficient balance", "no resource package", "recharge")


def _explain_429(body: str) -> str:
    low = (body or "").lower()
    if any(m in low for m in _NO_BALANCE):
        return ("HET TIEN trong tai khoan API (khong phai nghen toc do) — "
                "nap them tien cho provider roi chay lai. Cho doi khong giup gi.")
    return "bi gioi han toc do (429) — cho mot chut roi chay lai"


def _openai_chat(
    system: str, user: str, cfg: dict, max_tokens: int, json_mode: bool, kind: str = ""
) -> str:
    """Goi endpoint OpenAI-compatible (GLM/OpenAI/Gemini), tra ve content tho.

    Neu rong do finish_reason=length (reasoning cua GLM ngon het max_tokens — KHONG phai
    het tien): tu dong goi lai voi max_tokens gap doi, toi da 2 lan (bai hoc 2026-07-11).
    """
    import httpx  # co san vi la dependency cua `anthropic`

    label = PROVIDERS[cfg["provider"]]["label"]
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": user})

    for attempt in range(3):
        payload = {"model": cfg["model"], "messages": messages,
                   "max_tokens": min(max_tokens, _MAX_TOKENS_CAP)}
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        try:
            resp = httpx.post(
                f"{cfg['base_url'].rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {cfg['api_key']}"},
                json=payload,
                # Model thinking (vd GLM) co the chay lau -> read timeout rong
                timeout=httpx.Timeout(600.0, connect=30.0),
            )
        except httpx.HTTPError as e:
            raise RuntimeError(f"Loi ket noi mang khi goi {label}: {e}") from e

        if resp.status_code == 401:
            raise RuntimeError(f"API key {label} sai — kiem tra {PROVIDERS[cfg['provider']]['key_env']} trong .env")
        if resp.status_code == 429:
            # HET TIEN (z.ai code 1113) -> cho vo ich, bao ngay. Nghen TOC DO -> backoff
            # roi thu lai: nhieu nguoi VIET SONG SONG (per-user jobs 2026-07-16) lam 429
            # thoang qua thanh chuyen thuong ngay; chet giua chuong vi 1 cu 429 la phi
            # checkpoint.
            low = (resp.text or "").lower()
            if any(m in low for m in _NO_BALANCE):
                raise RuntimeError(f"{label}: {_explain_429(resp.text)}")
            if attempt < 2:
                time.sleep(10 * (attempt + 1))
                continue
            raise RuntimeError(f"{label}: {_explain_429(resp.text)}")
        if resp.status_code >= 400:
            raise RuntimeError(f"Loi {label} API ({resp.status_code}): {resp.text[:300]}")

        try:
            data = resp.json()
            choice = data["choices"][0]
            content = choice["message"]["content"]
        except (KeyError, IndexError, ValueError) as e:
            raise RuntimeError(f"{label} tra ve response khong dung dinh dang: {resp.text[:300]}") from e
        # Ghi token TRUOC khi xet content: lan tra rong vi reasoning dot het max_tokens
        # VAN TON TIEN, khong ghi la so ghi thieu dung cho luc dat nhat (2026-07-15).
        usage.record_openai_usage(data.get("usage"), cfg["provider"], cfg["model"], kind=kind)
        if content and content.strip():
            return content
        # rong: neu do length va con duoi tran -> tang gap doi, thu lai
        if (choice.get("finish_reason") == "length"
                and max_tokens < _MAX_TOKENS_CAP and attempt < 2):
            max_tokens = min(max_tokens * 2, _MAX_TOKENS_CAP)
            continue
        raise RuntimeError(
            f"{label} khong tra ve noi dung (finish_reason={choice.get('finish_reason')}) — "
            f"reasoning dot het max_tokens (da thu toi {min(max_tokens, _MAX_TOKENS_CAP)}); "
            "KHONG phai het tien. Thu model khac (vd GLM 5.2 / Claude) hoac chuong ngan hon."
        )


def _anthropic_chat(
    system: str, user: str, cfg: dict, max_tokens: int, schema: dict | None, kind: str = ""
) -> str:
    """Goi Claude qua SDK, tra ve text tho (co the la JSON neu truyen schema)."""
    try:
        import anthropic
    except ImportError as e:
        raise RuntimeError(
            'Thieu package `anthropic`. Cai bang: .venv/bin/pip install -e ".[llm]"'
        ) from e

    client = anthropic.Anthropic(api_key=cfg["api_key"])
    kwargs: dict = {
        "model": cfg["model"],
        "max_tokens": max_tokens,
        "thinking": {"type": "adaptive"},
        "messages": [{"role": "user", "content": user}],
    }
    if system:
        kwargs["system"] = system
    if schema is not None:
        kwargs["output_config"] = {"format": {"type": "json_schema", "schema": schema}}
    try:
        response = client.messages.create(**kwargs)
    except anthropic.AuthenticationError as e:
        raise RuntimeError("API key Anthropic sai — kiem tra ANTHROPIC_API_KEY trong .env") from e
    except anthropic.RateLimitError as e:
        raise RuntimeError("Claude bi gioi han toc do (429) — cho mot chut roi chay lai") from e
    except anthropic.APIStatusError as e:
        raise RuntimeError(f"Loi Claude API ({e.status_code}): {e.message}") from e
    except anthropic.APIConnectionError as e:
        raise RuntimeError("Loi ket noi mang khi goi Claude API") from e

    u = getattr(response, "usage", None)
    if u is not None:
        usage.record_usage(cfg["provider"], cfg["model"],
                           getattr(u, "input_tokens", 0), getattr(u, "output_tokens", 0),
                           kind=kind,
                           cached=getattr(u, "cache_read_input_tokens", 0) or 0)
    if response.stop_reason == "refusal":
        raise RuntimeError("Claude tu choi yeu cau (stop_reason=refusal)")
    text = next((b.text for b in response.content if b.type == "text"), "")
    if not text:
        raise RuntimeError(f"Claude khong tra ve text (stop_reason={response.stop_reason})")
    return text


# --- API cho logic domain ---------------------------------------------------------

def llm_text(system: str, user: str, cfg: dict, max_tokens: int = 16000,
             kind: str = "text") -> str:
    """Sinh van ban tu do (Module 5 generator). cfg tu provider_config/available_providers.

    `kind` chi la nhan cho so ghi token (tab Quan ly) — khong doi hanh vi goi API.
    """
    if cfg.get("openai_compatible"):
        return _openai_chat(system, user, cfg, max_tokens, json_mode=False, kind=kind)
    return _anthropic_chat(system, user, cfg, max_tokens, schema=None, kind=kind)


def llm_json(prompt: str, schema: dict, cfg: dict, max_tokens: int = 49152,
             kind: str = "json") -> dict:
    """Sinh JSON theo `schema` (Module 3 rhetoric). cfg tu provider_config."""
    if cfg.get("openai_compatible"):
        full = (
            f"{prompt}\n\n"
            "Return ONLY a single JSON object that validates against this JSON Schema — "
            "no prose, no markdown fences:\n"
            f"{json.dumps(schema, ensure_ascii=False)}"
        )
        content = _openai_chat("", full, cfg, max_tokens, json_mode=True, kind=kind)
    else:
        content = _anthropic_chat("", prompt, cfg, max_tokens=16000, schema=schema, kind=kind)
    return parse_json_text(content)


def parse_json_text(text: str) -> dict:
    """Parse JSON tu text LLM tra ve, chiu duoc truong hop bi boc trong ```json fence."""
    text = text.strip()
    fenced = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"LLM tra ve JSON khong hop le: {text[:200]}") from e
