# -*- coding: utf-8 -*-
"""Danh bạ thực thể chung (thị trường → ngách → kênh) — mảnh ④ tầng nền, bản DB.

Đ1 khối đế (DE.md, Owner chốt 16/08/2026): nguồn sự thật là SQLite
data/nen/danh_ba.db (CRUD qua UI /general, có vết) thay CSV seed. API ĐỌC giữ
nguyên chữ ký thời CSV (doc_danh_muc / tra_thuc_the / khoa_ung_dung / liet_ke)
— cầu nối P6 và dropdown app không đổi; tham số `duong` giờ trỏ file DB.

Mọi mảnh khác tra qua module này — KHÔNG app nào tự đoán tên thực thể.
Hàm GHI chỉ gateway gọi (audit ghi ở tầng route bằng iam.ghi_nhat_ky).
"""
from __future__ import annotations

import csv
import io
import os
import re
import sqlite3
import unicodedata
from datetime import datetime
from pathlib import Path

from nen.common.sqlite_migrate import migrate

ROOT = Path(__file__).resolve().parents[2]
DUONG_MAC_DINH = ROOT / "data" / "nen" / "danh_ba.db"
MIGRATIONS = Path(__file__).resolve().parent / "danh_ba_migrations"

# Danh mục vòng đời — Owner chốt 24/08/2026 (đổi tập giá trị, có migration 003).
# TRANG_THAI_KENH = 5 nấc HIỆN trên stepper; 'khai_tu' (Retired) ẨN — chỉ đặt qua
# khai_tu_kenh() (nút Retire chỉ Owner), không bấm được trên stepper.
TRANG_THAI_KENH = ("uom_mam", "sandbox", "hoat_dong", "monetized", "shadow_ban")
TRANG_THAI_KENH_AN = ("khai_tu",)
TRANG_THAI_KENH_HOP_LE = TRANG_THAI_KENH + TRANG_THAI_KENH_AN
TRANG_THAI_NGACH = ("khai_thac", "mo_rong", "duy_tri", "nghi")

# Nhãn hiển thị vòng đời — MỘT nguồn dùng chung (29/08/2026). Trước đó khai cứng
# trong nen_channels.html; Data Analytics cần đúng bộ nhãn này để badge không drift
# giữa hai app. Template gateway đọc qua biến, không tự khai lại.
NHAN_TRANG_THAI_KENH = {
    "uom_mam": "Incubating", "sandbox": "Testing", "hoat_dong": "Traction",
    "monetized": "Monetized", "shadow_ban": "Shadowbanned", "khai_tu": "Retired",
}

# Tương thích cột khóa thời CSV → app_slug (caller cũ truyền cột cũ vẫn chạy).
_COT_CU_SANG_SLUG = {
    "seo_profile": "seo-optimize",
    "plannery_project": "plannery",
    "radary_niche": "radary",
    "niche_project": "niche-research",
    "mau_ten_bao_cao": "bao-cao",
}


def _duong_hieu_luc(duong: Path | str | None) -> Path:
    """Ưu tiên tham số → env DANH_BA_DB (test/cách ly) → DB thật."""
    if duong:
        return Path(duong)
    return Path(os.environ.get("DANH_BA_DB") or DUONG_MAC_DINH)


def ket_noi(duong: Path | str | None = None) -> sqlite3.Connection:
    p = _duong_hieu_luc(duong)
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(p)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    migrate(conn, MIGRATIONS)
    return conn


def chuan_hoa_ten(ten: str) -> str:
    """Chuẩn hóa tên để so khớp: thường hóa, bỏ dấu, đ→d, gọn khoảng trắng.

    'đ' (U+0111) KHÔNG phân rã qua NFD nên phải thay riêng — bẫy tiếng Việt
    đã dính ở SEO Optimize 05/08/2026.
    """
    if not ten:
        return ""
    s = ten.casefold()
    s = s.replace("đ", "d").replace("Đ", "d")
    s = unicodedata.normalize("NFD", s)
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _luc() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ---------- ĐỌC (chữ ký giữ nguyên thời CSV; cache theo mtime DB) ----------

