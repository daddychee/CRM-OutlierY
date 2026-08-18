"""Kiểm nhanh LLM đang cấu hình có gọi được không: `python -m seo.checkllm`.

Không đụng quota YouTube, tốn ~20 token. Dùng ngay sau khi đổi nhà cung cấp trong .env.
"""
from __future__ import annotations

import os

from . import common, llm


def main() -> int:
    common.load_env()
    prov = (os.environ.get("LLM_PROVIDER") or "glm").lower()
    pfx = prov.replace(".", "").upper()
    key = os.environ.get("LLM_API_KEY") or os.environ.get(f"{pfx}_API_KEY") or ""
    model = os.environ.get("LLM_MODEL") or os.environ.get(f"{pfx}_MODEL") or "(mặc định)"
    base = os.environ.get("LLM_BASE_URL") or os.environ.get(f"{pfx}_BASE_URL") or "(mặc định)"
    print(f"provider : {prov}")
    print(f"model    : {model}")
    print(f"base_url : {base}")
    print(f"key      : {'CHƯA ĐIỀN' if not key else f'có, dài {len(key)}, bắt đầu {key[:7]}…'}")
    if not key:
        print(f"\n❌ Thiếu {pfx}_API_KEY trong .env — mở file .env, điền vào sau dấu =, rồi chạy lại.")
        return 1
    print("\nGọi thử…")
    try:
        out = llm.call("Trả đúng 2 chữ: OK NHE", "ping", max_tokens=20, temperature=0, cache=False)
        print(f"✅ trả lời: {str(out)[:120]!r}")
    except Exception as e:                                   # noqa: BLE001
        print(f"❌ {type(e).__name__}: {str(e)[:400]}")
        return 1
    print("\nThử JSON mode (đường mà mọi stage thật đều đi qua)…")
    try:
        j = llm.call_json('Trả JSON {"ok":true,"n":2}.', "ping", max_tokens=60, temperature=0)
        print(f"✅ parse được: {j}")
    except Exception as e:                                   # noqa: BLE001
        print(f"❌ JSON mode hỏng: {type(e).__name__}: {str(e)[:400]}")
        return 1
    print("\nSẵn sàng chạy tool.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
