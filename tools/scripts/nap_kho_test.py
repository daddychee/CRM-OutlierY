# -*- coding: utf-8 -*-
"""Nạp kho TEST cho platform v2 — chuyển thể từ scripts/nap_lai_kho.py hệ cũ.

Nguồn: data/tri-thuc/kho/kho-tai-lieu (BẢN SAO từ D:\\OUTLIERY-backup, 52 file).
Đích: Qdrant TEST :6343. ID điểm = UUID5(doc_code#chunk) → chạy lại là ghi đè.
Chạy: python tools/scripts/nap_kho_test.py   (Qdrant test phải đang bật)
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "apps" / "tri-thuc"
os.environ["MOCK_MODE"] = "false"
os.environ.setdefault("QDRANT_URL", "http://127.0.0.1:6343")
os.environ.setdefault("KHO_TAI_LIEU", str(ROOT / "data" / "tri-thuc" / "kho" / "kho-tai-lieu"))
sys.path.insert(0, str(APP))
os.chdir(APP)

from src.main import doc_catalog                     # noqa: E402
from src.vector_client import ALIAS, QdrantClientWrapper  # noqa: E402

client = QdrantClientWrapper()
kho = Path(os.environ["KHO_TAI_LIEU"])
rows = doc_catalog()
print(f"Catalog: {len(rows)} dòng. Bắt đầu nạp vào {os.environ['QDRANT_URL']}...")

ok = loi = 0
for r in rows:
    ma = r["Mã tài liệu"]
    f = kho / r["Ngăn"] / r["Tên file mới"]
    if not f.is_file():
        print(f"  BỎ QUA {ma}: không thấy file {f.name}")
        loi += 1
        continue
    ml = (r["Level tối thiểu"] or "").strip()
    metadata = {
        "title": r["Tiêu đề"], "keywords": r["Chủ đề/Từ khóa"],
        "owner": r["Phụ trách"], "version": r["Phiên bản"],
        "department": r["Bộ phận"], "doc_type": r["Loại tài liệu"],
        "effective_status": r["Hiệu lực"], "access_level": r["Mức truy cập"],
        "doc_code": ma, "import_date": r["Ngày nhập"],
        "original_filename": r["Tên file mới"],
        "is_scanned": "true" if (r["PDF scan"] or "").strip().lower() in ("có", "co", "true") else "false",
        "tang_nguon": (r["Tầng nguồn"] or "").strip() or "noi_bo",
        "nguon_ten": (r["Tên nguồn"] or "").strip() or "Official",
    }
    if ml.isdigit():
        metadata["min_level"] = int(ml)
    try:
        client.upload_document(str(f), metadata)
        print(f"  OK {ma}: {client.dem_chunk_doc_code(ma)} chunk  ({f.name})")
        ok += 1
    except Exception as e:  # noqa: BLE001
        print(f"  LỖI {ma}: {e}")
        loi += 1

print(f"\nXong: {ok} nạp, {loi} lỗi/bỏ. Tổng point: {client.client.count(ALIAS).count}")
