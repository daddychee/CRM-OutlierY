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

# App V3 đã có mục sidebar RIÊNG (hoặc app mẫu) — không lặp lại ở nhóm Tools.
# niche-research: GỘP vào Data Analytics 18/08 (chốt Owner) — engine ẩn khỏi Tools,
# trang gộp là /niche của data-analytics; engine vẫn proxy được qua URL trực tiếp.
KHONG_LAP_TOOLS = {"ai-agent", "data-analytics", "to-chuc", "app-mau", "niche-research"}


def sb_apps_tu_claims(apps_vao) -> list[dict]:
    """App ĐÃ DI TRÚ hiện ở nhóm Tools (APPS.md bước 2: thêm app vào apps.json là
    sidebar tự ăn): giao giữa hợp đồng app và danh sách user được vào
    (X-Remote-Apps — gateway quyết). App chưa di trú không có trong hợp đồng nên
    tự ẩn (giữ chốt 16/08). Lỗi đọc hợp đồng → rỗng, không vỡ trang.
    href — ĐỒNG NHẤT URL 18/08 (Owner bắt "cùng nút mà URL khác họ"): mọi nút
    Tools = /<slug>, gateway phục vụ qua _ALIAS (app native) hoặc _ALIAS_KHUNG
    (app khung, cùng trang với /open/<slug>). Thêm app mới = thêm alias bên
    gateway, sidebar tự khớp."""
    try:
        from nen.common.hop_dong import doc_hop_dong
        return [{"slug": a["slug"], "ten": a["ten"], "href": f"/{a['slug']}"}
                for a in doc_hop_dong()
                if a["slug"] in apps_vao and a["slug"] not in KHONG_LAP_TOOLS]
    except Exception:
        return []


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
            "sb_apps": sb_apps_tu_claims(apps_vao),
            "sb_da": "data-analytics" in apps_vao,
            "sb_ns": "quan-tri" in apps_vao, "sb_cho_duyet": 0,
            "sb_nas": "nas" in apps_vao,
            # Khu chức năng (DE.md mục 10): gateway phát cờ 'hr'/'finance' —
            # sidebar chỉ hiện mục khi có cờ, app không tự tính quyền.
            "sb_hr": "hr" in apps_vao, "sb_fin": "finance" in apps_vao,
            # Cờ 'accounts' (HR HUB một cửa 16/08): tab Accounts trong /hr —
            # gateway phát theo giỏ quan_tai_khoan, template chỉ tin cờ.
            "sb_accounts": "accounts" in apps_vao}
