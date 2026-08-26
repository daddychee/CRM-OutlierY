# -*- coding: utf-8 -*-
"""BẢNG LƯƠNG (D1) + CẢNH BÁO ĐI MUỘN (D6) — spec `docs/finance-hub-spec.md` mục 3.

Owner chốt 26/08/2026, và đây là những chỗ TUYỆT ĐỐI không được "tối ưu" lại:

- Chấm công CHỈ đo giờ CÓ MẶT (lần mở CRM đầu ngày). Trong phiên không đo —
  `cham_cong.bang_cong_thang()['tong_giay']` không dùng ở đây.
- **Máy KHÔNG tự trừ lương.** Lương = cơ bản × hệ số xếp loại + điều chỉnh HR.
  Không có hệ số công/ngày-làm-việc: một con số đo hiện diện trên hệ công cụ
  không đủ tư cách cắt tiền của ai (van trung thực của `cham_cong`).
- Đi muộn chỉ CẢNH BÁO (D6), không vào công thức.
- Thiếu xếp loại hoặc thiếu lương cơ bản → để trống kèm lý do, KHÔNG đoán, và
  người đó không vào tổng.

Sổ (đều chỉ-thêm, ghi nguyên tử):
  data/to-chuc/db/luong-co-ban.json      HR đặt, giữ lịch sử từng lần đặt
  data/to-chuc/db/dieu-chinh-luong.json  mỗi điều chỉnh một dòng, lý do bắt buộc
  data/to-chuc/db/bang-luong/<kỳ>.json   bản ĐÃ DUYỆT của kỳ
"""
from __future__ import annotations

import calendar
import csv
import json
import os
import threading
from datetime import date, datetime
from pathlib import Path

from src import cham_cong, kpi_danh_gia, tai_chinh

_APP_DIR = Path(__file__).resolve().parents[1]
_khoa = threading.Lock()

HE_SO_MAC_DINH = {"A": 1.10, "B": 1.00, "C": 0.90}
GIO_VAO_MAC_DINH = "08:30"
DUNG_SAI_MAC_DINH = 10        # phút
NGUONG_MUON_MAC_DINH = 5      # buổi/tháng thì gắn cờ cho HR


# ---------- luật ngoài code ----------

def _doc_csv(duong: Path) -> list[dict]:
    if not duong.is_file():
        return []
    with duong.open(encoding="utf-8-sig", newline="") as f:
        return [d for d in csv.DictReader(f)]


def doc_ngay_nghi_le() -> set[str]:
    """rules/ngay_nghi_le.csv — Owner tự thêm Tết, 30/4, 1/5, 2/9, Giỗ tổ."""
    p = Path(os.getenv("NGAY_NGHI_LE", _APP_DIR / "rules" / "ngay_nghi_le.csv"))
    ra = set()
    for d in _doc_csv(p):
        ngay = (d.get("ngay") or "").strip()
        try:
            date.fromisoformat(ngay)
        except ValueError:
            continue
        ra.add(ngay)
    return ra


def doc_he_so() -> dict[str, float]:
    """rules/he_so_xep_loai.csv — thiếu tệp thì dùng mặc định A/B/C."""
    p = Path(os.getenv("HE_SO_XEP_LOAI", _APP_DIR / "rules" / "he_so_xep_loai.csv"))
    ra = {}
    for d in _doc_csv(p):
        ma = (d.get("xep_loai") or "").strip().upper()
        try:
            ra[ma] = float(d.get("he_so"))
        except (TypeError, ValueError):
            continue
    return ra or dict(HE_SO_MAC_DINH)


def doc_gio_lam_viec() -> dict:
    """rules/gio_lam_viec.csv — giờ vào chuẩn + dung sai + ngưỡng nhắc."""
    p = Path(os.getenv("GIO_LAM_VIEC", _APP_DIR / "rules" / "gio_lam_viec.csv"))
    for d in _doc_csv(p):
        try:
            return {"gio_vao": (d.get("gio_vao") or GIO_VAO_MAC_DINH).strip(),
                    "dung_sai": int(d.get("dung_sai_phut") or DUNG_SAI_MAC_DINH),
                    "nguong": int(d.get("nguong_buoi") or NGUONG_MUON_MAC_DINH)}
        except (TypeError, ValueError):
            break
    return {"gio_vao": GIO_VAO_MAC_DINH, "dung_sai": DUNG_SAI_MAC_DINH,
            "nguong": NGUONG_MUON_MAC_DINH}


def ngay_lam_viec(ky: str) -> int:
    """Ngày làm việc của tháng: số ngày − chủ nhật − lễ. Lễ rơi vào Chủ nhật
    KHÔNG trừ hai lần (Owner chốt: công ty nghỉ Chủ nhật)."""
    nam, thang = int(ky[:4]), int(ky[5:7])
    so_ngay = calendar.monthrange(nam, thang)[1]
    le = doc_ngay_nghi_le()
    dem = 0
    for d in range(1, so_ngay + 1):
        ngay = date(nam, thang, d)
        if ngay.weekday() == 6:                 # chủ nhật
            continue
        if ngay.isoformat() in le:
            continue
        dem += 1
    return dem


