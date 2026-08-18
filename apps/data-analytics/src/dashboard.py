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

from fastapi import APIRouter, Depends, Form, Header, HTTPException, Request
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
        # Danh bạ có thể trả ten=None → fallback mã bỏ tiền tố TT- (hết in "None")
        return {t["ma"]: (t.get("ten") or t["ma"].removeprefix("TT-"))
                for t in danh_ba.liet_ke("thi_truong")}
    except Exception:
        return {}


def _map_projects() -> dict:
    """{ngach_ma: {thi_truong_ma: project_niche_research}} — sổ ánh xạ ngoài code."""
    p = _duong_map()
    if not p.is_file():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


# ---------- toạ độ SVG (PY tính — template chỉ vẽ, đúng nguyên tắc vàng) ----------

import math

_RADAR_TRUC = ["demand", "monetization", "crackability", "competition", "trend"]


def _radar_points(pillars: dict) -> str | None:
    """Polygon 5 trụ trên ngũ giác tâm (60,60) R=48 — thiếu trụ nào coi như 0."""
    if not pillars:
        return None
    pts = []
    for i, ten in enumerate(_RADAR_TRUC):
        v = max(0, min(100, pillars.get(ten) or 0)) / 100
        goc = math.radians(-90 + i * 72)
        pts.append(f"{60 + 48 * v * math.cos(goc):.1f},{60 + 48 * v * math.sin(goc):.1f}")
    return " ".join(pts)


def _scatter_beachhead(beachhead: list[dict]) -> list[dict]:
    """Toạ độ bản đồ cụm (viewBox 270×150): x = cạnh tranh, y = điểm, r ~ √size.
    Accent đúng 2 cụm đầu bảng (ngữ pháp diagram-design: accent 1–2 điểm nhìn trước)."""
    if not beachhead:
        return []
    dinh = max((c.get("diem") or 0) for c in beachhead) or 1
    out = []
    for i, c in enumerate(beachhead):
        comp = max(0.0, min(1.0, c.get("canh_tranh") or 0))
        diem = max(0.0, c.get("diem") or 0)
        out.append({
            "x": round(10 + comp * 240, 1),
            "y": round(130 - (diem / dinh) * 105, 1),
            "r": round(max(3.0, min(9.0, math.sqrt(c.get("size") or 1))), 1),
            "accent": i < 2, "anchor": c.get("anchor"), "diem": c.get("diem"),
        })
    return out


def _fmt_vn(n) -> str:
    return "{:,}".format(round(n)).replace(",", ".")


def _bang_chung(so: dict) -> list[dict]:
    """Bảng SỐ LIỆU — DEMAND EVIDENCE cho tab Bằng chứng (PY dựng chuỗi, template
    chỉ in). Cột 'đọc ra điều gì' CHỈ ghi khi suy được từ enum/tỉ lệ đã tính —
    không suy diễn ngoài số (van chống bịa)."""
    rows: list[dict] = []
    p = so.get("pipeline") or {}
    if so.get("view_trung_vi"):
        ten = "View trung vị video trưởng thành"
        if p.get("video_truong_thanh"):
            ten += f" (n={_fmt_vn(p['video_truong_thanh'])})"
        rows.append({"ten": ten, "so": _fmt_vn(so["view_trung_vi"]),
                     "doc": "Mức nền của ngách — mốc so với video của mình",
                     "nguon": "demand.json"})
    if so.get("moc_trung"):
        x = so.get("moc_trung_x")
        doc = (f"Chênh {x}× trung vị → thị trường ăn theo cú trúng" if x and x >= 5
               else (f"Chênh {x}× trung vị" if x else ""))
        rows.append({"ten": "Top 10% (p90) — mốc video “trúng”",
                     "so": _fmt_vn(so["moc_trung"]), "doc": doc, "nguon": "demand.json"})
    if so.get("cung_thang"):
        rows.append({"ten": "Nguồn cung", "so": f"{round(so['cung_thang'])} video/tháng",
                     "doc": "Mật độ ra bài của ngách", "nguon": "demand.json"})
    if so.get("trend"):
        st = so.get("trend_strength")
        gia_tri = so["trend"] + (f" ({str(round(st, 2)).replace('.', ',')})"
                                 if st is not None else "")
        doc = {"FLAT": "Thị trường trưởng thành — giành phần, không đón sóng",
               "RISING": "Sóng đang lên — cửa sổ vào sớm",
               "DECLINING": "Nhu cầu đang co — thận trọng"}.get(so["trend"], "")
        rows.append({"ten": "Xu hướng 12 tháng (OX slope, khử tuổi video)",
                     "so": gia_tri, "doc": doc, "nguon": "demand.json"})
    if p.get("comment"):
        rows.append({"ten": "Comment đã quét", "so": _fmt_vn(p["comment"]),
                     "doc": "Nguồn gap & demand từ khán giả thật", "nguon": "gaps.json"})
    if p.get("cau_hoi"):
        rows.append({"ten": "Câu hỏi khán giả", "so": _fmt_vn(p["cau_hoi"]),
                     "doc": "Câu hỏi chưa được trả lời = demand còn trống",
                     "nguon": "gaps.json"})
    return rows


