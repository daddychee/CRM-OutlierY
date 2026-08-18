"""Tab QUẢN TRỊ — đọc/ghi API key (YouTube + LLM) ngay trên board (03/08/2026).

Vì sao cần: trước giờ đổi key là mở .env bằng Notepad trên server — chỉ một người
với tay tới máy làm được, sai một ký tự là tool âm thầm rơi về mặc định (bẫy BOM
đã cắn 2026-07-30). Giờ Owner sửa trên board; quyền `users` (chỉ Owner) — key là
thứ đắt nhất trong hệ, cùng mâm với quản tài khoản.

Nguyên tắc:
- **Key không bao giờ đi ngược ra ngoài**: `summary()` chỉ trả SỐ LƯỢNG key YouTube
  và 4 ký tự cuối key LLM. Không có endpoint nào đọc lại key trần.
- **Ghi .env NGUYÊN TỬ** (file tạm + os.replace) và GIỮ NGUYÊN mọi dòng không quản —
  comment, PORT, biến lạ… đều sống sót. Chỉ các dòng thuộc nhóm đang thay mới bị gỡ.
- **os.environ phải được đồng bộ TAY** ngay sau khi ghi: `load_env` cố ý không đè
  biến đã có trong tiến trình (đúng bài học tab Setting của agent-app) — chỉ ghi
  file thì tới restart mới ăn.
- Ghi LLM bằng bộ `LLM_*` (LLM_PROVIDER/LLM_API_KEY/LLM_MODEL/LLM_BASE_URL):
  `llm._cfg` đọc `LLM_*` TRƯỚC prefix (`GLM_*`…) nên bộ này luôn thắng cấu hình cũ
  còn sót trong .env mà không phải đụng tới chúng.
"""
from __future__ import annotations

import os
import re
import time

from . import common

# Biến thuộc quyền quản của tab này — gỡ khỏi .env khi ghi nhóm tương ứng.
_YT_RE = re.compile(r"^YOUTUBE_API_KEYS?(_\d+)?\s*=")
_LLM_RE = re.compile(r"^LLM_(PROVIDER|API_KEY|MODEL|BASE_URL)\s*=")
PROVIDERS = ("glm", "anthropic", "openai")


def _duoi(k: str) -> str:
    return ("…" + k[-4:]) if len(k) >= 8 else ("…" if k else "")


def summary() -> dict:
    """Trạng thái hiện tại — CHỈ số lượng + đuôi key, không bao giờ key trần."""
    common.load_env()
    provider = (os.environ.get("LLM_PROVIDER") or "glm").lower()
    pfx = provider.upper()
    key = os.environ.get("LLM_API_KEY") or os.environ.get(f"{pfx}_API_KEY") or ""
    model = os.environ.get("LLM_MODEL") or os.environ.get(f"{pfx}_MODEL") or ""
    return {"youtube_n": len(common.load_keys()),
            "llm": {"provider": provider, "model": model, "key_duoi": _duoi(key)},
            # api.txt (nếu có) là nguồn key THÊM ngoài .env — board phải nói ra,
            # không thì Owner thay key xong vẫn thấy số cũ và tưởng lưu hỏng.
            "co_api_txt": (common.ROOT / "api.txt").exists()}


def _tach_yt(tho: str) -> list[str]:
    """Tách danh sách key YouTube từ ô nhập (xuống dòng / phẩy / khoảng trắng)."""
    ra, loi = [], []
    for s in re.split(r"[\s,;]+", tho or ""):
        s = s.strip()
        if not s:
            continue
        if not common._KEY_RE.match(s):
            loi.append(s[:12] + "…")
        elif s not in ra:
            ra.append(s)
    if loi:
        raise ValueError("Key YouTube sai dạng (phải bắt đầu AIza…): " + ", ".join(loi[:3]))
    return ra


