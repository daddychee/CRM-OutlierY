# -*- coding: utf-8 -*-
"""SỔ THU CHI + MỤC TIÊU + DANH MỤC (Finance Hub, DE.md mục 10 + 13.6).

Bất biến (luật toàn cục Owner 16/08):
- SỐ TIỀN là DỮ LIỆU BẢO QUẢN LÂU DÀI: sổ data/to-chuc/db/so-thu-chi/YYYY.jsonl
  CHỈ-THÊM — không sửa/xóa dòng đã ghi; sửa sai = BÚT TOÁN ĐẢO (loai='dao', số
  tiền âm, tham_chieu id gốc) — sổ luôn kể được chuyện gì đã xảy ra.
- Mọi bút toán GẮN MỤC TIÊU (dropdown từ sổ muc-tieu.json) + kênh TỪ DANH BẠ ĐẾ
  (nen.common.danh_ba — app không tự đẻ sổ kênh, luật phân công DE.md mục 2);
  kenh_ma rỗng = 'chung hệ' (chi phí/thu không thuộc kênh nào).
- Danh mục khoản = LUẬT NGOÀI CODE: rules/danh_muc_thu_chi.csv (user sửa Excel).

Ghi sổ: append MỘT dòng JSON dưới khóa tiến trình — append-only giữ nguyên mọi
dòng cũ (không rewrite cả file như tmp+replace nên không có cửa mất dòng);
reader bỏ qua dòng hỏng (dở dang do mất điện) — khuôn phan_hoi.csv/jobs_log hệ cũ.
"""
from __future__ import annotations

import csv
import json
import os
import secrets
import threading
from datetime import date, datetime
from pathlib import Path

from nen.common import danh_ba

_APP_DIR = Path(__file__).resolve().parents[1]
_khoa = threading.Lock()

KENH_CHUNG = ""          # kenh_ma rỗng = bút toán 'chung hệ'
LOAI = ("thu", "chi", "dao")
TRANG_THAI_MT = ("dang_chay", "tam_dung", "xong")


# ---------- danh mục khoản (rules CSV — luật ngoài code) ----------

def _duong_danh_muc() -> Path:
    return Path(os.getenv("DANH_MUC_THU_CHI",
                          _APP_DIR / "rules" / "danh_muc_thu_chi.csv"))


def doc_danh_muc() -> list[dict]:
    """[{ma, ten, loai, ghi_chu}] từ CSV — utf-8-sig cho Excel; dòng thiếu mã/loại
    lạ bị bỏ qua (đọc khoan dung, không vỡ trang vì một dòng Excel gõ hỏng)."""
    p = _duong_danh_muc()
    if not p.is_file():
        return []
    ra = []
    with p.open(encoding="utf-8-sig", newline="") as f:
        for d in csv.DictReader(f):
            ma = (d.get("ma") or "").strip()
            loai = (d.get("loai") or "").strip().lower()
            if ma and loai in ("thu", "chi"):
                ra.append({"ma": ma, "ten": (d.get("ten") or "").strip(),
                           "loai": loai, "ghi_chu": (d.get("ghi_chu") or "").strip()})
    return ra


def _loai_theo_ma() -> dict[str, str]:
    return {d["ma"]: d["loai"] for d in doc_danh_muc()}


# ---------- sổ mục tiêu (muc-tieu.json — ghi nguyên tử) ----------

def _duong_muc_tieu() -> Path:
    return Path(os.getenv("MUC_TIEU_PATH", "nhan-su/muc-tieu.json"))


def doc_muc_tieu() -> list[dict]:
    p = _duong_muc_tieu()
    if not p.is_file():
        return []
    try:
        du = json.loads(p.read_text(encoding="utf-8"))
        return du if isinstance(du, list) else []
    except ValueError:
        return []


