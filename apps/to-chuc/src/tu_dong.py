# -*- coding: utf-8 -*-
"""TỰ ĐỘNG: B5 đối soát AdSense · C3 tiền API từ quota log · C2 luật gợi ý.

Ba việc khác nhau nhưng chung một nguyên tắc, và đó là lý do gom một chỗ:
**máy chỉ ĐỀ NGHỊ, người CHỐT.** Không hàm nào ở đây tự ghi vào sổ tiền — chúng
dựng bản nháp, route đợi người bấm duyệt rồi mới gọi `tai_chinh.them_but_toan`.

Nguồn (CHỈ ĐỌC):
  CSV chi trả của Google  — người tải về rồi nạp lên
  nen/common/quota_log    — từng lượt gọi API ngoài (app, việc, khóa, lượt)
  rules/luat_goi_y.csv    — luật gợi ý phân loại, sửa bằng Excel
"""
from __future__ import annotations

import csv
import io
import json
import os
import re
import unicodedata
from datetime import date
from pathlib import Path

from nen.common import danh_ba

from src import tai_chinh

_APP_DIR = Path(__file__).resolve().parents[1]


def _khong_dau(s: str) -> str:
    s = unicodedata.normalize("NFD", str(s or "").lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


# ══════════════ B5 — đối soát chi trả AdSense ══════════════

_COT_KENH = ("channel", "kênh", "kenh", "channel name", "tên kênh")
_COT_TIEN = ("amount", "earnings", "payment", "số tiền", "so tien", "doanh thu")


def _tim_cot(dau: list[str], ung_vien: tuple) -> str | None:
    for c in dau:
        if _khong_dau(c).strip() in [_khong_dau(u) for u in ung_vien]:
            return c
    return None


def doi_soat_adsense(noi_dung_csv: str, thang: str) -> dict:
    """CSV chi trả của Google → bảng nháp: khớp tên kênh với danh bạ, so tiền
    thật với doanh thu ƯỚC TÍNH đã ghi trong kỳ.

    Khớp tên: so không dấu, không phân biệt hoa thường. Không khớp → để trống
    `kenh_ma` cho người chọn, TUYỆT ĐỐI không đoán bừa.
    """
    doc = csv.DictReader(io.StringIO(noi_dung_csv))
    dau = doc.fieldnames or []
    c_kenh, c_tien = _tim_cot(dau, _COT_KENH), _tim_cot(dau, _COT_TIEN)
    if not c_kenh or not c_tien:
        raise ValueError(
            "Tệp không có cột tên kênh và số tiền — cần cột dạng Channel / Amount.")

    ds_kenh = danh_ba.liet_ke("kenh")
    theo_ten = {_khong_dau(k.get("ten_chuan", "")): k["ma"] for k in ds_kenh if k.get("ten_chuan")}
    # doanh thu ước tính đã ghi trong kỳ, gộp theo kênh
    uoc_tinh: dict[str, float] = {}
    for b in tai_chinh.doc_so():
        if (b.get("ngay") or "")[:7] != thang or b.get("danh_muc") != "THU-ADS":
            continue
        ma = b.get("kenh_ma") or ""
        uoc_tinh[ma] = uoc_tinh.get(ma, 0.0) + float(b.get("so_tien") or 0)

    dong = []
    for r in doc:
        ten = (r.get(c_kenh) or "").strip()
        if not ten:
            continue
        try:
            tien = float(str(r.get(c_tien) or "0").replace(",", "").strip())
        except ValueError:
            continue
        ma = theo_ten.get(_khong_dau(ten), "")
        ut = uoc_tinh.get(ma) if ma else None
        dong.append({"ten_trong_tep": ten, "kenh_ma": ma, "chac_chan": bool(ma),
                     "uoc_tinh": ut, "tien_that": tien,
                     "chenh": round(tien - ut, 2) if ut is not None else None})
    return {"thang": thang, "dong": dong,
            "tong_that": round(sum(d["tien_that"] for d in dong), 2)}


def duyet_doi_soat(nguoi: str, dong: list[dict], thang: str, muc_tieu: str,
                   vi: str) -> list[dict]:
    """Người chốt xong mới ghi sổ. Mỗi dòng một bút toán THU-ADS trạng thái
    'đã về ví' — số tiền THẬT, không phải ước tính."""
    ra = []
    for d in dong:
        ma = (d.get("kenh_ma") or "").strip()
        tien = float(d.get("tien_that") or 0)
        if tien <= 0:
            continue
        ra.append(tai_chinh.them_but_toan(
            nguoi, date.today().isoformat(), "THU-ADS", tien, muc_tieu,
            kenh_ma=ma, ghi_chu=f"chi trả AdSense kỳ {thang}", vi=vi,
            nguon="adsense", trang_thai_thu="da_ve_vi"))
    return ra


# ══════════════ C3 — tiền API từ nhật ký quota ══════════════

def _duong_don_gia() -> Path:
    return Path(os.getenv("DON_GIA_API_PATH", "nhan-su/don-gia-api.json"))


def doc_don_gia() -> dict[str, float]:
    p = _duong_don_gia()
    if not p.is_file():
        return {}
    try:
        du = json.loads(p.read_text(encoding="utf-8"))
        return {k: float(v) for k, v in du.items()} if isinstance(du, dict) else {}
    except (ValueError, TypeError):
        return {}


def dat_don_gia(api: str, usd_moi_luot) -> dict[str, float]:
    """Đơn giá mỗi lượt gọi, theo API. Luật ngoài code (sổ JSON sửa được)."""
    try:
        gia = float(usd_moi_luot)
    except (TypeError, ValueError):
        raise ValueError("Đơn giá phải là số.")
    if gia < 0:
        raise ValueError("Đơn giá không âm.")
    ds = doc_don_gia()
    ds[api] = gia
    p = _duong_don_gia()
    p.parent.mkdir(parents=True, exist_ok=True)
    tam = p.with_name(p.name + ".tmp")
    tam.write_text(json.dumps(ds, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tam, p)
    return ds


def _doc_quota_thang(thang: str) -> list[dict]:
    """Gộp log cả tháng (quota_log.doc() chỉ đọc một ngày)."""
    goc = Path(os.getenv("LOGS_DIR", "logs")) / "quota" / thang[:4] / thang[5:7]
    if not goc.is_dir():
        return []
    ra = []
    for p in sorted(goc.glob("*.log")):
        for dong in p.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                d = json.loads(dong)
            except ValueError:
                continue
            if isinstance(d, dict) and d.get("api"):
                ra.append(d)
    return ra


def tien_api_thang(thang: str) -> dict:
    """Quy lượt gọi API thành tiền, gộp theo app + việc.

    API chưa khai đơn giá → `thanh_tien_usd=None` kèm lý do, và KHÔNG cộng vào
    tổng: một con số không biết thì không được lẫn vào con số biết.
    """
    don_gia = doc_don_gia()
    gom: dict[tuple, dict] = {}
    for d in _doc_quota_thang(thang):
        khoa = (d.get("app", ""), d.get("viec", ""), d.get("api", ""))
        m = gom.setdefault(khoa, {"app": khoa[0], "viec": khoa[1], "api": khoa[2],
                                  "luot": 0, "quota_tieu": 0})
        m["luot"] += int(d.get("luot") or 0)
        m["quota_tieu"] += int(d.get("quota_tieu") or 0)

    dong, tong = [], 0.0
    for m in sorted(gom.values(), key=lambda x: (-x["luot"], x["app"])):
        gia = don_gia.get(m["api"])
        if gia is None:
            m["thanh_tien_usd"] = None
            m["thieu"] = f"chưa có đơn giá cho API '{m['api']}'"
        else:
            m["thanh_tien_usd"] = round(m["luot"] * gia, 4)
            m["thieu"] = ""
            tong += m["thanh_tien_usd"]
        dong.append(m)
    return {"thang": thang, "dong": dong, "tong_usd": round(tong, 4),
            "thieu_don_gia": [m["api"] for m in dong if m["thanh_tien_usd"] is None]}


def ghi_tien_api(nguoi: str, thang: str, muc_tieu: str, vi: str) -> dict:
    """MỘT bút toán tổng hợp cho cả tháng; chi tiết vẫn nằm ở bảng quota.
    Ghi hai lần cùng kỳ bị chặn — không chi đôi."""
    kq = tien_api_thang(thang)
    if kq["tong_usd"] <= 0:
        raise ValueError("Kỳ này chưa có lượt gọi API nào tính được thành tiền.")
    dau = f"tiền API kỳ {thang}"
    if any(b.get("nguon") == "quota" and dau in (b.get("ghi_chu") or "")
           for b in tai_chinh.doc_so()):
        raise ValueError(f"Tiền API kỳ {thang} đã ghi rồi.")
    return tai_chinh.them_but_toan(
        nguoi, date.today().isoformat(), "CHI-API", kq["tong_usd"], muc_tieu,
        ghi_chu=f"{dau} — {len(kq['dong'])} nhóm việc", vi=vi, nguon="quota")


# ══════════════ C2 — luật gợi ý phân loại ══════════════

def doc_luat_goi_y() -> list[dict]:
    """rules/luat_goi_y.csv: khop (nhiều từ cách nhau bằng ;) → danh_muc, vi, kenh_ma."""
    p = Path(os.getenv("LUAT_GOI_Y", _APP_DIR / "rules" / "luat_goi_y.csv"))
    if not p.is_file():
        return []
    ra = []
    with p.open(encoding="utf-8-sig", newline="") as f:
        for d in csv.DictReader(f):
            khop = [x.strip() for x in (d.get("khop") or "").split(";") if x.strip()]
            if khop:
                ra.append({"khop": khop, "danh_muc": (d.get("danh_muc") or "").strip(),
                           "vi": (d.get("vi") or "").strip(),
                           "kenh_ma": (d.get("kenh_ma") or "").strip()})
    return ra


def goi_y(ghi_chu: str) -> dict:
    """Luật ĐẦU TIÊN khớp thì trả gợi ý. Chỉ để ĐIỀN SẴN ô trong form — người
    ghi sửa được, không áp thầm. Không khớp → {} (im lặng)."""
    van = _khong_dau(ghi_chu)
    for luat in doc_luat_goi_y():
        if any(_khong_dau(k) in van for k in luat["khop"]):
            return {k: v for k, v in luat.items() if k != "khop" and v}
    return {}