# ---------- D6: đi muộn ----------

def _phut(gio: str) -> int | None:
    try:
        h, m = gio.split(":")[:2]
        return int(h) * 60 + int(m)
    except (AttributeError, ValueError):
        return None


def di_muon_thang(ky: str) -> dict[str, dict]:
    """{user: {so_buoi, tong_phut, muon_nhat, qua_nguong, chi_tiet}} — đo bằng
    LẦN MỞ CRM ĐẦU NGÀY. Ngày không mở CRM là VẮNG, không tính muộn."""
    lv = doc_gio_lam_viec()
    chuan = _phut(lv["gio_vao"]) or 0
    moc = chuan + lv["dung_sai"]      # quá mốc mới TÍNH là buổi muộn…
    ra: dict[str, dict] = {}
    for ngay, nguoi in sorted(cham_cong.doc_thang(ky).items()):
        for ten, d in nguoi.items():
            vao = d.get("vao") or ""
            p = _phut(vao)
            if p is None or p <= moc:
                continue
            m = ra.setdefault(ten, {"so_buoi": 0, "tong_phut": 0, "muon_nhat": "",
                                    "qua_nguong": False, "chi_tiet": []})
            m["so_buoi"] += 1
            m["tong_phut"] += p - chuan       # …nhưng phút muộn đếm từ GIỜ CHUẨN
            m["muon_nhat"] = max(m["muon_nhat"], vao)
            m["chi_tiet"].append({"ngay": ngay, "vao": vao, "tre_phut": p - chuan})
    for m in ra.values():
        m["qua_nguong"] = m["so_buoi"] > lv["nguong"]
    return ra


# ---------- lương cơ bản (HR đặt) ----------

def _duong(ten_tep: str) -> Path:
    return Path(os.getenv("LUONG_DIR", "nhan-su/luong")) / ten_tep


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


def dat_luong_co_ban(nguoi_dat: str, ten: str, so_tien) -> dict:
    """Chỉ-THÊM một lần đặt lương (giữ lịch sử ai đặt bao nhiêu, lúc nào)."""
    try:
        so_tien = float(so_tien)
    except (TypeError, ValueError):
        raise ValueError("Lương cơ bản phải là số.")
    if so_tien < 0:
        raise ValueError("Lương cơ bản không âm.")
    ban = {"ten": ten, "so_tien": so_tien, "nguoi_dat": nguoi_dat,
           "luc": datetime.now().isoformat(timespec="seconds")}
    with _khoa:
        p = _duong("luong-co-ban.json")
        ds = _doc_json(p, [])
        ds.append(ban)
        _ghi_json(p, ds)
    return ban


def luong_co_ban_hien_tai() -> dict[str, float]:
    """{user: lương} — bản ĐẶT SAU đè bản trước khi hiển thị (dữ liệu vẫn giữ)."""
    ra = {}
    for b in _doc_json(_duong("luong-co-ban.json"), []):
        ra[b.get("ten")] = float(b.get("so_tien") or 0)
    return ra


# ---------- điều chỉnh của HR (đường DUY NHẤT ảnh hưởng lương) ----------

def them_dieu_chinh(nguoi_nhap: str, ky: str, ten: str, so_tien, ly_do: str) -> dict:
    ly_do = (ly_do or "").strip()
    if not ly_do:
        raise ValueError("Điều chỉnh lương bắt buộc có lý do.")
    try:
        so_tien = float(so_tien)
    except (TypeError, ValueError):
        raise ValueError("Số tiền điều chỉnh phải là số.")
    ban = {"ky": ky, "ten": ten, "so_tien": so_tien, "ly_do": ly_do,
           "nguoi_nhap": nguoi_nhap,
           "luc": datetime.now().isoformat(timespec="seconds")}
    with _khoa:
        p = _duong("dieu-chinh-luong.json")
        ds = _doc_json(p, [])
        ds.append(ban)
        _ghi_json(p, ds)
    return ban


def dieu_chinh_ky(ky: str) -> dict[str, dict]:
    """{user: {so_tien, ly_do}} — bản mới nhất của kỳ."""
    ra = {}
    for b in _doc_json(_duong("dieu-chinh-luong.json"), []):
        if b.get("ky") == ky:
            ra[b.get("ten")] = {"so_tien": float(b.get("so_tien") or 0),
                                "ly_do": b.get("ly_do", "")}
    return ra


# ---------- bảng lương ----------