_cache: dict = {}


def _dau_phien_ban(p: Path) -> tuple:
    """Dấu đổi-dữ-liệu chịu được WAL: commit ghi vào file -wal, mtime db chính
    KHÔNG đổi → phải gộp cả mtime+size của -wal (bẫy bắt được bằng test Đ1)."""
    dau = [p.stat().st_mtime_ns, p.stat().st_size]
    wal = Path(str(p) + "-wal")
    if wal.exists():
        dau += [wal.stat().st_mtime_ns, wal.stat().st_size]
    return tuple(dau)


def _nap(duong: Path | str | None) -> list[dict]:
    p = _duong_hieu_luc(duong)
    if not p.exists():
        return []
    mtime = _dau_phien_ban(p)
    khoa = str(p)
    if _cache.get(khoa, (None, None))[0] == mtime:
        return _cache[khoa][1]
    conn = ket_noi(p)
    try:
        ket_qua: list[dict] = []
        alias: dict[str, list[str]] = {}
        for r in conn.execute("SELECT bi_danh, thuc_the_ma FROM bi_danh"):
            alias.setdefault(r["thuc_the_ma"], []).append(r["bi_danh"])
        lk: dict[str, dict[str, str]] = {}
        for r in conn.execute("SELECT thuc_the_ma, app_slug, khoa FROM lien_ket_app"):
            lk.setdefault(r["thuc_the_ma"], {})[r["app_slug"]] = r["khoa"]
        # Thị trường CỦA TỪNG NGÁCH — user chọn, không có mặc định (002, 18/08/2026)
        tt_ngach: dict[str, list[str]] = {}
        for r in conn.execute(
                "SELECT ngach_ma, thi_truong_ma FROM ngach_thi_truong "
                "ORDER BY tao_luc, thi_truong_ma"):
            tt_ngach.setdefault(r["ngach_ma"], []).append(r["thi_truong_ma"])
        for r in conn.execute("SELECT * FROM ngach ORDER BY tao_luc, ma"):
            t = dict(r)
            t["loai"] = "ngach"
            t["bi_danh"] = ";".join(alias.get(t["ma"], []))
            t["lien_ket"] = lk.get(t["ma"], {})
            t["thi_truong_cua"] = tt_ngach.get(t["ma"], [])
            ket_qua.append(t)
        for r in conn.execute("SELECT * FROM kenh ORDER BY tao_luc, ma"):
            t = dict(r)
            t["loai"] = "kenh"
            t["bi_danh"] = ";".join(alias.get(t["ma"], []))
            t["lien_ket"] = lk.get(t["ma"], {})
            ket_qua.append(t)
        for r in conn.execute("SELECT * FROM thi_truong ORDER BY tao_luc, ma"):
            t = dict(r)
            t["loai"] = "thi_truong"
            t["ten_chuan"] = t.pop("ten")
            t["bi_danh"] = ""
            t["lien_ket"] = {}
            ket_qua.append(t)
        _cache[khoa] = (mtime, ket_qua)
        return ket_qua
    finally:
        conn.close()


def doc_danh_muc(duong: Path | str | None = None) -> list[dict]:
    return _nap(duong)


def _cac_ten_khop(thuc_the: dict) -> list[str]:
    ten = [thuc_the.get("ten_chuan", "")]
    ten += [t for t in (thuc_the.get("bi_danh") or "").split(";") if t.strip()]
    return [chuan_hoa_ten(t) for t in ten if t]


