# -*- coding: utf-8 -*-
"""Log chuẩn chung cả hệ (mảnh ⑤): JSON-lines, một khuôn cho mọi app.

Đường: data/logs/<app>/<năm>/<tháng>/<YYYY-MM-DD>.log — đúng Luật 5 (năm/tháng),
tra bằng Explorer hoặc grep đều được, mọi app một định dạng: luc, app, user,
hanh_dong, chi_tiet.

ponytail: append 1 dòng nhỏ coi như nguyên tử ở mức OS — không khóa file;
trần: 2 tiến trình ghi CÙNG file cùng lúc có thể xen dòng (hệ 1 worker/app nên
thực tế không xảy ra). Nâng cấp: khóa file hoặc queue khi đa worker.
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _duong_logs() -> Path:
    return Path(os.environ.get("LOGS_DIR", ROOT / "data" / "logs"))


def ghi(app: str, user: str, hanh_dong: str, chi_tiet: str = "") -> None:
    gio = datetime.now()
    duong = (_duong_logs() / app / f"{gio:%Y}" / f"{gio:%m}")
    duong.mkdir(parents=True, exist_ok=True)
    dong = json.dumps({"luc": gio.isoformat(timespec="seconds"), "app": app,
                       "user": user, "hanh_dong": hanh_dong,
                       "chi_tiet": chi_tiet}, ensure_ascii=False)
    with open(duong / f"{gio:%Y-%m-%d}.log", "a", encoding="utf-8") as f:
        f.write(dong + "\n")
