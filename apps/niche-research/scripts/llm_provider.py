"""Generic multi-provider LLM caller for the JUDGEMENT stages (S9b namer / S12 auditor / S13 plan /
S16-17 DNA). Config-driven so ANY provider works — Claude, ChatGPT, GLM, Grok, or a custom
OpenAI-compatible endpoint — without touching the pipeline code. Configure in .env (see
.env.example). Before this module is wired in (via run_agent.py), those stages don't exist as
running code — every "verdict" the report shows is a Python threshold rule, not a model's judgement.

Two independent ROLES can point at DIFFERENT providers, so the Auditor (S12) can genuinely be a
different model than the rest of the pipeline — required for real critique, not a rubber stamp
(residual R-0 in references/outlier_method.md / references/dong_kiem_protocol.md):

    LLM_PROVIDER=anthropic          # used by namer / plan / dna (role="default")
    AUDITOR_LLM_PROVIDER=glm        # used by the Auditor only (role="auditor") — falls back to
                                     # LLM_PROVIDER if unset.
    AUDITOR_MODEL=claude-sonnet-4   # optional per-role model override (same provider, diff model)

Supported providers: anthropic (Claude), openai (ChatGPT), glm (Zhipu GLM), grok (xAI), or
custom (any OpenAI-compatible endpoint — set CUSTOM_BASE_URL/CUSTOM_API_KEY/CUSTOM_MODEL).
"""
import os, re, json
import requests
from _common import get_env

_ANTHROPIC_DEFAULT_MODEL = "claude-sonnet-4-5"
_OPENAI_DEFAULT_MODEL    = "gpt-4o"
_GLM_DEFAULT_MODEL       = "glm-5.2"
# Z.AI (docs.z.ai) — international endpoint. Domestic Zhipu accounts (bigmodel.cn) use a different
# base URL/key; override via GLM_BASE_URL in .env if that's what you have.
_GLM_DEFAULT_BASE        = "https://api.z.ai/api/paas/v4"
# Models that always reason (see the note where extra_body is built).
_GLM_ALWAYS_THINKING     = ("glm-5.3",)
_GROK_DEFAULT_MODEL      = "grok-4"
_GROK_DEFAULT_BASE       = "https://api.x.ai/v1"


class LLMError(Exception):
    pass


def _always_thinking(model: str) -> bool:
    m = (model or "").lower()
    return any(m.startswith(x) for x in _GLM_ALWAYS_THINKING)


def _anthropic_call(system, user, *, work, max_tokens, cache_prefix=None, model_override=None):
    key = get_env("ANTHROPIC_API_KEY", work)
    if not key: raise LLMError("ANTHROPIC_API_KEY not set in .env")
    model = model_override or get_env("ANTHROPIC_MODEL", work, _ANTHROPIC_DEFAULT_MODEL)
    # cache_prefix = a large STATIC block reused across calls (method+evidence). Marking it
    # cache_control ephemeral means later calls within ~5 min reuse it at ~10% input cost — same
    # content, zero quality loss. See run_agent.run_summary (3 passes share one prefix).
    if cache_prefix:
        system_field = [
            {"type": "text", "text": cache_prefix, "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": system},
        ]
    else:
        system_field = system
    # STREAM the response: large max_tokens can take minutes to generate; streaming reads deltas as
    # they arrive so we never hit a single-read timeout (the 180s applies PER CHUNK, not to the whole
    # generation). This is the robust way to fetch long outputs (auditor / summary).
    r = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
        json={"model": model, "max_tokens": max_tokens, "system": system_field, "stream": True,
              "messages": [{"role": "user", "content": user}]},
        timeout=180, stream=True,
    )
    if r.status_code != 200:
        raise LLMError(f"Anthropic API {r.status_code}: {r.text[:300]}")
    parts = []
    try:
        for raw in r.iter_lines():
            if not raw: continue
            line = raw.decode("utf-8", "ignore")
            if not line.startswith("data:"): continue
            try: obj = json.loads(line[5:].strip())
            except Exception: continue
            t = obj.get("type")
            if t == "content_block_delta" and obj.get("delta", {}).get("type") == "text_delta":
                parts.append(obj["delta"].get("text", ""))
            elif t == "error":
                raise LLMError(f"Anthropic stream error: {obj.get('error', obj)}")
    except (requests.ConnectionError, requests.ChunkedEncodingError) as e:
        # Mid-stream network drop — retry once with non-streaming fallback
        if parts:
            print(f"  ⚠ Anthropic stream dropped mid-generation ({e.__class__.__name__}) — "
                  f"returning PARTIAL output ({len(''.join(parts)):,} chars); result may be truncated")
            return "".join(parts)  # partial output is better than nothing — but say so (V19)
        r2 = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={"model": model, "max_tokens": max_tokens, "system": system_field,
                  "messages": [{"role": "user", "content": user}]},
            timeout=300,
        )
        if r2.status_code != 200:
            raise LLMError(f"Anthropic retry {r2.status_code}: {r2.text[:300]}")
        return r2.json().get("content", [{}])[0].get("text", "")
    if not parts:
        raise LLMError("Anthropic: empty stream (no content deltas received)")
    return "".join(parts)


