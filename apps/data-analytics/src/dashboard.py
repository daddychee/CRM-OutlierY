# -*- coding: utf-8 -*-
"""Dashboard Niche (module Data Analytics gộp) — trang /niche.

Bản chốt UI 18/08 (artifact 02a5a49f): rail trái = chọn Niche → Overall / từng kênh
+ New report; pane phải = dashboard tile kiểu Shopify. Button/menu tiếng ANH, nội
dung tiếng VIỆT, icon line-SVG (quy ước user 18/08).

Nguồn dữ liệu:
- Danh bạ nền (nen.common.danh_ba): danh sách ngách / kênh / thị trường — KHÔNG tự
  đẻ registry (tầng này phiên khác đã xây xong 17/08).
- niche_bridge: số báo cáo ngách theo snapshot (van chống bịa trên từng tile).
- Ánh xạ ngách×thị-trường → project niche-research: data/niche_projects.json
  (env NICHE_PROJECTS_MAP; `ponytail:` chuyển vào lien_ket_app danh bạ khi nền
  có đa khóa theo thị trường — hiện lien_ket_app chỉ 1 khóa/app/thực-thể).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse

from src import niche_bridge

_APP_DIR = Path(__file__).resolve().parents[1]
_ROOT = _APP_DIR.parents[1]

router = APIRouter()


# Claims như main.lay_user — chép tại chỗ để router không import ngược main
# (`ponytail:` gộp về src/claims.py chung khi có mảnh thứ ba cần).
def _lay_user(x_remote_user: str = Header(""), x_remote_level: str = Header("0"),
              x_remote_role: str = Header("")) -> dict:
    if not x_remote_user:
        raise HTTPException(401, "Thiếu danh tính — vào qua cổng OUTLIERY.")
    try:
        level = int(x_remote_level or 0)
    except ValueError:
        level = 0
    return {"ten": x_remote_user, "level": level, "vai": x_remote_role}


def _ds_ngach() -> list[dict]:
    """Ngách từ danh bạ nền; danh bạ chưa có/lỗi → [] (trang hiện hướng dẫn)."""
    try:
        from nen.common import danh_ba
        return danh_ba.liet_ke("ngach")
    except Exception:
        return []


def _ds_kenh(ngach_ma: str) -> list[dict]:
    try:
        from nen.common import danh_ba
        return [k for k in danh_ba.liet_ke("kenh")
                if k.get("ngach_ma") == ngach_ma and k.get("trang_thai") != "khai_tu"]
    except Exception:
        return []


def _ten_thi_truong() -> dict[str, str]:
    try:
        from nen.common import danh_ba
        return {t["ma"]: t.get("ten", t["ma"]) for t in danh_ba.liet_ke("thi_truong")}
    except Exception:
        return {}


def _map_projects() -> dict:
    """{ngach_ma: {thi_truong_ma: project_niche_research}} — sổ ánh xạ ngoài code."""
    p = Path(os.environ.get("NICHE_PROJECTS_MAP")
             or _ROOT / "data" / "data-analytics" / "niche_projects.json")
    if not p.is_file():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


@router.get("/niche", response_class=HTMLResponse)
def trang_niche(request: Request, user: dict = Depends(_lay_user),
                ngach: str = "", ngay: str = "latest"):
    from src.main import templates   # main đã khởi tạo Jinja (import lúc gọi, tránh vòng)
    ds_ngach = _ds_ngach()
    ngach_hien = next((n for n in ds_ngach if n["ma"] == ngach), ds_ngach[0] if ds_ngach else None)

    ten_tt = _ten_thi_truong()
    thi_truong = []
    ds_ngay: list[str] = []
    if ngach_hien:
        mapping = _map_projects().get(ngach_hien["ma"], {})
        for tt_ma, project in mapping.items():
            tom_tat = niche_bridge.tom_tat_overall(project, ngay)
            thi_truong.append({"ma": tt_ma, "ten": ten_tt.get(tt_ma, tt_ma),
                               "project": project, "so": tom_tat})
            for d in (tom_tat.get("ds_snapshot") or []):
                if d not in ds_ngay:
                    ds_ngay.append(d)
    ds_ngay.sort()

    return templates.TemplateResponse(request, "dashboard.html", {
        "user": user, "ds_ngach": ds_ngach, "ngach": ngach_hien,
        "thi_truong": thi_truong, "ds_kenh": _ds_kenh(ngach_hien["ma"]) if ngach_hien else [],
        "ds_ngay": ds_ngay, "ngay_chon": ngay,
    })


# ---------- chạy pipeline ngách (tính năng 2: báo cáo mới tự cập nhật dashboard) ----------

def _project_hop_le(project: str) -> bool:
    return project in {p for tt in _map_projects().values() for p in tt.values()}


@router.post("/niche/chay/{project}")
def chay_niche(project: str, user: dict = Depends(_lay_user)):
    from src import niche_run
    if user["level"] < 3:
        raise HTTPException(403, "Chỉ Leader trở lên được chạy phân tích ngách.")
    if not _project_hop_le(project):
        raise HTTPException(404)
    try:
        return niche_run.chay_lai(project, user)
    except Exception as e:
        raise HTTPException(502, f"Niche service không phản hồi: {e}")


@router.get("/niche/chay/{project}/trang-thai")
def chay_trang_thai(project: str, user: dict = Depends(_lay_user)):
    from src import niche_run
    if not _project_hop_le(project):
        raise HTTPException(404)
    try:
        return niche_run.trang_thai(project, user)
    except Exception as e:
        raise HTTPException(502, f"Niche service không phản hồi: {e}")


# ---------- pane KÊNH ----------

def _kenh_theo_ma(kenh_ma: str) -> dict | None:
    try:
        from nen.common import danh_ba
        return next((k for k in danh_ba.liet_ke("kenh") if k["ma"] == kenh_ma), None)
    except Exception:
        return None


def _bao_cao_cua_kenh(kenh: dict) -> list[dict]:
    """Report của kênh: so `ten_kenh` bản ghi với tên chuẩn + bí danh danh bạ
    (chuẩn hóa không dấu — hàm thuần, không cần DB). Mới nhất trước."""
    try:
        from nen.common.danh_ba import chuan_hoa_ten
    except Exception:
        return []
    from src.bao_cao_lich_su import doc_bao_cao_moi_nguoi
    ten_hop_le = {chuan_hoa_ten(kenh.get("ten_chuan", ""))}
    ten_hop_le |= {chuan_hoa_ten(b) for b in (kenh.get("bi_danh") or "").split(";") if b.strip()}
    ds = [r for r in doc_bao_cao_moi_nguoi()
          if chuan_hoa_ten(r.get("ten_kenh", "")) in ten_hop_le]
    ds.sort(key=lambda r: r.get("thoi_gian", ""), reverse=True)
    return ds


def _chi_tiet_tu_goc(rec: dict, moc_song=None) -> dict:
    """Best&Worst video + line chart, dựng lại từ FILE GỐC (rẻ, không LLM — khuôn
    trang lịch sử). Mọi bước hỏng → trả lý do, pane vẫn sống (van chống bịa)."""
    duong = Path(rec.get("duong_dan_goc", ""))
    if not duong.is_file():
        return {"loi": "Không thấy file gốc — chỉ hiện số tóm tắt của bản ghi."}
    try:
        from src.diagnosis_engine import chan_doan_toan_bo, doc_bao_cao, doc_chart_data
        df = doc_bao_cao(duong)
        df_chart = doc_chart_data(duong)
        toan_bo = chan_doan_toan_bo(df, df_chart=df_chart, loai_kenh=rec.get("loai_kenh") or None)
        vids = [v for v in toan_bo.get("videos", []) if v.get("views") is not None]
        vids.sort(key=lambda v: v["views"], reverse=True)
        so_song = sum(1 for v in vids if moc_song and v["views"] >= moc_song) if moc_song else None
        chart = _duong_views(df_chart)
        return {"loi": None, "tong_video": len(toan_bo.get("videos", [])),
                "top": vids[:3], "bot": list(reversed(vids[-3:])) if len(vids) > 3 else [],
                "so_song": so_song, "chart": chart}
    except Exception as e:                                   # file lạ không được giết pane
        return {"loi": f"Không dựng được chi tiết từ file gốc: {e}"}


def _duong_views(df_chart) -> dict | None:
    """Điểm polyline SVG từ Chart data (PY tính sẵn — template chỉ vẽ). Không có
    cột ngày/views nhận diện được → None (không đoán)."""
    if df_chart is None or getattr(df_chart, "empty", True):
        return None
    cot_ngay = cot_views = None
    for c in df_chart.columns:
        t = str(c).lower()
        if cot_ngay is None and ("date" in t or "ngày" in t or "ngay" in t):
            cot_ngay = c
        if cot_views is None and ("views" in t or "lượt xem" in t):
            cot_views = c
    if cot_ngay is None or cot_views is None:
        return None
    import pandas as pd
    s = (df_chart[[cot_ngay, cot_views]].dropna()
         .assign(_v=lambda d: pd.to_numeric(d[cot_views], errors="coerce")).dropna(subset=["_v"]))
    s = s.sort_values(by=cot_ngay).tail(60)
    vals = s["_v"].tolist()
    if len(vals) < 2:
        return None
    W, H, dinh = 270, 120, max(vals) or 1
    n = len(vals)
    pts = " ".join(f"{10 + i * (W - 20) / (n - 1):.1f},{H - 10 - (v / dinh) * (H - 30):.1f}"
                   for i, v in enumerate(vals))
    return {"points": pts, "dinh": int(dinh), "so_ngay": n,
            "tu": str(s[cot_ngay].iloc[0])[:10], "den": str(s[cot_ngay].iloc[-1])[:10]}


@router.get("/niche/kenh/{kenh_ma}", response_class=HTMLResponse)
def trang_kenh(kenh_ma: str, request: Request, user: dict = Depends(_lay_user),
               id: str = "latest"):
    from src.main import templates
    kenh = _kenh_theo_ma(kenh_ma)
    if kenh is None:
        raise HTTPException(404)
    ds_ngach = _ds_ngach()
    ngach = next((n for n in ds_ngach if n["ma"] == kenh.get("ngach_ma")), None)

    ds_bao_cao = _bao_cao_cua_kenh(kenh)
    rec = next((r for r in ds_bao_cao if r.get("id") == id),
               ds_bao_cao[0] if ds_bao_cao else None)

    # benchmark ngách của đúng thị trường kênh này (giá trị của việc gộp)
    benchmark = None
    if ngach:
        project = _map_projects().get(ngach["ma"], {}).get(kenh.get("thi_truong_ma", ""))
        if project:
            so = niche_bridge.tom_tat_overall(project)
            if so.get("co_bao_cao"):
                benchmark = {"song": so.get("view_trung_vi"), "trung": so.get("moc_trung"),
                             "snapshot": so.get("snapshot")}

    chi_tiet = _chi_tiet_tu_goc(rec, (benchmark or {}).get("song")) if rec else None
    return templates.TemplateResponse(request, "dashboard.html", {
        "user": user, "ds_ngach": ds_ngach, "ngach": ngach,
        "thi_truong": [], "ds_kenh": _ds_kenh(kenh["ngach_ma"]) if kenh.get("ngach_ma") else [],
        "ds_ngay": [], "ngay_chon": "latest",
        "kenh_pane": {"kenh": kenh, "ten_tt": _ten_thi_truong().get(kenh.get("thi_truong_ma", ""), ""),
                      "ds_bao_cao": ds_bao_cao, "rec": rec,
                      "benchmark": benchmark, "chi_tiet": chi_tiet},
    })


@router.get("/niche/tai/{project}/{snap_id}/{ten_file}")
def tai_bao_cao(project: str, snap_id: str, ten_file: str, inline: int = 0,
                user: dict = Depends(_lay_user)):
    """Read report (inline=1, mở HTML tại chỗ) / Download (attachment).
    Chỉ file có trong sổ snapshot — ngoài sổ 404 lặng lẽ (khuôn RBAC hệ)."""
    p = niche_bridge.duong_bao_cao(project, snap_id, ten_file)
    if p is None:
        raise HTTPException(404)
    media = "text/html" if p.suffix == ".html" else "application/octet-stream"
    if inline and p.suffix == ".html":
        return FileResponse(p, media_type=media)
    return FileResponse(p, media_type=media, filename=p.name)
