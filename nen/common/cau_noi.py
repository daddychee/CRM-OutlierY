# -*- coding: utf-8 -*-
"""CẦU NỐI (P6) — connector chỉ-đọc + router hỏi số liệu.

Triết lý đã chốt với Owner (phiên bàn 16/08):
- Tri thức TĨNH ở kho (RAG); dữ liệu SỐNG phải TÍNH TẠI NGUỒN lúc hỏi — connector
  gọi API của app sở hữu dữ liệu, KHÔNG đọc trộm file của app (Luật 4).
- Connector chạy DƯỚI DANH NGHĨA NGƯỜI HỎI: kiểm quyền vào app bằng iam.co_quyen
  TRƯỚC (không có quyền → nói thẳng "cần quyền X" — app là thứ ai cũng biết tồn
  tại, khác tài liệu phải từ chối lặng lẽ).
- Van chống bịa số liệu: kênh không có trong danh bạ → hỏi lại kèm gợi ý; chưa có
  báo cáo → nói thẳng, kèm báo cáo gần nhất nếu có; MỌI kết quả kèm nguồn + tuổi
  dữ liệu.
- Router v1 là LUẬT (so tên qua danh bạ) — không LLM: một connector thì luật đủ,
  rẻ, test được. ponytail: khi nhiều connector mới cân nhắc LLM định tuyến.
"""
from __future__ import annotations

import httpx

from nen.common import danh_ba
from nen.iam import iam

CONG_DATA_ANALYTICS = 9102


def _goi_api_app(cong: int, duong: str, user: dict) -> httpx.Response:
    """Gọi API app dưới danh nghĩa người hỏi (claims như gateway tiêm)."""
    from urllib.parse import quote
    headers = {"X-Remote-User": user["ten"],
               "X-Remote-Level": str(user.get("level", 0)),
               "X-Remote-Role": user.get("vai", "")}
    if user.get("bo_phan"):
        headers["X-Remote-Dept"] = quote(user["bo_phan"])
    return httpx.get(f"http://127.0.0.1:{cong}{duong}", headers=headers, timeout=10)


def bao_cao_kenh(kenh: dict, user: dict, conn=None) -> dict:
    """Connector #1 — báo cáo Data Analytics mới nhất của một kênh (đã tra danh bạ).

    Trả (một trong ba, LUÔN kèm nguồn):
    - {"loai": "co_bao_cao", "bao_cao": {...}, "nguon": ..., "tuoi_du_lieu": ...}
    - {"loai": "chua_co_bao_cao", "kenh": ...}
    - {"loai": "khong_du_quyen"} / {"loai": "nguon_chet", "loi": ...}
    """
    if not iam.co_quyen(user, "vao", "data-analytics", conn):
        return {"loai": "khong_du_quyen",
                "noi_thang": "Bạn cần quyền Data Analytics (Kinh doanh L2+ hoặc "
                             "Manager+) để hỏi số liệu kênh."}
    try:
        r = _goi_api_app(CONG_DATA_ANALYTICS, "/api/bao-cao-lich-su", user)
        r.raise_for_status()
    except httpx.HTTPError as e:
        return {"loai": "nguon_chet",
                "noi_thang": "App Data Analytics không phản hồi — xem trang Sức khỏe hệ.",
                "loi": str(e)}
    ten_chuan = kenh["ten_chuan"]
    can = danh_ba.chuan_hoa_ten(ten_chuan)
    # Khớp theo ten_kenh (định danh chuẩn — form upload có dropdown danh bạ) TRƯỚC;
    # báo cáo cũ chưa gắn ten_kenh thì mới dò tên báo cáo chứa tên kênh.
    khop = [b for b in r.json().get("bao_cao", [])
            if danh_ba.chuan_hoa_ten(str(b.get("ten_kenh") or "")) == can
            or (not b.get("ten_kenh")
                and can in danh_ba.chuan_hoa_ten(str(b.get("ten") or "")))]
    if not khop:
        return {"loai": "chua_co_bao_cao", "kenh": ten_chuan,
                "noi_thang": f"Chưa có báo cáo nào của kênh {ten_chuan} trong Data "
                             f"Analytics. Muốn có số liệu: xuất report YouTube Studio "
                             f"rồi upload vào Data Analytics (nhớ chọn kênh {ten_chuan})."}
    moi_nhat = khop[0]  # API đã sort mới nhất trước
    return {"loai": "co_bao_cao", "kenh": ten_chuan, "bao_cao": moi_nhat,
            "so_bao_cao": len(khop),
            "nguon": f"Báo cáo '{moi_nhat.get('ten')}' do {moi_nhat.get('nguoi_chay')} "
                     f"chạy trong Data Analytics",
            "tuoi_du_lieu": moi_nhat.get("thoi_gian"),
            "duong_mo": f"/app/data-analytics/bao-cao-lich-su/{moi_nhat.get('id')}"}


def hoi_so_lieu(cau_hoi: str, user: dict, conn=None) -> dict:
    """ROUTER hỏi số liệu v1 — luật: tìm tên kênh trong câu hỏi qua DANH BẠ
    (tên chuẩn + bí danh, chuẩn hóa 2 phía). Không khớp → hỏi lại kèm gợi ý,
    TUYỆT ĐỐI không đoán."""
    can = danh_ba.chuan_hoa_ten(cau_hoi)
    kenh_khop = [t for t in danh_ba.liet_ke("kenh")
                 if any(ten and ten in can
                        for ten in ([danh_ba.chuan_hoa_ten(t["ten_chuan"])]
                                    + [danh_ba.chuan_hoa_ten(b)
                                       for b in (t.get("bi_danh") or "").split(";") if b]))]
    if not kenh_khop:
        return {"loai": "khong_khop",
                "noi_thang": "Không nhận ra kênh nào trong câu hỏi.",
                "goi_y": [t["ten_chuan"] for t in danh_ba.liet_ke("kenh")]}
    if len(kenh_khop) > 1:
        return {"loai": "nhieu_kenh",
                "noi_thang": "Câu hỏi khớp nhiều kênh — bạn muốn kênh nào?",
                "goi_y": [t["ten_chuan"] for t in kenh_khop]}
    return bao_cao_kenh(kenh_khop[0], user, conn)
