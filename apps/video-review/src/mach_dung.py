# -*- coding: utf-8 -*-
"""Đo mạch dựng từ file video và dịch số đo thành CÂU BỆNH.

Cách đo port từ RenderY (autoedit/autoedit/nhip/do.py): hai thước ffmpeg chạy
song song rồi kiểm hội tụ. Ngưỡng lấy từ hồ sơ niche đo thật của RenderY, để
NGOÀI CODE tại rules/ho_so_nhip.csv — thêm niche là thêm dòng, không sửa code.

Số đo là CẬN DƯỚI: hiệu chuẩn của RenderY trên video 24 mối cắt, cả hai thước
chỉ thấy 12 (sót mối nối giữa hai clip cùng tông màu). Nên chỉ so tương đối với
hồ sơ, không tuyên bố con số tuyệt đối.

Không chấm điểm, không đạt/không-đạt: trả về danh sách phát hiện có mức độ,
cổng cuối là mắt người duyệt.
"""
from __future__ import annotations

import csv
import os
import re
import statistics
import subprocess
from pathlib import Path

_APP_DIR = Path(__file__).resolve().parents[1]

NGUONG_SELECT = 0.30
NGUONG_SCDET = 10
HOOK_GIAY = 30.0
MEGA_SHOT_GIAY = 30.0
NGUONG_HOI_TU = 0.25
CUA_SO_CONG = 60.0
BUOC_CONG = 15.0


def duong_ho_so() -> Path:
    return Path(os.environ.get("VR_HO_SO_NHIP", str(_APP_DIR / "rules" / "ho_so_nhip.csv")))


def doc_ho_so(niche: str = "") -> dict:
    """Hồ sơ nhịp của niche; không có dòng riêng thì lùi về _mac_dinh."""
    f = duong_ho_so()
    if not f.is_file():
        return {}
    theo = {}
    with open(f, newline="", encoding="utf-8-sig") as r:
        for d in csv.DictReader(r):
            theo[d["niche"].strip().lower()] = d
    d = theo.get((niche or "").strip().lower()) or theo.get("_mac_dinh")
    if not d:
        return {}
    ra = {"niche": d["niche"]}
    for k in ("than_p50", "cat_phut", "hook_p50", "hook_chop", "hold", "std_san"):
        try:
            ra[k] = float(d[k])
        except (KeyError, ValueError):
            ra[k] = 0.0
    return ra


def _ffmpeg() -> str | None:
    from src import kho_video
    return kho_video.ffmpeg_exe()


def _cat_bang_select(p: Path) -> list[float]:
    exe = _ffmpeg()
    if exe is None:
        return []
    try:
        ra = subprocess.run(
            [exe, "-i", str(p), "-filter:v", f"select='gt(scene,{NGUONG_SELECT})',showinfo",
             "-f", "null", "-"], capture_output=True, text=True, timeout=900)
    except (OSError, subprocess.SubprocessError):
        return []
    return [float(m) for m in re.findall(r"pts_time:([0-9.]+)", ra.stderr or "")]


def _cat_bang_scdet(p: Path) -> list[float]:
    exe = _ffmpeg()
    if exe is None:
        return []
    try:
        ra = subprocess.run(
            [exe, "-i", str(p), "-filter:v", f"scdet=threshold={NGUONG_SCDET}",
             "-f", "null", "-"], capture_output=True, text=True, timeout=900)
    except (OSError, subprocess.SubprocessError):
        return []
    return [float(m) for m in re.findall(r"lavfi\.scd\.time:\s*([0-9.]+)", ra.stderr or "")]


def _do_dai(cac_moc: list[float], tong: float) -> list[float]:
    moc = sorted(set([0.0] + [m for m in cac_moc if 0 < m < tong] + [tong]))
    return [b - a for a, b in zip(moc, moc[1:]) if b > a]