def _openai_compatible_call(base_url, key_env, model_env, default_model, system, user, *, work, max_tokens, label, cache_prefix=None, model_override=None, extra_body=None):
    key = get_env(key_env, work)
    if not key: raise LLMError(f"{key_env} not set in .env")
    model = model_override or get_env(model_env, work, default_model)
    if not model: raise LLMError(f"{model_env} not set in .env (no default for provider '{label}')")
    # OpenAI/GLM/etc do automatic server-side prefix caching — put the static block FIRST so an
    # identical prefix across calls is cached transparently (no per-call flag needed).
    sys_text = (cache_prefix + "\n\n" + system) if cache_prefix else system
    body = {"model": model, "max_tokens": max_tokens, "stream": True,
            "messages": [{"role": "system", "content": sys_text}, {"role": "user", "content": user}]}
    if extra_body: body.update(extra_body)
    # STREAM (see _anthropic_call) — robust to minutes-long generations without a read timeout.
    r = requests.post(
        f"{base_url.rstrip('/')}/chat/completions",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json=body, timeout=180, stream=True,
    )
    if r.status_code != 200:
        raise LLMError(f"{label} API {r.status_code}: {r.text[:300]}")
    parts = []; reasoning_only = []   # reasoning_content = the model's chain-of-thought (e.g. GLM
    # "thinking" models) — never the answer, but captured as a diagnostic fallback if content is empty.
    try:
        for raw in r.iter_lines():
            if not raw: continue
            line = raw.decode("utf-8", "ignore")
            if not line.startswith("data:"): continue
            data = line[5:].strip()
            if data == "[DONE]": break
            try: obj = json.loads(data)
            except Exception: continue
            try:
                delta = obj["choices"][0].get("delta", {})
                if delta.get("content"): parts.append(delta["content"])
                elif delta.get("reasoning_content"): reasoning_only.append(delta["reasoning_content"])
            except (KeyError, IndexError):
                continue
    except (requests.ConnectionError, requests.ChunkedEncodingError) as e:
        # Mid-stream network drop — retry once with non-streaming fallback
        if parts:
            print(f"  ⚠ {label} stream dropped mid-generation ({e.__class__.__name__}) — "
                  f"returning PARTIAL output ({len(''.join(parts)):,} chars); result may be truncated")
            return "".join(parts)  # partial output is better than nothing — but say so (V19)
        r2 = requests.post(
            f"{base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={k: v for k, v in body.items() if k != "stream"},
            timeout=300,
        )
        if r2.status_code != 200:
            raise LLMError(f"{label} retry {r2.status_code}: {r2.text[:300]}")
        return r2.json().get("choices", [{}])[0].get("message", {}).get("content", "")
    if not parts:
        if reasoning_only:
            raise LLMError(f"{label}: model only emitted reasoning/thinking tokens before hitting "
                           f"max_tokens (no final answer) — raise max_tokens or set GLM_THINKING=disabled")
        raise LLMError(f"{label}: empty stream (no content deltas)")
    return "".join(parts)