def save(b: dict, root=None) -> dict:
    """Ghi các nhóm CÓ MẶT trong body; nhóm vắng mặt giữ nguyên. Trả summary() mới."""
    root = root or common.ROOT
    yt = _tach_yt(str(b.get("youtube_keys") or "")) if str(b.get("youtube_keys") or "").strip() else None
    llm: dict[str, str] = {}
    if str(b.get("llm_provider") or "").strip():
        p = str(b["llm_provider"]).strip().lower()
        if p not in PROVIDERS:
            raise ValueError(f"Provider lạ '{p}' — chọn một trong: " + ", ".join(PROVIDERS))
        llm["LLM_PROVIDER"] = p
    if str(b.get("llm_key") or "").strip():
        llm["LLM_API_KEY"] = str(b["llm_key"]).strip()
    if str(b.get("llm_model") or "").strip():
        llm["LLM_MODEL"] = str(b["llm_model"]).strip()
    if str(b.get("llm_base_url") or "").strip():
        llm["LLM_BASE_URL"] = str(b["llm_base_url"]).strip()
    if yt is None and not llm:
        raise ValueError("Chưa có gì để lưu — điền key YouTube hoặc phần LLM rồi bấm lại")

    f = root / ".env"
    dong = f.read_text(encoding="utf-8-sig", errors="replace").splitlines() if f.exists() else []
    giu = []
    for d in dong:
        s = d.strip().lstrip("﻿")
        if yt is not None and _YT_RE.match(s):
            continue                                   # thay cả nhóm YouTube
        if llm and _LLM_RE.match(s):
            continue                                   # bộ LLM_* ghi lại bên dưới
        giu.append(d)
    moi = [f"# --- Quản trị (board) cập nhật {time.strftime('%Y-%m-%d %H:%M')} ---"]
    if yt is not None:
        moi.append("YOUTUBE_API_KEYS=" + ",".join(yt))
    moi += [f"{k}={v}" for k, v in llm.items()]
    tam = f.with_name(".env.tmp")
    tam.write_text("\n".join(giu + moi) + "\n", encoding="utf-8")
    os.replace(tam, f)

    # Đồng bộ tiến trình đang chạy — load_env không đè biến đã có (cố ý).
    if yt is not None:
        for k in [k for k in os.environ if k.startswith("YOUTUBE_API_KEY")]:
            del os.environ[k]
        os.environ["YOUTUBE_API_KEYS"] = ",".join(yt)
    os.environ.update(llm)
    return summary()


if __name__ == "__main__":                             # self-test offline (tmp root + env cách ly)
    import tempfile
    from pathlib import Path

    giu_env = dict(os.environ)
    giu_root = common.ROOT
    try:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # Cách ly TRỌN: summary() đi qua common.load_env/load_keys vốn đọc common.ROOT
            # — không patch thì self-test đọc .env THẬT của dự án (nạp lại key cũ vào
            # environ, đếm key thật) và kết quả phụ thuộc máy đang chạy.
            common.ROOT = root
            (root / ".env").write_text("# giu nguyen dong nay\nPORT=8760\n"
                                       "YOUTUBE_API_KEY_1=AIzaCuKeyMotXXXXXXXXXXXXXXX\n"
                                       "GLM_API_KEY=cu-khong-dung-nua\n", encoding="utf-8")
            os.environ["YOUTUBE_API_KEY_1"] = "AIzaCuKeyMotXXXXXXXXXXXXXXX"
            k1, k2 = "AIza" + "A" * 30, "AIza" + "B" * 30
            r = save({"youtube_keys": f"{k1}\n{k2},{k2}",       # lẫn xuống dòng + phẩy + trùng
                      "llm_provider": "glm", "llm_key": "key-moi-1234",
                      "llm_model": "glm-5.2"}, root=root)
            nd = (root / ".env").read_text(encoding="utf-8")
            assert "# giu nguyen dong nay" in nd and "PORT=8760" in nd, "dòng lạ phải sống sót"
            assert "YOUTUBE_API_KEY_1=" not in nd, "key cũ phải bị gỡ khi thay cả nhóm"
            assert f"YOUTUBE_API_KEYS={k1},{k2}" in nd, "2 key mới, đã bỏ trùng"
            assert "LLM_API_KEY=key-moi-1234" in nd and "GLM_API_KEY=cu-khong-dung-nua" in nd, \
                "LLM_* ghi thêm, GLM_* cũ giữ nguyên (LLM_* thắng khi đọc)"
            assert os.environ.get("YOUTUBE_API_KEYS") == f"{k1},{k2}"
            assert "YOUTUBE_API_KEY_1" not in os.environ, "environ phải gỡ key số cũ"
            assert r["llm"]["key_duoi"] == "…1234" and "key-moi" not in str(r), \
                "summary chỉ đuôi key, không key trần"
            try:
                save({"youtube_keys": "khong-phai-key"}, root=root)
                raise AssertionError("key sai dạng phải bị chặn")
            except ValueError:
                pass
            try:
                save({}, root=root)
                raise AssertionError("body rỗng phải bị chặn")
            except ValueError:
                pass
    finally:
        common.ROOT = giu_root
        os.environ.clear()
        os.environ.update(giu_env)
    print("admin_keys.py self-test OK · ghi nguyên tử · thay nhóm · mask đuôi key")