def do_video(p: Path, thoi_luong: float = 0.0) -> dict:
    """Đo thô: trả số shot, trung vị, cắt/phút, tỉ lệ chớp/hold, đường cong nhịp.
    Hai thước lệch quá NGUONG_HOI_TU → cờ tin_cay=False, không nên kết luận."""
    from src import kho_video
    if thoi_luong <= 0:
        thoi_luong = kho_video._thoi_luong(p)
    if thoi_luong <= 0:
        return {}
    a, b = _cat_bang_select(p), _cat_bang_scdet(p)
    if not a and not b:
        return {}
    da, db = _do_dai(a, thoi_luong), _do_dai(b, thoi_luong)
    tin_cay = True
    if da and db:
        ma, mb = statistics.median(da), statistics.median(db)
        if max(ma, mb) > 0:
            tin_cay = abs(ma - mb) / max(ma, mb) <= NGUONG_HOI_TU
    moc = sorted(set(a) | set(b)) if not a or not b else sorted(set(a))
    dai = _do_dai(moc, thoi_luong)
    thuong = [d for d in dai if d <= MEGA_SHOT_GIAY]
    if not thuong:
        return {}
    hook = [d for m, d in zip([0.0] + moc, dai) if m < HOOK_GIAY and d <= MEGA_SHOT_GIAY]
    phut = thoi_luong / 60.0
    return {
        "thoi_luong": thoi_luong,
        "so_shot": len(thuong),
        "shot_p50": statistics.median(thuong),
        "shot_std": statistics.pstdev(thuong) if len(thuong) > 1 else 0.0,
        "cat_phut": len(thuong) / phut if phut else 0.0,
        "chop": sum(1 for d in thuong if d <= 2.0) / len(thuong),
        "hold": sum(1 for d in thuong if d >= 5.0) / len(thuong),
        "shot_dai_nhat": max(thuong),
        "hook_p50": statistics.median(hook) if hook else 0.0,
        "hook_chop": (sum(1 for d in hook if d <= 2.0) / len(hook)) if hook else 0.0,
        "hook_so_cat": len(hook),
        "tin_cay": tin_cay,
        "moc_cat": moc,
        "duong_cong": _duong_cong(moc, thoi_luong),
    }


def _duong_cong(moc: list[float], tong: float) -> list[tuple[float, float]]:
    """Cắt/phút theo cửa sổ trượt 60 giây, bước 15 giây — thấy chỗ nhịp tụt."""
    ra = []
    t = 0.0
    while t < max(tong - CUA_SO_CONG, 0) + BUOC_CONG:
        het = min(t + CUA_SO_CONG, tong)
        if het - t < 5:
            break
        n = sum(1 for m in moc if t <= m < het)
        ra.append((t, n / ((het - t) / 60.0)))
        t += BUOC_CONG
    return ra


def _mmss(g: float) -> str:
    return f"{int(g) // 60:02d}:{int(g) % 60:02d}"


