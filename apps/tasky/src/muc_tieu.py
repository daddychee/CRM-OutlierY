# -*- coding: utf-8 -*-
"""MỤC TIÊU — tầng trên của việc (Owner chốt 24-25/08, FLOW-v3 §12).

```
Owner giao NHIỆM VỤ cho Manager ──► Manager dựng thành MỤC TIÊU ──► chẻ VIỆC ──► giao nhân sự
                                          (có kết quả cần đạt)          (checklist do nhân sự viết)
```

Sổ riêng `TASKY_DIR/muc-tieu.json` vì mục tiêu **sống xuyên tuần** (hạn riêng), còn
việc vẫn nằm theo tuần. Ghi nguyên tử + nhật ký dùng chung khuôn của `tuan.py` —
không dựng lại cơ chế thứ hai.

HAI LUẬT KHÔNG ĐƯỢC NỚI:
1. **Tiến độ = việc con ĐÃ NGHIỆM THU / tổng việc con.** Không có trọng số, không
   quy đổi ra %. Owner đã bác cách gán "đóng góp": việc như *họp phân tích đối thủ*
   không đóng góp được X% AVD, ép gán là bịa số.
2. **Xong hết việc KHÔNG tự thành "đạt".** Mục tiêu chỉ chuyển sang chờ Manager
   kết luận; kết quả thật do người chốt, kèm nhận xét và tên họ. Máy không phán.
"""
from __future__ import annotations

import uuid
from datetime import date

from src.tuan import (XAC_NHAN, _ghi_json, _goc, doc_tuan, ghi_nhat_ky, _gio, _khoa,
                      _han_hop_le, cac_tuan_gan, doc_json)

DANG_CHAY, DAT, MOT_PHAN, KHONG_DAT = "dang_chay", "dat", "mot_phan", "khong_dat"
KET_QUA = (DAT, MOT_PHAN, KHONG_DAT)
MANAGER_LEVEL = 4
OWNER_LEVEL = 5


def _duong():
    return _goc() / "muc-tieu.json"


def doc_tat_ca() -> list[dict]:
    """Sổ mục tiêu. Chưa có / hỏng → [] (đọc khoan dung như sổ tuần)."""
    d = doc_json(_duong(), {"muc_tieu": []})
    ds = d.get("muc_tieu")
    return ds if isinstance(ds, list) else []


def _ghi(ds: list[dict]) -> None:
    _ghi_json(_duong(), {"muc_tieu": ds})


def _tim(ds: list[dict], mt_id: str) -> dict:
    for m in ds:
        if m["id"] == mt_id:
            return m
    raise ValueError("Không tìm thấy mục tiêu này.")


# ---------- quyền ----------

def duoc_dat_muc_tieu(user: dict) -> bool:
    """Owner chốt: công việc bắt đầu từ Manager (L4+). Leader vẫn giao việc lẻ được
    như cũ, nhưng không đặt mục tiêu."""
    return user["level"] >= MANAGER_LEVEL


def duoc_sua(mt: dict, user: dict) -> bool:
    """Người tạo, hoặc Manager cùng bộ phận, hoặc Owner."""
    if user["level"] >= OWNER_LEVEL or mt.get("nguoi_tao") == user["ten"]:
        return True
    return (user["level"] >= MANAGER_LEVEL
            and bool(user.get("bo_phan")) and mt.get("bo_phan") == user["bo_phan"])


# ---------- thao tác ----------

def tao(user: dict, tieu_de: str, ket_qua_can_dat: str, han: str = "",
        tu_nhiem_vu: str = "") -> dict:
    """Manager đặt mục tiêu. `tu_nhiem_vu` = id việc Owner giao, khi mục tiêu này
    được dựng lên từ một nhiệm vụ (giữ liên kết ngược để Owner theo dõi)."""
    if not duoc_dat_muc_tieu(user):
        raise PermissionError("Chỉ Manager trở lên mới đặt được mục tiêu.")
    tieu_de = (tieu_de or "").strip()
    if not tieu_de:
        raise ValueError("Mục tiêu phải có tên.")
    if not (ket_qua_can_dat or "").strip():
        raise ValueError("Phải nêu kết quả cần đạt — mục tiêu không đo được thì không chốt được.")
    with _khoa:
        ds = doc_tat_ca()
        mt = {"id": "mt-" + uuid.uuid4().hex[:8],
              "tieu_de": tieu_de[:200],
              "ket_qua_can_dat": ket_qua_can_dat.strip()[:300],
              "bo_phan": user.get("bo_phan", ""),
              "nguoi_tao": user["ten"],
              "han": _han_hop_le(han),
              "trang_thai": DANG_CHAY,
              "ket_luan": "", "luc_chot": None, "nguoi_chot": None,
              "tu_nhiem_vu": tu_nhiem_vu or "",
              "luc_tao": _gio()}
        ds.append(mt)
        _ghi(ds)
    ghi_nhat_ky("tao_muc_tieu", user["ten"],
                {"muc_tieu": mt["id"], "tieu_de": mt["tieu_de"],
                 "tu_nhiem_vu": mt["tu_nhiem_vu"]})
    return mt


