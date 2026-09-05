# -*- coding: utf-8 -*-
"""QUẢN LÝ TÀI SẢN — vật lý (kiểm kê + bàn giao) và số (mật khẩu ở Vault).

Owner chốt 29/08/2026.

HAI KHO, HAI VAI — điều quan trọng nhất của module này:
  sổ tài sản   giữ DANH MỤC: cái gì, mua bao giờ, ai đang giữ, để ở đâu
  Vault        giữ BÍ MẬT: mật khẩu, mã hai lớp, khóa khôi phục

Tài sản số chỉ mang `vault_id` — một mã trỏ sang mục trong két. Sổ này KHÔNG có
trường mật khẩu và không được thêm: ai cần đăng nhập thì sang Vault (chỉ Owner,
mở bằng master, tự khóa sau 10 phút, mỗi lượt xem đều vào nhật ký).

Bàn giao là sổ CHỈ-THÊM: đổi người giữ thì thêm một dòng, không sửa dòng cũ. Hỏi
"tháng trước máy này ai cầm" luôn trả lời được — và khi ai đó nghỉ việc thì tra
ra ngay họ đang giữ những gì.
"""
from __future__ import annotations

import json
import os
import secrets
import threading
from datetime import date, datetime
from pathlib import Path

_khoa = threading.Lock()

LOAI = ("vat_ly", "so")
NHOM = {
    # vật lý
    "may_tinh": "Máy tính", "dien_thoai": "Điện thoại", "may_quay": "Máy quay",
    "man_hinh": "Màn hình", "thiet_bi_mang": "Thiết bị mạng", "noi_that": "Nội thất",
    "khac_vl": "Khác (vật lý)",
    # số
    "kenh_youtube": "Kênh YouTube", "tai_khoan_quang_cao": "Tài khoản quảng cáo",
    "ten_mien": "Tên miền", "proxy_ip": "Proxy / IP", "phan_mem": "Phần mềm bản quyền",
    "khac_so": "Khác (số)",
}
NHOM_VAT_LY = ("may_tinh", "dien_thoai", "may_quay", "man_hinh", "thiet_bi_mang",
               "noi_that", "khac_vl")
TINH_TRANG = ("dang_dung", "dang_sua", "hong", "da_thanh_ly")


def _duong(ten_tep: str) -> Path:
    return Path(os.getenv("TAI_SAN_DIR", "nhan-su/tai-san")) / ten_tep


def _doc_json(p: Path, mac_dinh):
    if not p.is_file():
        return mac_dinh
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except ValueError:
        return mac_dinh