def call(provider, system, user, *, work=".", max_tokens=4096, cache_prefix=None, model_override=None):
    """Call ONE named provider directly. `cache_prefix` = a large static block shared across calls
    (cached: Anthropic explicit, OpenAI-compatible automatic). `model_override` lets callers swap
    the model within a provider without changing LLM_PROVIDER (e.g. Auditor uses AUDITOR_MODEL
    while staying on the same provider). See the module docstring for names."""
    provider = (provider or "anthropic").lower().strip()
    if provider in ("anthropic", "claude"):
        return _anthropic_call(system, user, work=work, max_tokens=max_tokens, cache_prefix=cache_prefix, model_override=model_override)
    if provider in ("openai", "chatgpt", "gpt"):
        return _openai_compatible_call("https://api.openai.com/v1", "OPENAI_API_KEY", "OPENAI_MODEL",
                                       _OPENAI_DEFAULT_MODEL, system, user, work=work,
                                       max_tokens=max_tokens, label="OpenAI", cache_prefix=cache_prefix, model_override=model_override)
    if provider == "glm":
        base = get_env("GLM_BASE_URL", work, _GLM_DEFAULT_BASE)
        # GLM-5.x are reasoning models: by default they stream a "reasoning_content" chain-of-thought
        # BEFORE the real "content" — on a small max_tokens that reasoning alone can exhaust the
        # budget, leaving no room for the actual answer. Our agents want clean JSON/markdown output,
        # not exposed reasoning, so thinking is OFF by default; set GLM_THINKING=enabled to restore it.
        # GLM 5.3+ can't disable thinking at all: sending a `thinking` field returns
        # 400 (z.ai code 1210 "always engages in thinking ... use low, high, or max").
        # Measured 23/08/2026 — the reverse holds too: on glm-5.2 `reasoning_effort`
        # does NOT cut reasoning (still 178-205 tokens), so the older models keep
        # thinking:disabled. Two generations, two switches — never swap blindly.
        model_that = model_override or get_env("GLM_MODEL", work, _GLM_DEFAULT_MODEL)
        if _always_thinking(model_that):
            # z.ai only accepts low | high | max ("minimal" → 400).
            extra = {"reasoning_effort": get_env("GLM_REASONING_EFFORT", work, "low")}
        else:
            thinking = get_env("GLM_THINKING", work, "disabled")
            extra = {"thinking": {"type": thinking}} if thinking in ("enabled", "disabled") else None
        return _openai_compatible_call(base, "GLM_API_KEY", "GLM_MODEL", _GLM_DEFAULT_MODEL,
                                       system, user, work=work, max_tokens=max_tokens, label="GLM",
                                       cache_prefix=cache_prefix, model_override=model_override, extra_body=extra)
    if provider in ("grok", "xai"):
        base = get_env("GROK_BASE_URL", work, _GROK_DEFAULT_BASE)
        return _openai_compatible_call(base, "GROK_API_KEY", "GROK_MODEL", _GROK_DEFAULT_MODEL,
                                       system, user, work=work, max_tokens=max_tokens, label="Grok", cache_prefix=cache_prefix, model_override=model_override)
    if provider == "custom":
        base = get_env("CUSTOM_BASE_URL", work)
        if not base: raise LLMError("CUSTOM_BASE_URL not set in .env for provider=custom")
        return _openai_compatible_call(base, "CUSTOM_API_KEY", "CUSTOM_MODEL", "",
                                       system, user, work=work, max_tokens=max_tokens, label="custom", cache_prefix=cache_prefix, model_override=model_override)
    raise LLMError(f"unknown provider '{provider}'. Supported: anthropic, openai, glm, grok, custom")


def call_role(role, system, user, *, work=".", max_tokens=4096, cache_prefix=None):
    """ONE provider (LLM_PROVIDER) drives every task by default — pick Claude OR GLM (etc.) and use it
    throughout. role='auditor' MAY point at a second model via AUDITOR_LLM_PROVIDER + AUDITOR_MODEL
    (so Builder=claude-opus-4, Auditor=claude-sonnet-4 on the SAME provider is supported — fulfills
    the auditor.md contract "Builder ≠ Auditor" without forcing a provider switch).
    `cache_prefix` = a large static block shared across calls (cached to cut token cost).
    Returns (text, provider_name_used)."""
    default_provider = get_env("LLM_PROVIDER", work, "anthropic")
    model = None
    if role == "auditor":
        provider = get_env("AUDITOR_LLM_PROVIDER", work) or default_provider
        if provider == default_provider:
            # Same provider — the per-role model override matters
            model = get_env("AUDITOR_MODEL", work) or None
    else:
        provider = default_provider
    return call(provider, system, user, work=work, max_tokens=max_tokens, cache_prefix=cache_prefix, model_override=model), provider


_OC = {"{": "}", "[": "]"}

