# -*- coding: utf-8 -*-
"""Cờ sidebar chuẩn theo UI_FLOW.md mục 2 — cho app KHÔNG phải ai-agent.

Nguồn sự thật: gateway phát claims X-Remote-Apps (danh sách slug user được vào,
kèm cờ phụ 'nas' khi đã cấu hình, 'quan-tri' khi mở được trang quản trị IAM).
App CHỈ đọc, không tự tính quyền. ai-agent có context processor riêng (thêm
danh sách phiên chat) nhưng đọc cùng một header này.
"""
from datetime import datetime
from urllib.parse import unquote

TEN_LEVEL = {1: "Intern", 2: "Staff", 3: "Leader", 4: "Manager", 5: "Owner"}


def ctx_sidebar(request) -> dict:
    ngay = datetime.now().strftime("%d/%m/%Y")
    ten = request.headers.get("x-remote-user", "")
    if not ten:
        return {"sb_user": None, "sb_ngay": ngay, "sb_phien": [], "sb_level_chu": "", "lite": False,
                "sb_apps": [], "sb_da": False, "sb_ns": False, "sb_cho_duyet": 0,
                "sb_nas": False, "sb_hr": False, "sb_fin": False,
                "sb_accounts": False}
    try:
        level = int(request.headers.get("x-remote-level") or 0)
    except ValueError:
        level = 0
    dept = unquote(request.headers.get("x-remote-dept") or "")
    ten_ht = unquote(request.headers.get("x-remote-name") or "")
    apps_vao = [s for s in (request.headers.get("x-remote-apps") or "").split(",") if s]
    return {"sb_user": {"ten": ten, "level": level, "bo_phan": dept,
                        "ten_hien_thi": ten_ht},
            "sb_ngay": ngay,
            "sb_phien": [],   # phiên chat thuộc ai-agent — app khác không truy chéo (Luật 4)
            "sb_level_chu": TEN_LEVEL.get(level, ""), "lite": False,
            "sb_apps": [],    # app phụ chưa di trú: ẨN HẲN (Owner chốt 16/08)
            "sb_da": "data-analytics" in apps_vao,
            "sb_ns": "quan-tri" in apps_vao, "sb_cho_duyet": 0,
            "sb_nas": "nas" in apps_vao,
            # Khu chức năng (DE.md mục 10): gateway phát cờ 'hr'/'finance' —
            # sidebar chỉ hiện mục khi có cờ, app không tự tính quyền.
            "sb_hr": "hr" in apps_vao, "sb_fin": "finance" in apps_vao,
            # Cờ 'accounts' (HR HUB một cửa 16/08): tab Accounts trong /hr —
            # gateway phát theo giỏ quan_tai_khoan, template chỉ tin cờ.
            "sb_accounts": "accounts" in apps_vao}
