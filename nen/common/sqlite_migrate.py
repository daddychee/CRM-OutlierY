# -*- coding: utf-8 -*-
"""Migration SQLite theo bậc — dùng CHUNG cho mọi DB tầng nền (iam.db, ket.db…).

Mỗi DB có thư mục migrations/ chứa NNN_ten.sql; bảng schema_version ghi bậc hiện
tại (hiến pháp mục 2.1 — DB tự biết phiên bản của nó).

ponytail: migrate chạy mỗi lần mở kết nối — khi không có gì mới chỉ tốn 1 query
SELECT (vài trăm µs). Nâng cấp nếu cần: cache phiên bản theo đường db trong process.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path


def migrate(conn: sqlite3.Connection, thu_muc_migrations: Path) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_version (phien_ban INTEGER NOT NULL)")
    dong = conn.execute("SELECT phien_ban FROM schema_version").fetchone()
    if dong is None:
        conn.execute("INSERT INTO schema_version VALUES (0)")
    hien_tai = dong[0] if dong else 0
    for f in sorted(thu_muc_migrations.glob("*.sql")):
        so = int(f.name.split("_")[0])
        if so > hien_tai:
            with conn:
                conn.executescript(f.read_text(encoding="utf-8"))
                conn.execute("UPDATE schema_version SET phien_ban=?", (so,))
            hien_tai = so