def _salvage(s):
    """Recover a partial JSON value: cut at the last clean boundary and close any open brackets.
    Used when the model's JSON is truncated or malformed mid-way — better to keep the fields parsed
    so far than to lose the whole result."""
    # Only a comma or a closing bracket marks a boundary BETWEEN complete elements — a closed string
    # alone does not (it might be a key still awaiting its value). Cutting only at these boundaries
    # avoids leaving a dangling "key" with no value.
    stack = []; in_str = False; esc = False; last_safe = 0
    for i, ch in enumerate(s):
        if in_str:
            if esc: esc = False
            elif ch == "\\": esc = True
            elif ch == '"': in_str = False
            continue
        if ch == '"': in_str = True
        elif ch in "{[": stack.append(_OC[ch]); last_safe = i + 1
        elif ch in "}]":
            if stack: stack.pop()
            last_safe = i + 1
        elif ch == ",": last_safe = i          # cut BEFORE a dangling comma (keeps prior elements)
    cut = re.sub(r"[,\s]+$", "", s[:last_safe])
    # recompute open brackets for the trimmed string, then close them
    stack = []; in_str = False; esc = False
    for ch in cut:
        if in_str:
            if esc: esc = False
            elif ch == "\\": esc = True
            elif ch == '"': in_str = False
            continue
        if ch == '"': in_str = True
        elif ch in "{[": stack.append(_OC[ch])
        elif ch in "}]":
            if stack: stack.pop()
    if in_str: cut += '"'
    while stack: cut += stack.pop()
    return cut

def _escape_control_chars(s):
    """Fix literal control characters inside JSON string values (newlines, tabs, etc).
    LLMs sometimes emit raw newlines inside string values instead of \\n, which breaks json.loads
    with "Expecting ',' delimiter" or "Unterminated string" errors."""
    # Walk the string, track whether we're inside a JSON string, and escape raw control chars
    out = []; in_str = False; esc = False
    for ch in s:
        if in_str:
            if esc:
                out.append(ch); esc = False; continue
            if ch == '\\':          # was '\\\\' — a 2-char string a single char can never equal (V18)
                out.append(ch); esc = True; continue
            if ch == '"':
                out.append(ch); in_str = False; continue
            if ch == '\n':
                out.append('\\n'); continue
            if ch == '\r':
                out.append('\\r'); continue
            if ch == '\t':
                out.append('\\t'); continue
            if ord(ch) < 32:
                out.append(f'\\u{ord(ch):04x}'); continue
            out.append(ch)
        else:
            if ch == '"':
                in_str = True
            out.append(ch)
    return ''.join(out)

def _load_forgiving(s):
    """json.loads with escalating repairs:
    1. Direct parse
    2. Kill trailing commas
    3. Escape unescaped control characters inside strings (common LLM mistake)
    4. Truncate-at-error + salvage (recover valid prefix)
    5. Full salvage from end (work backwards from the error position)
    """
    # 1. Direct
    try: return json.loads(s)
    except json.JSONDecodeError: pass
    # 2. Trailing commas
    s2 = re.sub(r",(\s*[}\]])", r"\1", s)
    try: return json.loads(s2)
    except json.JSONDecodeError: pass
    # 3. Escape control chars inside strings (LLMs often emit raw newlines in string values)
    s3 = _escape_control_chars(s2)
    try: return json.loads(s3)
    except json.JSONDecodeError as e:
        pos = e.pos if getattr(e, "pos", None) else len(s3)
    # 4. Salvage from error position (keep valid prefix)
    try: return json.loads(_salvage(s3[:pos]))
    except Exception: pass
    # 5. Full salvage on the entire string (don't cut at error — try to recover from the end)
    try: return json.loads(_salvage(s3))
    except Exception as e2:
        raise e2

def extract_json(text):
    """Pull JSON out of an LLM reply and parse it ROBUSTLY — tolerates ```json fences, surrounding
    prose, trailing commas, mid-string syntax errors, and truncation (recovers the valid prefix)."""
    t = (text or "").strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", t, re.DOTALL)
    if m: t = m.group(1).strip()
    start = next((i for i, c in enumerate(t) if c in "{["), None)
    if start is None:
        raise LLMError(f"no JSON found in LLM output (got {len(t)} chars): {t[:200]!r}")
    frag = t[start:]
    try:
        return _load_forgiving(frag)
    except Exception as e:
        raise LLMError(f"could not parse/repair JSON from LLM output ({e}); "
                       f"tail: {frag[-120:]!r}") from e


def validate_json(obj, required_fields, label="output"):
    """Lightweight schema validation — checks that required top-level fields exist and are the right
    type. Does NOT use jsonschema (no external dep). Raises LLMError with a clear message on failure
    so the caller knows the LLM returned bad structure, not bad numbers."""
    if not isinstance(obj, dict):
        raise LLMError(f"{label}: expected JSON object, got {type(obj).__name__}")
    missing = [f for f in required_fields if f not in obj or obj[f] is None]
    if missing:
        raise LLMError(f"{label}: missing required fields: {missing}. Got keys: {list(obj.keys())}")
    return obj
