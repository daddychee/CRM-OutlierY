# -*- coding: utf-8 -*-
"""CHI PHÍ SẢN XUẤT THEO NGÁCH (D3) — spec `docs/finance-hub-spec.md` mục 5.

Owner: "Chi phí sản xuất cho niche được tính bằng số lượng ngày công làm cho
niche đó."

Nguồn (CHỈ ĐỌC, Luật 4 — app khác giữ dữ liệu của nó):
  PlannerY `plan.json`  projects[].ngach_ma · channels[].kenh_ma · assignments[]
  D1 `luong.don_gia_ngay(ky)`  — CHỈ kỳ đã duyệt
  `cham_cong.bang_cong_thang(ky)` — ngày công
  sổ thu chi + danh bạ — tiền mặt theo kênh, gộp lên ngách

Van chống bịa:
- người KHÔNG có phân công nào → ngày công về hàng "chưa phân công", không rải
  đều cho các ngách;
- người lương CHƯA DUYỆT → không thành chi phí (ô ghi rõ lý do), vì lấy lương dự
  kiến làm chi phí là bịa;
- PlannerY chết → `thieu_nguon=True`, `tong_nhan_cong=None`, KHÔNG dựng số.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from nen.common import danh_ba

from src import cham_cong, luong, tai_chinh


def _doc_plan() -> dict | None:
    p = Path(os.getenv("PLANNERY_PLAN", "plan.json"))
    if not p.is_file():
        return None
    try:
        du = json.loads(p.read_text(encoding="utf-8"))
        return du if isinstance(du, dict) else None
    except ValueError:
        return None


def phan_cong_ngach() -> dict[str, list[str]] | None:
    """{planner_id: [mã ngách]} từ PlannerY. Không đọc được → None."""
    plan = _doc_plan()
    if plan is None:
        return None
    ngach_cua_du_an = {d.get("id"): (d.get("ngach_ma") or "")
                       for d in plan.get("projects", [])}
    ra: dict[str, list[str]] = {}
    for pc in plan.get("assignments", []):
        ma = ngach_cua_du_an.get(pc.get("project_id"))
        if not ma:
            continue
        ds = ra.setdefault(pc.get("person_id"), [])
        if ma not in ds:
            ds.append(ma)
    return ra


def _ngach_cua_kenh() -> dict[str, str]:
    return {k["ma"]: k.get("ngach_ma", "") for k in danh_ba.liet_ke("kenh")}


def tien_mat_theo_ngach(ky: str) -> dict[str, float]:
    """Chi tiền mặt của kỳ, gộp từ kênh lên ngách (bút toán 'chung hệ' không
    thuộc ngách nào → bỏ, B1 mới là chỗ phân bổ chi phí chung)."""
    ngach_cua = _ngach_cua_kenh()
    ra: dict[str, float] = {}
    for ma_kenh, m in tai_chinh.pnl_theo_kenh(ky).items():
        ma_ngach = ngach_cua.get(ma_kenh, "")
        if not ma_ngach:
            continue
        ra[ma_ngach] = ra.get(ma_ngach, 0.0) + m.get("chi", 0.0)
    return ra


def chi_phi_ngach(ky: str, ds_nguoi: list[dict]) -> dict:
    """Chi phí sản xuất từng ngách trong kỳ.

    ngày công người P cho ngách N = công chốt(P) ÷ số ngách P được phân công
    (chia đều — nâng cấp sang chia theo SỐ VIDEO ngay khi PlannerY có video gắn
    tên người: dữ liệu chính xác hơn thì thắng, Owner đã đồng ý không hỏi lại).
    """
    pc = phan_cong_ngach()
    cong = cham_cong.bang_cong_thang(ky)
    don_gia = luong.don_gia_ngay(ky)          # chỉ kỳ ĐÃ DUYỆT
    tien_mat = tien_mat_theo_ngach(ky)
    ten_ngach = {n["ma"]: n.get("ten_chuan", "") for n in danh_ba.liet_ke("ngach")}

    if pc is None:
        return {"ky": ky, "thieu_nguon": True, "dong": [], "tong_nhan_cong": None,
                "chua_phan_cong": {"ngay_cong": 0.0, "nhan_cong": None, "ghi_chu":
                                   "Không đọc được phân công từ PlannerY."}}

    gom: dict[str, dict] = {}
    chua = {"ngay_cong": 0.0, "nhan_cong": 0.0, "ghi_chu": "", "nguoi": []}
    thieu_luong = False
    for n in ds_nguoi:
        ten = n.get("ten")
        so_ngay = float(cong.get(ten, {}).get("so_ngay", 0))
        if not so_ngay:
            continue
        gia = don_gia.get(ten)                # None = lương kỳ này chưa duyệt
        ds_ngach = pc.get(n.get("planner_id") or "", [])
        if not ds_ngach:
            chua["ngay_cong"] += so_ngay
            chua["nguoi"].append(ten)
            if gia is None:
                thieu_luong = True
            else:
                chua["nhan_cong"] += so_ngay * gia
            continue
        phan = so_ngay / len(ds_ngach)
        for ma in ds_ngach:
            m = gom.setdefault(ma, {"ngach_ma": ma, "ten": ten_ngach.get(ma, ma),
                                    "ngay_cong": 0.0, "nhan_cong": 0.0,
                                    "nguoi": [], "chua_duyet_luong": False})
            m["ngay_cong"] += phan
            if ten not in m["nguoi"]:
                m["nguoi"].append(ten)
            if gia is None:
                m["chua_duyet_luong"] = True
            else:
                m["nhan_cong"] += phan * gia

    dong = []
    for ma, m in sorted(gom.items()):
        tm = tien_mat.get(ma, 0.0)
        m["nhan_cong"] = round(m["nhan_cong"], 2)
        m["ngay_cong"] = round(m["ngay_cong"], 2)
        m["tien_mat"] = tm
        m["tong"] = round(m["nhan_cong"] + tm, 2)
        dong.append(m)

    if thieu_luong or (chua["ngay_cong"] and not chua["nhan_cong"]):
        chua["nhan_cong"] = None
        chua["ghi_chu"] = "Lương kỳ này chưa duyệt — ngày công chưa thành chi phí."
    chua["ngay_cong"] = round(chua["ngay_cong"], 2)
    return {"ky": ky, "thieu_nguon": False, "dong": dong,
            "tong_nhan_cong": round(sum(d["nhan_cong"] for d in dong)
                                    + (chua["nhan_cong"] or 0.0), 2),
            "tong_tien_mat": round(sum(d["tien_mat"] for d in dong), 2),
            "chua_phan_cong": chua}