def tra_thuc_the(
    ten: str, loai: str | None = None, duong: Path | str | None = None
) -> dict | None:
    """Tra theo tên chuẩn HOẶC bí danh (chuẩn hóa 2 phía). Không khớp → None
    (người gọi phải hỏi lại người dùng, KHÔNG đoán)."""
    can = chuan_hoa_ten(ten)
    if not can:
        return None
    for thuc_the in doc_danh_muc(duong):
        if loai and thuc_the.get("loai") != loai:
            continue
        if can in _cac_ten_khop(thuc_the):
            return thuc_the
    return None


def khoa_ung_dung(thuc_the: dict | None, cot: str) -> str | None:
    """Khóa định danh của thực thể ở một app (nhận app_slug hoặc tên cột CSV cũ).
    Chưa nối → None (nói thẳng, không đoán)."""
    if not thuc_the:
        return None
    slug = _COT_CU_SANG_SLUG.get(cot, cot)
    gia_tri = (thuc_the.get("lien_ket") or {}).get(slug, "").strip()
    return gia_tri or None


def liet_ke(loai: str | None = None, duong: Path | str | None = None) -> list[dict]:
    ds = doc_danh_muc(duong)
    return [t for t in ds if t.get("loai") == loai] if loai else ds


# ---------- GHI (chỉ gateway gọi; route lo gate + audit) ----------

_BANG = {"kenh": "K", "ngach": "N", "thi_truong": "TT"}


def sinh_ma(conn: sqlite3.Connection, loai: str, ten: str) -> str:
    """Mã máy cấp DẠNG SỐ: N-001, K-014, TT-003 — BẤT BIẾN sau khi lưu.

    03/09 Owner: "đặt code thì đặt là một dãy số, tránh gây hiểu nhầm". Mã cũ
    sinh TỪ TÊN (What If → N-WHAT-IF) trông y như tên, nên đổi tên mà mã đứng
    yên thì tưởng đổi hỏng. Mã số không ai nhầm với tên.

    Số chạy tăng theo số LỚN NHẤT đang có, KHÔNG lấp chỗ trống: mã đã xóa vẫn
    còn trong nhật ký + liên kết app, cấp lại là hai thực thể chung một mã.
    Mã CŨ dạng chữ giữ nguyên — chúng nối sang RadarY/Niche Research/SEO.
    `ten` giữ trong chữ ký cho tương thích caller, không còn dùng để sinh mã."""
    bang = "thi_truong" if loai == "thi_truong" else loai
    tien_to = _BANG[loai]
    lon_nhat = 0
    for (ma_cu,) in conn.execute(f"SELECT ma FROM {bang}"):
        m = re.fullmatch(rf"{re.escape(tien_to)}-(\d+)", ma_cu or "")
        if m:
            lon_nhat = max(lon_nhat, int(m.group(1)))
    return f"{tien_to}-{lon_nhat + 1:03d}"


def _kiem_bi_danh_ranh(conn: sqlite3.Connection, ten: str, ma_bo_qua: str = "") -> None:
    """Tên/bí danh mới không được đụng tên chuẩn hay alias của thực thể khác."""
    can = chuan_hoa_ten(ten)
    r = conn.execute("SELECT thuc_the_ma FROM bi_danh WHERE bi_danh=?", (can,)).fetchone()
    if r and r["thuc_the_ma"] != ma_bo_qua:
        raise ValueError(f"'{ten}' đã là bí danh của {r['thuc_the_ma']}")


def them_thi_truong(conn, ten: str, ngon_ngu: str = "", ghi_chu: str = "") -> str:
    ma = sinh_ma(conn, "thi_truong", ten)
    with conn:
        conn.execute("INSERT INTO thi_truong VALUES (?,?,?,?,?)",
                     (ma, ten.strip(), ngon_ngu.strip(), ghi_chu.strip(), _luc()))
    return ma


