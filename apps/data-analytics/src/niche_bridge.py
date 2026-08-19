# -*- coding: utf-8 -*-
"""Cầu nối ĐỌC snapshot báo cáo ngách từ app niche-research (bậc 1: đọc đĩa).

Module Data Analytics gộp (dashboard Niche) cần số của báo cáo ngách. Nguyên tắc
V3 "không import chéo app" giữ nguyên: đây KHÔNG import code niche-research —
chỉ đọc bộ artifact JSON đã được `scripts/snapshot.py` (bên niche-research) đóng
băng theo ngày. Đường dữ liệu qua env `NICHE_PROJECTS_DIR` (test trỏ tmp).
`ponytail:` bậc 2 nâng thành HTTP khi niche-research chạy như service trong hub.

Van chống bịa: mọi hàm trả None/[] + lý do khi thiếu dữ liệu — dashboard hiện "—"
kèm lý do, TUYỆT ĐỐI không số 0 giả (luật KPI 31/07 hệ cũ).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

_APP_DIR = Path(__file__).resolve().parents[1]
_ROOT = _APP_DIR.parents[1]


def _projects_dir() -> Path:
    # Nhà V3 của dữ liệu ngách = data/niche-research/projects (cùng chỗ service :9113
    # đọc — dời 18/08); env cho test/cách ly.
    return Path(os.environ.get("NICHE_PROJECTS_DIR")
                or _ROOT / "data" / "niche-research" / "projects")


def ds_snapshot(project: str) -> list[dict]:
    """Sổ snapshot của một dự án ngách (cũ → mới). Không có → []."""
    p = _projects_dir() / project / "snapshots" / "index.json"
    if not p.is_file():
        return []
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def chon_snapshot(project: str, snap_id: str = "latest") -> dict | None:
    """Bản ghi index của snapshot theo id, hoặc bản mới nhất."""
    index = ds_snapshot(project)
    if not index:
        return None
    if snap_id == "latest":
        return index[-1]
    return next((b for b in index if b.get("id") == snap_id), None)


def doc_artifact(project: str, snap_id: str, ten: str) -> dict | None:
    """Một artifact JSON trong snapshot. Thiếu/hỏng → None (không ném)."""
    ban_ghi = chon_snapshot(project, snap_id)
    if ban_ghi is None:
        return None
    p = _projects_dir() / project / "snapshots" / ban_ghi["id"] / ten
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def duong_bao_cao(project: str, snap_id: str, ten_file: str) -> Path | None:
    """Đường tới file báo cáo (HTML/xlsx) trong snapshot — cho nút Download.
    Chỉ trả file có khai trong index (chống lấy file ngoài sổ)."""
    ban_ghi = chon_snapshot(project, snap_id)
    if ban_ghi is None or ten_file not in ban_ghi.get("bao_cao", []):
        return None
    p = _projects_dir() / project / "snapshots" / ban_ghi["id"] / ten_file
    return p if p.is_file() else None


# ---------- trích tầng NGHĨA từ báo cáo gộp (user chốt 18/08: tab phải DIỄN GIẢI
# LẠI kiểu dashboard, không nhúng nguyên báo cáo) ----------

import re as _re


def _bo_the(t: str) -> str:
    return _re.sub(r"\s+", " ", _re.sub(r"<[^>]+>", " ", t)).strip()


def trich_nghia(project: str, snap_id: str = "latest") -> dict:
    """Cắt 2 khối NGHĨA từ báo cáo gộp HTML (file do chính pipeline/phiên này build,
    cấu trúc ổn định id p0..p8): Audience Profile Canvas (bảng 3 nhóm) + các Phương
    án Positioning. Parser KHOAN DUNG: khối nào không cắt được thì bỏ khối đó (UI
    fallback), tuyệt đối không bịa. Có bao_cao_writer sinh NGHĨA vào JSON thì hàm
    này nghỉ hưu — đọc JSON thay."""
    ban_ghi = chon_snapshot(project, snap_id)
    if ban_ghi is None:
        return {}
    html = next((f for f in ban_ghi.get("bao_cao", []) if f.endswith(".html")), None)
    if not html:
        return {}
    p = _projects_dir() / project / "snapshots" / ban_ghi["id"] / html
    try:
        s = p.read_text(encoding="utf-8")
    except OSError:
        return {}
    out: dict = {}

    # 1) Audience Profile Canvas — bảng đầu tiên sau tiêu đề, CHỈ trong đoạn tới
    # nhãn layer kế (báo cáo tự build 19/08 để canvas là slot chờ writer — không
    # bound là vớ nhầm bảng của mục sau thành "canvas")
    i = s.find("Audience Profile Canvas")
    if i != -1:
        # bound đa mốc (19/08: builder dùng nháy ĐƠN class='layer' — bound một mốc
        # nháy kép trượt, extractor vớ nhầm bảng P2 thành "canvas")
        cac_moc = [s.find(m, i + 1)
                   for m in ('class="layer', "class='layer", "</section>")]
        cac_moc = [x for x in cac_moc if x != -1]
        doan = s[i:min(cac_moc)] if cac_moc else s[i:i + 20000]
        m = _re.search(r"<table>(.*?)</table>", doan, _re.S)
        if m:
            hang = [[_bo_the(c) for c in _re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", h, _re.S)]
                    for h in _re.findall(r"<tr>(.*?)</tr>", m.group(1), _re.S)]
            if len(hang) >= 2 and len(hang[0]) >= 2:
                out["canvas"] = {"cot": hang[0][1:],
                                 "hang": [{"ten": h[0], "o": h[1:]}
                                          for h in hang[1:] if len(h) >= 2]}

    # 2) Phương án Positioning — các card <h4> trong mục id="p3"
    i3, i4 = s.find('id="p3"'), s.find('id="p4"')
    if i3 != -1:
        p3 = s[i3:i4] if i4 > i3 else s[i3:]
        pa = []
        for c in _re.split(r'<div class="card">', p3)[1:]:
            cac_cut = [x for x in (c.find('<div class="layer'),
                                   c.find("<div class='layer")) if x != -1]
            if cac_cut:
                c = c[:min(cac_cut)]
            mh = _re.search(r"<h4[^>]*>(.*?)</h4>", c, _re.S)
            if not mh:
                continue
            ten = _bo_the(mh.group(1))
            if not (ten.startswith("Phương án") or ten.startswith("Anti-positioning")):
                continue
            than = c[mh.end():]
            muc = [_bo_the(x) for x in _re.findall(r"<li[^>]*>(.*?)</li>", than, _re.S)]
            noi_dung = [x for x in muc if x] or ([_bo_the(than)[:700]] if _bo_the(than) else [])
            if noi_dung:
                pa.append({"ten": ten, "noi_dung": noi_dung})
        if pa:
            out["phuong_an"] = pa
    return out


# ---------- tóm tắt cho dashboard (chỉ NHẶT số đã tính sẵn, không tính lại) ----------

def tom_tat_overall(project: str, snap_id: str = "latest") -> dict:
    """Bộ số cho dashboard Overall của MỘT thị trường (một dự án ngách).

    Trả {"co_bao_cao": False, "ly_do": ...} khi chưa có snapshot — dashboard
    hiện trạng thái thay vì số giả. Mọi ô thiếu nguồn = None + lý do riêng.
    """
    ban_ghi = chon_snapshot(project, snap_id)
    if ban_ghi is None:
        return {"co_bao_cao": False, "ly_do": "Chưa có báo cáo — chạy phân tích để tạo bản đầu tiên."}

    d1 = doc_artifact(project, ban_ghi["id"], "decision1.json") or {}
    demand = doc_artifact(project, ban_ghi["id"], "demand.json") or {}
    crack = doc_artifact(project, ban_ghi["id"], "crackability.json") or {}
    money = doc_artifact(project, ban_ghi["id"], "monetization.json") or {}
    d2 = doc_artifact(project, ban_ghi["id"], "decision2.json") or {}
    analysis = doc_artifact(project, ban_ghi["id"], "analysis.json") or {}
    gaps = doc_artifact(project, ban_ghi["id"], "gaps.json") or {}
    channels = doc_artifact(project, ban_ghi["id"], "channels.json")
    bets_raw = (doc_artifact(project, ban_ghi["id"], "bets.json") or {}).get("bets") or []

    def _mau(ds, n, truong):
        """Top-n một bảng analysis, chỉ giữ trường cần render (kèm 1 ví dụ thật)."""
        out = []
        for m in (ds or [])[:n]:
            muc = {t: m.get(t) for t in truong}
            vi_du = (m.get("examples") or [None])[0]
            if vi_du:
                muc["vi_du"] = vi_du
            out.append(muc)
        return out

    # từ/cụm/tag lift cao gộp một bảng — có kiểm định (sig) xếp trước, lift giảm dần
    lift_gop = []
    for loai, khoa in (("tag", "lift_tags"), ("cụm", "lift_bigrams"), ("từ", "lift_unigrams")):
        for m in (analysis.get(khoa) or []):
            lift_gop.append({"key": m.get("key"), "lift": m.get("lift"),
                             "sig": bool(m.get("sig")), "channels": m.get("channels"),
                             "loai": loai})
    lift_gop.sort(key=lambda m: (not m["sig"], -(m["lift"] or 0)))

    ranked = d2.get("ranked") or []
    rpm = money.get("rpm_band_usd")
    med, p90 = demand.get("demand_median_views"), demand.get("reach_p90_views")
    diem_cum = [r.get("beachhead_score") for r in ranked
                if isinstance(r.get("beachhead_score"), (int, float))]
    return {
        "co_bao_cao": True,
        "snapshot": ban_ghi["id"],
        "ds_snapshot": [b["id"] for b in ds_snapshot(project)],
        "bao_cao_files": ban_ghi.get("bao_cao", []),
        # 6 tile — None = nguồn thiếu, template hiện "—" + lý do
        "diem_hap_dan": d1.get("attractiveness"),
        "phan_quyet": d1.get("decision"),
        "ly_do_gate": d1.get("gate_reason"),
        "tru_diem": d1.get("pillars") or {},
        "view_trung_vi": demand.get("demand_median_views"),
        "moc_trung": demand.get("reach_p90_views"),
        "cung_thang": demand.get("supply_per_month"),
        "trend": demand.get("trend"),
        "trend_strength": demand.get("trend_strength"),
        "cua_vao_rate": crack.get("newcomer_rate"),
        "cua_vao_verdict": crack.get("verdict"),
        "rpm_band": f"${rpm[0]}–{rpm[1]}" if isinstance(rpm, list) and len(rpm) == 2 else None,
        # chú giải tile + banner — số DẪN XUẤT từ artifact (PY tính, template chỉ in)
        "moc_trung_x": round(p90 / med) if med and p90 else None,
        "cua_vao_thang": crack.get("young_months"),
        "rpm_nhan": money.get("category"),
        "so_cum": len(ranked) or None,
        "diem_cum_tb": round(sum(diem_cum) / len(diem_cum)) if diem_cum else None,
        # TỔNG QUAN SỐ CỦA PIPELINE (kéo từ báo cáo gộp ra overview — user chốt 18/08):
        # mỗi ô thiếu nguồn = None, template in "—" (van chống bịa, không 0 giả)
        "pipeline": {
            "kenh_resolve": len(channels) if isinstance(channels, dict) and channels else None,
            "video_quet": analysis.get("total_videos"),
            "video_truong_thanh": demand.get("n_matured"),
            "outlier": analysis.get("n_winners"),
            "tin_hieu_som": analysis.get("n_early_confirmed"),
            "comment": gaps.get("total_comments"),
            "cau_hoi": gaps.get("total_questions"),
            "hhi": d1.get("competition_hhi"),
            "cung_thang": demand.get("supply_per_month"),
        },
        # tab Bằng chứng (user chốt 18/08 — 3 nội dung show bằng tab): câu hỏi khán
        # giả like cao nhất + theme comment nổi bật, nguyên văn từ gaps.json
        "cau_hoi_top": [
            {"q": q.get("q"), "like": q.get("like"), "video": q.get("video")}
            for q in (gaps.get("top_questions") or [])[:8]
        ],
        "theme_top": [
            {"theme": t.get("theme"), "count": t.get("count"), "pct": t.get("pct")}
            for t in (gaps.get("themes") or [])[:6]
        ],
        # tab WINNING FORMAT — khuôn thắng từ analysis.json (câu mở đầu / khuôn
        # title / từ CAPS / lift), tab POSITIONING — beachhead chọn + bets có
        # falsifier. Tất cả nhặt nguyên từ artifact, chỉ cắt top-n.
        "wf": {
            "openers": _mau(analysis.get("openers"), 8, ("key", "freq", "channels")),
            "templates": _mau(analysis.get("templates"), 6, ("key", "freq", "channels")),
            "emphasis": _mau(analysis.get("emphasis"), 10, ("key", "freq")),
            "lift": lift_gop[:12],
        },
        "pos_chon": d2.get("decision"),
        "pos_ly_do": d2.get("reason"),
        "bets": [
            {"term": b.get("term"), "kind": b.get("kind"),
             "verdict": b.get("builder_verdict"), "lift": b.get("lift"),
             "kenh": b.get("n_channels"), "outlier": b.get("n_outliers"),
             "excess": b.get("sum_excess"), "tap_trung": b.get("concentration"),
             "tuoi_ngay": b.get("median_age_days")}
            for b in bets_raw[:8]
        ],
        # beachhead: top 2 accent + toàn bộ toạ độ cho scatter (PY đã tính sẵn)
        "beachhead": [
            {"anchor": r.get("anchor"), "diem": r.get("beachhead_score"),
             "canh_tranh": r.get("competition"), "size": r.get("size"),
             "kenh": r.get("n_channels")}
            for r in ranked
        ],
        # Best & Worst cụm: top 3 / bottom 3 theo thứ hạng sẵn có
        "cum_tot": ranked[:3],
        "cum_xau": ranked[-3:] if len(ranked) > 3 else [],
    }
