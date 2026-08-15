# -*- coding: utf-8 -*-
"""Tạo users TEST cho giai đoạn dev (P1 — trước khi có IAM ở P2).

Chạy từ root:  python -m nen.gateway.tao_user_test
Ghi data/nen/users.txt (nguyên tử) với 3 tài khoản, mật khẩu đều là: test123
KHÔNG dùng cho bản thay thế thật — user thật migrate từ hệ cũ ở P2.
"""
import os
import tempfile
from pathlib import Path

import bcrypt

ROOT = Path(__file__).resolve().parents[2]
DUONG = Path(os.environ.get("NEN_USERS", ROOT / "data" / "nen" / "users.txt"))

USERS_TEST = [
    ("owner", "Ban quản trị", 5),
    ("quanly", "Kinh doanh", 4),
    ("nhanvien", "Vận hành - Sản xuất", 2),
]


def main() -> None:
    DUONG.parent.mkdir(parents=True, exist_ok=True)
    dong = ["# users TEST (P1) — tên:bcrypt:bộ_phận:level — mật khẩu chung: test123"]
    for ten, bo_phan, level in USERS_TEST:
        h = bcrypt.hashpw(b"test123", bcrypt.gensalt()).decode()
        dong.append(f"{ten}:{h}:{bo_phan}:{level}")
    fd, tmp = tempfile.mkstemp(dir=DUONG.parent, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write("\n".join(dong) + "\n")
    os.replace(tmp, DUONG)  # ghi nguyên tử — bất biến kế thừa
    print(f"Đã ghi {DUONG} — 3 user: owner / quanly / nhanvien (mật khẩu: test123)")


if __name__ == "__main__":
    main()