def dat_thi_truong_ngach(conn, ngach_ma: str, ds_thi_truong: list[str]) -> None:
    """Đặt tập thị trường của MỘT ngách — thay cả tập (gỡ hết chọn lại).
    Luật Owner 18/08/2026: thị trường là DO USER CHỌN, ngách mới = 0 thị trường;
    không hàm nào được tự gán mặc định. Mã lạ / ngách lạ → ValueError."""
    if not conn.execute("SELECT 1 FROM ngach WHERE ma=?", (ngach_ma,)).fetchone():
        raise ValueError("ngách không tồn tại")
    co = {r["ma"] for r in conn.execute("SELECT ma FROM thi_truong")}
    ds = [t for t in dict.fromkeys(ds_thi_truong) if t]   # bỏ rỗng + dedup giữ thứ tự
    la = [t for t in ds if t not in co]
    if la:
        raise ValueError("thị trường không tồn tại: " + ", ".join(la))
    with conn:
        conn.execute("DELETE FROM ngach_thi_truong WHERE ngach_ma=?", (ngach_ma,))
        conn.executemany(
            "INSERT INTO ngach_thi_truong (ngach_ma, thi_truong_ma, tao_luc) "
            "VALUES (?,?,?)", [(ngach_ma, t, _luc()) for t in ds])


def them_ngach(conn, ten_chuan: str, trang_thai: str = "khai_thac", ghi_chu: str = "") -> str:
    if trang_thai not in TRANG_THAI_NGACH:
        raise ValueError("trạng thái ngách không hợp lệ")
    _kiem_bi_danh_ranh(conn, ten_chuan)
    ma = sinh_ma(conn, "ngach", ten_chuan)
    with conn:
        conn.execute("INSERT INTO ngach VALUES (?,?,?,?,?)",
                     (ma, ten_chuan.strip(), trang_thai, ghi_chu.strip(), _luc()))
    return ma


def them_kenh(conn, ten_chuan: str, ngach_ma: str, thi_truong_ma: str = "",
              channel_id: str = "", loai_kenh: str = "", trang_thai: str = "uom_mam",
              kenh_goc_ma: str = "", phu_trach: str = "", bo_phan_chu_quan: str = "",
              ghi_chu: str = "", nguoi_tao: str = "") -> str:
    """Niche có TRƯỚC kênh — ngach_ma bắt buộc tồn tại (FK chặn từ cửa)."""
    if trang_thai not in TRANG_THAI_KENH:
        raise ValueError("trạng thái kênh không hợp lệ")
    _kiem_bi_danh_ranh(conn, ten_chuan)
    ma = sinh_ma(conn, "kenh", ten_chuan)
    with conn:
        conn.execute(
            "INSERT INTO kenh VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (ma, ten_chuan.strip(), channel_id.strip() or None, ngach_ma,
             thi_truong_ma or None, loai_kenh.strip(), trang_thai,
             kenh_goc_ma or None, phu_trach.strip(), bo_phan_chu_quan.strip(),
             ghi_chu.strip(), _luc(), nguoi_tao))
    return ma


_SUA_DUOC = {"kenh": {"ten_chuan", "channel_id", "ngach_ma", "thi_truong_ma",
                      "loai_kenh", "kenh_goc_ma", "phu_trach", "bo_phan_chu_quan",
                      "ghi_chu"},
             "ngach": {"ten_chuan", "trang_thai", "ghi_chu"},
             "thi_truong": {"ten", "ngon_ngu", "ghi_chu"}}


def sua_thuc_the(conn, loai: str, ma_thuc_the: str, **truong) -> None:
    """Sửa trường vận hành. MÃ KHÔNG BAO GIỜ đổi qua đường này (bất biến —
    'ma' lọt vào **truong cũng bị whitelist _SUA_DUOC lọc bỏ)."""
    hop_le = _SUA_DUOC[loai]
    xau = {k: v for k, v in truong.items() if k in hop_le}
    if not xau:
        return
    if "ten_chuan" in xau:
        _kiem_bi_danh_ranh(conn, xau["ten_chuan"], ma_bo_qua=ma_thuc_the)
    if "channel_id" in xau and not (xau["channel_id"] or "").strip():
        xau["channel_id"] = None
    bang = "thi_truong" if loai == "thi_truong" else loai
    dat = ", ".join(f"{k}=?" for k in xau)
    with conn:
        cur = conn.execute(f"UPDATE {bang} SET {dat} WHERE ma=?",
                           (*xau.values(), ma_thuc_the))
        if cur.rowcount == 0:
            raise ValueError(f"không có {loai} mã {ma_thuc_the}")


