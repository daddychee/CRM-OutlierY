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
