# -*- coding: utf-8 -*-
"""Danh sách người — đọc CHỈ-ĐỌC sổ IAM chung (nen/iam), khuôn `_ds_nguoi_iam`
của app to-chuc.

App vẫn TỰ ĐỨNG: IAM lỗi → trả (None, lý do) để UI nói thẳng, KHÔNG dựng bảng rỗng
giả vờ "công ty không có ai" — cùng họ van chống bịa với `ti_le = None`.

Tasky chỉ cần 3 thứ của mỗi người: tên tài khoản, level, bộ phận (để chấm luật
"level cao giao level thấp, cùng bộ phận") + họ tên để hiển thị.
"""
from __future__ import annotations


def ds_nguoi() -> tuple[list[dict] | None, str]:
    """[{ten, level, bo_phan, ho_ten}] — người đã thôi việc bị loại khỏi danh sách
    (đúng lệ to-chuc: hồ sơ còn nhưng không vào bảng vận hành)."""
    try:
        from nen.iam import iam
        conn = iam.ket_noi()
        try:
            ho_so = {n["ma"]: n for n in iam.liet_ke_nguoi(conn)}
            ds = []
            for tk in iam.liet_ke_tai_khoan(conn):
                hs = ho_so.get(tk.get("nguoi_ma") or "") or {}
                if hs.get("trang_thai") == "nghi":
                    continue
                ds.append({"ten": tk["ten"],
                           "level": int(tk.get("level") or 0),
                           "bo_phan": tk.get("bo_phan") or "",
                           "ho_ten": hs.get("ho_ten", "")})
            return ds, ""
        finally:
            conn.close()
    except Exception as e:
        return None, (f"Không đọc được sổ IAM ({e.__class__.__name__}) — "
                      "chưa dựng được danh sách người.")


def cap_duoi_cua(nguoi_giao: dict) -> tuple[list[dict] | None, str]:
    """Những người user này ĐƯỢC PHÉP giao việc (lọc bằng chính luật của lõi, không
    chép lại điều kiện — một nguồn sự thật)."""
    from src.tuan import duoc_giao_cho
    ds, loi = ds_nguoi()
    if ds is None:
        return None, loi
    # duoc_giao_cho() nay cho phép tự giao cho mình → chính user cũng nằm trong
    # danh sách; sắp họ xuống cuối để không bấm nhầm khi giao cho quân.
    ra = [n for n in ds if duoc_giao_cho(nguoi_giao, n)]
    return sorted(ra, key=lambda n: n["ten"] == nguoi_giao["ten"]), ""


def ngang_cap_bo_phan_khac(user: dict) -> tuple[list[dict] | None, str]:
    """Quản lý bộ phận KHÁC mà user này gửi được yêu cầu phối hợp — lọc bằng chính
    luật của lõi (một nguồn sự thật, không chép lại điều kiện)."""
    from src.tuan import duoc_yeu_cau_phoi_hop
    ds, loi = ds_nguoi()
    if ds is None:
        return None, loi
    return [n for n in ds if duoc_yeu_cau_phoi_hop(user, n)], ""


def trong_pham_vi_bao_cao(user: dict, toan_cong_ty: bool) -> tuple[list[dict] | None, str]:
    """Phạm vi báo cáo (FLOW-v3 §9.1): Manager L4+ và HR Leader+ xem TOÀN CÔNG TY
    (cờ `toan_cong_ty` do route tính từ X-Remote-Actions), Leader xem bộ phận mình.
    Người xem luôn có mặt trong bảng của chính mình."""
    ds, loi = ds_nguoi()
    if ds is None:
        return None, loi
    if toan_cong_ty:
        return ds, ""
    bp = user.get("bo_phan") or ""
    return [n for n in ds if n["bo_phan"] == bp or n["ten"] == user["ten"]], ""
