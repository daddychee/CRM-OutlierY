# -*- coding: utf-8 -*-
"""SỐ LIỆU CHO DASHBOARD — gom sẵn ở server, template chỉ vẽ.

Hai báo cáo trả lời hai câu hỏi khác nhau (Owner chốt 25/08):

| | Manager | Owner |
|---|---|---|
| Câu hỏi | *tuần tới tôi điều ai làm gì?* | *công ty có đi đúng hướng không?* |
| Đơn vị nhìn | người + việc | bộ phận + Goal |
| Bóc từng người | có | **không** — đó là việc của Manager |

Van chống bịa giữ nguyên khắp nơi: không ai có việc → tỉ lệ `None` (UI hiện "—"),
không bao giờ 0% giả.
"""
from __future__ import annotations

from src import muc_tieu as mt
from src import tuan as t

SO_TUAN_XU_HUONG = 8


def _ti_le(bang: list[dict]) -> int | None:
    co = [d for d in bang if d["so_viec"]]
    tong = sum(d["so_viec"] for d in co)
    return round(100 * sum(d["xong"] for d in co) / tong) if tong else None


def xu_huong(ds_nguoi: list[dict], ma_tuan_nay: str = "",
             so_tuan: int = SO_TUAN_XU_HUONG) -> list[dict]:
    """Tỉ lệ hoàn thành N tuần gần nhất của một nhóm người — cho biểu đồ đường.

    Tuần chưa ai làm gì trả `ti_le = None`; UI vẽ đứt đoạn ở đó chứ KHÔNG nối liền
    như thể tuần ấy 0% (nối liền là bịa một cú tụt không có thật)."""
    ma_nay = ma_tuan_nay or t.ma_tuan()
    ra = []
    for i in range(so_tuan - 1, -1, -1):
        ma = t.tuan_lien_ke(ma_nay, -i)
        bang = t.bang_bao_cao(ma, ds_nguoi)
        ra.append({"ma": ma, "nhan": "T" + ma[-2:].lstrip("0"), "ti_le": _ti_le(bang)})
    return ra


def theo_bo_phan(ma: str, ds_nguoi: list[dict]) -> list[dict]:
    """Gom số theo BỘ PHẬN — Owner nhìn ở mức này, không bóc từng người.
    Bộ phận phân biệt bằng KHỐI RIÊNG + TÊN, không bằng màu (luật màu §12.2)."""
    gom: dict[str, list[dict]] = {}
    for n in ds_nguoi:
        gom.setdefault(n.get("bo_phan") or "(chưa gán bộ phận)", []).append(n)
    ra = []
    for bp, ds in sorted(gom.items()):
        bang = t.bang_bao_cao(ma, ds)
        ra.append({"bo_phan": bp, "so_nguoi": len(ds),
                   "ti_le": _ti_le(bang),
                   "so_viec": sum(d["so_viec"] for d in bang),
                   "xong": sum(d["xong"] for d in bang),
                   "ket": sum(d["ket"] for d in bang),
                   "buoc_tong": sum(d["buoc_tong"] for d in bang),
                   "da_dong": sum(1 for d in bang if d["da_dong"]),
                   "chua_co_viec": sum(1 for d in bang if not d["so_viec"])})
    return ra


def tong_hop_goal(ds_mt: list[dict] | None = None) -> dict:
    """Đếm Goal theo trạng thái — cho biểu đồ tròn. `cho_chot` = xong hết việc mà
    Manager chưa kết luận (đây là thứ Owner cần thúc, không phải 'đã đạt')."""
    ds = mt.doc_tat_ca() if ds_mt is None else ds_mt
    gom = mt.viec_theo_muc_tieu()
    dem = {"dat": 0, "mot_phan": 0, "khong_dat": 0, "dang_chay": 0,
           "cho_chot": 0, "tre_han": 0}
    for m in ds:
        if m["trang_thai"] != mt.DANG_CHAY:
            dem[m["trang_thai"]] += 1
            continue
        td = mt.tien_do(m["id"], gom.get(m["id"], []))
        if td["xong_het"]:
            dem["cho_chot"] += 1
        else:
            dem["dang_chay"] += 1
        n = mt.con_han(m)
        if n is not None and n < 0:
            dem["tre_han"] += 1
    dem["tong"] = len(ds)
    return dem


def goal_kem_tien_do(ds_mt: list[dict]) -> list[dict]:
    """Danh sách Goal kèm tiến độ + cảnh báo, sắp việc-cần-để-ý lên đầu."""
    gom = mt.viec_theo_muc_tieu()
    ra = []
    for m in ds_mt:
        viec = gom.get(m["id"], [])
        ra.append({**m, "tien_do": mt.tien_do(m["id"], viec),
                   "canh_bao": mt.canh_bao(m, viec), "con_han": mt.con_han(m)})
    ra.sort(key=lambda g: (g["trang_thai"] != mt.DANG_CHAY, -len(g["canh_bao"]),
                           g["tieu_de"]))
    return ra


def nhiem_vu_da_giao(user: dict, so_tuan: int = 26) -> list[dict]:
    """Nhiệm vụ CHÍNH user này giao cho quản lý cấp dưới, kèm Goal đã dựng (nếu có).

    Đây là khối riêng của báo cáo Owner: nhiệm vụ giao rồi mà Manager chưa chẻ việc
    là thứ không bảng tỉ lệ nào nói ra được."""
    ds_mt = mt.doc_tat_ca()
    ra = []
    for ma in t.cac_tuan_gan(so_tuan):
        for v in t.doc_tuan(ma)["viec"]:
            if v.get("nguoi_giao") != user["ten"] or v.get("muc_tieu_id"):
                continue
            g = mt.nhiem_vu_da_dung(v["id"], ds_mt)
            if v["trang_thai"] == t.DOI:
                continue          # đã dời sang tuần sau → bản MỚI đại diện, nếu không
                                  # lọc thì một nhiệm vụ hiện hai dòng (Owner báo 25/08)
            if g is None and v["trang_thai"] in (t.XAC_NHAN, t.HUY, t.TU_CHOI):
                continue          # việc thường đã ngã ngũ — không phải nhiệm vụ treo
            ra.append({"viec": v, "tuan": ma, "goal": g,
                       "tien_do": mt.tien_do(g["id"]) if g else None})
    ra.sort(key=lambda x: (x["goal"] is not None, x["viec"]["luc_tao"]))
    return ra
