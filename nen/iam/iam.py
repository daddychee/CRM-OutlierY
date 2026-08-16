# -*- coding: utf-8 -*-
"""IAM — MỘT sổ người–tài khoản–vai–quyền cho cả hệ (mảnh ② tầng nền, Phase 2).

Mô hình 3 khối (đối chiếu Keycloak/Odoo): NGƯỜI (hồ sơ NS) → TÀI KHOẢN (đăng nhập)
→ QUYỀN (luật ngoài code nen/rules/phan_quyen.json + ô tick quyen_override).

Hai giỏ quản trị:
- GIỎ OWNER TUYỆT ĐỐI (vault, két, bảng phân quyền, xóa cứng): CHỈ level 5,
  không tick nào đè được.
- GIỎ ỦY QUYỀN (tài khoản thường ngày, duyệt hồ sơ, nạp tài liệu, duyệt Q&A,
  giám sát): level 5 HOẶC tài khoản bật admin_uy_quyen.

Ba luật sắt của Admin ủy quyền (kèm luật chống-tự-khóa kế thừa hệ cũ):
1. KHÔNG tự nâng quyền mình (mọi thao tác quyền lên chính mình bị chặn,
   trừ đổi mật khẩu bản thân).
2. KHÔNG đụng tài khoản Owner (level 5) — kể cả xem như thao tác được.
3. MỌI thao tác ghi nhật ký (nhat_ky_quyen) — không có thay đổi quyền vô danh.

App KHÔNG giữ sổ vai riêng — gateway phát claims mỗi request từ sổ này.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
from datetime import datetime
from pathlib import Path

import bcrypt

from nen.common import sqlite_migrate

ROOT = Path(__file__).resolve().parents[2]
DUONG_MIGRATIONS = Path(__file__).parent / "migrations"
DUONG_PHAN_QUYEN = ROOT / "nen" / "rules" / "phan_quyen.json"

OWNER_LEVEL = 5


class LoiIam(ValueError):
    """Lỗi nghiệp vụ IAM — thông điệp tiếng Việt, route trả 4xx."""


# ---------- kết nối + migration ----------

def _duong_db() -> Path:
    return Path(os.environ.get("IAM_DB", ROOT / "data" / "nen" / "iam.db"))


def ket_noi(duong: Path | str | None = None) -> sqlite3.Connection:
    duong = Path(duong) if duong else _duong_db()
    duong.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(duong, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    _migrate(conn)
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    sqlite_migrate.migrate(conn, DUONG_MIGRATIONS)


def _gio() -> str:
    return datetime.now().isoformat(timespec="seconds")


_luat_cache: dict = {}


def _luat() -> dict:
    """Cache theo mtime — đổi phan_quyen.json vẫn ăn ngay, hết mở file mỗi lần
    co_quyen (load test 16/08: blocking I/O trên event loop làm loop nghẹt)."""
    mtime = DUONG_PHAN_QUYEN.stat().st_mtime
    if _luat_cache.get("mtime") != mtime:
        _luat_cache["mtime"] = mtime
        _luat_cache["luat"] = json.loads(
            DUONG_PHAN_QUYEN.read_text(encoding="utf-8-sig"))
    return _luat_cache["luat"]


# ---------- nhật ký ----------

def ghi_nhat_ky(conn: sqlite3.Connection, ai: str, hanh_dong: str, chi_tiet: str) -> None:
    with conn:
        conn.execute(
            "INSERT INTO nhat_ky_quyen (luc, ai, hanh_dong, chi_tiet) VALUES (?,?,?,?)",
            (_gio(), ai, hanh_dong, chi_tiet))


def doc_nhat_ky(conn: sqlite3.Connection, gioi_han: int = 50) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM nhat_ky_quyen ORDER BY id DESC LIMIT ?", (gioi_han,)).fetchall()
    return [dict(r) for r in rows]


# ---------- tài khoản ----------

def lay_tai_khoan(conn: sqlite3.Connection, ten: str) -> dict | None:
    r = conn.execute("SELECT * FROM tai_khoan WHERE ten=?", (ten,)).fetchone()
    return dict(r) if r else None


def liet_ke_tai_khoan(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("SELECT * FROM tai_khoan ORDER BY level DESC, ten").fetchall()
    return [dict(r) for r in rows]


def dem_tai_khoan(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) c FROM tai_khoan").fetchone()["c"]


def xac_thuc(conn: sqlite3.Connection, ten: str, mat_khau: str) -> dict | None:
    """Đăng nhập → claims. Sai/khóa → None (không phân biệt lý do ra ngoài)."""
    tk = lay_tai_khoan(conn, ten.strip())
    if not tk or tk["khoa"]:
        return None
    if not bcrypt.checkpw(mat_khau.encode("utf-8"), tk["mk_bcrypt"].encode("utf-8")):
        return None
    return claims_cua(tk)


def claims_cua(tk: dict) -> dict:
    return {"ten": tk["ten"], "bo_phan": tk["bo_phan"], "level": tk["level"],
            "admin_uy_quyen": bool(tk["admin_uy_quyen"]),
            "ten_hien_thi": tk.get("ten_hien_thi", "") or ""}


# ---------- hồ sơ cá nhân (trang Profile — tự phục vụ, UI_FLOW.md mục 8) ----------

def sua_ho_so_ca_nhan(conn: sqlite3.Connection, ai_lam: dict,
                      ten_hien_thi: str = "", email: str = "",
                      dien_thoai: str = "") -> None:
    """Tự sửa hồ sơ CỦA MÌNH. Bộ phận/level KHÔNG sửa được ở đây (Owner quản —
    nhân viên tự sửa là tự thăng quyền)."""
    with conn:
        conn.execute(
            "UPDATE tai_khoan SET ten_hien_thi=?, email=?, dien_thoai=? WHERE ten=?",
            (ten_hien_thi.strip()[:80], email.strip()[:120],
             dien_thoai.strip()[:30], ai_lam["ten"]))
    ghi_nhat_ky(conn, ai_lam["ten"], "sua_ho_so_ca_nhan", ai_lam["ten"])


def doi_mat_khau_ca_nhan(conn: sqlite3.Connection, ai_lam: dict,
                         mk_hien_tai: str, mk_moi: str) -> None:
    """Đổi mật khẩu CỦA MÌNH — bắt gõ mật khẩu hiện tại (luật V1, v2 từng thiếu)."""
    if not xac_thuc(conn, ai_lam["ten"], mk_hien_tai):
        raise LoiIam("Current password is incorrect.")
    doi_mat_khau(conn, ai_lam, ai_lam["ten"], mk_moi, ep_doi_lan_sau=False)


def _kiem_khong_tu_sua(ai_lam: dict, ten_dich: str) -> None:
    if ai_lam["ten"] == ten_dich:
        raise LoiIam("Không được thao tác quyền lên chính mình (luật sắt 1).")


def _kiem_khong_dung_owner(ai_lam: dict, tk_dich: dict | None) -> None:
    """Admin ủy quyền không đụng Owner; Owner cũng không đụng Owner KHÁC (kế thừa)."""
    if tk_dich and tk_dich["level"] >= OWNER_LEVEL and ai_lam["ten"] != tk_dich["ten"]:
        raise LoiIam("Không được thao tác lên tài khoản Owner (luật sắt 2).")


def _yeu_cau_quan_tai_khoan(conn: sqlite3.Connection, ai_lam: dict) -> None:
    if not co_quyen(ai_lam, "quan_tai_khoan"):
        raise LoiIam("Bạn không có quyền quản tài khoản.")


def tao_tai_khoan(conn: sqlite3.Connection, ai_lam: dict | None, ten: str,
                  mat_khau: str, bo_phan: str, level: int,
                  nguoi_ma: str | None = None, phai_doi_mk: bool = True) -> dict:
    """Tạo tài khoản. Sổ RỖNG: cho phép tự khởi tạo nhưng user đầu PHẢI là Owner
    (kế thừa luật hệ cũ — không bao giờ có hệ không Owner)."""
    ten = ten.strip()
    if not re.fullmatch(r"[a-z0-9._-]{2,32}", ten):
        raise LoiIam("Tên đăng nhập chỉ gồm a-z 0-9 . _ - (2–32 ký tự).")
    if not (1 <= int(level) <= 5):
        raise LoiIam("Level phải trong thang 1–5.")
    if len(mat_khau) < 6:
        raise LoiIam("Mật khẩu tối thiểu 6 ký tự.")
    if lay_tai_khoan(conn, ten):
        raise LoiIam("Tên đăng nhập đã tồn tại.")
    if dem_tai_khoan(conn) == 0:
        if int(level) != OWNER_LEVEL:
            raise LoiIam("Tài khoản ĐẦU TIÊN của hệ phải là Owner (level 5).")
    else:
        if ai_lam is None:
            raise LoiIam("Thiếu danh tính người thao tác.")
        _yeu_cau_quan_tai_khoan(conn, ai_lam)
        if int(level) >= OWNER_LEVEL and ai_lam["level"] < OWNER_LEVEL:
            raise LoiIam("Chỉ Owner được tạo tài khoản Owner.")
    h = bcrypt.hashpw(mat_khau.encode("utf-8"), bcrypt.gensalt()).decode()
    with conn:
        conn.execute(
            "INSERT INTO tai_khoan (ten, mk_bcrypt, nguoi_ma, bo_phan, level, "
            "admin_uy_quyen, phai_doi_mk, khoa, tao_luc) VALUES (?,?,?,?,?,0,?,0,?)",
            (ten, h, nguoi_ma, bo_phan, int(level), int(phai_doi_mk), _gio()))
    ghi_nhat_ky(conn, (ai_lam or {}).get("ten", "(khoi tao)"), "tao_tai_khoan",
                f"{ten} bo_phan={bo_phan} level={level}")
    return lay_tai_khoan(conn, ten)


def doi_mat_khau(conn: sqlite3.Connection, ai_lam: dict, ten_dich: str,
                 mk_moi: str, ep_doi_lan_sau: bool = False) -> None:
    """Tự đổi mật khẩu mình: luôn được. Đổi cho người khác: cần quyền quản tài
    khoản + không đụng Owner."""
    tk = lay_tai_khoan(conn, ten_dich)
    if not tk:
        raise LoiIam("Không có tài khoản này.")
    if ai_lam["ten"] != ten_dich:
        _yeu_cau_quan_tai_khoan(conn, ai_lam)
        _kiem_khong_dung_owner(ai_lam, tk)
    if len(mk_moi) < 6:
        raise LoiIam("Mật khẩu tối thiểu 6 ký tự.")
    h = bcrypt.hashpw(mk_moi.encode("utf-8"), bcrypt.gensalt()).decode()
    with conn:
        conn.execute("UPDATE tai_khoan SET mk_bcrypt=?, phai_doi_mk=? WHERE ten=?",
                     (h, int(ep_doi_lan_sau), ten_dich))
    ghi_nhat_ky(conn, ai_lam["ten"], "doi_mat_khau", ten_dich)


def sua_tai_khoan(conn: sqlite3.Connection, ai_lam: dict, ten_dich: str,
                  bo_phan: str | None = None, level: int | None = None,
                  admin_uy_quyen: bool | None = None, khoa: bool | None = None,
                  nguoi_ma: str | None = None) -> None:
    """Sửa thuộc tính quyền của tài khoản — nơi 3 luật sắt canh cửa."""
    tk = lay_tai_khoan(conn, ten_dich)
    if not tk:
        raise LoiIam("Không có tài khoản này.")
    _yeu_cau_quan_tai_khoan(conn, ai_lam)
    _kiem_khong_tu_sua(ai_lam, ten_dich)          # luật sắt 1
    _kiem_khong_dung_owner(ai_lam, tk)            # luật sắt 2
    if level is not None:
        if int(level) >= OWNER_LEVEL and ai_lam["level"] < OWNER_LEVEL:
            raise LoiIam("Chỉ Owner được nâng tài khoản lên Owner.")
        if not (1 <= int(level) <= 5):
            raise LoiIam("Level phải trong thang 1–5.")
    if admin_uy_quyen is not None and ai_lam["level"] < OWNER_LEVEL:
        raise LoiIam("Chỉ Owner được bật/tắt Admin ủy quyền.")  # ủy quyền là việc của chủ
    cap_nhat, gia_tri = [], []
    for cot, gt in (("bo_phan", bo_phan), ("level", level),
                    ("admin_uy_quyen", admin_uy_quyen), ("khoa", khoa),
                    ("nguoi_ma", nguoi_ma)):
        if gt is not None:
            cap_nhat.append(f"{cot}=?")
            gia_tri.append(int(gt) if isinstance(gt, bool) else gt)
    if not cap_nhat:
        return
    with conn:
        conn.execute(f"UPDATE tai_khoan SET {', '.join(cap_nhat)} WHERE ten=?",
                     (*gia_tri, ten_dich))
    ghi_nhat_ky(conn, ai_lam["ten"], "sua_tai_khoan",
                f"{ten_dich}: {', '.join(cap_nhat)} = {gia_tri}")


def xoa_tai_khoan(conn: sqlite3.Connection, ai_lam: dict, ten_dich: str) -> None:
    tk = lay_tai_khoan(conn, ten_dich)
    if not tk:
        raise LoiIam("Không có tài khoản này.")
    _yeu_cau_quan_tai_khoan(conn, ai_lam)
    if ai_lam["ten"] == ten_dich:
        raise LoiIam("Không được tự xóa mình (chống tự khóa).")
    _kiem_khong_dung_owner(ai_lam, tk)
    with conn:
        conn.execute("DELETE FROM tai_khoan WHERE ten=?", (ten_dich,))
        conn.execute("DELETE FROM quyen_override WHERE ten_tai_khoan=?", (ten_dich,))
    ghi_nhat_ky(conn, ai_lam["ten"], "xoa_tai_khoan", ten_dich)


# ---------- người (hồ sơ) ----------

HR_BO_PHAN = "Hành chính Nhân sự"
TRANG_THAI_NGUOI = ("cho_duyet", "hoat_dong", "nghi")
# MỘT nguồn danh mục bộ phận cả hệ (DE.md mục 10: 4→5, thêm Kế toán) — hồ sơ mới
# phải chọn từ đây; bản ghi cũ ngoài danh mục vẫn ĐỌC được (grandfather 04/08 hệ cũ).
DEPARTMENTS = ("Kinh doanh", "Vận hành - Sản xuất", "Hành chính Nhân sự",
               "Kế toán", "Ban quản trị")
CAP_BAC = ("intern", "staff", "leader", "manager")   # lưu slug, UI hiện nhãn EN
DUONG_CHUC_DANH = ROOT / "nen" / "rules" / "chuc_danh.csv"

_chuc_danh_cache: dict = {}


def doc_chuc_danh() -> list[dict]:
    """Danh mục VỊ TRÍ ngoài code (nen/rules/chuc_danh.csv — kế thừa V2): thêm vị
    trí = thêm dòng Excel, không sửa code. Cột bo_phan gắn vị trí ↔ bộ phận
    (';' = nhiều, RỖNG = mọi bộ phận). Cache theo mtime như _luat."""
    import csv
    mtime = DUONG_CHUC_DANH.stat().st_mtime
    if _chuc_danh_cache.get("mtime") != mtime:
        ds = []
        with open(DUONG_CHUC_DANH, encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                if (r.get("chuc_danh") or "").strip():
                    ds.append({"chuc_danh": r["chuc_danh"].strip(),
                               "bo_phan": [b.strip() for b in
                                           (r.get("bo_phan") or "").split(";")
                                           if b.strip()]})
        _chuc_danh_cache.update(mtime=mtime, ds=ds)
    return _chuc_danh_cache["ds"]


def _kiem_cap_bo_phan_vi_tri(bo_phan: str, vi_tri: str) -> None:
    """Kiểm CẶP bộ phận×vị trí Ở SERVER (bài học 01/08 hệ cũ: 2 dropdown kiểm độc
    lập vẫn lọt người sai bộ phận — phải kiểm trên giá trị SAU GỘP)."""
    if bo_phan not in DEPARTMENTS:
        raise LoiIam("Bộ phận phải chọn từ danh mục: " + " / ".join(DEPARTMENTS))
    if not vi_tri:
        return                                    # vị trí bỏ trống = chưa khai
    muc = next((c for c in doc_chuc_danh() if c["chuc_danh"] == vi_tri), None)
    if muc is None:
        raise LoiIam("Vị trí không có trong danh mục chuc_danh.csv.")
    if muc["bo_phan"] and bo_phan not in muc["bo_phan"]:
        raise LoiIam(f"Vị trí '{vi_tri}' không thuộc bộ phận '{bo_phan}'.")


def _kiem_truong_ho_so(cap_bac: str = "", ngay_sinh: str = "",
                       ngay_vao: str = "", cccd: str = "") -> None:
    """Validate các trường hồ sơ mở rộng (rỗng = chưa khai, cho qua)."""
    if cap_bac and cap_bac not in CAP_BAC:
        raise LoiIam("Cấp bậc phải là: " + " / ".join(CAP_BAC))
    for nhan, gt in (("Ngày sinh", ngay_sinh), ("Ngày vào làm", ngay_vao)):
        if gt and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", gt):
            raise LoiIam(f"{nhan} phải dạng YYYY-MM-DD.")
    if cccd and not re.fullmatch(r"\d{12}", cccd):
        raise LoiIam("CCCD phải gồm đúng 12 chữ số (hoặc bỏ trống).")


def quyen_nhan_su(claims: dict) -> bool:
    """Ai được vào trang Nhân sự (UI_FLOW.md mục 6, đúng V1): Owner + HR L3+.
    Giỏ ủy quyền duyet_ho_so mở thêm cho Admin ủy quyền (mặc định TẮT)."""
    return co_quyen(claims, "duyet_ho_so") or \
        (claims.get("bo_phan") == HR_BO_PHAN and claims["level"] >= 3)


def tao_nguoi(conn: sqlite3.Connection, ai_lam: dict | None, ho_ten: str,
              bo_phan: str, vi_tri: str = "", ngay_sinh: str = "",
              cccd: str = "", dia_chi: str = "", ngay_vao: str = "",
              cap_bac: str = "") -> dict:
    if ai_lam is not None and not quyen_nhan_su(ai_lam):
        raise LoiIam("Bạn không có quyền quản hồ sơ nhân sự.")
    if not ho_ten.strip():
        raise LoiIam("Thiếu họ tên.")
    _kiem_cap_bo_phan_vi_tri(bo_phan, vi_tri)
    _kiem_truong_ho_so(cap_bac, ngay_sinh, ngay_vao, cccd)
    so = conn.execute(
        "SELECT COALESCE(MAX(CAST(SUBSTR(ma,4) AS INTEGER)),0)+1 s FROM nguoi"
    ).fetchone()["s"]
    ma = f"NS-{so:03d}"
    with conn:
        conn.execute(
            "INSERT INTO nguoi (ma, ho_ten, bo_phan, vi_tri, trang_thai, tao_luc, "
            "ngay_sinh, cccd, dia_chi, ngay_vao, cap_bac) "
            "VALUES (?,?,?,?, 'hoat_dong', ?,?,?,?,?,?)",
            (ma, ho_ten.strip(), bo_phan, vi_tri, _gio(),
             ngay_sinh, cccd, dia_chi.strip(), ngay_vao, cap_bac))
    ghi_nhat_ky(conn, (ai_lam or {}).get("ten", "(khoi tao)"), "tao_nguoi",
                f"{ma} {ho_ten} {bo_phan}")
    return dict(conn.execute("SELECT * FROM nguoi WHERE ma=?", (ma,)).fetchone())


def sua_nguoi(conn: sqlite3.Connection, ai_lam: dict | None, ma: str,
              ho_ten: str | None = None, bo_phan: str | None = None,
              vi_tri: str | None = None, trang_thai: str | None = None,
              ngay_sinh: str | None = None, cccd: str | None = None,
              dia_chi: str | None = None, ngay_vao: str | None = None,
              cap_bac: str | None = None) -> None:
    """Sửa hồ sơ người (trả nợ 'hồ sơ chỉ tạo được' — DE.md mục 9/12). None = giữ
    nguyên trường đó. KHÔNG có xóa hồ sơ: nghỉ việc = trang_thai 'nghi' (gỡ mềm,
    mã NS bất biến như doc_code). Đụng bộ phận/vị trí → kiểm CẶP trên giá trị
    SAU GỘP (bài học 01/08); không đụng → bản ghi cũ ngoài danh mục vẫn sửa được
    trạng thái (grandfather)."""
    if ai_lam is not None and not quyen_nhan_su(ai_lam):
        raise LoiIam("Bạn không có quyền quản hồ sơ nhân sự.")
    hien = conn.execute("SELECT * FROM nguoi WHERE ma=?", (ma,)).fetchone()
    if not hien:
        raise LoiIam("Không có hồ sơ này.")
    if ho_ten is not None and not ho_ten.strip():
        raise LoiIam("Thiếu họ tên.")
    if trang_thai is not None and trang_thai not in TRANG_THAI_NGUOI:
        raise LoiIam("Trạng thái phải là: " + " / ".join(TRANG_THAI_NGUOI))
    if bo_phan is not None or vi_tri is not None:
        _kiem_cap_bo_phan_vi_tri(
            bo_phan if bo_phan is not None else hien["bo_phan"],
            vi_tri if vi_tri is not None else (hien["vi_tri"] or ""))
    _kiem_truong_ho_so(cap_bac or "", ngay_sinh or "", ngay_vao or "", cccd or "")
    cap_nhat, gia_tri = [], []
    for cot, gt in (("ho_ten", ho_ten.strip() if ho_ten else None),
                    ("bo_phan", bo_phan), ("vi_tri", vi_tri),
                    ("trang_thai", trang_thai), ("ngay_sinh", ngay_sinh),
                    ("cccd", cccd), ("dia_chi", dia_chi),
                    ("ngay_vao", ngay_vao), ("cap_bac", cap_bac)):
        if gt is not None:
            cap_nhat.append(f"{cot}=?")
            gia_tri.append(gt)
    if not cap_nhat:
        return
    with conn:
        conn.execute(f"UPDATE nguoi SET {', '.join(cap_nhat)} WHERE ma=?",
                     (*gia_tri, ma))
    # Nhật ký KHÔNG ghi giá trị cccd/dia_chi (nhạy cảm) — chỉ ghi tên cột đã đổi.
    ghi_nhat_ky(conn, (ai_lam or {}).get("ten", "(khoi tao)"), "sua_nguoi",
                f"{ma}: doi {', '.join(c.rstrip('=?') for c in cap_nhat)}")


def liet_ke_nguoi(conn: sqlite3.Connection) -> list[dict]:
    return [dict(r) for r in conn.execute("SELECT * FROM nguoi ORDER BY ma").fetchall()]


# ---------- quyền ----------

def gan_override(conn: sqlite3.Connection, ai_lam: dict, ten_dich: str,
                 app_slug: str, hanh_dong: str, cho_phep: bool | None,
                 ly_do: str = "") -> None:
    """Tick ô quyền lẻ. cho_phep=None là gỡ tick (không cần lý do). Đặt cho/chặn
    BẮT BUỘC lý do (mockup P5 — mọi ngoại lệ tra được vì sao). Tick giỏ Owner
    tuyệt đối → chặn."""
    luat = _luat()
    if hanh_dong in luat.get("gio_owner_tuyet_doi", []):
        raise LoiIam("Quyền này thuộc giỏ Owner tuyệt đối — không tick được.")
    if ai_lam["level"] < OWNER_LEVEL:
        raise LoiIam("Chỉ Owner được tick quyền lẻ (bảng phân quyền là của Owner).")
    _kiem_khong_tu_sua(ai_lam, ten_dich)
    tk = lay_tai_khoan(conn, ten_dich)
    _kiem_khong_dung_owner(ai_lam, tk)
    if cho_phep is not None and not ly_do.strip():
        raise LoiIam("Ngoại lệ phải có LÝ DO (để sổ P5 tra được vì sao).")
    with conn:
        conn.execute(
            "DELETE FROM quyen_override WHERE ten_tai_khoan=? AND app_slug=? AND hanh_dong=?",
            (ten_dich, app_slug, hanh_dong))
        if cho_phep is not None:
            conn.execute(
                "INSERT INTO quyen_override (ten_tai_khoan, app_slug, hanh_dong, "
                "cho_phep, ly_do, ai_gan, luc) VALUES (?,?,?,?,?,?,?)",
                (ten_dich, app_slug, hanh_dong, int(cho_phep), ly_do.strip(),
                 ai_lam["ten"], _gio()))
    ghi_nhat_ky(conn, ai_lam["ten"], "gan_override",
                f"{ten_dich} {app_slug}/{hanh_dong} = {cho_phep}"
                + (f" ({ly_do.strip()})" if ly_do.strip() else ""))


# ---------- CẤP TRUY CẬP (acting — mockup P3, DE.md mục 14) ----------

def dat_cap_truy_cap(conn: sqlite3.Connection, ai_lam: dict, ten_dich: str,
                     cap: int | None, ly_do: str = "") -> None:
    """Truy cập như cấp 1-4 — chức danh thật KHÔNG đổi; cap=None là gỡ (về chức
    danh thật). KHÔNG áp lên Owner thật (level 5) — chống tự khóa; chỉ Owner đặt."""
    if ai_lam["level"] < OWNER_LEVEL:
        raise LoiIam("Chỉ Owner được đặt cấp truy cập.")
    _kiem_khong_tu_sua(ai_lam, ten_dich)
    tk = lay_tai_khoan(conn, ten_dich)
    if not tk:
        raise LoiIam("Không có tài khoản này.")
    _kiem_khong_dung_owner(ai_lam, tk)
    if tk["level"] >= OWNER_LEVEL:
        raise LoiIam("Owner thật không bao giờ bị đổi cấp truy cập.")
    with conn:
        conn.execute("DELETE FROM cap_truy_cap WHERE ten=?", (ten_dich,))
        if cap is not None:
            if not (1 <= int(cap) <= 4):
                raise LoiIam("Cấp truy cập phải trong thang 1–4.")
            conn.execute(
                "INSERT INTO cap_truy_cap (ten, cap, ly_do, ai_gan, luc) "
                "VALUES (?,?,?,?,?)",
                (ten_dich, int(cap), ly_do.strip(), ai_lam["ten"], _gio()))
    ghi_nhat_ky(conn, ai_lam["ten"], "dat_cap_truy_cap",
                f"{ten_dich} cap={cap}" + (f" ({ly_do.strip()})" if ly_do.strip() else ""))


def doc_cap_truy_cap(conn: sqlite3.Connection, ten: str) -> dict | None:
    r = conn.execute("SELECT * FROM cap_truy_cap WHERE ten=?", (ten,)).fetchone()
    return dict(r) if r else None


def hieu_luc(claims: dict, conn: sqlite3.Connection) -> dict:
    """Claims với LEVEL HIỆU LỰC: có cấp truy cập → level = cap (giữ level_that
    để UI minh bạch). Owner thật KHÔNG bao giờ bị đổi. Áp MỘT chỗ ở gateway lúc
    dựng claims — mọi kiểm quyền sau đó tự ăn (ưu tiên: override > acting > luật)."""
    if claims["level"] >= OWNER_LEVEL:
        return claims
    r = conn.execute("SELECT cap FROM cap_truy_cap WHERE ten=?",
                     (claims["ten"],)).fetchone()
    if not r:
        return claims
    return {**claims, "level_that": claims["level"], "level": int(r["cap"])}


def co_quyen(claims: dict, hanh_dong: str, app_slug: str = "*",
             conn: sqlite3.Connection | None = None) -> bool:
    """MỘT cửa kiểm quyền cho cả hệ (thay các gate rải rác hệ cũ).

    Thứ tự: giỏ Owner tuyệt đối → ô tick lẻ (nếu có conn) → giỏ ủy quyền →
    luật mặc định per app (min_level + bộ phận).
    """
    luat = _luat()
    if hanh_dong in luat.get("gio_owner_tuyet_doi", []):
        return claims["level"] >= OWNER_LEVEL         # không gì đè được
    if conn is not None:
        r = conn.execute(
            "SELECT cho_phep FROM quyen_override WHERE ten_tai_khoan=? "
            "AND app_slug IN (?, '*') AND hanh_dong=? ORDER BY app_slug DESC LIMIT 1",
            (claims["ten"], app_slug, hanh_dong)).fetchone()
        if r is not None:
            return bool(r["cho_phep"])
    if hanh_dong in luat.get("gio_uy_quyen", []):
        return claims["level"] >= OWNER_LEVEL or claims.get("admin_uy_quyen", False)
    dieu_kien = (luat.get("apps", {}).get(app_slug, {}) or {}).get(hanh_dong)
    if dieu_kien is None:
        return claims["level"] >= OWNER_LEVEL         # hành động lạ: fail-closed, trừ Owner
    if claims["level"] < dieu_kien.get("min_level", 1):
        return False
    bo_phan_can = dieu_kien.get("bo_phan")
    if bo_phan_can and claims["bo_phan"] not in bo_phan_can and claims["level"] < 4:
        return False   # L4+ bỏ rào bộ phận (luật Manager 31/07 hệ cũ)
    return True


def hanh_dong_cua_app(app_slug: str) -> dict:
    """Các HÀNH ĐỘNG THẬT app khai trong luật (Permissions v2): mục dict có 'nhan'
    — 'vao'/'vai_xoa'/'_ghi_chu' không phải hành động. nhan/mo_ta là metadata UI,
    co_quyen chỉ đọc min_level/bo_phan."""
    app_luat = _luat().get("apps", {}).get(app_slug, {}) or {}
    return {ma: dk for ma, dk in app_luat.items()
            if isinstance(dk, dict) and "nhan" in dk}


def cac_hanh_dong(claims: dict, app_slug: str,
                  conn: sqlite3.Connection | None = None) -> list[str]:
    """Danh sách hành động user ĐƯỢC PHÉP với một app — gateway tiêm
    X-Remote-Actions mỗi request; app CHỈ TIN CỜ, không tự tính (luật ghim #2)."""
    return [ma for ma in hanh_dong_cua_app(app_slug)
            if co_quyen(claims, ma, app_slug, conn)]


VAI_THEO_LEVEL = {5: "admin", 4: "manager", 3: "leader"}


def vai_cho_app(claims: dict, app_slug: str,
                conn: sqlite3.Connection | None = None) -> str:
    """Vai gửi sang app (X-Remote-Role) — dịch từ HÀNH ĐỘNG, dừng-tại-hit-đầu
    (khuôn vai_trong_app V2, DE.md mục 14): quan_tri → admin; xoa/toan_quyen →
    vai_xoa của app (mặc định admin); sua/tao/them → leader; còn lại viewer.
    App chưa khai hành động → fallback level (5 admin / 4 manager / 3 leader /
    viewer). DANH PHÁP CHUẨN HÓA: 'owner' hết là tên vai app — chữ đó chỉ còn
    MỘT nghĩa là Owner của OUTLIERY (V2 lệch radary/seo gọi owner)."""
    app_luat = _luat().get("apps", {}).get(app_slug, {}) or {}
    hd = hanh_dong_cua_app(app_slug)
    if not hd:
        return VAI_THEO_LEVEL.get(claims["level"], "viewer")
    if co_quyen(claims, "quan_tri", app_slug, conn):
        return "admin"
    for ma in hd:
        if ("xoa" in ma or "toan_quyen" in ma) and co_quyen(claims, ma, app_slug, conn):
            return app_luat.get("vai_xoa", "admin")
    for ma in hd:
        if any(t in ma for t in ("sua", "tao", "them")) \
                and co_quyen(claims, ma, app_slug, conn):
            return "leader"
    return "viewer"
