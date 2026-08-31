# -*- coding: utf-8 -*-
"""GĐ2 ThumbY — đọc RadarY CHỈ-ĐỌC, cô lập MỘT module (docs/thumby.md mục 6).

Mọi truy cập dữ liệu RadarY nằm hết ở đây: RadarY đổi schema thì chỉ sửa file
này. SQLite mở `mode=ro` (luật sổ địa bạ — không bao giờ ghi vào DB app khác);
thumbs đọc file trực tiếp, không đụng cache của RadarY.

"Đang nổ cùng chủ đề": video sống 2-60 ngày tuổi (khớp định nghĩa mạch Đang
nóng 22/08), khớp CHỦ ĐỀ với title người dùng nhập (n-gram sau khi bỏ stopword
EN), xếp theo `last_vph` — cột views/giờ RadarY đã tính sẵn (không đụng bảng
ticks 1,2 triệu dòng ngoài 1 truy vấn điểm cho top video).
"""
from __future__ import annotations

import os
import re
import sqlite3
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]              # D:\AI AGENT OUTLIERY

# Van chống bịa: dưới ngưỡng này coi như "chưa tìm thấy" — không độn video lạc.
TOI_THIEU_KHOP = 3
# Sàn tuổi = 0: video đăng HÔM NAY đang nổ chính là thứ cần thấy nhất — đo thật
# 31/08 sàn 2 ngày (mượn từ mạch dviews RadarY) loại oan các video vph 16-19k
# vừa đăng; last_vph RadarY tính sẵn nên không cần chờ khung dviews chốt.
TUOI_MIN_NGAY = 0
TUOI_MAX_NGAY = 60

# Stopword EN tối thiểu — chỉ để cụm chủ đề không bị "the/of/in" làm nhiễu.
_STOP = frozenset(
    "the a an of in on at for to and or is are was were be been i you he she "
    "it we they my your his her its our this that these those with from by as "
    "vs what why how when where who which not no do does did done have has had "
    "will would can could s t re ve ll d m".split())


def _duong_db() -> str:
    return os.environ.get("RADARY_DB", str(_ROOT / "data" / "radary" / "radary.db"))


def _duong_thumbs() -> Path:
    return Path(os.environ.get("RADARY_THUMBS", str(_ROOT / "data" / "radary" / "thumbs")))


def _ket_noi() -> sqlite3.Connection:
    """mode=ro qua URI — sai đường/thiếu file là nổ ngay ở đây, KHÔNG tự tạo DB
    rỗng (bẫy sqlite mặc định); timeout ngắn vì RadarY đang chạy song song."""
    return sqlite3.connect(f"file:{_duong_db()}?mode=ro", uri=True, timeout=5)


def _tach_tu(chu: str) -> list[str]:
    """Bỏ stopword + gộp số nhiều đơn giản (storms→storm): chỉ cắt 's' đuôi khi
    từ ≥5 ký tự — 'news' (4) giữ nguyên, không thành 'new'."""
    ra = []
    for t in re.split(r"[^a-z0-9]+", (chu or "").casefold()):
        if not t or t in _STOP:
            continue
        if len(t) >= 5 and t.endswith("s") and not t.endswith("ss"):
            t = t[:-1]
        ra.append(t)
    return ra


def _ngram(tu: list[str]) -> tuple[set, set, set]:
    """(unigram, bigram, trigram) trên chuỗi từ ĐÃ bỏ stopword — cụm liền kề
    sau lọc, cùng cách làm với mapping RadarY."""
    u = set(tu)
    b = {" ".join(tu[i:i + 2]) for i in range(len(tu) - 1)}
    g = {" ".join(tu[i:i + 3]) for i in range(len(tu) - 2)}
    return u, b, g


def diem_khop(title_nhap: str, title_video: str) -> int:
    """Điểm cùng-chủ-đề: trigram trùng ×3, bigram ×2, từ đơn ×1.
    NHẬN khi có ≥1 cụm 2-3 từ trùng HOẶC ≥2 từ đơn trùng — 1 từ đơn lẻ
    ('storm') chưa đủ nói hai video cùng chủ đề."""
    u1, b1, g1 = _ngram(_tach_tu(title_nhap))
    u2, b2, g2 = _ngram(_tach_tu(title_video))
    cum = len(g1 & g2) * 3 + len(b1 & b2) * 2
    don = len(u1 & u2)
    if cum == 0 and don < 2:
        return 0
    return cum + don


def danh_sach_pool() -> list[dict]:
    """Pool cho dropdown (Owner chốt: BẮT chọn pool trước khi tìm)."""
    with _ket_noi() as c:
        rows = c.execute(
            "SELECT w.id, w.name, COUNT(v.id) AS so_video FROM workspaces w "
            "LEFT JOIN videos v ON v.workspace_id = w.id AND v.dead = 0 "
            "GROUP BY w.id ORDER BY w.name COLLATE NOCASE").fetchall()
    return [{"id": r[0], "ten": r[1], "so_video": r[2]} for r in rows if r[2] > 0]


def video_cung_chu_de(title_nhap: str, ws_id: int, gioi_han: int = 8) -> dict:
    """Top video ĐANG NỔ cùng chủ đề trong MỘT pool.

    Trả {"du": bool, "videos": [...], "ly_do": str}. du=False khi khớp <
    TOI_THIEU_KHOP — người gọi phải nói thẳng, không độn (van chống bịa)."""
    bay_gio = time.time()
    tu, den = bay_gio - TUOI_MAX_NGAY * 86400, bay_gio - TUOI_MIN_NGAY * 86400
    with _ket_noi() as c:
        ung = c.execute(
            "SELECT id, yt_id, title, channel_title, pub_ts, duration_s, "
            "       last_vph, thumb_ck, workspace_id FROM videos "
            "WHERE workspace_id = ? AND dead = 0 AND last_vph IS NOT NULL "
            "  AND pub_ts BETWEEN ? AND ?", (ws_id, tu, den)).fetchall()
        khop = []
        for r in ung:
            d = diem_khop(title_nhap, r[2])
            if d > 0:
                khop.append((d, r))
        # cùng chủ đề rồi thì "đang nổ" quyết thứ hạng: last_vph trước, điểm sau
        khop.sort(key=lambda x: (-(x[1][6] or 0), -x[0]))
        chon = khop[:gioi_han]
        videos = []
        for d, r in chon:
            vid, yt_id, title, kenh, pub_ts, dur, vph, ck, ws = r
            row = c.execute("SELECT views FROM ticks WHERE video_id = ? "
                            "ORDER BY ts DESC LIMIT 1", (vid,)).fetchone()
            thumb = ""
            if ck:
                f = _duong_thumbs() / str(ws) / f"{yt_id}_{str(ck)[:10]}.jpg"
                if f.is_file():                     # chỉ trả URL khi FILE TỒN TẠI
                    thumb = f"/thumby-thumb/{ws}/{f.name}"
            videos.append({
                "yt_id": yt_id, "title": title, "kenh": kenh or "",
                "ngay_tuoi": max(1, int((bay_gio - (pub_ts or bay_gio)) / 86400)),
                "duration_s": int(dur or 0), "vph": round(vph or 0),
                "views": int(row[0]) if row else None, "thumb": thumb,
                "diem": d,
            })
    if len(videos) < TOI_THIEU_KHOP:
        return {"du": False, "videos": videos,
                "ly_do": f"Chỉ khớp {len(videos)} video cùng chủ đề trong pool "
                         f"(cần ≥{TOI_THIEU_KHOP}) — giữ card mẫu, không độn video lạc chủ đề."}
    return {"du": True, "videos": videos, "ly_do": ""}