@router.get("/niche", response_class=HTMLResponse)
def trang_niche(request: Request, user: dict = Depends(_lay_user),
                ngach: str = "", ngay: str = "latest", tt: str = ""):
    from src.main import templates   # main đã khởi tạo Jinja (import lúc gọi, tránh vòng)
    ds_ngach = _ds_ngach()
    ngach_hien = next((n for n in ds_ngach if n["ma"] == ngach), ds_ngach[0] if ds_ngach else None)

    ten_tt = _ten_thi_truong()
    thi_truong = []
    ds_ngay: list[str] = []
    pills: list[dict] = []      # pill thị trường = MỌI market trong danh bạ
    if ngach_hien:
        mapping = _map_projects().get(ngach_hien["ma"], {})
        # User bắt lỗi 18/08: General có 3 thị trường mà dashboard chỉ hiện 2 —
        # pills phải liệt kê ĐỦ danh bạ; market chưa gán dự án hiện khối hướng dẫn
        # (New report nhánh Niche tự tạo pool + tự gán map), không được giấu.
        thu_tu = sorted(ten_tt, key=lambda m: (m not in mapping, ten_tt[m]))
        pills = [{"ma": m, "ten": ten_tt[m]} for m in thu_tu]
        chon = [tt] if tt in ten_tt else thu_tu   # pill chọn 1; rỗng/lạ = All
        for tt_ma in chon:
            project = mapping.get(tt_ma)
            if project:
                tom_tat = niche_bridge.tom_tat_overall(project, ngay)
                from src import gates as gates_mod
                gates = gates_mod.trang_thai(ngach_hien["ma"], tt_ma,
                                             tom_tat.get("co_bao_cao", False),
                                             user["level"])
            else:
                tom_tat = {"co_bao_cao": False,
                           "ly_do": "Chưa gán dự án nghiên cứu — bấm New report "
                                    "(nhánh Niche), chọn thị trường này và dán pool "
                                    "đối thủ để tạo bản đầu tiên."}
                gates = []
            thi_truong.append({"ma": tt_ma, "ten": ten_tt.get(tt_ma, tt_ma),
                               "project": project, "so": tom_tat,
                               "bang_chung": _bang_chung(tom_tat),
                               "radar": _radar_points(tom_tat.get("tru_diem") or {}),
                               "scatter": _scatter_beachhead(tom_tat.get("beachhead") or []),
                               "gates": gates})
            for d in (tom_tat.get("ds_snapshot") or []):
                if d not in ds_ngay:
                    ds_ngay.append(d)
    ds_ngay.sort()

    return templates.TemplateResponse(request, "dashboard.html", {
        "user": user, "ds_ngach": ds_ngach, "ngach": ngach_hien,
        "thi_truong": thi_truong, "ds_kenh": _ds_kenh(ngach_hien["ma"]) if ngach_hien else [],
        "ds_ngay": ds_ngay, "ngay_chon": ngay,
        "pills": pills, "tt_chon": tt,
        "ds_thi_truong": sorted(_ten_thi_truong().items(), key=lambda x: x[1]),
    })


