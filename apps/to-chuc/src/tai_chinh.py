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
import re
import secrets
import threading
import urllib.request
from datetime import date, datetime
from pathlib import Path

from nen.common import danh_ba

_APP_DIR = Path(__file__).resolve().parents[1]
_khoa = threading.Lock()

KENH_CHUNG = ""          # kenh_ma rỗng = bút toán 'chung hệ'
LOAI = ("thu", "chi", "dao")
LOAI_VI = ("vi_dien_tu", "ngan_hang", "quy", "phai_thu")   # phai_thu KHÔNG là tiền khả dụng
DONG_VAN_HANH = "VND"          # A2 — mọi tổng hợp quy về đây
DUOI_CHUNG_TU = (".jpg", ".jpeg", ".png", ".webp", ".pdf")   # A3
TRAN_TEP = 10 * 1024 * 1024    # 10 MB mỗi tệp
TRAN_SO_TEP = 5
TY_GIA_TIMEOUT = 8             # giây; KHÔNG retry ngầm (bài học SDK 19/07 + 06/08)
VCB_URL = "https://www.vietcombank.com.vn/api/exchangerates?date=now"
ER_API_URL = "https://open.er-api.com/v6/latest/"
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


# ---------- danh mục ví (A1 — rules CSV, luật ngoài code) ----------

def _duong_danh_muc_vi() -> Path:
    return Path(os.getenv("DANH_MUC_VI",
                          _APP_DIR / "rules" / "danh_muc_vi.csv"))


def doc_danh_muc_vi() -> list[dict]:
    """[{ma, ten, loai, tien_te, ghi_chu}] — loai ∈ LOAI_VI; dòng thiếu mã hoặc
    loại lạ bị bỏ qua (đọc khoan dung như doc_danh_muc)."""
    p = _duong_danh_muc_vi()
    if not p.is_file():
        return []
    ra = []
    with p.open(encoding="utf-8-sig", newline="") as f:
        for d in csv.DictReader(f):
            ma = (d.get("ma") or "").strip()
            loai = (d.get("loai") or "").strip().lower()
            if ma and loai in LOAI_VI:
                ra.append({"ma": ma, "ten": (d.get("ten") or "").strip(),
                           "loai": loai,
                           "tien_te": (d.get("tien_te") or "VND").strip().upper(),
                           "ghi_chu": (d.get("ghi_chu") or "").strip()})
    return ra


def _vi_theo_ma() -> dict[str, dict]:
    return {d["ma"]: d for d in doc_danh_muc_vi()}


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
                  ghi_chu: str = "", vi: str = "", ty_gia=None,
                  tep_dinh_kem: list | None = None) -> dict:
    """Ghi MỘT bút toán mới. loai suy từ DANH MỤC (dropdown quyết thu/chi — không
    có cửa chọn lệch); mục tiêu BẮT BUỘC tồn tại (DE.md 13.6); kênh phải có trong
    danh bạ đế hoặc rỗng = chung hệ; VÍ bắt buộc (A1 — tiền phải biết nằm ở đâu)."""
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
    vi = (vi or "").strip()
    vi_map = _vi_theo_ma()
    if vi not in vi_map:
        raise ValueError(f"Ví '{vi}' không có trong rules/danh_muc_vi.csv.")
    # A2 — tiền tệ suy từ VÍ (một nguồn sự thật, không có cửa khai lệch)
    tien_te = vi_map[vi]["tien_te"]
    nguon_tg = ""
    if tien_te == DONG_VAN_HANH:
        ty_gia = 1.0
    elif ty_gia:
        ty_gia = float(ty_gia)
        nguon_tg = "tay"
    else:
        tg = ty_gia_ngay(ngay, tien_te)
        if tg is None:
            raise ValueError(
                f"Chưa có tỷ giá {tien_te} cho ngày {ngay} — lấy tỷ giá hoặc nhập tay.")
        ty_gia, nguon_tg = tg["gia"], tg["nguon"]
    if ty_gia <= 0:
        raise ValueError("Tỷ giá phải lớn hơn 0.")
    b = {"id": f"BT-{datetime.now():%y%m%d%H%M%S}-{secrets.token_hex(2)}",
         "ngay": ngay, "loai": loai, "danh_muc": danh_muc.strip(),
         "so_tien": so_tien, "muc_tieu": muc_tieu, "kenh_ma": kenh_ma,
         "vi": vi, "tien_te": tien_te, "ty_gia": ty_gia, "nguon_ty_gia": nguon_tg,
         "tep_dinh_kem": list(tep_dinh_kem or []),
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
             "vi": goc.get("vi", ""), "tep_dinh_kem": list(goc.get("tep_dinh_kem") or []),
             "tien_te": goc.get("tien_te", DONG_VAN_HANH),
             "ty_gia": goc.get("ty_gia", 1.0), "nguon_ty_gia": goc.get("nguon_ty_gia", ""),
             "nguoi_ghi": nguoi_ghi, "chung_tu": "", "tham_chieu": id_goc,
             "ghi_chu": (ghi_chu or "").strip() or f"Đảo bút toán {id_goc}",
             "tao_luc": datetime.now().isoformat(timespec="seconds")}
        _ghi_dong(b)
    return b


