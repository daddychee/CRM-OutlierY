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


def quyen_nhan_su(claims: dict) -> bool:
    """Ai được vào trang Nhân sự (UI_FLOW.md mục 6, đúng V1): Owner + HR L3+.
    Giỏ ủy quyền duyet_ho_so mở thêm cho Admin ủy quyền (mặc định TẮT)."""
    return co_quyen(claims, "duyet_ho_so") or \
        (claims.get("bo_phan") == HR_BO_PHAN and claims["level"] >= 3)


def tao_nguoi(conn: sqlite3.Connection, ai_lam: dict | None, ho_ten: str,
              bo_phan: str, vi_tri: str = "") -> dict:
    if ai_lam is not None and not quyen_nhan_su(ai_lam):
        raise LoiIam("Bạn không có quyền quản hồ sơ nhân sự.")
    if not ho_ten.strip():
        raise LoiIam("Thiếu họ tên.")
    so = conn.execute(
        "SELECT COALESCE(MAX(CAST(SUBSTR(ma,4) AS INTEGER)),0)+1 s FROM nguoi"
    ).fetchone()["s"]
    ma = f"NS-{so:03d}"
    with conn:
        conn.execute(
            "INSERT INTO nguoi (ma, ho_ten, bo_phan, vi_tri, trang_thai, tao_luc) "
            "VALUES (?,?,?,?, 'hoat_dong', ?)",
            (ma, ho_ten.strip(), bo_phan, vi_tri, _gio()))
    ghi_nhat_ky(conn, (ai_lam or {}).get("ten", "(khoi tao)"), "tao_nguoi",
                f"{ma} {ho_ten} {bo_phan}")
    return dict(conn.execute("SELECT * FROM nguoi WHERE ma=?", (ma,)).fetchone())


def sua_nguoi(conn: sqlite3.Connection, ai_lam: dict | None, ma: str,
              ho_ten: str | None = None, bo_phan: str | None = None,
              vi_tri: str | None = None, trang_thai: str | None = None) -> None:
    """Sửa hồ sơ người (trả nợ 'hồ sơ chỉ tạo được' — DE.md mục 9/12). None = giữ
    nguyên trường đó. KHÔNG có xóa hồ sơ: nghỉ việc = trang_thai 'nghi' (gỡ mềm,
    mã NS bất biến như doc_code)."""
    if ai_lam is not None and not quyen_nhan_su(ai_lam):
        raise LoiIam("Bạn không có quyền quản hồ sơ nhân sự.")
    if not conn.execute("SELECT 1 FROM nguoi WHERE ma=?", (ma,)).fetchone():
        raise LoiIam("Không có hồ sơ này.")
    if ho_ten is not None and not ho_ten.strip():
        raise LoiIam("Thiếu họ tên.")
    if trang_thai is not None and trang_thai not in TRANG_THAI_NGUOI:
        raise LoiIam("Trạng thái phải là: " + " / ".join(TRANG_THAI_NGUOI))
    cap_nhat, gia_tri = [], []
    for cot, gt in (("ho_ten", ho_ten.strip() if ho_ten else None),
                    ("bo_phan", bo_phan), ("vi_tri", vi_tri),
                    ("trang_thai", trang_thai)):
        if gt is not None:
            cap_nhat.append(f"{cot}=?")
            gia_tri.append(gt)
    if not cap_nhat:
        return
    with conn:
        conn.execute(f"UPDATE nguoi SET {', '.join(cap_nhat)} WHERE ma=?",
                     (*gia_tri, ma))
    ghi_nhat_ky(conn, (ai_lam or {}).get("ten", "(khoi tao)"), "sua_nguoi",
                f"{ma}: {', '.join(cap_nhat)} = {gia_tri}")


def liet_ke_nguoi(conn: sqlite3.Connection) -> list[dict]:
    return [dict(r) for r in conn.execute("SELECT * FROM nguoi ORDER BY ma").fetchall()]


# ---------- quyền ----------

def gan_override(conn: sqlite3.Connection, ai_lam: dict, ten_dich: str,
                 app_slug: str, hanh_dong: str, cho_phep: bool | None) -> None:
    """Tick ô quyền lẻ. cho_phep=None là gỡ tick. Tick giỏ Owner tuyệt đối → chặn."""
    luat = _luat()
    if hanh_dong in luat.get("gio_owner_tuyet_doi", []):
        raise LoiIam("Quyền này thuộc giỏ Owner tuyệt đối — không tick được.")
    if ai_lam["level"] < OWNER_LEVEL:
        raise LoiIam("Chỉ Owner được tick quyền lẻ (bảng phân quyền là của Owner).")
    _kiem_khong_tu_sua(ai_lam, ten_dich)
    tk = lay_tai_khoan(conn, ten_dich)
    _kiem_khong_dung_owner(ai_lam, tk)
    with conn:
        conn.execute(
            "DELETE FROM quyen_override WHERE ten_tai_khoan=? AND app_slug=? AND hanh_dong=?",
            (ten_dich, app_slug, hanh_dong))
        if cho_phep is not None:
            conn.execute(
                "INSERT INTO quyen_override (ten_tai_khoan, app_slug, hanh_dong, cho_phep) "
                "VALUES (?,?,?,?)", (ten_dich, app_slug, hanh_dong, int(cho_phep)))
    ghi_nhat_ky(conn, ai_lam["ten"], "gan_override",
                f"{ten_dich} {app_slug}/{hanh_dong} = {cho_phep}")


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


def vai_cho_app(claims: dict, app_slug: str) -> str:
    """Vai gửi sang app (X-Remote-Role) — đọc bảng vai per app, thiếu thì bảng chung."""
    luat = _luat()
    bang = (luat.get("apps", {}).get(app_slug, {}) or {}).get("vai") \
        or luat.get("vai_mac_dinh", {})
    return bang.get(str(claims["level"]), bang.get("mac_dinh", "viewer"))
