# -*- coding: utf-8 -*-
"""SỔ GỌI API (01/09/2026) — usage THẬT cho Command Center.

Mọi call ra dịch vụ ngoài ghi MỘT DÒNG JSON-lines:
  {luc, app, dich_vu, duoi, viec, model, units, ms, ok, ma_loi}
- dich_vu: "youtube" / "llm" / tên khác — mở, không enum cứng.
- duoi: 4 ký tự cuối của key (app không cần biết id két; Command Center join
  với két theo đuôi — két đã lưu đuôi 4).
- Đường ghi: app repo cha gọi thẳng ghi(); app tự đủ (radary/seo/content…)
  POST /api/so-goi loopback (khuôn heartbeat — không session, bọc try phía
  app: sổ chết không được làm hỏng việc thật).

File data/logs/so-goi/YYYY/MM/YYYY-MM-DD.log (khuôn nhat_ky, append 1 dòng
nguyên tử mức OS). Sống/chết của key = CALL THẬT gần nhất — không probe đốt
quota, không bịa số.
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _goc() -> Path:
    return Path(os.environ.get("SO_GOI_DIR", ROOT / "data" / "logs" / "so-goi"))


def ghi(app: str, dich_vu: str, duoi: str = "", viec: str = "", model: str = "",
        units: float = 0, ms: float | None = None, ok: bool = True,
        ma_loi: str = "") -> None:
    gio = datetime.now()
    duong = _goc() / f"{gio:%Y}" / f"{gio:%m}"
    duong.mkdir(parents=True, exist_ok=True)
    dong = json.dumps({"luc": gio.isoformat(timespec="seconds"), "app": app,
                       "dich_vu": dich_vu, "duoi": duoi, "viec": viec,
                       "model": model, "units": units,
                       "ms": round(ms) if ms is not None else None,
                       "ok": ok, "ma_loi": ma_loi}, ensure_ascii=False)
    with open(duong / f"{gio:%Y-%m-%d}.log", "a", encoding="utf-8") as f:
        f.write(dong + "\n")


def tom_tat_hom_nay() -> dict:
    """Tổng hợp file HÔM NAY: per dịch vụ {calls, loi, tong_units,
    theo_duoi{duoi: {units, calls, loi, ok_cuoi, ma_loi, luc_cuoi}},
    theo_viec{app · viec: {calls, loi, ms_max}}}. Dòng hỏng bỏ qua."""
    gio = datetime.now()
    f = _goc() / f"{gio:%Y}" / f"{gio:%m}" / f"{gio:%Y-%m-%d}.log"
    ket: dict = {}
    if not f.exists():
        return ket
    try:
        dong_tho = f.read_text(encoding="utf-8").splitlines()
    except OSError:
        return ket
    for ln in dong_tho:
        try:
            d = json.loads(ln)
        except ValueError:
            continue
        dv = ket.setdefault(d.get("dich_vu", "?"), {
            "calls": 0, "loi": 0, "tong_units": 0,
            "theo_duoi": {}, "theo_viec": {}})
        dv["calls"] += 1
        if not d.get("ok", True):
            dv["loi"] += 1
        dv["tong_units"] += d.get("units", 0) or 0
        duoi = d.get("duoi") or ""
        if duoi:
            k = dv["theo_duoi"].setdefault(duoi, {
                "units": 0, "calls": 0, "loi": 0, "ok_cuoi": True,
                "ma_loi": "", "luc_cuoi": ""})
            k["units"] += d.get("units", 0) or 0
            k["calls"] += 1
            if not d.get("ok", True):
                k["loi"] += 1
            k["ok_cuoi"] = bool(d.get("ok", True))
            k["ma_loi"] = d.get("ma_loi", "") if not d.get("ok", True) else ""
            k["luc_cuoi"] = (d.get("luc") or "")[11:16]
        if d.get("app"):
            khoa_v = f"{d['app']} · {d.get('viec') or d.get('model') or d.get('dich_vu')}"
            v = dv["theo_viec"].setdefault(khoa_v, {"calls": 0, "loi": 0, "ms_max": 0})
            v["calls"] += 1
            if not d.get("ok", True):
                v["loi"] += 1
            if d.get("ms"):
                v["ms_max"] = max(v["ms_max"], d["ms"])
    return ket
