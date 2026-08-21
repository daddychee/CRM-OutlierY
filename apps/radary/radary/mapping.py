# -*- coding: utf-8 -*-
"""MAPPING — ghep CAU (discovery) voi CUNG (kho video RadarY) thanh ban do 4 o.

Ly do ton tai (do that 21/08/2026 tren radary.db): CUNG THAP co HAI NGHIA TRAI NGUOC
  - `tuvalu`          14 video · view trung vi   781  -> it nguoi lam VI it nguoi xem
  - `why do people…`   4 video ·  2 kenh          -> CHUA AI LAM
Nhin rieng ve cung thi hai ca nay giong het nhau. Chi khi ghep voi cau moi phan biet
duoc — do la toan bo gia tri cua module nay.

VAN CHONG BIA:
  - KHONG diem tong. Hai truc de rieng, moi truc ghi ro do bang gi.
  - KHONG nguong cung ("cau >= 7.0 la tot"). Chia o bang TRUNG VI CUA CHINH PHIEN QUET
    — cao/thap la so voi cac cum cung dot, khong phai voi mot con so tu tren troi.
  - Mau nho thi KHONG chia o (duoi TOI_THIEU_CUM) — cung luat voi engine chan doan
    "khong du mau thi noi thang, khong ket luan".

Python do — 0 LLM, 0 quota: toan bo ve cung doc tu SQLite san co (31.917 title, 0,21s).
"""
from __future__ import annotations

import re
import statistics
import time

TOI_THIEU_CUM = 5        # duoi nguong nay khong chia o (mau qua nho de lay trung vi)

O_KHOANG_TRONG = "khoang_trong"    # cau cao · cung thap
O_DO_LUA = "do_lua"                # cau cao · cung cao
O_BAO_HOA = "bao_hoa"              # cau thap · cung cao
O_HOANG = "hoang"                  # cau thap · cung thap

NHAN_O = {
    O_KHOANG_TRONG: ("Khoảng trống", "Có người tìm mà gần như chưa ai làm — ưu tiên soi kỹ"),
    O_DO_LUA: ("Đỏ lửa", "Nhiều người tìm và nhiều người làm — phải hơn hẳn mới thắng"),
    O_BAO_HOA: ("Bão hoà", "Đông người làm mà ít người tìm — thường không đáng vào"),
    O_HOANG: ("Hoang", "Ít cả hai — thường có lý do, kiểm trước khi tin là cơ hội"),
}


def _rx(cum: str) -> re.Pattern:
    """Khop theo RANH GIOI TU, khong phai LIKE %x%.

    Bai hoc SEO 18/08 (khop ten ngach): 'Life' nuot 'Life In'. O day neu dung LIKE thi
    'life in' khop ca 'life incremental roblox' — sai han ban chat.
    """
    return re.compile(r"(?<!\w)" + re.escape(cum.strip().lower()).replace(r"\ ", r"\s+") + r"(?!\w)")


def tai_kho(conn, ws: int) -> list[dict]:
    """Doc MOT LAN toan bo video cua workspace (title + view moi nhat + velocity).

    Doc mot lan roi khop trong bo nho: 55 cum x 31.917 video ma ban 55 query LIKE thi
    ton ~11s; tai mot lan roi quet chuoi thi duoi 1s.
    """
    rows = conn.execute("""
        SELECT v.id, v.title, v.channel_title, v.channel_yt_id, v.yt_id,
               v.pub_ts, v.last_vph,
               (SELECT MAX(t.views) FROM ticks t WHERE t.video_id = v.id) AS views
        FROM videos v WHERE v.workspace_id = ? AND v.dead = 0
    """, (ws,)).fetchall()
    return [{"id": r["id"], "title": r["title"] or "", "title_l": (r["title"] or "").lower(),
             "kenh": r["channel_title"] or "", "kenh_yt": r["channel_yt_id"] or "",
             "yt_id": r["yt_id"], "pub_ts": r["pub_ts"] or 0,
             "vph": r["last_vph"] or 0, "views": r["views"] or 0}
            for r in rows]


def do_cung(kho: list[dict], cum: str, tran_vi_du: int = 8) -> dict:
    """Ve CUNG cua mot cum: bao nhieu video, ai lam, view bao nhieu, moi nhat bao gio."""
    rx = _rx(cum)
    khop = [v for v in kho if rx.search(v["title_l"])]
    if not khop:
        return {"so_video": 0, "so_kenh": 0, "view_trung_vi": 0, "vph_trung_vi": 0.0,
                "moi_nhat": 0, "vi_du": []}
    views = sorted(v["views"] for v in khop)
    vph = sorted(v["vph"] for v in khop)
    vi_du = sorted(khop, key=lambda v: -v["views"])[:tran_vi_du]
    return {
        "so_video": len(khop),
        "so_kenh": len({v["kenh_yt"] or v["kenh"] for v in khop}),
        "view_trung_vi": views[len(views) // 2],
        "vph_trung_vi": round(vph[len(vph) // 2], 2),
        "moi_nhat": max(v["pub_ts"] for v in khop),
        "vi_du": [{"title": v["title"], "kenh": v["kenh"], "views": v["views"],
                   "pub_ts": v["pub_ts"], "yt_id": v["yt_id"]} for v in vi_du],
    }


def _o(cau_cao: bool, cung_cao: bool) -> str:
    if cau_cao:
        return O_DO_LUA if cung_cao else O_KHOANG_TRONG
    return O_BAO_HOA if cung_cao else O_HOANG


def ban_do(kho: list[dict], cums: list[dict]) -> dict:
    """Ghep cau x cung -> ban do. `cums` la dau ra cua discovery.quet().

    Nguong = TRUNG VI CUA CHINH PHIEN QUET (khong phai hang so). Duoi TOI_THIEU_CUM
    thi tra `du_mau=False` va KHONG xep o — noi thang thay vi doan.
    """
    muc = []
    for c in cums:
        cung = do_cung(kho, c["cum"])
        muc.append({**c, **cung})

    du_mau = len(muc) >= TOI_THIEU_CUM
    nguong_cau = nguong_cung = None
    if du_mau:
        nguong_cau = statistics.median([m["do_phu"] for m in muc])
        nguong_cung = statistics.median([m["so_video"] for m in muc])
        for m in muc:
            # KHÔNG có video nào thì KHÔNG BAO GIỜ là "cung cao" — kể cả khi trung vị
            # của phiên bằng 0 (ca rất hay gặp: quét một seed mới, phần lớn cụm chưa ai
            # làm). Thiếu vế này thì cụm 0 video bị xếp 'đỏ lửa' — ngược hẳn sự thật.
            cung_cao = m["so_video"] > 0 and m["so_video"] >= nguong_cung
            m["o"] = _o(m["do_phu"] >= nguong_cau, cung_cao)
    else:
        for m in muc:
            m["o"] = None

    muc.sort(key=lambda m: (-m["do_phu"], m["so_video"]))
    dem = {k: sum(1 for m in muc if m["o"] == k) for k in NHAN_O} if du_mau else {}
    return {
        "muc": muc,
        "du_mau": du_mau,
        "ly_do_thieu_mau": (None if du_mau else
                            f"Chỉ có {len(muc)} cụm — cần ít nhất {TOI_THIEU_CUM} "
                            "để lấy trung vị làm mốc cao/thấp. Quét thêm seed rồi xem lại."),
        "nguong": {"cau_do_phu": nguong_cau, "cung_so_video": nguong_cung},
        "dem_o": dem,
        "so_video_trong_kho": len(kho),
        "quet_luc": time.time(),
    }
