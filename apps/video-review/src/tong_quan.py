# -*- coding: utf-8 -*-
"""TỔNG QUAN — sàn chung Content ↔ Editor (mockup vòng 6, màn Overview).

Mỗi tập một THẺ: ba trạm Writing / Editing / Publish + VIỆC KẾ TIẾP đang chờ ai.
Nguyên tắc (giữ như mọi module của app này):
  - KHÔNG bịa trạng thái: tập viết ngoài tool ghi đúng "viết ngoài tool", tập
    chưa đăng ghi "—", không suy diễn cho quá khứ.
  - Việc kế tiếp chỉ nói điều ĐỌC ĐƯỢC từ sổ; không đoán deadline, không chấm điểm.
Hàm thuần trên dữ liệu kho_video/hau_kiem — không đụng NAS, không gọi LLM.
"""
from __future__ import annotations

from src import hau_kiem, kho_video

# Ba trạm, đúng thứ tự tab trên navigator.
TRAM = ("writing", "editing", "publish")


def _trang_thai_writing(ma_tap: str, kich_ban: dict | None) -> tuple[str, str, str]:
    """(tình trạng máy đọc, chữ hiển thị, trạng thái thanh tiến trình)."""
    if kich_ban is None:
        return "ngoai_tool", "viết ngoài tool", "trong"
    if kich_ban.get("chot_luc"):
        return "da_chot", f"Đã chốt {kich_ban.get('ban', 'v1')}", "xong"
    return "cho_duyet", "chờ leader duyệt", "dang"


def _trang_thai_editing(tap: dict) -> tuple[str, str, str]:
    ds = tap.get("duyet") or []
    if not ds:
        return "chua_co", "chưa có bản dựng", "trong"
    cho = [v for v in ds if v["trang_thai"] != "da_duyet"]
    if tap.get("xong_duyet"):
        return "xong", f"{len(ds)} bản · Approved", "xong"
    return "dang", f"{len(ds)} bản · {len(cho)} chờ duyệt", "dang"


def _trang_thai_publish(tap: dict, gc: dict | None) -> tuple[str, str, str]:
    full = tap.get("full")
    if not full:
        return "chua_dang", "—", "trong"
    if gc is not None:
        return "hau_kiem_xong", "hậu kiểm xong", "xong"
    return "da_dang", "đã đăng · chưa hậu kiểm", "dang"


def _viec_ke(w: tuple, e: tuple, p: tuple) -> str:
    """Một câu: việc kế tiếp đang chờ AI làm. Đọc từ trạng thái ba trạm."""
    if w[0] == "cho_duyet":
        return "→ leader: duyệt kịch bản"
    if e[0] == "dang":
        return "→ leader: duyệt bản dựng đang chờ"
    if w[0] == "da_chot" and e[0] == "chua_co":
        return "→ editor: gen voice rồi nộp RenderY"
    if p[0] == "da_dang":
        return "→ đủ dữ liệu thì chạy hậu kiểm"
    if p[0] == "hau_kiem_xong":
        return "→ content + editor: áp kết luận vào tập sau"
    return ""


def cac_the(kich_ban_theo_tap: dict[str, dict] | None = None) -> list[dict]:
    """Danh sách thẻ tập cho màn Overview. `kich_ban_theo_tap` do tầng kịch bản
    cấp (chưa nối thì mọi tập là 'viết ngoài tool' — đúng sự thật hiện nay)."""
    kb = kich_ban_theo_tap or {}
    ra = []
    for tap in kho_video.cac_tap():
        gc = hau_kiem.lay_giu_chan(tap["ma"]) if tap.get("full") else None
        w = _trang_thai_writing(tap["ma"], kb.get(tap["ma"]))
        e = _trang_thai_editing(tap)
        p = _trang_thai_publish(tap, gc)
        ra.append({
            "ma": tap["ma"],
            "ten": (tap.get("full") or (tap["duyet"] or [{}])[0]).get("ten", ""),
            "tram": {"writing": {"ma": w[0], "chu": w[1], "thanh": w[2]},
                     "editing": {"ma": e[0], "chu": e[1], "thanh": e[2]},
                     "publish": {"ma": p[0], "chu": p[1], "thanh": p[2]}},
            "viec_ke": _viec_ke(w, e, p),
        })
    return ra
