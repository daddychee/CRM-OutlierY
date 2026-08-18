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