# ---------- kho chứng từ (A3 — tệp cạnh sổ, khuôn kho tài liệu hồ sơ) ----------

def thu_muc_chung_tu(id_bt: str) -> Path:
    """<CHUNG_TU_DIR>/<năm>/<id>. id đã do máy sinh (BT-yymmddHHMMSS-xxxx) nên
    an toàn, vẫn lọc ký tự lạ phòng gọi từ chỗ khác."""
    id_sach = re.sub(r"[^0-9A-Za-z-]", "", id_bt)[:40] or "khong-ro"
    nam = id_sach[3:5] if id_sach.startswith("BT-") else ""
    goc = Path(os.getenv("CHUNG_TU_DIR", "nhan-su/chung-tu"))
    return goc / (f"20{nam}" if nam.isdigit() else "khac") / id_sach


def _ten_tep_sach(ten: str) -> str:
    """Bỏ đường dẫn + ký tự cấm của Windows; GIỮ dấu tiếng Việt (bài học đặt tên
    tệp của module nhập liệu)."""
    ten = str(ten).replace("\\", "/").split("/")[-1]
    ten = re.sub(r'[<>:"|?*\x00-\x1f]', "", ten).strip(" .")
    return ten[:120] or "tep"


def kiem_tep(tep: list) -> list:
    """[(tên, bytes)] → [(tên đã dọn, bytes)]; KHÔNG ghi gì. Validate ở trust
    boundary: đuôi cho phép, trần 10 MB mỗi tệp, tối đa 5 tệp. Route gọi hàm này
    TRƯỚC khi ghi sổ để tệp sai không kịp đẻ dòng rác."""
    if len(tep) > TRAN_SO_TEP:
        raise ValueError(f"Tối đa {TRAN_SO_TEP} tệp mỗi bút toán.")
    sach = []
    for ten, du_lieu in tep:
        ten = _ten_tep_sach(ten)
        if not ten.lower().endswith(DUOI_CHUNG_TU):
            raise ValueError(f"Tệp '{ten}': chỉ nhận {', '.join(DUOI_CHUNG_TU)}.")
        if len(du_lieu) > TRAN_TEP:
            raise ValueError(f"Tệp '{ten}' quá {TRAN_TEP // 1024 // 1024} MB.")
        sach.append((ten, du_lieu))
    return sach


def luu_chung_tu(id_bt: str, tep: list) -> list[str]:
    """Ghi tệp vào kho của MỘT bút toán, trả danh sách tên đã dọn."""
    sach = kiem_tep(tep)
    thu_muc = thu_muc_chung_tu(id_bt)
    thu_muc.mkdir(parents=True, exist_ok=True)
    for ten, du_lieu in sach:
        (thu_muc / ten).write_bytes(du_lieu)
    return [t for t, _ in sach]


