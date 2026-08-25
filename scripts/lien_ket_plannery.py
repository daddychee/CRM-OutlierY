# -*- coding: utf-8 -*-
"""Ghi LIÊN KẾT PlannerY vào danh bạ: K-xxx ↔ ch_xxx và N-xxx ↔ pr_xxx.

Sau khi Owner ghép kênh/ngách trong PlannerY (khối "kênh chưa gắn danh bạ"),
plan.json đã biết mã đế. Chiều ngược lại — đế biết khóa của app — nằm ở bảng
`lien_ket_app`, và chỉ Owner được sửa (DE.md mục 1 Q4), nên nó đi bằng script
này chứ không phải app tự ghi.

Chạy:  python -m scripts.lien_ket_plannery [--chay]

MẶC ĐỊNH CHỈ LIỆT KÊ (bài học gan_tang_nguon hệ cũ: liệt kê trước, --chay mới
ghi). Có --chay thì VACUUM INTO backup danh_ba.db trước khi ghi. Idempotent:
liên kết đã đúng thì bỏ qua; đang trỏ khóa KHÁC thì cảnh báo và KHÔNG tự đè —
một thực thể một khóa mỗi app, đè nhầm là mất dấu vết ghép cũ.
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

from nen.common import danh_ba

ROOT = Path(__file__).resolve().parents[1]


def _duong_plan() -> Path:
    thu_muc = os.environ.get("PLANNER_DATA_DIR") or (ROOT / "data" / "plannery")
    return Path(thu_muc) / "plan.json"


def gom(plan: dict) -> list[tuple[str, str, str]]:
    """[(mã đế, khóa app, nhãn để người đọc)] — cả ngách lẫn kênh."""
    ra = []
    for pr in plan.get("projects", []):
        if pr.get("ngach_ma"):
            ra.append((pr["ngach_ma"], pr["id"], f"ngách {pr.get('name', '')}"))
        for ch in pr.get("channels", []):
            if ch.get("kenh_ma"):
                ra.append((ch["kenh_ma"], ch["id"], f"kênh {ch.get('name', '')}"))
    return ra


def chay(ghi: bool) -> int:
    duong = _duong_plan()
    if not duong.exists():
        print(f"Không thấy {duong} — đặt PLANNER_DATA_DIR nếu dữ liệu ở chỗ khác.")
        return 1
    plan = json.loads(duong.read_text(encoding="utf-8"))
    cap = gom(plan)
    if not cap:
        print("plan.json chưa có kênh/ngách nào gắn mã đế — ghép trong PlannerY trước.")
        return 0

    ds = {t["ma"]: t for t in danh_ba.doc_danh_muc()}
    viec, bo_qua, canh_bao = [], [], []
    for ma, khoa, nhan in cap:
        thuc_the = ds.get(ma)
        if not thuc_the:
            canh_bao.append(f"{ma} ({nhan}) không có trong danh bạ — mã sai hoặc đã bị xóa.")
            continue
        cu = (thuc_the.get("lien_ket") or {}).get("plannery")
        if cu == khoa:
            bo_qua.append(f"{ma} ↔ {khoa} ({nhan})")
        elif cu:
            canh_bao.append(f"{ma} ({nhan}) đang trỏ '{cu}', plan.json nói '{khoa}' "
                            f"— sửa tay ở General › Channels, script KHÔNG tự đè.")
        else:
            viec.append((ma, khoa, nhan))

    print(f"— đã đúng sẵn: {len(bo_qua)}")
    for d in bo_qua:
        print(f"    {d}")
    print(f"— sẽ ghi: {len(viec)}")
    for ma, khoa, nhan in viec:
        print(f"    {ma} ↔ {khoa}   ({nhan})")
    if canh_bao:
        print(f"— cần người xử lý: {len(canh_bao)}")
        for d in canh_bao:
            print(f"    ⚠ {d}")
    if not ghi:
        print("\n(chỉ liệt kê — thêm --chay để ghi)")
        return 0
    if not viec:
        print("\nKhông có gì để ghi.")
        return 0

    goc = danh_ba._duong_hieu_luc(None)
    bk = goc.parent / "backup" / f"danh_ba-truoc-lien-ket-plannery-{datetime.now():%Y%m%d-%H%M%S}.db"
    bk.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(goc)
    c.execute("VACUUM INTO ?", (str(bk),))
    c.close()
    print(f"\nĐã backup {bk}")

    conn = danh_ba.ket_noi()
    try:
        for ma, khoa, _ in viec:
            danh_ba.dat_lien_ket(conn, ma, "plannery", khoa)
        conn.commit()
    finally:
        conn.close()
    print(f"Đã ghi {len(viec)} liên kết.")
    return 0


if __name__ == "__main__":
    sys.exit(chay("--chay" in sys.argv))