def them_muc_tieu(ten: str, ngan_sach: float, trang_thai: str = "dang_chay") -> dict:
    ten = (ten or "").strip()
    if not ten:
        raise ValueError("Thiếu tên mục tiêu.")
    if trang_thai not in TRANG_THAI_MT:
        raise ValueError("Trạng thái mục tiêu không hợp lệ.")
    try:
        ngan_sach = float(ngan_sach)
    except (TypeError, ValueError):
        raise ValueError("Ngân sách phải là số.")
    if ngan_sach < 0:
        raise ValueError("Ngân sách không âm.")
    with _khoa:
        ds = doc_muc_tieu()
        if any(m.get("ten") == ten for m in ds):
            raise ValueError(f"Mục tiêu '{ten}' đã có rồi.")
        ban = {"ten": ten, "ngan_sach": ngan_sach, "trang_thai": trang_thai,
               "tao_luc": datetime.now().isoformat(timespec="seconds")}
        ds.append(ban)
        p = _duong_muc_tieu()
        p.parent.mkdir(parents=True, exist_ok=True)
        tam = p.with_name(p.name + ".tmp")
        tam.write_text(json.dumps(ds, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tam, p)
    return ban


# ---------- sổ thu chi (JSONL theo năm — CHỈ-THÊM) ----------

def _thu_muc_so() -> Path:
    return Path(os.getenv("SO_THU_CHI_DIR", "nhan-su/so-thu-chi"))


def doc_so(nam: str | None = None) -> list[dict]:
    """Đọc sổ (một năm hoặc mọi năm), theo thứ tự ghi. Dòng hỏng bị bỏ qua."""
    thu_muc = _thu_muc_so()
    if not thu_muc.is_dir():
        return []
    ra: list[dict] = []
    for p in sorted(thu_muc.glob("*.jsonl")):
        if nam and p.stem != nam:
            continue
        for dong in p.read_text(encoding="utf-8", errors="replace").splitlines():
            if not dong.strip():
                continue
            try:
                b = json.loads(dong)
            except ValueError:
                continue
            if isinstance(b, dict) and b.get("id"):
                ra.append(b)
    return ra


def tim_but_toan(id_bt: str) -> dict | None:
    for b in doc_so():
        if b.get("id") == id_bt:
            return b
    return None


def _ghi_dong(b: dict) -> None:
    p = _thu_muc_so() / f"{b['ngay'][:4]}.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(b, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())


def _kenh_hop_le(kenh_ma: str) -> bool:
    return any(k.get("ma") == kenh_ma for k in danh_ba.liet_ke("kenh"))


def them_but_toan(nguoi_ghi: str, ngay: str, danh_muc: str, so_tien,
                  muc_tieu: str, kenh_ma: str = KENH_CHUNG, chung_tu: str = "",
                  ghi_chu: str = "") -> dict:
    """Ghi MỘT bút toán mới. loai suy từ DANH MỤC (dropdown quyết thu/chi — không
    có cửa chọn lệch); mục tiêu BẮT BUỘC tồn tại (DE.md 13.6); kênh phải có trong
    danh bạ đế hoặc rỗng = chung hệ."""
    try:
        date.fromisoformat(ngay)
    except (TypeError, ValueError):
        raise ValueError("Ngày bút toán phải dạng YYYY-MM-DD.")
    loai = _loai_theo_ma().get((danh_muc or "").strip())
    if loai is None:
        raise ValueError(f"Danh mục '{danh_muc}' không có trong rules/danh_muc_thu_chi.csv.")
    try:
        so_tien = float(so_tien)
    except (TypeError, ValueError):
        raise ValueError("Số tiền phải là số.")
    if so_tien <= 0:
        raise ValueError("Số tiền phải lớn hơn 0 (âm chỉ dành cho bút toán đảo).")
    muc_tieu = (muc_tieu or "").strip()
    if not any(m.get("ten") == muc_tieu for m in doc_muc_tieu()):
        raise ValueError(f"Mục tiêu '{muc_tieu}' chưa có trong sổ mục tiêu.")
    kenh_ma = (kenh_ma or "").strip()
    if kenh_ma and not _kenh_hop_le(kenh_ma):
        raise ValueError(f"Kênh '{kenh_ma}' không có trong danh bạ đế.")
    b = {"id": f"BT-{datetime.now():%y%m%d%H%M%S}-{secrets.token_hex(2)}",
         "ngay": ngay, "loai": loai, "danh_muc": danh_muc.strip(),
         "so_tien": so_tien, "muc_tieu": muc_tieu, "kenh_ma": kenh_ma,
         "nguoi_ghi": nguoi_ghi, "chung_tu": (chung_tu or "").strip()[:200],
         "ghi_chu": (ghi_chu or "").strip()[:500],
         "tao_luc": datetime.now().isoformat(timespec="seconds")}
    with _khoa:
        _ghi_dong(b)
    return b


def dao_but_toan(nguoi_ghi: str, id_goc: str, ghi_chu: str = "") -> dict:
    """BÚT TOÁN ĐẢO — cách sửa DUY NHẤT của sổ chỉ-thêm: sinh dòng mới loai='dao'
    số tiền ÂM tham chiếu id gốc; dòng gốc không đụng một byte. Chặn đảo đúp và
    đảo-của-đảo (đảo hai lần = hủy hai lần — sai bản chất)."""
    goc = tim_but_toan(id_goc)
    if goc is None:
        raise ValueError(f"Không có bút toán id '{id_goc}'.")
    if goc.get("loai") == "dao":
        raise ValueError("Không đảo bút toán đảo — ghi bút toán mới nếu cần.")
    with _khoa:
        if any(b.get("tham_chieu") == id_goc for b in doc_so()):
            raise ValueError(f"Bút toán '{id_goc}' đã có bút toán đảo rồi.")
        b = {"id": f"BT-{datetime.now():%y%m%d%H%M%S}-{secrets.token_hex(2)}",
             "ngay": date.today().isoformat(), "loai": "dao",
             "danh_muc": goc.get("danh_muc", ""), "so_tien": -float(goc.get("so_tien", 0)),
             "muc_tieu": goc.get("muc_tieu", ""), "kenh_ma": goc.get("kenh_ma", ""),
             "nguoi_ghi": nguoi_ghi, "chung_tu": "", "tham_chieu": id_goc,
             "ghi_chu": (ghi_chu or "").strip() or f"Đảo bút toán {id_goc}",
             "tao_luc": datetime.now().isoformat(timespec="seconds")}
        _ghi_dong(b)
    return b


# ---------- tổng hợp (đọc-tính, không ghi) ----------

def _phia(b: dict, loai_map: dict[str, str]) -> str | None:
    """Bút toán rơi vào bên THU hay CHI: theo LOẠI của danh mục (bút toán đảo
    mang danh mục gốc nên số âm tự trừ đúng bên); danh mục lạ → theo loai dòng;
    không xếp được → None (bỏ khỏi tổng, không đoán)."""
    l = loai_map.get(b.get("danh_muc", ""))
    if l in ("thu", "chi"):
        return l
    return b.get("loai") if b.get("loai") in ("thu", "chi") else None


def tong_thang(thang: str) -> dict:
    """{'thu': x, 'chi': y} của một tháng (YYYY-MM) — đã trừ bút toán đảo."""
    loai_map = _loai_theo_ma()
    ra = {"thu": 0.0, "chi": 0.0}
    for b in doc_so():
        if (b.get("ngay") or "")[:7] != thang:
            continue
        phia = _phia(b, loai_map)
        if phia:
            ra[phia] += float(b.get("so_tien") or 0)
    return ra


def tong_hop_danh_muc(thang: str) -> dict[str, dict]:
    """{ma danh mục: {thang: tổng tháng chọn, luy_ke: tổng mọi thời}} từ sổ."""
    ra: dict[str, dict] = {}
    for b in doc_so():
        dm = b.get("danh_muc", "")
        if not dm:
            continue
        m = ra.setdefault(dm, {"thang": 0.0, "luy_ke": 0.0})
        tien = float(b.get("so_tien") or 0)
        m["luy_ke"] += tien
        if (b.get("ngay") or "")[:7] == thang:
            m["thang"] += tien
    return ra


def tong_hop_muc_tieu() -> dict[str, dict]:
    """{tên mục tiêu: {da_chi, da_thu}} mọi thời — bút toán đảo tự trừ."""
    loai_map = _loai_theo_ma()
    ra: dict[str, dict] = {}
    for b in doc_so():
        mt = b.get("muc_tieu", "")
        if not mt:
            continue
        m = ra.setdefault(mt, {"da_chi": 0.0, "da_thu": 0.0})
        phia = _phia(b, loai_map)
        if phia == "thu":
            m["da_thu"] += float(b.get("so_tien") or 0)
        elif phia == "chi":
            m["da_chi"] += float(b.get("so_tien") or 0)
    return ra


def pnl_theo_kenh(thang: str) -> dict[str, dict]:
    """Lãi/lỗ theo kênh một tháng: {kenh_ma ('' = chung hệ): {thu, chi}}."""
    loai_map = _loai_theo_ma()
    ra: dict[str, dict] = {}
    for b in doc_so():
        if (b.get("ngay") or "")[:7] != thang:
            continue
        phia = _phia(b, loai_map)
        if not phia:
            continue
        m = ra.setdefault(b.get("kenh_ma", "") or KENH_CHUNG, {"thu": 0.0, "chi": 0.0})
        m[phia] += float(b.get("so_tien") or 0)
    return ra