def _ghi_json(p: Path, du) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tam = p.with_name(p.name + ".tmp")
    tam.write_text(json.dumps(du, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tam, p)


# ---------- sổ tài sản ----------

def doc_tai_san() -> list[dict]:
    return _doc_json(_duong("tai-san.json"), [])


def luu_tai_san(nguoi: str, loai: str, ten: str, nhom: str, ma: str = "",
                ma_dinh_danh: str = "", ngay_mua: str = "", nguyen_gia=0,
                tien_te: str = "VND", noi_de: str = "", vault_id: str = "",
                tinh_trang: str = "dang_dung", kenh_ma: str = "",
                ghi_chu: str = "") -> dict:
    """Thêm mới (ma rỗng) hoặc sửa. KHÔNG nhận tham số mật khẩu — cố truyền vào
    thì Python tự báo TypeError, đó là chủ đích."""
    ten = (ten or "").strip()
    if not ten:
        raise ValueError("Thiếu tên tài sản.")
    if loai not in LOAI:
        raise ValueError(f"Loại '{loai}' không hợp lệ (vat_ly hoặc so).")
    if nhom not in NHOM:
        raise ValueError(f"Nhóm '{nhom}' không có trong danh mục.")
    hop = nhom in NHOM_VAT_LY
    if (loai == "vat_ly") != hop:
        raise ValueError(f"Nhóm '{NHOM[nhom]}' không thuộc loại tài sản đã chọn.")
    if tinh_trang not in TINH_TRANG:
        raise ValueError(f"Tình trạng '{tinh_trang}' không hợp lệ.")
    if ngay_mua:
        date.fromisoformat(ngay_mua)
    try:
        nguyen_gia = float(nguyen_gia or 0)
    except (TypeError, ValueError):
        raise ValueError("Nguyên giá phải là số.")
    if nguyen_gia < 0:
        raise ValueError("Nguyên giá không âm.")

    with _khoa:
        ds = doc_tai_san()
        ban = {"loai": loai, "ten": ten, "nhom": nhom,
               "ma_dinh_danh": (ma_dinh_danh or "").strip(),
               "ngay_mua": ngay_mua, "nguyen_gia": nguyen_gia,
               "tien_te": (tien_te or "VND").upper(),
               "noi_de": (noi_de or "").strip(),
               "vault_id": (vault_id or "").strip(),
               "tinh_trang": tinh_trang, "kenh_ma": (kenh_ma or "").strip(),
               "ghi_chu": (ghi_chu or "").strip(),
               "sua_luc": datetime.now().isoformat(timespec="seconds"),
               "nguoi_sua": nguoi}
        if ma:
            cu = next((d for d in ds if d.get("ma") == ma), None)
            if cu is None:
                raise ValueError(f"Không có tài sản mã '{ma}'.")
            cu.update(ban)
            ban = cu
        else:
            ban["ma"] = "TS-" + secrets.token_hex(3)
            ban["tao_luc"] = ban["sua_luc"]
            ds.append(ban)
        _ghi_json(_duong("tai-san.json"), ds)
    return ban


def tim_tai_san(ma: str) -> dict | None:
    return next((d for d in doc_tai_san() if d.get("ma") == ma), None)


# ---------- bàn giao (sổ chỉ-thêm) ----------

def doc_ban_giao() -> list[dict]:
    return _doc_json(_duong("ban-giao.json"), [])


def ban_giao(nguoi_lam: str, ma: str, nguoi_giu: str, ngay: str = "",
             ghi_chu: str = "") -> dict:
    """Ghi MỘT lượt bàn giao. `nguoi_giu` rỗng = thu hồi về kho.

    Chỉ-thêm: không sửa dòng cũ, nên lịch sử ai từng giữ vẫn còn nguyên.
    """
    if tim_tai_san(ma) is None:
        raise ValueError(f"Không có tài sản mã '{ma}'.")
    ngay = ngay or date.today().isoformat()
    date.fromisoformat(ngay)
    ban = {"ma": ma, "nguoi_giu": (nguoi_giu or "").strip(), "ngay": ngay,
           "ghi_chu": (ghi_chu or "").strip(), "nguoi_lam": nguoi_lam,
           "luc": datetime.now().isoformat(timespec="seconds")}
    with _khoa:
        ds = doc_ban_giao()
        ds.append(ban)
        _ghi_json(_duong("ban-giao.json"), ds)
    return ban


def lich_su_ban_giao(ma: str) -> list[dict]:
    """Theo thứ tự thời gian, cũ trước."""
    return sorted((d for d in doc_ban_giao() if d.get("ma") == ma),
                  key=lambda d: (d.get("ngay", ""), d.get("luc", "")))


def nguoi_dang_giu(ma: str) -> str:
    """Tên người đang giữ, rỗng = đang ở kho."""
    ls = lich_su_ban_giao(ma)
    return ls[-1]["nguoi_giu"] if ls else ""


# ---------- tổng hợp ----------

def tong_hop(ds_nguoi: list[dict]) -> dict:
    """Số liệu cho trang + CẢNH BÁO những chỗ cần người xử lý.

    Hai cảnh báo có ích thật: người không còn trong danh sách nhân sự mà vẫn giữ
    tài sản (nghỉ việc chưa thu hồi), và tài sản số chưa có mã Vault (mật khẩu
    đang nằm ngoài két, hoặc chưa ai cất).
    """
    ds = doc_tai_san()
    ten_cua = {n["ten"]: n.get("ho_ten") or n["ten"] for n in ds_nguoi}

    dong, canh_bao = [], []
    giu: dict[str, int] = {}
    for d in ds:
        ai = nguoi_dang_giu(d["ma"])
        dong.append({**d, "nguoi_giu": ai,
                     "ho_ten_giu": ten_cua.get(ai, ai)})
        if d.get("tinh_trang") == "da_thanh_ly":
            continue
        if ai:
            giu[ai] = giu.get(ai, 0) + 1
            if ai not in ten_cua:
                canh_bao.append({"ma": d["ma"], "ten": d["ten"], "nguoi_giu": ai,
                                 "ly_do": f"'{ai}' không còn trong danh sách nhân sự "
                                          "mà vẫn đang giữ tài sản này."})
        if d["loai"] == "so" and not d.get("vault_id"):
            canh_bao.append({"ma": d["ma"], "ten": d["ten"], "nguoi_giu": "",
                             "ly_do": "Tài sản số chưa gắn mã Vault — mật khẩu "
                                      "chưa được cất trong két."})

    con = [d for d in ds if d.get("tinh_trang") != "da_thanh_ly"]
    return {
        "dong": sorted(dong, key=lambda d: (d["loai"], d.get("ten", ""))),
        "so_vat_ly": sum(1 for d in con if d["loai"] == "vat_ly"),
        "so_tai_san_so": sum(1 for d in con if d["loai"] == "so"),
        "nguyen_gia_vat_ly": round(sum(d.get("nguyen_gia") or 0 for d in con
                                       if d["loai"] == "vat_ly"), 2),
        "dang_o_kho": sum(1 for d in con
                          if d["loai"] == "vat_ly" and not nguoi_dang_giu(d["ma"])),
        "theo_nguoi": sorted(
            ({"tai_khoan": k, "ten": ten_cua.get(k, k), "so_tai_san": v}
             for k, v in giu.items()), key=lambda x: -x["so_tai_san"]),
        "canh_bao": canh_bao,
    }


def tai_san_cua(tai_khoan: str) -> list[dict]:
    """Người này đang giữ những gì — dùng khi làm thủ tục nghỉ việc."""
    return [d for d in doc_tai_san()
            if nguoi_dang_giu(d["ma"]) == tai_khoan
            and d.get("tinh_trang") != "da_thanh_ly"]