def bang_luong(ky: str, ds_nguoi: list[dict]) -> dict:
    """Bảng ĐỀ NGHỊ (đọc-tính, không ghi gì). Trả {ky, ngay_lam_viec, da_chot_cong,
    da_duyet, dong: [...], tong}."""
    cong = cham_cong.bang_cong_thang(ky)
    muon = di_muon_thang(ky)
    xep = kpi_danh_gia.moi_nhat_theo_nguoi(ky)
    he_so = doc_he_so()
    co_ban = luong_co_ban_hien_tai()
    dc = dieu_chinh_ky(ky)

    dong, tong = [], 0.0
    for n in ds_nguoi:
        ten = n.get("ten")
        xl = (xep.get(ten) or {}).get("xep_loai")
        hs = he_so.get(xl) if xl else None
        cb = co_ban.get(ten)
        d = dc.get(ten, {})
        thieu = ""
        if cb is None:
            thieu = "chưa có lương cơ bản"
        elif hs is None:
            thieu = "chưa có xếp loại kỳ này"
        thuc_nhan = None if thieu else round(cb * hs + d.get("so_tien", 0.0), 2)
        if thuc_nhan is not None:
            tong += thuc_nhan
        dong.append({
            "ten": ten, "ma": n.get("ma", ""), "ho_ten": n.get("ho_ten", ""),
            "vi_tri": n.get("vi_tri", ""), "bo_phan": n.get("bo_phan", ""),
            "cong_chot": cong.get(ten, {}).get("so_ngay", 0),
            "di_muon": muon.get(ten, {"so_buoi": 0, "tong_phut": 0,
                                      "qua_nguong": False}),
            "xep_loai": xl, "nhan_xet": (xep.get(ten) or {}).get("nhan_xet", ""),
            "he_so": hs, "luong_co_ban": cb,
            "dieu_chinh": d.get("so_tien"), "ly_do_dieu_chinh": d.get("ly_do", ""),
            "thuc_nhan": thuc_nhan, "thieu": thieu})
    return {"ky": ky, "ngay_lam_viec": ngay_lam_viec(ky),
            "da_chot_cong": cham_cong.doc_chot(ky) is not None,
            "da_duyet": doc_bang_luong(ky) is not None,
            "dong": dong, "tong": round(tong, 2)}


def doc_bang_luong(ky: str) -> dict | None:
    p = _duong(f"bang-luong/{ky}.json")
    return _doc_json(p, None) if p.is_file() else None


def duyet_bang_luong(nguoi_duyet: str, ky: str, ds_nguoi: list[dict],
                     muc_tieu: str, vi: str) -> dict:
    """Owner duyệt → ghi bản duyệt (chỉ-thêm, một lần một kỳ) RỒI sinh bút toán
    CHI-LUONG cho từng người đủ dữ liệu.

    Thứ tự có chủ đích: chặn hết điều kiện TRƯỚC, ghi bản duyệt, rồi mới ghi sổ
    tiền — sổ tiền là thứ không xóa được.
    """
    if not cham_cong.doc_chot(ky):
        raise ValueError(f"Kỳ {ky} chưa chốt công — chốt công trước khi duyệt lương.")
    if doc_bang_luong(ky) is not None:
        raise ValueError(f"Bảng lương kỳ {ky} đã duyệt rồi.")
    bang = bang_luong(ky, ds_nguoi)
    tra = [d for d in bang["dong"] if d["thuc_nhan"]]
    if not tra:
        raise ValueError("Không có dòng nào đủ dữ liệu để chi.")

    with _khoa:
        if doc_bang_luong(ky) is not None:
            raise ValueError(f"Bảng lương kỳ {ky} đã duyệt rồi.")
        ban = {"ky": ky, "nguoi_duyet": nguoi_duyet,
               "luc": datetime.now().isoformat(timespec="seconds"),
               "ngay_lam_viec": bang["ngay_lam_viec"], "tong": bang["tong"],
               "dong": bang["dong"]}
        _ghi_json(_duong(f"bang-luong/{ky}.json"), ban)

    for d in tra:
        tai_chinh.them_but_toan(
            nguoi_duyet, date.today().isoformat(), "CHI-LUONG", d["thuc_nhan"],
            muc_tieu, ghi_chu=f"lương kỳ {ky} — {d['ma'] or d['ten']}",
            vi=vi, nguon="luong")
    return ban


def don_gia_ngay(ky: str) -> dict[str, float]:
    """{user: đơn giá một ngày công} của kỳ ĐÃ DUYỆT — đầu vào của D3. Kỳ chưa
    duyệt → {} (không lấy lương dự kiến làm chi phí)."""
    ban = doc_bang_luong(ky)
    if not ban:
        return {}
    return {d["ten"]: round(d["thuc_nhan"] / d["cong_chot"], 2)
            for d in ban.get("dong", [])
            if d.get("thuc_nhan") and d.get("cong_chot")}


# ---------- D5: phiếu lương kèm báo cáo hiệu suất ----------

def du_lieu_phieu(ky: str, ten: str, kpi_nguon: dict | None = None,
                  ngach: list | None = None) -> dict | None:
    """Dữ liệu một phiếu — CHỈ lấy từ bảng lương ĐÃ DUYỆT (kỳ chưa duyệt thì
    không có phiếu nháp nào trôi ra ngoài). Không có người → None."""
    ban = doc_bang_luong(ky)
    if not ban:
        return None
    d = next((x for x in ban.get("dong", []) if x.get("ten") == ten), None)
    if d is None:
        return None
    return {"ky": ky, "dong": d, "ngay_lam_viec": ban.get("ngay_lam_viec"),
            "nguoi_duyet": ban.get("nguoi_duyet"), "duyet_luc": ban.get("luc"),
            "kpi": kpi_nguon or {}, "ngach": ngach or []}
