# -*- coding: utf-8 -*-
"""QUOTA LOG chuẩn P4 (JSON-lines) — MỘT nguồn cho trang API Keys: tab Quota log
(K8) + cột "lượt gọi hôm nay" (K1-K4). Mỗi lượt gọi API ngoài MỘT dòng:

  {luc, api, khoa_duoi, app, viec, luot, quota_tieu}

Đường: data/logs/quota/<năm>/<tháng>/<YYYY-MM-DD>.log (đúng khuôn nhat_ky.py,
Luật 5 năm/tháng — tra bằng grep/Explorer đều được). Các app NỐI DẦN vào helper
này; chưa app nào ghi → trang hiện "No usage logged yet", KHÔNG bịa số.

ponytail: append 1 dòng nhỏ = nguyên tử mức OS (cùng trần với nhat_ky — hệ 1
worker/app nên không xen dòng; nâng cấp: khóa file khi đa worker).
"""
from __future__ import annotations

import json
import os
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _duong_logs() -> Path:
    return Path(os.environ.get("LOGS_DIR", ROOT / "data" / "logs")) / "quota"


def ghi(api: str, khoa_duoi: str, app: str, viec: str,
        luot: int = 1, quota_tieu: int = 0) -> None:
    """Ghi một lượt gọi. TUYỆT ĐỐI không đưa giá trị khóa vào đây — chỉ đuôi 4."""
    gio = datetime.now()
    duong = _duong_logs() / f"{gio:%Y}" / f"{gio:%m}"
    duong.mkdir(parents=True, exist_ok=True)
    dong = json.dumps({"luc": gio.isoformat(timespec="seconds"), "api": api,
                       "khoa_duoi": khoa_duoi, "app": app, "viec": viec,
                       "luot": int(luot), "quota_tieu": int(quota_tieu)},
                      ensure_ascii=False)
    with open(duong / f"{gio:%Y-%m-%d}.log", "a", encoding="utf-8") as f:
        f.write(dong + "\n")


def doc(ngay: str = "", api: str = "", khoa_duoi: str = "",
        app: str = "") -> list[dict]:
    """Đọc log MỘT ngày (mặc định hôm nay) + lọc api/khóa/app; mới nhất trước.
    Dòng hỏng bị bỏ qua (log là append thô — không để một dòng lỗi vỡ trang)."""
    ngay = (ngay or "").strip() or date.today().isoformat()
    duong = _duong_logs() / ngay[:4] / ngay[5:7] / f"{ngay}.log"
    if not duong.is_file():
        return []
    ra = []
    for dong in duong.read_text(encoding="utf-8").splitlines():
        try:
            d = json.loads(dong)
        except ValueError:
            continue
        if api and d.get("api") != api:
            continue
        if khoa_duoi and d.get("khoa_duoi") != khoa_duoi:
            continue
        if app and d.get("app") != app:
            continue
        ra.append(d)
    return ra[::-1]


def luot_hom_nay() -> dict[str, int]:
    """Tổng LƯỢT hôm nay theo đuôi khóa — cột 'lượt gọi hôm nay' tab Add API."""
    tong: dict[str, int] = {}
    for d in doc():
        duoi = d.get("khoa_duoi") or ""
        tong[duoi] = tong.get(duoi, 0) + int(d.get("luot") or 0)
    return tong
