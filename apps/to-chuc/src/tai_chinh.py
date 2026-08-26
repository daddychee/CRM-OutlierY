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
import io
import json
import os
import re
import secrets
import threading
import urllib.request
from datetime import date, datetime, timedelta
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
NHOM_DICH_VU = ("proxy", "api", "cong_cu", "email", "khac")      # D2
CHU_KY = {"thang": 1, "quy": 3, "nam": 12, "mot_lan": 0}         # số tháng
TRANG_THAI_DV = ("dang_dung", "sap_bo", "da_huy")
QUY_TAC_PHAN_BO = ("doanh_thu", "chia_deu", "ngay_cong", "khong")   # B1
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
                  tep_dinh_kem: list | None = None, nguon: str = "tay",
                  trang_thai_thu: str = "") -> dict:
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
         "tep_dinh_kem": list(tep_dinh_kem or []), "nguon": nguon,
         "trang_thai_thu": trang_thai_thu,
         "dieu_chinh_ky_truoc": doc_chot_ky(ngay[:7]) is not None,
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
             "nguon": "dao",
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


# ---------- A4: lọc + xuất ----------

def loc_so(thang: str = "", tu: str = "", den: str = "", loai: str = "",
           vi: str = "", kenh: str = "", muc_tieu: str = "", danh_muc: str = "",
           nguoi: str = "", q: str = "") -> list[dict]:
    """Lọc sổ Ở SERVER, mới nhất trước. Điều kiện rỗng = không lọc theo cột đó.
    q tìm trong ghi chú + số chứng từ, không phân biệt hoa thường."""
    q = (q or "").strip().lower()
    ra = []
    for b in doc_so():
        ngay = b.get("ngay") or ""
        if thang and ngay[:7] != thang:
            continue
        if tu and ngay < tu:
            continue
        if den and ngay > den:
            continue
        if loai and b.get("loai") != loai:
            continue
        if vi and b.get("vi") != vi:
            continue
        if kenh and (b.get("kenh_ma") or "") != kenh:
            continue
        if muc_tieu and b.get("muc_tieu") != muc_tieu:
            continue
        if danh_muc and b.get("danh_muc") != danh_muc:
            continue
        if nguoi and b.get("nguoi_ghi") != nguoi:
            continue
        if q and q not in f"{b.get('ghi_chu', '')} {b.get('chung_tu', '')}".lower():
            continue
        ra.append(b)
    return sorted(ra, key=lambda b: (b.get("ngay", ""), b.get("tao_luc", "")),
                  reverse=True)


COT_CSV = ("id", "ngay", "loai", "danh_muc", "so_tien", "tien_te", "ty_gia",
           "quy_vnd", "vi", "muc_tieu", "kenh_ma", "nguoi_ghi", "chung_tu",
           "tep_dinh_kem", "ghi_chu", "tham_chieu", "tao_luc")


def xuat_csv(ds: list[dict]) -> str:
    """CSV cho Excel — route tự thêm BOM utf-8-sig."""
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(COT_CSV)
    for b in ds:
        w.writerow([("; ".join(b.get("tep_dinh_kem") or [])) if c == "tep_dinh_kem"
                    else (f"{quy_vnd(b):.0f}" if c == "quy_vnd" else b.get(c, ""))
                    for c in COT_CSV])
    return buf.getvalue()


def _tk_beancount(b: dict, loai_map: dict) -> tuple[str, str]:
    """(tài khoản khoản mục, tài khoản ví) theo 5 gốc chuẩn để Fava mở được."""
    phia = _phia(b, loai_map)
    goc = "Income" if phia == "thu" else "Expenses"
    ma = re.sub(r"[^0-9A-Za-z-]", "", (b.get("danh_muc") or "KHAC")).upper() or "KHAC"
    vi = re.sub(r"[^0-9A-Za-z-]", "", (b.get("vi") or "KHAC")).upper() or "KHAC"
    return f"{goc}:{ma}", f"Assets:{vi}"


