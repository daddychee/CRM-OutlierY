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

GỘP THUÊ BAO (Owner chốt 07/09): trước đây một thứ như Envato phải khai HAI lần
— một ở sổ tài sản, một ở sổ thuê bao — nên hai nguồn sự thật cho cùng một món,
và không bên nào biết bên kia. Nay chu kỳ trả phí là MẤY TRƯỜNG gắn thẳng vào
bản ghi tài sản; tab Thuê bao chỉ còn là khung nhìn lọc "món nào đang trả phí".

TÁCH ID VÀ MẬT KHẨU (Owner chốt 07/09): `tai_khoan` là ID đăng nhập, nằm THẲNG
trên sổ để tra cứu nhanh — biết ngay kênh này đăng nhập bằng email nào mà không
phải mở két. Mật khẩu vẫn CHỈ ở Vault, sổ này không bao giờ chứa.

CÂY CHA–CON: nghề nuôi kênh mất một email là mất cả chùm — kênh, GA, AdSense đều
đăng nhập bằng nó. Trường `dang_nhap_bang` trỏ về tài sản cha, nên xem một email
biết ngay nó đang đỡ những gì, và cảnh báo "chưa cất két" nói rõ kéo theo mấy
tài khoản.
"""
from __future__ import annotations

import json
import os
import secrets
import threading
from datetime import date, datetime, timedelta
from pathlib import Path

_khoa = threading.Lock()

LOAI = ("vat_ly", "so")
NHOM = {
    # vật lý
    "may_tinh": "Máy tính", "dien_thoai": "Điện thoại", "may_quay": "Máy quay",
    "man_hinh": "Màn hình", "thiet_bi_mang": "Thiết bị mạng",
    "o_cung": "Ổ cứng", "noi_that": "Nội thất", "khac_vl": "Khác (vật lý)",
    # số — email là GỐC của cả chùm nên đứng đầu
    "email": "Email", "kenh_youtube": "Kênh YouTube",
    "tai_khoan_quang_cao": "Tài khoản quảng cáo (AdSense/Ads)",
    "analytics": "Google Analytics", "tai_khoan_ai": "Tài khoản AI / API",
    "ten_mien": "Tên miền", "proxy_ip": "Proxy / IP",
    "phan_mem": "Phần mềm bản quyền", "khac_so": "Khác (số)",
}
CHU_KY = {"": 0, "thang": 1, "quy": 3, "nam": 12, "mot_lan": 0}   # số tháng
NHOM_VAT_LY = ("may_tinh", "dien_thoai", "may_quay", "man_hinh", "thiet_bi_mang",
               "o_cung", "noi_that", "khac_vl")
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
                ghi_chu: str = "", tai_khoan: str = "",
                dang_nhap_bang: str = "",
                phi=0, chu_ky: str = "", ngay_gia_han: str = "",
                tu_dong_gia_han: bool = True, danh_muc: str = "",
                vi: str = "") -> dict:
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

    # --- chu kỳ trả phí (gộp từ sổ thuê bao) ---
    chu_ky = (chu_ky or "").strip()
    if chu_ky not in CHU_KY:
        raise ValueError(f"Chu kỳ '{chu_ky}' không hợp lệ.")
    if chu_ky and chu_ky != "mot_lan":
        if not ngay_gia_han:
            raise ValueError("Có chu kỳ trả phí thì phải khai ngày gia hạn kế tiếp.")
        if not danh_muc:
            raise ValueError("Có chu kỳ trả phí thì phải chọn mã khoản để ghi bút toán.")
    if ngay_gia_han:
        date.fromisoformat(ngay_gia_han)
    try:
        phi = float(phi or 0)
    except (TypeError, ValueError):
        raise ValueError("Phí phải là số.")
    if phi < 0:
        raise ValueError("Phí không âm.")

    # --- cây cha–con: đăng nhập bằng tài khoản nào ---
    dang_nhap_bang = (dang_nhap_bang or "").strip()
    if dang_nhap_bang:
        if dang_nhap_bang == ma:
            raise ValueError("Tài sản không thể đăng nhập bằng chính nó.")
        if tim_tai_san(dang_nhap_bang) is None:
            raise ValueError(f"Không có tài sản mã '{dang_nhap_bang}' để làm tài khoản gốc.")
        if ma and _tao_vong(ma, dang_nhap_bang):
            raise ValueError("Trỏ như vậy tạo vòng lặp tài khoản gốc.")
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
               "tai_khoan": (tai_khoan or "").strip(),
               "dang_nhap_bang": dang_nhap_bang,
               "phi": phi, "chu_ky": chu_ky, "ngay_gia_han": ngay_gia_han,
               "tu_dong_gia_han": bool(tu_dong_gia_han),
               "danh_muc": (danh_muc or "").strip(), "vi": (vi or "").strip(),
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


def _tao_vong(ma: str, cha: str) -> bool:
    """Trỏ `ma` vào `cha` có tạo vòng lặp không (a→b→a)."""
    thay_roi, hien = set(), cha
    while hien:
        if hien == ma or hien in thay_roi:
            return True
        thay_roi.add(hien)
        d = tim_tai_san(hien)
        hien = (d or {}).get("dang_nhap_bang") or ""
    return False


def tai_khoan_con(ma: str) -> list[dict]:
    """Những tài khoản đăng nhập BẰNG tài sản này — mất nó là mất cả chùm."""
    return [d for d in doc_tai_san() if d.get("dang_nhap_bang") == ma]


# ---------- chu kỳ trả phí (gộp từ sổ thuê bao) ----------

def den_han(hom_nay: str = "", trong_ngay: int = 14) -> list[dict]:
    """Tài sản tới hạn trả phí trong N ngày, KỂ CẢ đã quá hạn (cờ qua_han) —
    quá hạn mà im lặng là mất tiền oan. Bỏ món đã thanh lý."""
    hom_nay = hom_nay or date.today().isoformat()
    moc = (date.fromisoformat(hom_nay) + timedelta(days=trong_ngay)).isoformat()
    ra = []
    for d in doc_tai_san():
        if d.get("tinh_trang") == "da_thanh_ly" or not d.get("chu_ky"):
            continue
        han = d.get("ngay_gia_han") or ""
        if not han or han > moc:
            continue
        ra.append({**d, "qua_han": han < hom_nay})
    return sorted(ra, key=lambda d: d.get("ngay_gia_han") or "")


def _phi_thang(d: dict) -> float:
    """Phí quy về MỘT tháng. Ngoại tệ quy VND theo tỷ giá sổ; chưa có tỷ giá → 0
    (không đoán). Chu kỳ một-lần → 0 vì không phải chi phí lặp."""
    so_thang = CHU_KY.get(d.get("chu_ky") or "", 0)
    if not so_thang:
        return 0.0
    phi = float(d.get("phi") or 0) / so_thang
    tt = (d.get("tien_te") or "VND").upper()
    if tt == "VND":
        return phi
    from src import tai_chinh
    tg = tai_chinh.ty_gia_ngay(date.today().isoformat(), tt)
    return phi * tg["gia"] if tg else 0.0


def chi_dinh_ky_thang() -> float:
    """Tổng chi định kỳ mỗi tháng (VND) — món đang dùng và sắp bỏ."""
    return round(sum(_phi_thang(d) for d in doc_tai_san()
                     if d.get("tinh_trang") in ("dang_dung", "dang_sua")), 2)


def day_gia_han(ma: str) -> dict:
    """Sau khi đã ghi bút toán kỳ này thì đẩy hạn sang kỳ kế tiếp."""
    with _khoa:
        ds = doc_tai_san()
        d = next((x for x in ds if x.get("ma") == ma), None)
        if d is None:
            raise ValueError(f"Không có tài sản mã '{ma}'.")
        so_thang = CHU_KY.get(d.get("chu_ky") or "", 0)
        if so_thang and d.get("ngay_gia_han"):
            cu = date.fromisoformat(d["ngay_gia_han"])
            th = cu.month - 1 + so_thang
            nam = cu.year + th // 12
            th = th % 12 + 1
            ngay = min(cu.day, [31, 29 if nam % 4 == 0 else 28, 31, 30, 31, 30,
                                31, 31, 30, 31, 30, 31][th - 1])
            d["ngay_gia_han"] = date(nam, th, ngay).isoformat()
        _ghi_json(_duong("tai-san.json"), ds)
    return d


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
        cha = tim_tai_san(d.get("dang_nhap_bang") or "") if d.get("dang_nhap_bang") else None
        dong.append({**d, "nguoi_giu": ai,
                     "ho_ten_giu": ten_cua.get(ai, ai),
                     "so_con": len(tai_khoan_con(d["ma"])),
                     "ten_cha": (cha or {}).get("tai_khoan") or (cha or {}).get("ten", "")})
        if d.get("tinh_trang") == "da_thanh_ly":
            continue
        if ai:
            giu[ai] = giu.get(ai, 0) + 1
            if ai not in ten_cua:
                canh_bao.append({"ma": d["ma"], "ten": d["ten"], "nguoi_giu": ai,
                                 "ly_do": f"'{ai}' không còn trong danh sách nhân sự "
                                          "mà vẫn đang giữ tài sản này."})
        if d["loai"] == "so" and not d.get("vault_id"):
            n_con = len(tai_khoan_con(d["ma"]))
            them = (f" Đang là tài khoản gốc của {n_con} tài khoản khác — "
                    "mất nó là mất cả chùm." if n_con else "")
            canh_bao.append({"ma": d["ma"], "ten": d["ten"], "nguoi_giu": "",
                             "ly_do": "Tài sản số chưa gắn mã Vault — mật khẩu "
                                      "chưa được cất trong két." + them})

    con = [d for d in ds if d.get("tinh_trang") != "da_thanh_ly"]
    return {
        "dong": sorted(dong, key=lambda d: (d["loai"], d.get("ten", ""))),
        "so_vat_ly": sum(1 for d in con if d["loai"] == "vat_ly"),
        "so_tai_san_so": sum(1 for d in con if d["loai"] == "so"),
        "nguyen_gia_vat_ly": round(sum(d.get("nguyen_gia") or 0 for d in con
                                       if d["loai"] == "vat_ly"), 2),
        "chi_dinh_ky": chi_dinh_ky_thang(),
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
