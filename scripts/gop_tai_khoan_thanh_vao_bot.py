# -*- coding: utf-8 -*-
"""Gộp tài khoản Owner đời V2 `thanh` vào `Bot` (Owner chốt 19/08).

BỐI CẢNH: `thanh` là tài khoản Owner thời V2 của Lê Công Thành (chủ doanh
nghiệp); sang V3 anh dùng `Bot` và muốn giữ tên đó. Hai tài khoản = hai chìa
khóa Owner, `thanh` ngưng dùng từ 16/08 → gộp dữ liệu SỞ HỮU về `Bot` rồi KHÓA
`thanh` (không xóa: xóa là mất khả năng tra 10 thao tác nó từng làm).

RANH GIỚI CÓ CHỦ ĐÍCH — chuyển cái gì, giữ cái gì:
  CHUYỂN (dữ liệu SỞ HỮU, nói "tài sản này của ai"):
    · Qdrant payload `owner` + cột "Phụ trách" của _catalog.csv (cùng một thứ,
      PHẢI đổi cùng nhau — nguyên tắc 21/07: Qdrant TRƯỚC, catalog SAU, hai kho
      không bao giờ lệch).
    · content-ultimate/library/index.json `created_by`.
  GIỮ NGUYÊN (SỬ LIỆU, nói "ai đã làm gì lúc nào" — viết lại là bịa lịch sử):
    · nhat_ky_quyen · seo-optimize/logs/audit.jsonl
    · content-ultimate/admin/{access,history}.jsonl
    · chấm công (giờ hiện diện có thật của phiên đăng nhập đó)
    · cau_kho_thieu_da_xoa.json · nas_dong_bo.json (tài khoản Windows riêng)

Mặc định LIỆT KÊ. Ghi thật: --chay (backup chạy TRƯỚC). Idempotent.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import httpx  # noqa: E402

from nen.iam import iam  # noqa: E402

CU, MOI = "thanh", "Bot"
QDRANT = os.getenv("QDRANT_URL", "http://127.0.0.1:6343").rstrip("/")
KHO = "kho_tri_thuc"
CATALOG = ROOT / "data" / "ai-agent" / "kho" / "kho-tai-lieu" / "_catalog.csv"
LIBRARY = ROOT / "data" / "content-ultimate" / "library" / "index.json"
COT_PHU_TRACH = "Phụ trách"


def _dem_qdrant(ai: str) -> int:
    r = httpx.post(f"{QDRANT}/collections/{KHO}/points/count",
                   json={"filter": {"must": [{"key": "owner", "match": {"value": ai}}]},
                         "exact": True}, timeout=15)
    r.raise_for_status()
    return r.json()["result"]["count"]


def _doc_catalog() -> list[dict]:
    if not CATALOG.exists():
        return []
    return list(csv.DictReader(io.StringIO(CATALOG.read_text(encoding="utf-8-sig"))))


def _doc_library() -> list:
    if not LIBRARY.exists():
        return []
    d = json.loads(LIBRARY.read_text(encoding="utf-8"))
    return d if isinstance(d, list) else d.get("items", [])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--chay", action="store_true", help="ghi thật (mặc định liệt kê)")
    tham_so = ap.parse_args()

    rows = _doc_catalog()
    so_cat = sum(1 for r in rows if (r.get(COT_PHU_TRACH) or "").strip() == CU)
    lib = _doc_library()
    so_lib = sum(1 for it in lib if isinstance(it, dict) and it.get("created_by") == CU)
    try:
        so_qd = _dem_qdrant(CU)
    except Exception as e:
        print(f"KHÔNG nối được Qdrant ({e}) — DỪNG: không đổi catalog khi chưa "
              "đổi được payload, hai kho phải nhất quán.")
        return 1

    conn = iam.ket_noi()
    try:
        tk = iam.lay_tai_khoan(conn, CU)
        print(f"Gộp '{CU}' → '{MOI}':")
        print(f"  Qdrant payload owner : {so_qd} point")
        print(f"  _catalog.csv Phụ trách: {so_cat} dòng")
        print(f"  library created_by    : {so_lib} mục")
        print(f"  tài khoản '{CU}'      : "
              + (f"còn sống (khoa={tk['khoa']}) → sẽ KHÓA" if tk else "KHÔNG còn"))
        print("  GIỮ NGUYÊN: nhật ký quyền · audit SEO · log Content · chấm công")

        if not tham_so.chay:
            print("\n(chỉ liệt kê — thêm --chay để ghi thật; backup tự chạy trước)")
            return 0

        bk_dir = ROOT / "data" / "nen" / "backup"
        bk_dir.mkdir(parents=True, exist_ok=True)
        bk = bk_dir / "iam-truoc-gop-thanh.db"
        if bk.exists():
            bk.unlink()
        conn.execute("VACUUM INTO ?", (str(bk),))
        if CATALOG.exists():
            shutil.copy2(CATALOG, bk_dir / "_catalog-truoc-gop-thanh.csv")
        if LIBRARY.exists():
            shutil.copy2(LIBRARY, bk_dir / "library-index-truoc-gop-thanh.json")
        print(f"\nĐã backup vào {bk_dir}")

        # 1) QDRANT TRƯỚC (nguyên tắc 21/07) + kiểm chứng lại bằng cách đếm
        if so_qd:
            r = httpx.post(f"{QDRANT}/collections/{KHO}/points/payload?wait=true",
                           json={"payload": {"owner": MOI},
                                 "filter": {"must": [{"key": "owner",
                                                      "match": {"value": CU}}]}},
                           timeout=60)
            r.raise_for_status()
            con_lai = _dem_qdrant(CU)
            if con_lai:
                print(f"LỖI: Qdrant còn {con_lai} point owner='{CU}' — DỪNG, "
                      "KHÔNG ghi catalog (tránh hai kho lệch).")
                return 1
            print(f"  Qdrant: {so_qd} point → owner='{MOI}' (kiểm lại: còn 0)")

        # 2) CATALOG SAU — ghi nguyên tử, chỉ đụng ô Phụ trách
        if so_cat:
            for r0 in rows:
                if (r0.get(COT_PHU_TRACH) or "").strip() == CU:
                    r0[COT_PHU_TRACH] = MOI
            tam = CATALOG.with_suffix(".csv.tmp")
            with tam.open("w", encoding="utf-8-sig", newline="") as f:
                w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                w.writeheader()
                w.writerows(rows)
            os.replace(tam, CATALOG)
            print(f"  _catalog.csv: {so_cat} dòng → Phụ trách='{MOI}'")

        # 3) Thư viện Content Ultimate
        if so_lib:
            d = json.loads(LIBRARY.read_text(encoding="utf-8"))
            items = d if isinstance(d, list) else d.get("items", [])
            for it in items:
                if isinstance(it, dict) and it.get("created_by") == CU:
                    it["created_by"] = MOI
            tam = LIBRARY.with_suffix(".json.tmp")
            tam.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(tam, LIBRARY)
            print(f"  library/index.json: {so_lib} mục → created_by='{MOI}'")

        # 4) KHÓA tài khoản cũ (không xóa — giữ đường tra lịch sử).
        #    Đi thẳng SQL: luật sắt 2 (iam._kiem_khong_dung_owner) cấm Owner
        #    thao tác lên Owner khác, kể cả qua giao diện.
        if tk and not tk["khoa"]:
            with conn:
                conn.execute("UPDATE tai_khoan SET khoa=1 WHERE ten=?", (CU,))
            print(f"  tài khoản '{CU}': ĐÃ KHÓA (bản ghi + nhật ký giữ nguyên)")
        iam.ghi_nhat_ky(conn, "(gop tai khoan)", "gop_tai_khoan",
                        f"{CU} → {MOI}: qdrant {so_qd} · catalog {so_cat} · "
                        f"library {so_lib}; khóa {CU}, giữ mọi nhật ký")
        print("\nXong.")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