def duong_chung_tu(id_bt: str, ten: str) -> Path | None:
    """Đường tệp nếu có THẬT trong kho của đúng bút toán đó — chặn leo thư mục."""
    ten = _ten_tep_sach(ten)
    p = thu_muc_chung_tu(id_bt) / ten
    try:
        p.resolve().relative_to(thu_muc_chung_tu(id_bt).resolve())
    except (ValueError, OSError):
        return None
    return p if p.is_file() else None


# ---------- sổ tỷ giá (A2 — JSONL chỉ-thêm, một dòng mỗi lần lấy) ----------

def _thu_muc_ty_gia() -> Path:
    return Path(os.getenv("TY_GIA_DIR", "nhan-su/ty-gia"))


def ghi_ty_gia(ngay: str, tien_te: str, gia, nguon: str) -> dict:
    """Chỉ-THÊM một dòng tỷ giá. Lấy lại cùng ngày = thêm dòng mới, dòng cũ giữ
    nguyên (sổ kể được chuyện gì đã xảy ra)."""
    date.fromisoformat(ngay)
    gia = float(gia)
    if gia <= 0:
        raise ValueError("Tỷ giá phải lớn hơn 0.")
    d = {"ngay": ngay, "tien_te": tien_te.upper(), "gia": gia, "nguon": nguon,
         "lay_luc": datetime.now().isoformat(timespec="seconds")}
    pth = _thu_muc_ty_gia() / f"{ngay[:4]}.jsonl"
    pth.parent.mkdir(parents=True, exist_ok=True)
    with _khoa, open(pth, "a", encoding="utf-8") as f:
        f.write(json.dumps(d, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())
    return d


def _doc_so_ty_gia(tien_te: str) -> list[dict]:
    thu_muc = _thu_muc_ty_gia()
    if not thu_muc.is_dir():
        return []
    ra = []
    for pth in sorted(thu_muc.glob("*.jsonl")):
        for dong in pth.read_text(encoding="utf-8", errors="replace").splitlines():
            if not dong.strip():
                continue
            try:
                d = json.loads(dong)
            except ValueError:
                continue
            if isinstance(d, dict) and d.get("tien_te") == tien_te.upper() and d.get("gia"):
                ra.append(d)
    return sorted(ra, key=lambda d: (d.get("ngay", ""), d.get("lay_luc", "")))


def ty_gia_ngay(ngay: str, tien_te: str = "USD") -> dict | None:
    """Tỷ giá dùng cho MỘT ngày, đọc SỔ (không chạm mạng): đúng ngày → cu=False;
    chưa có → dòng gần nhất TRƯỚC đó kèm cu=True; không có dòng nào trước đó →
    None (form bắt nhập tay, tuyệt đối không suy ngược một con số)."""
    ds = [d for d in _doc_so_ty_gia(tien_te) if d.get("ngay", "") <= ngay]
    if not ds:
        return None
    d = ds[-1]
    return {"gia": float(d["gia"]), "nguon": d.get("nguon", ""),
            "ngay": d["ngay"], "cu": d["ngay"] != ngay}


def _doc_url(url: str, timeout: int = TY_GIA_TIMEOUT) -> str:
    """Tách riêng để test monkeypatch — lõi không bao giờ gọi thật."""
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def lay_ty_gia_online(tien_te: str = "USD") -> dict | None:
    """VCB trước (giá MUA CHUYỂN KHOẢN = số VND thực nhận khi bán ngoại tệ),
    ExchangeRate-API mở dự phòng. Mọi đường chết → None, KHÔNG bịa."""
    tien_te = tien_te.upper()
    try:
        du = json.loads(_doc_url(VCB_URL))
        for m in du.get("Data", []):
            if (m.get("currencyCode") or "").upper() == tien_te and m.get("transfer"):
                return {"gia": float(str(m["transfer"]).replace(",", "")),
                        "nguon": "vcb_transfer"}
    except (OSError, ValueError, KeyError, TypeError):
        pass
    try:
        du = json.loads(_doc_url(ER_API_URL + tien_te))
        gia = (du.get("rates") or {}).get(DONG_VAN_HANH)
        if gia:
            return {"gia": float(gia), "nguon": "er_api"}
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return None


# ---------- tổng hợp (đọc-tính, không ghi) ----------

def quy_vnd(b: dict) -> float:
    """Số tiền của bút toán quy về đồng vận hành. KHÔNG lưu vào sổ — luôn tính
    lại để không có hai con số cãi nhau."""
    return float(b.get("so_tien") or 0) * float(b.get("ty_gia") or 1)

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
            ra[phia] += quy_vnd(b)
    return ra


def tong_hop_danh_muc(thang: str) -> dict[str, dict]:
    """{ma danh mục: {thang: tổng tháng chọn, luy_ke: tổng mọi thời}} từ sổ."""
    ra: dict[str, dict] = {}
    for b in doc_so():
        dm = b.get("danh_muc", "")
        if not dm:
            continue
        m = ra.setdefault(dm, {"thang": 0.0, "luy_ke": 0.0})
        tien = quy_vnd(b)
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
            m["da_thu"] += quy_vnd(b)
        elif phia == "chi":
            m["da_chi"] += quy_vnd(b)
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
        m[phia] += quy_vnd(b)
    return ra


def so_du_vi() -> dict[str, dict]:
    """{mã ví: {nguyen_te, tien_te, but_toan_cuoi}} — thu cộng, chi trừ; dòng đảo
    mang danh mục gốc + số tiền âm nên tự bù đúng bên. Ví chưa phát sinh bút toán
    nào thì KHÔNG hiện (không vẽ dòng 0 giả).

    A2: kèm 'quy_vnd' cộng theo tỷ giá đã chốt trên từng bút toán.
    """
    loai_map = _loai_theo_ma()
    vi_map = _vi_theo_ma()
    ra: dict[str, dict] = {}
    for b in doc_so():
        ma = (b.get("vi") or "").strip()
        phia = _phia(b, loai_map)
        if not ma or not phia:
            continue
        m = ra.setdefault(ma, {"nguyen_te": 0.0, "quy_vnd": 0.0,
                               "tien_te": vi_map.get(ma, {}).get("tien_te", "VND"),
                               "but_toan_cuoi": ""})
        dau = 1 if phia == "thu" else -1
        m["nguyen_te"] += dau * float(b.get("so_tien") or 0)
        m["quy_vnd"] += dau * quy_vnd(b)
        m["but_toan_cuoi"] = max(m["but_toan_cuoi"], b.get("ngay") or "")
    return ra


def tien_kha_dung() -> dict[str, float]:
    """{tiền tệ: tổng} của tiền THẬT đang có — bỏ ví loại 'phai_thu' (AdSense chưa
    chi trả chưa phải tiền của mình). Số dư 0 không hiện."""
    vi_map = _vi_theo_ma()
    ra: dict[str, float] = {}
    for ma, m in so_du_vi().items():
        if vi_map.get(ma, {}).get("loai") == "phai_thu":
            continue
        if m["nguyen_te"]:
            ra[m["tien_te"]] = ra.get(m["tien_te"], 0.0) + m["nguyen_te"]
    return ra


def tien_kha_dung_vnd() -> float:
    """Tổng tiền khả dụng quy về đồng vận hành — số dùng cho runway (B3)."""
    vi_map = _vi_theo_ma()
    return sum(m["quy_vnd"] for ma, m in so_du_vi().items()
               if vi_map.get(ma, {}).get("loai") != "phai_thu")
