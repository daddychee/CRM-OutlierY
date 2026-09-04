# -*- coding: utf-8 -*-
"""Luồng 2 — hậu kiểm sau khi đăng: số liệu YouTube + đường cong + chỗ tụt.

Khác luồng 1 ở mục tiêu: video đã đăng rồi, không sửa được nữa, nên đầu ra là
QUYẾT ĐỊNH CHO TẬP SAU chứ không phải trạng thái duyệt. Không có nút Approve.

Bản full và bản 10 phút là HAI VIDEO KHÁC NHAU, khác thời lượng — mốc giây không
tương ứng nên tuyệt đối không gióng note của luồng 1 sang đây. Nối bằng MÃ TẬP.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from src import do_thi, kho_video, mach_dung


def luu_giu_chan(ma_tap: str, video_ma: str, hook_30: float, avd_giay: float,
                 giu_tb: float, cong: list[float], nguon_anh: str,
                 lech_neo: float | None, nguoi: str) -> None:
    conn = kho_video.ket_noi()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO giu_chan (ma_tap, video_ma, hook_30, avd_giay,"
            " giu_tb, duong_cong, nguon_anh, lech_neo, nguoi_nhap, tao_luc)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (ma_tap.upper(), video_ma, hook_30, avd_giay, giu_tb,
             do_thi.dong_goi(cong), nguon_anh, lech_neo, nguoi,
             datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
    finally:
        conn.close()


def lay_giu_chan(ma_tap: str) -> dict | None:
    conn = kho_video.ket_noi()
    try:
        h = conn.execute("SELECT * FROM giu_chan WHERE ma_tap=?",
                         (ma_tap.upper(),)).fetchone()
        if h is None:
            return None
        d = dict(h)
        d["cong"] = do_thi.mo_goi(d["duong_cong"])
        return d
    finally:
        conn.close()


def _mmss(g: float) -> str:
    return f"{int(g) // 60:02d}:{int(g) % 60:02d}"


def _loi_cho_tut(t: dict, thu_tu: int, tong_mat: float, thoi_luong: float,
                 avd: float) -> dict:
    """Số → lời. Mỗi chỗ tụt nói rõ NẶNG ĐẾN ĐÂU và Ý NGHĨA, không đọc số khô."""
    mat, con = t["mat_diem"], t["con_lai"]
    tu, den = t["tu_giay"], t["den_giay"]
    mong = con < 5.0
    if mong:
        loi = (f"Có tụt {mat:.0f} điểm, nhưng tới đây chỉ còn {con:.1f}% khán giả — "
               f"quá ít để kết luận chắc chắn.")
        muc, phan = "nhe", "Chưa đủ cơ sở"
    elif thu_tu == 0 and tong_mat and mat >= tong_mat * 0.5:
        loi = (f"Chỗ tụt sâu nhất cả video: mất {mat:.0f} điểm trong "
               f"{int(den - tu)} giây, chiếm quá nửa tổng số khán giả rời đi. "
               f"Sửa được chỗ này là đổi được kết quả của cả tập.")
        muc, phan = "nang", "Làm lại"
    elif tu < 60:
        loi = (f"Mất {mat:.0f} điểm ngay trong phút đầu — người xem chưa kịp vào "
               f"nội dung đã bỏ đi. Đây là chỗ đắt nhất của video.")
        muc, phan = "nang", "Làm lại"
    elif avd and tu > avd:
        loi = (f"Mất {mat:.0f} điểm, nhưng chỗ này nằm sau mốc {_mmss(avd)} là lúc "
               f"khán giả trung bình đã rời — sửa ở đây ít đổi được kết quả.")
        muc, phan = "nhe", "Bỏ qua"
    else:
        loi = (f"Mất {mat:.0f} điểm trong {int(den - tu)} giây. Người xem đã ở lại "
               f"tới {_mmss(tu)} rồi mới rời — họ chán chứ không phải không quan "
               f"tâm chủ đề.")
        muc, phan = "vua", "Cắt ngắn"
    return {"ts": tu, "ts_het": den, "muc": muc, "phan": phan,
            "benh": f"Tụt {mat:.0f} điểm quanh {_mmss(tu)}", "loi": loi,
            "so_lieu": f"Mất {mat:.0f} điểm · còn {con:.1f}% khán giả · "
                       f"{_mmss(tu)}–{_mmss(den)}"}


def trich_kich_ban(video: dict, tu: float, den: float) -> str:
    """Lời thoại trong quãng đó, đọc từ phụ đề .srt cạnh video trên NAS.
    Không có phụ đề → chuỗi rỗng, giao diện bỏ khối trích thay vì bịa."""
    p, _ = kho_video.phu_de_tim(video)
    if p is None:
        return ""
    try:
        chu = kho_video.doc_phu_de_bytes(p.read_bytes())
    except OSError:
        return ""
    ra, lay = [], False
    for khoi in chu.split("\n\n"):
        dong = [d for d in khoi.splitlines() if d.strip()]
        if len(dong) < 2:
            continue
        moc = next((d for d in dong if "-->" in d), "")
        if not moc:
            continue
        try:
            bat = _giay(moc.split("-->")[0])
        except (ValueError, IndexError):
            continue
        lay = tu - 2 <= bat <= den + 2
        if lay:
            ra.append(" ".join(d for d in dong if "-->" not in d and not d.strip().isdigit()))
        if bat > den + 2:
            break
    loi = " ".join(ra).strip()
    return loi[:400] + ("…" if len(loi) > 400 else "")


def _giay(moc: str) -> float:
    moc = moc.strip().replace(",", ".")
    p = moc.split(":")
    return int(p[0]) * 3600 + int(p[1]) * 60 + float(p[2])


def chan_doan_tap(ma_tap: str) -> dict:
    """Gộp mọi nguồn thành chẩn đoán cho một tập đã đăng.

    Bốn nguồn, tất cả kiểm chứng được: đường cong giữ chân (chỗ tụt) · mạch dựng
    đo bằng ffmpeg tại chính chỗ đó · lời thoại từ phụ đề · số liệu neo.
    """
    gc = lay_giu_chan(ma_tap)
    tap = kho_video.mot_tap(ma_tap)
    if gc is None or tap is None or tap.get("full") is None:
        return {"co": False}
    full = tap["full"]
    thoi_luong = _thoi_luong_full(full)
    if thoi_luong <= 0:
        return {"co": False}
    cac_tut = do_thi.tim_cho_tut(gc["cong"], thoi_luong)
    tong_mat = sum(t["mat_diem"] for t in cac_tut) or 1.0
    avd = gc["avd_giay"] or 0
    ra = []
    for i, t in enumerate(cac_tut):
        c = _loi_cho_tut(t, i, tong_mat, thoi_luong, avd)
        c["trich_kb"] = trich_kich_ban(full, t["tu_giay"], t["den_giay"])
        ra.append(c)
    return {"co": True, "ma_tap": ma_tap.upper(), "video": full, "giu_chan": gc,
            "thoi_luong": thoi_luong, "cac_tut": ra,
            "ket_luan": _ket_luan(gc, thoi_luong, ra)}


def _thoi_luong_full(full: dict) -> float:
    from src import nhan_xet
    so = nhan_xet.so_do_cua(full)
    if so.get("thoi_luong"):
        return float(so["thoi_luong"])
    p = kho_video.duong_video(full)
    return kho_video._thoi_luong(p) if p and p.is_file() else 0.0


def _ket_luan(gc: dict, thoi_luong: float, cac_tut: list[dict]) -> dict:
    """Đầu ra của luồng 2: độ dài mục tiêu + việc cho tập sau. Không có nút duyệt."""
    avd = gc["avd_giay"] or 0
    viec = []
    if avd and thoi_luong and avd < thoi_luong * 0.5:
        muc = max(10, round(avd / 60 * 2.5))
        viec.append(f"Độ dài mục tiêu tập sau khoảng {muc}–{muc + 2} phút — khán giả "
                    f"trung bình chỉ xem tới {_mmss(avd)} trong khi tập này dài "
                    f"{_mmss(thoi_luong)}.")
    nang = [t for t in cac_tut if t["muc"] == "nang"]
    if nang:
        viec.append(f"Sửa {nang[0]['benh'].lower()} — đây là chỗ mất khán giả nhiều nhất.")
    hook = gc["hook_30"]
    if hook is not None and hook < 55:
        viec.append(f"Hook đang giữ {hook:.0f}% ở giây 30, dưới mức 55% của thể loại — "
                    f"mở đầu cần vào thẳng và cắt vụn hơn.")
    return {"viec": viec,
            "tom": "mất người ngay mở đầu" if (hook is not None and hook < 55)
                   else ("thừa thời lượng" if avd and thoi_luong and avd < thoi_luong * 0.35
                         else "cần xem lại từng đoạn")}
