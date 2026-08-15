# -*- coding: utf-8 -*-
"""KÉT CẤU HÌNH — API key + model LLM của CẢ HỆ ở MỘT chỗ (mảnh ③, Phase 3).

Hai ngăn tách bạch (chuẩn Vault/12-factor, hiến pháp mục 2.3):
- cau_hinh: không mật (provider, model, base_url, timeout) — đọc/ghi thẳng.
- bi_mat:   API key — mã hóa Fernet bằng khóa máy `data/nen/ket.key`, DB không
  bao giờ chứa plaintext, UI chỉ hiện ••••<4 cuối>.

ponytail: khóa Fernet nằm file cùng máy → trần bảo vệ = quyền NTFS thư mục data
(mọi tiến trình chạy cùng user đọc được). Đủ cho LAN 1 máy như đã chốt; nâng cấp:
DPAPI/TPM khi tách nhiều máy.

Quy ước khóa LLM theo VAI (writer/critic/extractor/router…):
  cau_hinh:  llm.<vai>.provider | llm.<vai>.model | llm.<vai>.base_url
  bi_mat:    llm.<vai>.api_key
  chung:     llm.timeout (mặc định 60) | llm.retry (mặc định 0)  ← bài học hệ cũ
             19/07 + 06/08 thành LUẬT NỀN: mọi lời gọi LLM có timeout, retry 0.
"""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime
from pathlib import Path

from cryptography.fernet import Fernet

from nen.common import sqlite_migrate

ROOT = Path(__file__).resolve().parents[2]
DUONG_MIGRATIONS = Path(__file__).parent / "migrations"

TIMEOUT_MAC_DINH = 60
RETRY_MAC_DINH = 0


def _duong_db() -> Path:
    return Path(os.environ.get("KET_DB", ROOT / "data" / "nen" / "ket.db"))


def _duong_khoa() -> Path:
    return Path(os.environ.get("KET_KEY", ROOT / "data" / "nen" / "ket.key"))


def ket_noi(duong: Path | str | None = None) -> sqlite3.Connection:
    duong = Path(duong) if duong else _duong_db()
    duong.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(duong, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    sqlite_migrate.migrate(conn, DUONG_MIGRATIONS)
    return conn


def _fernet() -> Fernet:
    f = _duong_khoa()
    if not f.exists():
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(Fernet.generate_key())
    return Fernet(f.read_bytes())


def _gio() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ---------- cấu hình (không mật) ----------

def dat_cau_hinh(conn: sqlite3.Connection, khoa: str, gia_tri: str) -> None:
    with conn:
        conn.execute(
            "INSERT INTO cau_hinh (khoa, gia_tri, sua_luc) VALUES (?,?,?) "
            "ON CONFLICT(khoa) DO UPDATE SET gia_tri=excluded.gia_tri, "
            "sua_luc=excluded.sua_luc", (khoa, gia_tri, _gio()))


def lay_cau_hinh(conn: sqlite3.Connection, khoa: str, mac_dinh: str = "") -> str:
    r = conn.execute("SELECT gia_tri FROM cau_hinh WHERE khoa=?", (khoa,)).fetchone()
    return r["gia_tri"] if r else mac_dinh


# ---------- bí mật (mã hóa) ----------

def dat_bi_mat(conn: sqlite3.Connection, khoa: str, gia_tri: str) -> None:
    ma = _fernet().encrypt(gia_tri.encode("utf-8")).decode("ascii")
    with conn:
        conn.execute(
            "INSERT INTO bi_mat (khoa, gia_tri_ma, duoi, sua_luc) VALUES (?,?,?,?) "
            "ON CONFLICT(khoa) DO UPDATE SET gia_tri_ma=excluded.gia_tri_ma, "
            "duoi=excluded.duoi, sua_luc=excluded.sua_luc",
            (khoa, ma, gia_tri[-4:], _gio()))


def lay_bi_mat(conn: sqlite3.Connection, khoa: str) -> str | None:
    r = conn.execute("SELECT gia_tri_ma FROM bi_mat WHERE khoa=?", (khoa,)).fetchone()
    if not r:
        return None
    return _fernet().decrypt(r["gia_tri_ma"].encode("ascii")).decode("utf-8")


def liet_ke(conn: sqlite3.Connection) -> dict:
    """Cho UI: cau_hinh đầy đủ; bi_mat CHỈ khóa + đuôi (không bao giờ trả plaintext)."""
    return {
        "cau_hinh": [dict(r) for r in
                     conn.execute("SELECT * FROM cau_hinh ORDER BY khoa").fetchall()],
        "bi_mat": [{"khoa": r["khoa"], "duoi": r["duoi"], "sua_luc": r["sua_luc"]}
                   for r in conn.execute("SELECT * FROM bi_mat ORDER BY khoa").fetchall()],
    }


# ---------- LLM theo vai ----------

def cau_hinh_llm(conn: sqlite3.Connection, vai: str) -> dict:
    """Trả cấu hình LLM đủ dùng cho một vai. Vai chưa khai → provider rỗng
    (app tự quyết mock/báo thiếu — KHÔNG bịa mặc định gọi nhầm nhà cung cấp)."""
    return {
        "vai": vai,
        "provider": lay_cau_hinh(conn, f"llm.{vai}.provider"),
        "model": lay_cau_hinh(conn, f"llm.{vai}.model"),
        "base_url": lay_cau_hinh(conn, f"llm.{vai}.base_url"),
        "api_key": lay_bi_mat(conn, f"llm.{vai}.api_key") or "",
        "timeout": int(lay_cau_hinh(conn, "llm.timeout", str(TIMEOUT_MAC_DINH))),
        "retry": int(lay_cau_hinh(conn, "llm.retry", str(RETRY_MAC_DINH))),
    }
