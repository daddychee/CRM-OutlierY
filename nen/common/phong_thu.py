# -*- coding: utf-8 -*-
"""LỚP PHÒNG THỦ API NGOÀI (05/09/2026) — spec docs/phong-thu-api-ngoai.md.

Bốn van, chạy tại MỘT điểm-ra LLM (src/llm của từng app nối qua base.py):
1. kiem_host   — BASE_URL phải https + host trong allowlist: .env bị sửa/gõ nhầm
   trỏ prompt + key sang server lạ là chết NGAY lúc dựng client.
2. kiem_secret — giá trị secret trong env xuất hiện nguyên văn trong prompt → chặn
   call (bắt cả bug ghép prompt lẫn tài liệu chứa key thật).
3. kiem_tran   — trần chi tiêu LLM/NGÀY (USD + số call, đọc sổ gọi so_goi);
   mặc định TẮT — Owner bật bằng .env, không đổi hành vi hệ đang chạy.
4. che_pii     — helper che email/SĐT (+ tên → mã NS theo bảng) TRƯỚC khi dữ liệu
   nhân sự vào prompt. Nơi gọi chủ động dùng, không tự động (che mù mọi prompt
   sẽ phá hỏi–đáp tài liệu thường).

Quy tắc fail: vi phạm CHỦ ĐÍCH → raise LoiPhongThu (lỗi NỔI, thông điệp rõ —
cùng họ LLM_RETRY=0); lỗi NỘI BỘ của chính van (sổ hỏng, env rác) → bỏ qua van
đó, KHÔNG giết call thật.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime
from urllib.parse import urlparse


class LoiPhongThu(RuntimeError):
    """Van phòng thủ chặn một lời gọi API ngoài — thông điệp nói rõ vì sao + cách gỡ."""


# Host API đã duyệt (khớp các nhà factory/openai_compatible đang hướng dẫn).
# Thêm nhà mới: .env LLM_HOST_CHO_PHEP=a.com,b.com (không cần sửa code).
HOST_MAC_DINH = frozenset({
    "api.anthropic.com", "api.openai.com", "api.z.ai",
    "open.bigmodel.cn", "api.deepseek.com", "api.x.ai",
    # Nhà KÉT khai chính thức (ket.NHA_LLM_INFO) phải mở luồng SẴN. Khai bằng
    # LLM_HOST_CHO_PHEP không cứu được: CHỈ gateway đọc .env, app nhận env từ
    # start-all nên dễ sót. Sự cố 12/09: mwapi vào KÉT 07/09 mà van chặn ngay tại
    # cửa → diễn giải chẩn đoán kênh chết lặng lẽ; Gemini cũng đang bị chặn y vậy.
    "generativelanguage.googleapis.com",   # Gemini (Google)
    "api.mwapi.dev",                       # Claude qua reseller mwapi
})
_LOOPBACK = ("localhost", "127.0.0.1", "::1")


def _hosts_cho_phep() -> set[str]:
    them = {h.strip().lower() for h in os.getenv("LLM_HOST_CHO_PHEP", "").split(",")
            if h.strip()}
    return set(HOST_MAC_DINH) | them


def kiem_host(base_url: str | None) -> None:
    """Chặn BASE_URL ngoài allowlist. Rỗng/None = mặc định SDK (đã trong
    allowlist) → qua; loopback (mock/dev) → qua, kể cả http."""
    if not base_url or not str(base_url).strip():
        return
    u = urlparse(str(base_url).strip())
    host = (u.hostname or "").lower()
    if host in _LOOPBACK:
        return
    if u.scheme != "https":
        raise LoiPhongThu(
            f"Chặn BASE_URL '{base_url}': API ngoài bắt buộc https "
            f"(chỉ loopback được miễn).")
    if host not in _hosts_cho_phep():
        raise LoiPhongThu(
            f"Chặn BASE_URL '{base_url}': host '{host}' không nằm trong allowlist "
            f"điểm-ra. Nhà cung cấp mới thì thêm vào .env "
            f"LLM_HOST_CHO_PHEP={host} (spec docs/phong-thu-api-ngoai.md).")


# Tên biến env coi là secret. Giá trị < 12 ký tự bỏ qua — tránh dương tính giả
# kiểu TOKENIZERS_PARALLELISM=false; key/mật khẩu thật luôn dài hơn.
_MAU_TEN_SECRET = re.compile(r"API_?KEY|SECRET|TOKEN|PASSWORD|MAT_KHAU", re.I)
_DAI_SECRET_TOI_THIEU = 12


def _secrets_env() -> list[tuple[str, str]]:
    return [(ten, gia) for ten, gia in os.environ.items()
            if _MAU_TEN_SECRET.search(ten) and len(gia) >= _DAI_SECRET_TOI_THIEU]


def kiem_secret(*van_ban: str) -> None:
    """Secret từ env nằm NGUYÊN VĂN trong văn bản sắp gửi ra ngoài → chặn."""
    for ten, gia in _secrets_env():
        for t in van_ban:
            if t and gia in t:
                raise LoiPhongThu(
                    f"Chặn gọi LLM: giá trị secret '{ten}' xuất hiện trong prompt "
                    f"— kiểm tra chỗ ghép prompt hoặc tài liệu nguồn đang chứa key thật.")


def _tieu_llm_hom_nay() -> tuple[float, int]:
    """(USD đã chốt, số call) của dịch vụ llm HÔM NAY từ sổ gọi. Lọc thô bằng
    substring trước khi parse — sổ một ngày có thể ~31k dòng (đa số youtube)."""
    from nen.common import so_goi
    gio = datetime.now()
    f = so_goi._goc() / f"{gio:%Y}" / f"{gio:%m}" / f"{gio:%Y-%m-%d}.log"
    usd, calls = 0.0, 0
    try:
        dong = f.read_text(encoding="utf-8").splitlines()
    except OSError:
        return 0.0, 0
    for ln in dong:
        if '"dich_vu": "llm"' not in ln:
            continue
        calls += 1
        try:
            d = json.loads(ln)
        except ValueError:
            continue
        if d.get("usd"):
            usd += float(d["usd"])
    return usd, calls


def kiem_tran() -> None:
    """Trần LLM/ngày: LLM_TRAN_USD_NGAY + LLM_TRAN_CALL_NGAY (.env; 0/trống = tắt).
    Call cap đếm MỌI call llm (kể cả stream/lỗi) nên là thước tin cậy; USD chỉ
    cộng dòng đã chốt giá (model chưa khai giá / stream chưa đo token không vào)."""
    try:
        tran_usd = float(os.getenv("LLM_TRAN_USD_NGAY", "0") or 0)
        tran_call = int(float(os.getenv("LLM_TRAN_CALL_NGAY", "0") or 0))
        if tran_usd <= 0 and tran_call <= 0:
            return
        usd, calls = _tieu_llm_hom_nay()
    except Exception:   # noqa: BLE001 — lỗi nội bộ của van không giết call thật
        return
    if tran_usd > 0 and usd >= tran_usd:
        raise LoiPhongThu(
            f"Chặn gọi LLM: hôm nay đã tiêu {usd:.2f} USD ≥ trần "
            f"LLM_TRAN_USD_NGAY={tran_usd:g} — nâng trần trong .env hoặc chờ sang ngày.")
    if tran_call > 0 and calls >= tran_call:
        raise LoiPhongThu(
            f"Chặn gọi LLM: hôm nay đã gọi {calls} lượt ≥ trần "
            f"LLM_TRAN_CALL_NGAY={tran_call} — nâng trần trong .env hoặc chờ sang ngày.")


def kiem_truoc_goi(system_prompt: str = "", user_prompt: str = "") -> None:
    """Bộ van chạy trước MỌI call LLM thật (mock không qua đây)."""
    kiem_secret(system_prompt, user_prompt)
    kiem_tran()


MAU_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")
# SĐT VN: 0xxxxxxxxx / +84xxxxxxxxx, cho phép ngăn cách ' ', '.', '-';
# (?<![\d.]) và (?!\d) chống ăn nhầm khúc giữa của số dài / số thập phân.
MAU_SDT = re.compile(r"(?<![\d.])(?:\+?84|0)\d(?:[ .\-]?\d){7,9}(?!\d)")


def che_pii(text: str, bang_ten: dict[str, str] | None = None) -> str:
    """Che email + SĐT VN; đưa bảng {tên thật: mã NS-xxx} thì che cả tên (so
    không phân biệt hoa thường, tên dài thay trước để không cắt đôi tên lồng)."""
    ra = MAU_EMAIL.sub("[email]", text)
    ra = MAU_SDT.sub("[sdt]", ra)
    for ten in sorted(bang_ten or {}, key=len, reverse=True):
        if ten.strip():
            ra = re.sub(re.escape(ten), bang_ten[ten], ra, flags=re.IGNORECASE)
    return ra