def xuat_beancount(ds: list[dict]) -> str:
    """Sổ → tệp .beancount mở được bằng Fava (bảng cân đối, báo cáo kết quả,
    treemap chi phí — khỏi phải tự viết báo cáo).

    ponytail: KHÔNG dựng cây tài khoản đầy đủ, chỉ 5 gốc chuẩn + mã khoản/ví;
    mục tiêu là mở được, không phải đạt chuẩn kế toán kép.
    """
    loai_map = _loai_theo_ma()
    dong = [f'option "operating_currency" "{DONG_VAN_HANH}"', ""]
    tk = sorted({t for b in ds for t in _tk_beancount(b, loai_map)})
    dong += [f"1900-01-01 open {t}" for t in tk] + [""]
    for b in sorted(ds, key=lambda b: (b.get("ngay", ""), b.get("tao_luc", ""))):
        tien = float(b.get("so_tien") or 0)
        tt = b.get("tien_te") or DONG_VAN_HANH
        tg = float(b.get("ty_gia") or 1)
        gia = "" if tt == DONG_VAN_HANH else f" @ {tg:.2f} {DONG_VAN_HANH}"
        tk_muc, tk_vi = _tk_beancount(b, loai_map)
        phia = _phia(b, loai_map)
        # thu: ví DƯƠNG / Income ÂM · chi: Expenses DƯƠNG / ví ÂM
        cap = ([(tk_vi, tien), (tk_muc, -tien)] if phia == "thu"
               else [(tk_muc, tien), (tk_vi, -tien)])
        ghi_chu = (b.get("ghi_chu") or b.get("danh_muc") or "").replace('"', "'")
        dong.append(f'{b.get("ngay", "")} * "{ghi_chu}"')
        for khoa, gt in (("chung-tu", b.get("chung_tu")), ("kenh", b.get("kenh_ma")),
                         ("muc-tieu", b.get("muc_tieu")),
                         ("tham-chieu", b.get("tham_chieu"))):
            if gt:
                dong.append(f'  {khoa}: "{str(gt)}"')
        for tk_x, gt in cap:
            dong.append(f"  {tk_x}      {gt:.2f} {tt}{gia}")
        dong.append("")
    return "\n".join(dong)


# ---------- D2: dịch vụ trả phí (gộp C1 — mỗi dịch vụ có chu kỳ LÀ khoản định kỳ) ----------
# KHÔNG có trường mật khẩu và sẽ không được thêm: Vault giữ bí mật, Finance giữ
# lịch gia hạn. vault_id chỉ là id trỏ sang mục trong két.

def _duong_dich_vu() -> Path:
    return Path(os.getenv("DICH_VU_PATH", "nhan-su/dich-vu-tra-phi.json"))


def doc_dich_vu() -> list[dict]:
    p = _duong_dich_vu()
    if not p.is_file():
        return []
    try:
        du = json.loads(p.read_text(encoding="utf-8"))
        return du if isinstance(du, list) else []
    except ValueError:
        return []