def doi_trang_thai_kenh(conn, ma: str, trang_thai: str, cho_an: bool = False) -> None:
    """cho_an=True mở thêm nấc ẨN (khai_tu) — chỉ khai_tu_kenh() dùng, để đường
    stepper công khai không đặt được Retired."""
    hop_le = TRANG_THAI_KENH_HOP_LE if cho_an else TRANG_THAI_KENH
    if trang_thai not in hop_le:
        raise ValueError("trạng thái kênh không hợp lệ")
    with conn:
        cur = conn.execute("UPDATE kenh SET trang_thai=? WHERE ma=?", (trang_thai, ma))
        if cur.rowcount == 0:
            raise ValueError(f"không có kênh mã {ma}")


def them_bi_danh(conn, thuc_the_ma: str, bi_danh: str) -> None:
    can = chuan_hoa_ten(bi_danh)
    if not can:
        raise ValueError("bí danh rỗng")
    r = conn.execute("SELECT thuc_the_ma FROM bi_danh WHERE bi_danh=?", (can,)).fetchone()
    if r:
        raise ValueError(f"'{bi_danh}' đã là bí danh của {r['thuc_the_ma']}")
    with conn:
        conn.execute("INSERT INTO bi_danh VALUES (?,?,?)", (can, thuc_the_ma, _luc()))


def xoa_bi_danh(conn, bi_danh: str) -> None:
    with conn:
        conn.execute("DELETE FROM bi_danh WHERE bi_danh=?", (chuan_hoa_ten(bi_danh),))


def dat_lien_ket(conn, thuc_the_ma: str, app_slug: str, khoa: str) -> None:
    """Khóa của thực thể ở một app — rỗng = gỡ liên kết."""
    with conn:
        if (khoa or "").strip():
            conn.execute(
                "INSERT INTO lien_ket_app VALUES (?,?,?,?) "
                "ON CONFLICT(thuc_the_ma, app_slug) DO UPDATE SET khoa=excluded.khoa",
                (thuc_the_ma, app_slug, khoa.strip(), _luc()))
        else:
            conn.execute("DELETE FROM lien_ket_app WHERE thuc_the_ma=? AND app_slug=?",
                         (thuc_the_ma, app_slug))


def khai_tu_kenh(conn, ma: str) -> None:
    """Gỡ mềm — dòng còn nguyên, trạng thái khai_tu (chỉ Owner, route kiểm)."""
    doi_trang_thai_kenh(conn, ma, "khai_tu", cho_an=True)


# ---------- CỬA EXCEL (bất biến hiến pháp: text-thuần, Excel là cửa xuất/nhập) ----------

_COT_CSV = ("loai", "ma", "ten_chuan", "bi_danh", "ngach_ma", "thi_truong_ma",
            "channel_id", "loai_kenh", "trang_thai", "kenh_goc_ma", "phu_trach",
            "bo_phan_chu_quan", "ngon_ngu", "ghi_chu", "tao_luc")


def xuat_csv(duong: Path | str | None = None) -> str:
    ra = io.StringIO()
    w = csv.DictWriter(ra, fieldnames=_COT_CSV, extrasaction="ignore")
    w.writeheader()
    for t in doc_danh_muc(duong):
        w.writerow({k: ("" if t.get(k) is None else t.get(k, "")) for k in _COT_CSV})
    return ra.getvalue()
