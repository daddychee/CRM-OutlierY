"""Kế hoạch thời lượng + lịch trả lời hứa của outline (V3, 2026-08-16). 0 LLM.

Nguyên tắc (giữ khuôn "Python đo — LLM sắp" của suggest.py): mọi con số về độ dài,
số chương, mốc phút, vị trí trả hứa đều do Python tính tất định — LLM chỉ gắn VAI
(tra_hua/payoff/linh_hoat) cho chương, Python kiểm và xếp vị trí.

- Số chương là ĐẦU RA của tổng ký tự: vùng ngọt chất lượng 2.500-4.000 ký tự/chương
  (đo 2026-07-08, DEVLOG — ép ngắn thì LLM nén phẳng, quá dài thì độn chữ).
- Phút chỉ là cách HIỂN THỊ ký tự cho người vận hành: CHARS_PER_MIN đo từ video đã
  đăng thật (23.888 ký tự / 29,1 phút ≈ 850 — kênh Outland 08/2026).
- Mốc AVD nhập tay ở màn tạo run (run_meta.json) — chương TRẢ HỨA phải kết thúc
  trước mốc đó: người xem trung vị phải rời đi với cảm giác "title không lừa"
  (bài học video RETIRING 27/07: title hứa một đằng, 0 chương trả → APV 18%).
"""
from __future__ import annotations

# GƯƠNG của board.html (HOOK_FIXED/endChars) — đổi bên nào phải đổi bên kia.
# suggest.py import lại từ đây (một nguồn phía Python, board.html là gương phía JS).
HOOK_CHARS = 375
CHARS_PER_MIN = 850
VUNG_NGOT_MID = 3250          # tâm vùng ngọt 2.500-4.000 ký tự/chương


def end_chars(total: int) -> int:
    return max(500, min(1200, round(0.07 * total)))


def so_chuong(total_chars: int) -> int:
    """Số chương đề xuất từ tổng ký tự (người chỉnh được trên board)."""
    total = max(4000, int(total_chars or 0))
    than = total - HOOK_CHARS - end_chars(total)
    return max(3, min(12, round(than / VUNG_NGOT_MID)))


def lich_phut(total_chars: int, n_chuong: int) -> list[dict]:
    """Mốc phút [{nhan, tu, den}] cho HOOK + N chương + END — chia đều như Writer
    (allocate_section_chars). Chỉ để hiển thị/kiểm vị trí, sai số ±1 chương là chấp
    nhận được (biến thiên ký-tự-mỗi-ý); đừng dùng nó đo tới từng giây."""
    total = max(4000, int(total_chars or 0))
    n = max(1, int(n_chuong))
    per = (total - HOOK_CHARS - end_chars(total)) / n
    out, t = [{"nhan": "HOOK", "tu": 0.0, "den": HOOK_CHARS / CHARS_PER_MIN}], HOOK_CHARS / CHARS_PER_MIN
    for i in range(n):
        out.append({"nhan": f"C{i + 1}", "tu": t, "den": t + per / CHARS_PER_MIN})
        t += per / CHARS_PER_MIN
    out.append({"nhan": "END", "tu": t, "den": t + end_chars(total) / CHARS_PER_MIN})
    return out


def _idx_vai(chapters: list[str], vai: dict, can_tim: str) -> int | None:
    for i, name in enumerate(chapters):
        if vai.get(name) == can_tim:
            return i
    return None


def sap_theo_vai(chapters: list[str], vai: dict, total_chars: int) -> list[str]:
    """Xếp lại thứ tự chương theo vai — tất định, giữ nguyên thứ tự tương đối còn lại:
    TRẢ HỨA lên chương 1 (trước mốc AVD); PAYOFF về chương có TÂM gần 65% thời lượng
    nhất (payoff sau điểm ai-cũng-đã-rời là hứa suông — xem kiem_lich)."""
    ch = list(chapters)
    i = _idx_vai(ch, vai, "tra_hua")
    if i is not None and i != 0:
        ch.insert(0, ch.pop(i))
    j = _idx_vai(ch, vai, "payoff")
    if j is not None:
        lich = lich_phut(total_chars, len(ch))
        tong = lich[-1]["den"]
        tam = lambda k: (lich[k + 1]["tu"] + lich[k + 1]["den"]) / 2 / tong  # noqa: E731
        muc_tieu = min(range(len(ch)), key=lambda k: abs(tam(k) - 0.65))
        if j != muc_tieu and muc_tieu != 0:
            ch.insert(muc_tieu, ch.pop(j))
    return ch


def kiem_lich(chapters: list[str], vai: dict, total_chars: int,
              avd_phut: float | None) -> list[str]:
    """Kiểm lịch trả hứa → danh sách cảnh báo (CHỈ BÁO, không chặn — luật A3).
    Không AVD / không vai → không kiểm (picks cũ chạy y như trước)."""
    canh_bao: list[str] = []
    if not chapters or not vai:
        return canh_bao
    lich = lich_phut(total_chars, len(chapters))
    tong = lich[-1]["den"]
    i = _idx_vai(chapters, vai, "tra_hua")
    if avd_phut and i is not None:
        het = lich[i + 1]["den"]
        if het > float(avd_phut) + 0.05:
            canh_bao.append(
                f"Chương TRẢ HỨA (C{i + 1}) kết thúc ở phút {het:.1f} — SAU mốc AVD "
                f"{avd_phut:.1f}′: người xem trung vị rời đi trước khi title được trả.")
    elif not avd_phut and _idx_vai(chapters, vai, "tra_hua") is not None:
        canh_bao.append("Chưa nhập AVD kênh (màn tạo run) — không kiểm được vị trí trả hứa.")
    j = _idx_vai(chapters, vai, "payoff")
    if j is not None:
        tam = (lich[j + 1]["tu"] + lich[j + 1]["den"]) / 2 / tong
        if not 0.5 <= tam <= 0.8:
            canh_bao.append(
                f"Chương PAYOFF (C{j + 1}) có tâm ở {tam * 100:.0f}% thời lượng — nên nằm "
                "vùng 60-70% (ending chỉ callback; để payoff ở đuôi là hứa suông với "
                "phần lớn khán giả).")
    return canh_bao