def _ghi_dich_vu(ds: list[dict]) -> None:
    p = _duong_dich_vu()
    p.parent.mkdir(parents=True, exist_ok=True)
    tam = p.with_name(p.name + ".tmp")
    tam.write_text(json.dumps(ds, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tam, p)


def luu_dich_vu(nguoi: str, ten: str, nhom: str, phi, tien_te: str, chu_ky: str,
                ngay_gia_han: str, danh_muc: str, vi: str, id: str = "",
                nha_cung_cap: str = "", tu_dong_gia_han: bool = True,
                trang_thai: str = "dang_dung", kenh_ma: str = KENH_CHUNG,
                vault_id: str = "", ghi_chu: str = "") -> dict:
    """Thêm mới (id rỗng) hoặc sửa. Validate ở trust boundary — mã khoản và ví
    phải có thật để lúc ghi bút toán không vỡ."""
    ten = (ten or "").strip()
    if not ten:
        raise ValueError("Thiếu tên dịch vụ.")
    if nhom not in NHOM_DICH_VU:
        raise ValueError(f"Nhóm '{nhom}' không hợp lệ.")
    if chu_ky not in CHU_KY:
        raise ValueError(f"Chu kỳ '{chu_ky}' không hợp lệ.")
    if trang_thai not in TRANG_THAI_DV:
        raise ValueError(f"Trạng thái '{trang_thai}' không hợp lệ.")
    if danh_muc not in _loai_theo_ma():
        raise ValueError(f"Danh mục '{danh_muc}' không có trong rules/danh_muc_thu_chi.csv.")
    if vi not in _vi_theo_ma():
        raise ValueError(f"Ví '{vi}' không có trong rules/danh_muc_vi.csv.")
    date.fromisoformat(ngay_gia_han)
    try:
        phi = float(phi)
    except (TypeError, ValueError):
        raise ValueError("Phí phải là số.")
    if phi < 0:
        raise ValueError("Phí không âm.")
    kenh_ma = (kenh_ma or "").strip()
    if kenh_ma and not _kenh_hop_le(kenh_ma):
        raise ValueError(f"Kênh '{kenh_ma}' không có trong danh bạ đế.")

    with _khoa:
        ds = doc_dich_vu()
        ban = {"ten": ten, "nha_cung_cap": (nha_cung_cap or "").strip(),
               "nhom": nhom, "phi": phi, "tien_te": (tien_te or "VND").upper(),
               "chu_ky": chu_ky, "ngay_gia_han": ngay_gia_han,
               "tu_dong_gia_han": bool(tu_dong_gia_han), "trang_thai": trang_thai,
               "danh_muc": danh_muc, "vi": vi, "kenh_ma": kenh_ma,
               "vault_id": (vault_id or "").strip(), "ghi_chu": (ghi_chu or "").strip(),
               "sua_luc": datetime.now().isoformat(timespec="seconds"),
               "nguoi_sua": nguoi}
        if id:
            cu = next((d for d in ds if d.get("id") == id), None)
            if cu is None:
                raise ValueError(f"Không có dịch vụ id '{id}'.")
            cu.update(ban)
            ban = cu
        else:
            ban["id"] = f"DV-{secrets.token_hex(3)}"
            ban["tao_luc"] = ban["sua_luc"]
            ds.append(ban)
        _ghi_dich_vu(ds)
    return ban


def den_han(hom_nay: str = "", trong_ngay: int = 14) -> list[dict]:
    """Dịch vụ tới hạn trong N ngày, KỂ CẢ đã quá hạn (cờ qua_han) — quá hạn mà
    im lặng là mất tiền oan. Bỏ dịch vụ đã hủy và loại một-lần đã qua."""
    hom_nay = hom_nay or date.today().isoformat()
    moc = (date.fromisoformat(hom_nay) + timedelta(days=trong_ngay)).isoformat()
    ra = []
    for d in doc_dich_vu():
        if d.get("trang_thai") == "da_huy":
            continue
        han = d.get("ngay_gia_han") or ""
        if not han or han > moc:
            continue
        ra.append({**d, "qua_han": han < hom_nay})
    return sorted(ra, key=lambda d: d.get("ngay_gia_han") or "")


def _phi_thang_vnd(d: dict) -> float:
    """Phí quy về MỘT tháng, quy VND theo tỷ giá sổ. Chu kỳ một-lần → 0 (không
    phải chi phí lặp). Ngoại tệ chưa có tỷ giá → 0 kèm không đoán."""
    so_thang = CHU_KY.get(d.get("chu_ky"), 0)
    if not so_thang:
        return 0.0
    phi = float(d.get("phi") or 0) / so_thang
    tt = (d.get("tien_te") or DONG_VAN_HANH).upper()
    if tt == DONG_VAN_HANH:
        return phi
    tg = ty_gia_ngay(date.today().isoformat(), tt)
    return phi * tg["gia"] if tg else 0.0


def chi_phi_thue_bao_thang() -> float:
    """Tổng chi thuê bao mỗi tháng (VND) — chỉ dịch vụ ĐANG DÙNG và SẮP BỎ."""
    return sum(_phi_thang_vnd(d) for d in doc_dich_vu()
               if d.get("trang_thai") in ("dang_dung", "sap_bo"))


def tiet_kiem_neu_bo() -> float:
    """Tiết kiệm mỗi tháng nếu bỏ hết dịch vụ đánh dấu 'sắp bỏ'."""
    return sum(_phi_thang_vnd(d) for d in doc_dich_vu()
               if d.get("trang_thai") == "sap_bo")


def day_gia_han(id: str) -> dict:
    """Sau khi đã ghi bút toán kỳ này thì đẩy hạn sang kỳ kế tiếp."""
    with _khoa:
        ds = doc_dich_vu()
        d = next((x for x in ds if x.get("id") == id), None)
        if d is None:
            raise ValueError(f"Không có dịch vụ id '{id}'.")
        so_thang = CHU_KY.get(d.get("chu_ky"), 0)
        if so_thang:
            cu = date.fromisoformat(d["ngay_gia_han"])
            thang = cu.month - 1 + so_thang
            nam = cu.year + thang // 12
            thang = thang % 12 + 1
            ngay = min(cu.day, [31, 29 if nam % 4 == 0 else 28, 31, 30, 31, 30,
                                31, 31, 30, 31, 30, 31][thang - 1])
            d["ngay_gia_han"] = date(nam, thang, ngay).isoformat()
        _ghi_dich_vu(ds)
    return d


def chuoi_thang(den_thang: str, so_thang: int = 12) -> list[str]:
    """['2025-09', …, '2026-08'] — trục thời gian cho dashboard."""
    nam, thang = int(den_thang[:4]), int(den_thang[5:7])
    ra = []
    for _ in range(so_thang):
        ra.append(f"{nam:04d}-{thang:02d}")
        thang -= 1
        if thang == 0:
            nam, thang = nam - 1, 12
    return list(reversed(ra))


def du_lieu_bieu_do(den_thang: str) -> dict:
    """Số cho 6 biểu đồ. Sổ rỗng → mảng rỗng để UI ghi 'chưa có dữ liệu' chứ
    KHÔNG vẽ trục rỗng trông như đã đo."""
    thang_ds = chuoi_thang(den_thang)
    co_du_lieu = bool(doc_so())
    thu, chi, so_du = [], [], []
    luy = 0.0
    for t in thang_ds:
        m = tong_thang(t)
        thu.append(round(m["thu"]))
        chi.append(round(m["chi"]))
        luy += m["thu"] - m["chi"]
        so_du.append(round(luy))
    dm = tong_hop_danh_muc(den_thang)
    co_cau = sorted(((ma, round(v["thang"])) for ma, v in dm.items() if v["thang"] > 0),
                    key=lambda x: -x[1])[:8]
    pnl = pnl_theo_kenh(den_thang)
    kenh = sorted(((ma or "chung hệ", round(v["thu"] - v["chi"]))
                   for ma, v in pnl.items()), key=lambda x: -x[1])[:10]
    tb: dict[str, float] = {}
    for d in doc_dich_vu():
        if d.get("trang_thai") in ("dang_dung", "sap_bo"):
            tb[d["nhom"]] = tb.get(d["nhom"], 0.0) + _phi_thang_vnd(d)
    return {"co_du_lieu": co_du_lieu, "thang": thang_ds, "thu": thu, "chi": chi,
            "so_du": so_du,
            "co_cau_nhan": [x[0] for x in co_cau], "co_cau_so": [x[1] for x in co_cau],
            "kenh_nhan": [x[0] for x in kenh], "kenh_so": [x[1] for x in kenh],
            "thue_bao_nhan": list(tb), "thue_bao_so": [round(v) for v in tb.values()]}


def muc_dot(den_thang: str, so_thang: int = 3) -> dict:
    """B3 — mức đốt và thời gian còn sống.

    dot_rong = chi trung bình − thu trung bình của N tháng gần nhất;
    so_thang_con = tiền khả dụng ÷ dot_rong.

    Van chống bịa: thu ≥ chi thì KHÔNG có khái niệm "còn sống mấy tháng"
    (duong=True); tiền khả dụng ≤ 0 thì het_tien=True. Cả hai ca đều trả
    so_thang_con=None chứ không nặn ra một con số.
    """
    ds = chuoi_thang(den_thang, so_thang)
    thu = sum(tong_thang(t)["thu"] for t in ds) / so_thang
    chi = sum(tong_thang(t)["chi"] for t in ds) / so_thang
    kha_dung = tien_kha_dung_vnd()
    dot = chi - thu
    ra = {"tu": ds[0], "den": ds[-1], "thu_tb": round(thu), "chi_tb": round(chi),
          "kha_dung": round(kha_dung), "dot_rong": None, "so_thang_con": None,
          "duong": False, "het_tien": False,
          "thue_bao_thang": round(chi_phi_thue_bao_thang())}
    if chi <= 0 and thu <= 0:
        return ra                                  # sổ chưa có gì để nói
    if dot <= 0:
        ra["duong"] = True
        return ra
    ra["dot_rong"] = round(dot)
    if kha_dung <= 0:
        ra["het_tien"] = True
        return ra
    ra["so_thang_con"] = round(kha_dung / dot, 1)
    return ra


# ---------- B1: phân bổ chi phí chung xuống kênh ----------

def pnl_phan_bo(thang: str, quy_tac: str = "doanh_thu",
                trong_so_ngoai: dict | None = None) -> dict:
    """Lãi/lỗ theo kênh CÓ phân bổ chi phí "chung hệ".

    Bản v1 để toàn bộ chi phí chung ở một hàng riêng nên mọi kênh đều trông có
    lãi còn cục lỗ đứng một mình — bảng nói dối một cách lịch sự. Đây là chỗ vá.

    Quy tắc: doanh_thu (theo tỷ lệ thu) · chia_deu · ngay_cong (trọng số truyền
    từ D3) · khong (giữ nguyên hàng chung hệ).

    TÍNH LÚC ĐỌC, KHÔNG sinh bút toán — sổ gốc giữ nguyên bản (bất biến số 5).
    """
    if quy_tac not in QUY_TAC_PHAN_BO:
        raise ValueError(f"Quy tắc phân bổ '{quy_tac}' không hợp lệ.")
    pnl = pnl_theo_kenh(thang)
    chung = pnl.get(KENH_CHUNG, {"thu": 0.0, "chi": 0.0})
    kenh = {ma: m for ma, m in pnl.items() if ma}

    trong_so: dict[str, float] = {}
    if kenh and quy_tac != "khong":
        if quy_tac == "doanh_thu":
            trong_so = {ma: m["thu"] for ma, m in kenh.items()}
        elif quy_tac == "chia_deu":
            trong_so = {ma: 1.0 for ma in kenh}
        elif quy_tac == "ngay_cong":
            trong_so = {ma: float((trong_so_ngoai or {}).get(ma, 0)) for ma in kenh}
        if sum(trong_so.values()) <= 0:       # trọng số rỗng → lùi về chia đều,
            trong_so = {ma: 1.0 for ma in kenh}   # KHÔNG im lặng bỏ chi phí chung

    tong_ts = sum(trong_so.values())
    can_chia = chung["chi"] - chung["thu"]
    dong, da_chia = [], 0.0
    for ma, m in sorted(kenh.items()):
        pb = round(can_chia * trong_so[ma] / tong_ts, 2) if tong_ts else 0.0
        da_chia += pb
        dong.append({"kenh_ma": ma, "thu": m["thu"], "chi": m["chi"],
                     "lai_lo_truoc": m["thu"] - m["chi"], "phan_bo": pb,
                     "lai_lo_sau": round(m["thu"] - m["chi"] - pb, 2)})
    return {"thang": thang, "quy_tac": quy_tac, "dong": dong,
            "chung_he": can_chia, "chung_he_con_lai": round(can_chia - da_chia, 2)}


# ---------- B4: ngân sách theo kỳ + chuyển tiếp ----------

def _duong_han_muc() -> Path:
    return Path(os.getenv("HAN_MUC_PATH", "nhan-su/han-muc.json"))


def dat_han_muc(nguoi: str, muc_tieu: str, so_tien, chuyen_tiep: bool = False) -> dict:
    """Hạn mức MỖI KỲ của một mục tiêu (chỉ-thêm, bản sau đè bản trước khi đọc)."""
    if not any(m.get("ten") == muc_tieu for m in doc_muc_tieu()):
        raise ValueError(f"Mục tiêu '{muc_tieu}' chưa có trong sổ.")
    try:
        so_tien = float(so_tien)
    except (TypeError, ValueError):
        raise ValueError("Hạn mức phải là số.")
    if so_tien < 0:
        raise ValueError("Hạn mức không âm.")
    ban = {"muc_tieu": muc_tieu, "so_tien": so_tien, "chuyen_tiep": bool(chuyen_tiep),
           "nguoi": nguoi, "luc": datetime.now().isoformat(timespec="seconds")}
    with _khoa:
        p = _duong_han_muc()
        ds = json.loads(p.read_text(encoding="utf-8")) if p.is_file() else []
        ds.append(ban)
        p.parent.mkdir(parents=True, exist_ok=True)
        tam = p.with_name(p.name + ".tmp")
        tam.write_text(json.dumps(ds, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tam, p)
    return ban


def han_muc_hien_tai() -> dict[str, dict]:
    p = _duong_han_muc()
    if not p.is_file():
        return {}
    try:
        ds = json.loads(p.read_text(encoding="utf-8"))
    except ValueError:
        return {}
    return {b["muc_tieu"]: b for b in ds if isinstance(b, dict) and b.get("muc_tieu")}


def _chi_theo_muc_tieu(thang: str) -> dict[str, float]:
    loai_map = _loai_theo_ma()
    ra: dict[str, float] = {}
    for b in doc_so():
        if (b.get("ngay") or "")[:7] != thang or _phia(b, loai_map) != "chi":
            continue
        mt = b.get("muc_tieu", "")
        ra[mt] = ra.get(mt, 0.0) + quy_vnd(b)
    return ra


def ngan_sach_ky(thang: str) -> dict:
    """Hạn mức kỳ · đã chi · chuyển tiếp từ kỳ trước · tiến độ.

    Vượt hạn mức KHÔNG chặn ghi bút toán — tiền đã tiêu thì sổ phải ghi được;
    chỉ cảnh báo (Owner chốt). Mục tiêu chưa đặt hạn mức → None, không đoán.
    """
    hm = han_muc_hien_tai()
    chi_nay = _chi_theo_muc_tieu(thang)
    thang_truoc = chuoi_thang(thang, 2)[0]
    chi_truoc = _chi_theo_muc_tieu(thang_truoc)
    dong = []
    for m in doc_muc_tieu():
        ten = m["ten"]
        h = hm.get(ten)
        muc = h["so_tien"] if h else None
        da_chi = chi_nay.get(ten, 0.0)
        ct = 0.0
        if h and h.get("chuyen_tiep"):
            ct = round(h["so_tien"] - chi_truoc.get(ten, 0.0), 2)
        tran = (muc + ct) if muc is not None else None
        dong.append({
            "muc_tieu": ten, "han_muc": muc, "chuyen_tiep": ct, "da_chi": da_chi,
            "con_lai": round(tran - da_chi, 2) if tran is not None else None,
            "ti_le": round(100 * da_chi / muc) if muc else None,
            "vuot": bool(muc and da_chi > muc), "trang_thai": m.get("trang_thai")})
    return {"thang": thang, "dong": dong}


# ---------- C5: chốt kỳ + đối chiếu số dư ví ----------

def _duong_chot_ky() -> Path:
    return Path(os.getenv("CHOT_KY_PATH", "nhan-su/chot-ky-tien.json"))


def _doc_chot_ky_all() -> list[dict]:
    p = _duong_chot_ky()
    if not p.is_file():
        return []
    try:
        ds = json.loads(p.read_text(encoding="utf-8"))
        return ds if isinstance(ds, list) else []
    except ValueError:
        return []


def doc_chot_ky(ky: str) -> dict | None:
    return next((b for b in _doc_chot_ky_all() if b.get("ky") == ky), None)


def doi_chieu_vi(ky: str, khai: dict) -> list[dict]:
    """So số dư SỔ TÍNH RA với số dư THẬT người khai (balance assertion của
    beancount). Chỉ ra lệch, không tự sửa gì."""
    sd = so_du_vi()
    vi_map = _vi_theo_ma()
    ra = []
    for ma, v in vi_map.items():
        so_so = round(sd.get(ma, {}).get("nguyen_te", 0.0), 2)
        if ma not in khai and not so_so:
            continue
        k = round(float(khai.get(ma, 0)), 2)
        ra.append({"vi": ma, "ten": v["ten"], "tien_te": v["tien_te"],
                   "so_so": so_so, "khai": k, "lech": round(k - so_so, 2),
                   "khop": abs(k - so_so) < 0.01})
    return ra


def chot_ky_tien(nguoi: str, ky: str, khai: dict) -> dict:
    """Chốt kỳ kế toán. KHÓA khi còn ví lệch — không cho chốt đè lên chênh lệch;
    chốt hai lần cũng bị chặn (bản chốt chỉ-thêm, không ghi đè lịch sử)."""
    if not re.fullmatch(r"\d{4}-\d{2}", ky or ""):
        raise ValueError("Kỳ phải dạng YYYY-MM.")
    if doc_chot_ky(ky) is not None:
        raise ValueError(f"Kỳ {ky} đã chốt rồi.")
    dc = doi_chieu_vi(ky, khai)
    lech = [d for d in dc if not d["khop"]]
    if lech:
        ten = ", ".join(d["ten"] for d in lech)
        raise ValueError(f"Còn ví lệch chưa giải trình: {ten}. "
                         "Ghi bút toán giải trình rồi chốt lại.")
    ban = {"ky": ky, "nguoi_chot": nguoi, "doi_chieu": dc,
           "luc": datetime.now().isoformat(timespec="seconds")}
    with _khoa:
        if doc_chot_ky(ky) is not None:
            raise ValueError(f"Kỳ {ky} đã chốt rồi.")
        ds = _doc_chot_ky_all()
        ds.append(ban)
        p = _duong_chot_ky()
        p.parent.mkdir(parents=True, exist_ok=True)
        tam = p.with_name(p.name + ".tmp")
        tam.write_text(json.dumps(ds, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tam, p)
    return ban