def chot_ket_qua(mt_id: str, user: dict, ket_qua: str, nhan_xet: str = "") -> dict:
    """Manager kết luận mục tiêu. Không phải 'đạt' thì BẮT ghi nhận xét — số liệu
    không nói được vì sao, người chốt phải nói."""
    if ket_qua not in KET_QUA:
        raise ValueError("Kết quả phải là: đạt / một phần / không đạt.")
    nhan_xet = (nhan_xet or "").strip()
    if ket_qua != DAT and not nhan_xet:
        raise ValueError("Chưa đạt trọn thì phải ghi nhận xét.")
    with _khoa:
        ds = doc_tat_ca()
        mt = _tim(ds, mt_id)
        if not duoc_sua(mt, user):
            raise PermissionError("Chỉ Manager của mục tiêu này (hoặc Owner) mới chốt được.")
        if mt["trang_thai"] != DANG_CHAY:
            raise ValueError("Mục tiêu này đã chốt rồi.")
        mt.update({"trang_thai": ket_qua, "ket_luan": nhan_xet[:500],
                   "luc_chot": _gio(), "nguoi_chot": user["ten"]})
        _ghi(ds)
    ghi_nhat_ky("chot_muc_tieu", user["ten"],
                {"muc_tieu": mt_id, "ket_qua": ket_qua, "nhan_xet": nhan_xet[:500]})
    return mt


def mo_lai(mt_id: str, user: dict) -> dict:
    """Chốt nhầm thì mở lại — cùng khuôn 'thu lại việc đóng tuần'."""
    with _khoa:
        ds = doc_tat_ca()
        mt = _tim(ds, mt_id)
        if not duoc_sua(mt, user):
            raise PermissionError("Chỉ Manager của mục tiêu này (hoặc Owner) mới mở lại được.")
        if mt["trang_thai"] == DANG_CHAY:
            raise ValueError("Mục tiêu này đang chạy, chưa chốt.")
        cu = mt["trang_thai"]
        mt.update({"trang_thai": DANG_CHAY, "luc_chot": None, "nguoi_chot": None})
        _ghi(ds)
    ghi_nhat_ky("mo_lai_muc_tieu", user["ten"], {"muc_tieu": mt_id, "ket_qua_cu": cu})
    return mt


# ---------- đọc theo phạm vi ----------

def trong_pham_vi(user: dict, toan_cong_ty: bool = False) -> list[dict]:
    """Mục tiêu user được xem: bộ phận mình, hoặc tất cả khi có quyền toàn công ty."""
    ds = doc_tat_ca()
    if toan_cong_ty or user["level"] >= OWNER_LEVEL:
        return ds
    bp = user.get("bo_phan") or ""
    return [m for m in ds if m.get("bo_phan") == bp]


def viec_cua_muc_tieu(mt_id: str, so_tuan: int = 26) -> list[dict]:
    """Mọi việc gắn vào mục tiêu, gom qua các tuần gần (mục tiêu sống xuyên tuần)."""
    ra = []
    for ma in cac_tuan_gan(so_tuan):
        ra += [v for v in doc_tuan(ma)["viec"] if v.get("muc_tieu_id") == mt_id]
    return ra


def viec_theo_muc_tieu(so_tuan: int = 26) -> dict[str, list[dict]]:
    """Gom việc của MỌI mục tiêu trong MỘT lượt quét — trang cây có 9 mục tiêu thì
    đọc 26 file một lần, không phải 9×26 lần."""
    gom: dict[str, list[dict]] = {}
    for ma in cac_tuan_gan(so_tuan):
        for v in doc_tuan(ma)["viec"]:
            if v.get("muc_tieu_id"):
                gom.setdefault(v["muc_tieu_id"], []).append(v)
    return gom