# ---------- New report nhánh Niche (modal — tạo/chạy project, pool cộng dồn) ----------

def _duong_map() -> Path:
    return Path(os.environ.get("NICHE_PROJECTS_MAP")
                or _ROOT / "data" / "data-analytics" / "niche_projects.json")


def _ghi_map(mapping: dict) -> None:
    p = _duong_map()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(mapping, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(p)


def _sinh_ten_project(ten_ngach: str, ten_tt: str) -> str:
    import re
    dau = "".join(w.capitalize() for w in re.findall(r"[A-Za-z0-9]+", ten_ngach)) or "Niche"
    duoi = re.sub(r"[^A-Za-z0-9]", "", ten_tt).upper()[:8] or "TT"
    return f"{dau}_{duoi}"


@router.post("/niche/tao-report")
def tao_report_niche(user: dict = Depends(_lay_user), ngach_ma: str = Form(...),
                     thi_truong_ma: str = Form(...), pool: str = Form("")):
    from src import niche_run
    if user["level"] < 3:
        raise HTTPException(403, "Chỉ Leader trở lên được tạo report ngách.")
    ngach = next((n for n in _ds_ngach() if n["ma"] == ngach_ma), None)
    ten_tt = _ten_thi_truong().get(thi_truong_ma)
    if ngach is None or ten_tt is None:
        raise HTTPException(404, "Niche/thị trường không có trong danh bạ.")

    mapping = _map_projects()
    project = mapping.get(ngach_ma, {}).get(thi_truong_ma)
    if project is None:
        project = _sinh_ten_project(ngach["ten_chuan"], ten_tt)
        mapping.setdefault(ngach_ma, {})[thi_truong_ma] = project
        _ghi_map(mapping)

    # pool CỘNG DỒN (chốt mockup v7): giữ dòng cũ, thêm dòng mới chưa có
    cu = ""
    comp = niche_bridge._projects_dir() / project / "competitors.txt"
    if comp.is_file():
        cu = comp.read_text(encoding="utf-8", errors="replace")
    dong_cu = {d.strip() for d in cu.splitlines() if d.strip()}
    dong_moi = [d.strip() for d in (pool or "").splitlines()
                if d.strip() and d.strip() not in dong_cu]
    if not dong_cu and not dong_moi:
        raise HTTPException(400, "Dán danh sách kênh đối thủ (mỗi dòng 1 kênh) — pool đang trống.")
    noi_dung = (cu.rstrip("\n") + "\n" if cu.strip() else "") + "\n".join(dong_moi)
    try:
        kq = niche_run.chay_moi(project, noi_dung, user)
    except Exception as e:
        raise HTTPException(502, f"Niche service không phản hồi: {e}")
    return {"project": project, "them_kenh": len(dong_moi), **kq}


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


# ---------- gate ký ----------

@router.post("/niche/gate/{ngach_ma}/{tt_ma}/{gate}")
def ky_gate(ngach_ma: str, tt_ma: str, gate: str, user: dict = Depends(_lay_user),
            phuong_an: str = Form(""), ghi_chu: str = Form("")):
    from src import gates as gates_mod
    try:
        return gates_mod.ky(ngach_ma, tt_ma, gate, user, phuong_an, ghi_chu)
    except KeyError:
        raise HTTPException(404, "Gate không tồn tại.")
    except ValueError as e:
        raise HTTPException(400, str(e))
    except PermissionError as e:
        raise HTTPException(403, str(e))


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
        "ds_thi_truong": sorted(_ten_thi_truong().items(), key=lambda x: x[1]),
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