def chan_doan(so: dict, ho_so: dict) -> list[dict]:
    """Số đo → CÂU BỆNH. Mỗi phát hiện: mốc, tên bệnh, lời giải thích, số liệu
    làm bằng chứng, việc nên làm. Không điểm số, không đạt/không-đạt."""
    if not so or not ho_so:
        return []
    ra = []

    if not so.get("tin_cay", True):
        ra.append({
            "ts": 0.0, "muc": "nhe", "benh": "Số đo không đáng tin",
            "loi": "Hai cách đếm cắt cho kết quả lệch nhau quá nhiều — video này đánh lừa "
                   "được thước đo (hay gặp khi nhiều cảnh cùng tông màu). Các nhận xét bên "
                   "dưới chỉ nên xem là gợi ý.",
            "so_lieu": "hai thước lệch quá 25%", "nen_lam": ""})

    hp50, hchop = so.get("hook_p50", 0), so.get("hook_chop", 0)
    c_hp50, c_hchop = ho_so.get("hook_p50", 0), ho_so.get("hook_chop", 0)
    if hp50 and c_hp50 and hp50 > c_hp50 * 1.5:
        lan = hp50 / c_hp50
        ra.append({
            "ts": 0.0, "ts_het": HOOK_GIAY, "muc": "nang",
            "benh": "Mở đầu chậm — hook chưa nổ",
            "loi": f"Ba mươi giây đầu đang chậm gấp {lan:.1f} lần cách kênh thường mở. Mỗi hình "
                   f"giữ trung bình {hp50:.1f} giây trong khi các tập giữ chân tốt chỉ giữ khoảng "
                   f"{c_hp50:.1f} giây — người xem chưa kịp thấy gì hấp dẫn thì đã trôi mất 30 giây.",
            "so_lieu": f"Hình giữ TB {hp50:.1f}s · chuẩn {c_hp50:.1f}s · "
                       f"hình chớp dưới 2s {hchop*100:.0f}% · chuẩn {c_hchop*100:.0f}%",
            "nen_lam": f"Cắt vụn 30 giây đầu — mỗi hình khoảng {c_hp50:.1f} giây, "
                       f"ít nhất {c_hchop*10:.0f}/10 hình dưới 2 giây."})
    elif hchop and c_hchop and hchop < c_hchop * 0.6:
        ra.append({
            "ts": 0.0, "ts_het": HOOK_GIAY, "muc": "nang",
            "benh": "Mở đầu thiếu hình chớp",
            "loi": f"Chỉ {hchop*100:.0f}% hình trong 30 giây đầu ngắn dưới 2 giây, trong khi các "
                   f"tập giữ chân tốt là {c_hchop*100:.0f}%. Nhịp mở không đủ dồn dập để giữ người xem.",
            "so_lieu": f"Hình chớp {hchop*100:.0f}% · chuẩn {c_hchop*100:.0f}%",
            "nen_lam": "Chèn thêm hình ngắn vào 30 giây đầu."})

    dai = so.get("shot_dai_nhat", 0)
    p50 = so.get("shot_p50", 0)
    # RenderY loại shot > 30s khỏi thống kê (mega-segment). Ở đây bắt sớm hơn:
    # gấp đôi hình trung bình VÀ dài hơn 6 giây thì đã là cảnh giữ bất thường.
    if dai and p50 and dai > max(p50 * 2.0, 6.0):
        ra.append({
            "ts": None, "muc": "nang", "benh": "Một cảnh bị giữ quá lâu",
            "loi": f"Có cảnh giữ liền {dai:.1f} giây không cắt — dài gấp {dai/p50:.1f} lần một "
                   f"hình bình thường của bản dựng này.",
            "so_lieu": f"Cảnh dài nhất {dai:.1f}s · hình giữ TB {p50:.1f}s",
            "nen_lam": "Cắt cảnh đó ngắn lại, hoặc chèn hình khác vào giữa."})

    cp, c_cp = so.get("cat_phut", 0), ho_so.get("cat_phut", 0)
    if cp and c_cp:
        if cp < c_cp / 2:
            ra.append({
                "ts": None, "muc": "nang", "benh": "Cả bản dựng cắt quá thưa",
                "loi": f"Trung bình {cp:.1f} cắt mỗi phút, chưa bằng nửa mức kênh vẫn làm "
                       f"({c_cp:.1f}). Mạch chậm đều từ đầu tới cuối chứ không riêng đoạn nào.",
                "so_lieu": f"{cp:.1f} cắt/phút · khung chấp nhận {c_cp/2:.1f}–{c_cp*2:.1f}",
                "nen_lam": "Tăng mật độ cắt toàn bản."})
        elif cp > c_cp * 2:
            ra.append({
                "ts": None, "muc": "vua", "benh": "Cắt quá dày",
                "loi": f"Trung bình {cp:.1f} cắt mỗi phút, hơn gấp đôi mức kênh vẫn làm "
                       f"({c_cp:.1f}). Xem lâu dễ mệt mắt.",
                "so_lieu": f"{cp:.1f} cắt/phút · khung chấp nhận {c_cp/2:.1f}–{c_cp*2:.1f}",
                "nen_lam": "Giãn bớt nhịp cắt ở phần thân."})

    std, san = so.get("shot_std", 0), ho_so.get("std_san", 0)
    if std and san and std < san:
        ra.append({
            "ts": None, "muc": "nhe", "benh": "Nhịp đều đều — thiếu tương phản",
            "loi": "Các hình dài gần bằng nhau nên mạch không có lúc dồn dập lúc thong thả. "
                   "Không phải lỗi, nhưng xem lâu dễ chán.",
            "so_lieu": f"Độ chênh lệch độ dài hình {std:.1f}s · sàn cảnh báo {san:.1f}s",
            "nen_lam": "Gom vài đoạn cắt nhanh liên tiếp rồi để một hình thở dài, thay vì rải đều."})

    for t, v in _tut_nhip(so, ho_so):
        ra.append({
            "ts": t, "muc": "nhe", "benh": "Nhịp tụt hẳn ở một quãng",
            "loi": f"Quãng quanh {_mmss(t)} nhịp chậm còn {v:.1f} cắt mỗi phút, dưới nửa mức "
                   f"kênh vẫn làm.",
            "so_lieu": f"{v:.1f} cắt/phút tại {_mmss(t)} · chuẩn {ho_so.get('cat_phut', 0):.1f}",
            "nen_lam": "Xem lại đoạn này, cân nhắc cắt bớt hoặc thêm hình."})
    return ra


def _tut_nhip(so: dict, ho_so: dict) -> list[tuple[float, float]]:
    """Các quãng trên đường cong nhịp tụt dưới nửa chuẩn; gộp quãng liền nhau."""
    cong, chuan = so.get("duong_cong", []), ho_so.get("cat_phut", 0)
    if not cong or not chuan:
        return []
    thap = [(t, v) for t, v in cong if v < chuan / 2]
    ra, truoc = [], -999.0
    for t, v in thap:
        if t - truoc > CUA_SO_CONG:
            ra.append((t, v))
        truoc = t
    return ra[:3]


def dat_dat(so: dict, ho_so: dict) -> str:
    """Câu tóm tắt một dòng cho đầu panel."""
    cd = chan_doan(so, ho_so)
    nang = [c for c in cd if c["muc"] == "nang"]
    if nang:
        return nang[0]["benh"].lower()
    return "đạt chuẩn" if cd else "chưa đo được"