def tien_do(mt_id: str, ds_viec: list[dict] | None = None) -> dict:
    """Tiến độ = việc ĐÃ NGHIỆM THU / tổng việc (luật 1). Chưa có việc nào → None,
    KHÔNG trả 0% (van chống bịa — cùng lệ với tỉ lệ hoàn thành của người)."""
    ds = viec_cua_muc_tieu(mt_id) if ds_viec is None else ds_viec
    song = [v for v in ds if v["trang_thai"] not in ("tu_choi", "huy", "doi")]
    xong = [v for v in song if v["trang_thai"] == XAC_NHAN]
    return {"tong": len(song), "xong": len(xong),
            "chua_giao": sum(1 for v in song if not v.get("nguoi")),
            "phan_tram": round(100 * len(xong) / len(song)) if song else None,
            "xong_het": bool(song) and len(xong) == len(song)}


def nhom_viec(ds_viec: list[dict]) -> dict:
    """Chia việc của một mục tiêu thành BA nhóm theo mức cần hành động (Owner chốt
    25/08: 10 việc đổ một mạch thì dễ miss).

    - `can_xu_ly`: việc của MANAGER — chưa phân công, chưa ai nhận, quá hạn, chờ nghiệm thu
    - `dang_chay`: có người đang làm, chỉ cần liếc
    - `xong`: đã nghiệm thu (UI thu gọn)
    """
    from src.tuan import (BAO_XONG, CHO_NHAN, CHO_PHOI_HOP, CHUA_GIAO, DANG_LAM,
                          XAC_NHAN, tinh_han)
    can, chay, xong = [], [], []
    for v in ds_viec:
        tt = v["trang_thai"]
        if tt == XAC_NHAN:
            xong.append(v)
        elif tt in (CHUA_GIAO, CHO_NHAN, CHO_PHOI_HOP, BAO_XONG):
            can.append(v)
        elif tt == DANG_LAM:
            (can if tinh_han(v)["muc"] == "cap" else chay).append(v)
    return {"can_xu_ly": can, "dang_chay": chay, "xong": xong}


def canh_bao(mt: dict, ds_viec: list[dict]) -> list[dict]:
    """Dải nhắc gọn trong ĐẦU mục tiêu (Owner 25/08: status là thông tin phụ, gộp
    vào khối trên, không dựng banner riêng). Mỗi mục có chữ — màu không đứng một mình."""
    from src.tuan import CHO_NHAN, CHUA_GIAO, DOI_LA_KET, XAC_NHAN, tinh_han
    song = [v for v in ds_viec if v["trang_thai"] not in ("tu_choi", "huy", "doi", XAC_NHAN)]
    ra = []
    qua = [v for v in song if tinh_han(v)["chu"].startswith("Quá hạn")]
    if qua:
        ra.append({"muc_do": "cap", "chu": f"{len(qua)} quá hạn", "so": len(qua)})
    chua = [v for v in song if v["trang_thai"] == CHUA_GIAO]
    if chua:
        ra.append({"muc_do": "cap", "chu": f"{len(chua)} chưa giao", "so": len(chua)})
    cho = [v for v in song if v["trang_thai"] == CHO_NHAN]
    if cho:
        ra.append({"muc_do": "luu_y", "chu": f"{len(cho)} chưa nhận", "so": len(cho)})
    ket = [v for v in song if v["so_lan_doi"] >= DOI_LA_KET]
    if ket:
        ra.append({"muc_do": "cap", "chu": f"{len(ket)} việc kẹt", "so": len(ket)})
    n = con_han(mt)
    if n is not None and n < 0 and mt["trang_thai"] == DANG_CHAY:
        ra.append({"muc_do": "cap", "chu": f"Trễ hạn {-n} ngày", "so": 1})
    return ra


def con_han(mt: dict, hom_nay: date | None = None) -> int | None:
    """Số ngày còn lại (âm = quá hạn). Không đặt hạn → None."""
    if not mt.get("han"):
        return None
    try:
        return (date.fromisoformat(mt["han"]) - (hom_nay or date.today())).days
    except ValueError:
        return None
