# -*- coding: utf-8 -*-
"""Gán mã tập cho các bản ghi có trước khi app biết khái niệm 'tập'.

Mã tập rút bằng chính kho_video.ma_tap() — cùng một luật với lúc app chạy, để
không có hai cách hiểu khác nhau về cùng một tên file.

    python scripts/gan_ma_tap.py            # CHỈ liệt kê, không ghi gì
    python scripts/gan_ma_tap.py --chay     # ghi mã tập vào sổ

Bản ghi không rút được mã (tên không theo quy ước) thì BỎ QUA, báo ra để người
đặt tay — thà để trống còn hơn gom nhầm hai tập vào nhau.
"""
from __future__ import annotations

import sys
from pathlib import Path

_APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_APP))
sys.path.insert(0, str(_APP.parents[1]))

from src import kho_video     # noqa: E402


def soat() -> list[dict]:
    conn = kho_video.ket_noi()
    try:
        hang = [dict(h) for h in conn.execute(
            "SELECT * FROM video WHERE trang_thai != 'da_xoa' ORDER BY id")]
    finally:
        conn.close()
    ra = []
    for v in hang:
        ra.append({"ma": v["ma"], "ten": v["ten"], "cu": v["ma_tap"],
                   "moi": kho_video.ma_tap(v)})
    return ra


def main() -> None:
    kho_video.khoi_tao()
    ds = soat()
    can = [d for d in ds if d["moi"] and d["moi"] != d["cu"]]
    khong = [d for d in ds if not d["moi"]]

    nhom: dict[str, list[str]] = {}
    for d in ds:
        if d["moi"]:
            nhom.setdefault(d["moi"], []).append(d["ma"])
    for ma in sorted(nhom):
        print(f"  {ma:8} {len(nhom[ma])} bản: {', '.join(nhom[ma])}")
    print(f"\n  {len(nhom)} tập · {len(can)} bản ghi cần gán · {len(khong)} bản không rút được mã")
    for d in khong:
        print(f"    BỎ QUA (đặt tay): {d['ma']} — {d['ten']}")

    if "--chay" not in sys.argv:
        print("\n(chỉ liệt kê — thêm --chay để ghi vào sổ)")
        return
    for d in can:
        kho_video.gan_tap(d["ma"], d["moi"], "duyet")
    print(f"\nĐã gán mã tập cho {len(can)} bản ghi.")


if __name__ == "__main__":
    main()
