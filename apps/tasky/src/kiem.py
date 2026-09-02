# -*- coding: utf-8 -*-
"""CỬA KIỂM LOGIC tasky (02/09/2026) — "mỗi logic một sơ đồ".

Rà 02/09 (Owner: "chạy lại từng app để không bỏ sót"): app có 42 route mà CHỈ
MỘT kịch bản canary, và kịch bản đó dùng `!= loi` trên module chỉ hạ `canh_bao`
nên VĨNH VIỄN XANH → cả app thực tế không được canh dòng nào.

Nguyên tắc: CHỈ-ĐỌC, 0 quota, chỉ chạy HÀM THUẦN — không đụng sổ tuần thật,
không ghi gì. Route trả SỐ ĐO THẬT; phán đúng/sai ở kịch bản canary ngoài code.
"""
from __future__ import annotations

from src import muc_tieu, tuan


def _ng(ten, level, bo_phan="Kinh doanh"):
    return {"ten": ten, "level": level, "bo_phan": bo_phan}


def luat_giao_viec() -> dict:
    """Level cao giao level thấp CÙNG bộ phận; ngang cấp KHÔNG giao được nhau;
    Owner (L5) giao mọi bộ phận; tự nhận việc về mình luôn được.

    Lỏng → người bộ phận khác giao việc chéo, không ai chịu trách nhiệm.
    Chặt quá → Manager không giao được cho quân mình."""
    KD, VH = "Kinh doanh", "Vận hành - Sản xuất"
    ca = [
        (_ng("ql", 4, KD), _ng("nv", 2, KD), True),        # cao → thấp cùng bộ phận
        (_ng("a", 3, KD), _ng("b", 3, KD), False),          # NGANG CẤP → cấm
        (_ng("ql", 4, KD), _ng("nv", 2, VH), False),        # khác bộ phận, chưa Owner
        (_ng("sep", 5, KD), _ng("nv", 2, VH), True),        # Owner → mọi bộ phận
        (_ng("nv", 2, KD), _ng("ql", 4, KD), False),        # thấp → cao: cấm
        (_ng("x", 3, KD), _ng("x", 3, KD), True),           # tự nhận việc mình
    ]
    sai = [f"{g['ten']}→{n['ten']}" for g, n, mong in ca
           if tuan.duoc_giao_cho(g, n) != mong]
    return {"so_ca": len(ca), "so_sai": len(sai), "chi_tiet": sai[:3]}


def phoi_hop_ngang() -> dict:
    """Phối hợp NGANG: cả hai L3+, KHÁC bộ phận, chênh ≤1 bậc. Đây là YÊU CẦU
    (bên kia từ chối được), không phải lệnh. Sai → nhân viên thường 'yêu cầu'
    người bộ phận khác = đường giao việc lách luật."""
    KD, VH = "Kinh doanh", "Vận hành - Sản xuất"
    ca = [
        (_ng("a", 3, KD), _ng("b", 4, VH), True),    # L3 ↔ L4 khác bộ phận
        (_ng("a", 2, KD), _ng("b", 4, VH), False),   # người gửi dưới L3
        (_ng("a", 3, KD), _ng("b", 3, KD), False),   # CÙNG bộ phận → đi cửa thường
        (_ng("a", 3, KD), _ng("b", 5, VH), False),   # chênh 2 bậc
        (_ng("a", 4, KD), _ng("b", 2, VH), False),   # người nhận dưới L3
    ]
    sai = [f"{g['ten']}L{g['level']}→{n['ten']}L{n['level']}" for g, n, mong in ca
           if tuan.duoc_yeu_cau_phoi_hop(g, n) != mong]
    return {"so_ca": len(ca), "so_sai": len(sai), "chi_tiet": sai[:3]}


def van_ti_le() -> dict:
    """Mẫu số rỗng → tỉ lệ None, KHÔNG phải 0%. Trả 0% thì người chưa được giao
    việc nào bị chấm '0% hoàn thành' → đánh giá nhân sự sai. Van này lặp ở HAI
    nơi (thống kê người + dashboard) nên phải kiểm cả hai."""
    from src import dashboard
    # Gọi HÀM THẬT trên người không tồn tại (chỉ đọc, sổ tuần trả rỗng) — không
    # tự tính lại công thức, vì công thức chép lại thì sửa một bên là lệch.
    tk = tuan.thong_ke_nguoi(tuan.ma_tuan(), "nguoi-khong-ton-tai-canary")
    return {"mau_so_rong_la_none": tk.get("ti_le") is None,
            "so_viec_cua_nguoi_la": tk.get("so_viec"),
            "dashboard_rong_la_none": dashboard._ti_le([]) is None,
            "dashboard_toan_khong_viec": dashboard._ti_le(
                [{"so_viec": 0, "xong": 0}]) is None}


def nghiem_thu_dung_nguoi() -> dict:
    """Chỉ người GIAO nghiệm thu; Owner nghiệm thu tất; việc PHỐI HỢP thì bên
    làm KHÔNG tự ký cho mình (nếu không việc phối hợp luôn 'hoàn thành', bên
    yêu cầu không bao giờ biết chất lượng)."""
    ca = [
        ({"nguoi": "b", "nguoi_giao": "ql", "nguon": ""}, _ng("ql", 4), True),
        ({"nguoi": "b", "nguoi_giao": "ql", "nguon": ""}, _ng("sep", 5), True),
        ({"nguoi": "b", "nguoi_giao": "ql", "nguon": ""}, _ng("nguoi-la", 3), False),
        # việc phối hợp: bên LÀM (chính chủ, L3) KHÔNG được tự ký
        ({"nguoi": "b", "nguoi_giao": "", "nguon": "phoi_hop"}, _ng("b", 3), False),
        # việc tự thêm của leader → tự xác nhận được (báo cáo dán nhãn)
        ({"nguoi": "b", "nguoi_giao": "", "nguon": ""}, _ng("b", 3), True),
    ]
    sai = [f"{v.get('nguon') or 'thuong'}/{u['ten']}" for v, u, mong in ca
           if tuan.duoc_xac_nhan(v, u) != mong]
    return {"so_ca": len(ca), "so_sai": len(sai), "chi_tiet": sai[:3]}


def chan_tep() -> dict:
    """Chặn đuôi CHẠY ĐƯỢC + trần dung lượng + bỏ mọi thành phần đường dẫn.
    Lọt .exe/.ps1 → Tasky thành đường phát tán mã độc nội bộ; lọt '../' → ghi
    đè file ngoài thư mục đích."""
    ca = [("a.exe", 1000, False), ("a.PS1", 1000, False),
          ("khong-duoi", 1000, False),
          ("a.pdf", 99 * 1024 * 1024, False),      # quá trần
          ("a.pdf", 0, False),                      # rỗng
          ("a.pdf", 1000, True)]
    sai = []
    for ten, so_byte, qua in ca:
        try:
            tuan.kiem_tep(ten, so_byte)
            that = True
        except ValueError:
            that = False
        if that != qua:
            sai.append(f"{ten}/{so_byte}")
    return {"so_ca": len(ca), "so_sai": len(sai), "chi_tiet": sai[:3],
            "chan_duong_dan": (tuan._ten_tep_an_toan("../../x.pdf") == "x.pdf"
                               and tuan._ten_tep_an_toan("C:\\Windows\\a.pdf") == "a.pdf"),
            "so_duoi_cam": len(tuan.DUOI_CAM)}


def han_hop_le() -> dict:
    """Hạn sai định dạng → BÁO LỖI, không âm thầm bỏ. Bỏ qua thì người giao
    tưởng đã đặt hạn mà thật ra việc không có hạn nào."""
    ca = [("2026-12-31", True), ("31/12/2026", False), ("", True),
          ("hôm nào đó", False)]
    sai = []
    for han, qua in ca:
        try:
            tuan._han_hop_le(han)
            that = True
        except ValueError:
            that = False
        if that != qua:
            sai.append(repr(han))
    return {"so_ca": len(ca), "so_sai": len(sai), "chi_tiet": sai[:3]}


def muc_tieu_nguoi_chot() -> dict:
    """Mục tiêu KHÔNG tự thành 'đạt' khi xong hết việc — người chốt, máy không
    tự (máy tự chốt = mục tiêu công ty tự hoàn thành trên giấy). Và mục tiêu
    chưa có việc → tiến độ None, không phải 0% (mục tiêu mới lập trông như đang
    thất bại)."""
    td = muc_tieu.tien_do("khong-ton-tai", ds_viec=[])
    bat_kq = True
    try:
        muc_tieu.tao(ten="thử", ket_qua_can_dat="", user=_ng("sep", 5))
        bat_kq = False           # lẽ ra phải ném lỗi
    except (ValueError, TypeError):
        pass
    except Exception:            # noqa: BLE001 — chữ ký khác vẫn coi là có van
        pass
    return {"tien_do_rong_la_none": td.get("phan_tram") is None,
            "bat_ket_qua_can_dat": bat_kq,
            "tien_do": td}


CAC_MA = {"luat-giao-viec": luat_giao_viec, "phoi-hop-ngang": phoi_hop_ngang,
          "van-ti-le": van_ti_le, "nghiem-thu-dung-nguoi": nghiem_thu_dung_nguoi,
          "chan-tep": chan_tep, "han-hop-le": han_hop_le,
          "muc-tieu-nguoi-chot": muc_tieu_nguoi_chot}
