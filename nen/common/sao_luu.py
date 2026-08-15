# -*- coding: utf-8 -*-
"""Backup theo MANIFEST (mảnh ⑤, Phase 4) — đọc mục `du_lieu` của từng app trong
nen/rules/apps.json + mục `du_lieu_nen` (store của tầng nền). Store không khai =
không được backup (Luật 6: mọi dữ liệu phải có danh phận).

Luật theo loại (hiến pháp mục 2.2 — DB sống KHÔNG copy trần):
- sqlite      → `VACUUM INTO` ra file snapshot (db đang mở WAL vẫn ra bản lành)
- kho-file / json / csv → copy cây/file (ghi nguyên tử ở nguồn nên file luôn lành)
- qdrant      → POST /snapshots qua API rồi copy file snapshot mới nhất
- file-khoa   → copy file lẻ (vd ket.key — chính nó là chìa để mở bi_mat)

Chạy tay / theo lịch:  python -m nen.common.sao_luu  (đích: env BACKUP_DIR,
mặc định D:/OUTLIERY-v2-backup — KHÔNG đụng D:/OUTLIERY-backup của hệ cũ).
Mỗi lần chạy ghi ket-qua.jsonl tại đích — backup không có sổ là backup trên niềm tin.
"""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

import httpx

from nen.common.hop_dong import DUONG_MAC_DINH as DUONG_APPS

ROOT = Path(__file__).resolve().parents[2]


def _doc_manifest(duong: Path | None = None) -> list[dict]:
    """Gom mọi store từ apps[].du_lieu + du_lieu_nen, gắn kèm app sở hữu."""
    du_lieu = json.loads((duong or DUONG_APPS).read_text(encoding="utf-8-sig"))
    stores: list[dict] = []
    for muc in du_lieu.get("du_lieu_nen", []):
        stores.append({"app": "nen", **muc})
    for app in du_lieu.get("apps", []):
        for muc in app.get("du_lieu", []):
            stores.append({"app": app["slug"], **muc})
    return stores


def _sao_sqlite(nguon: Path, dich: Path) -> None:
    dich.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(nguon, timeout=15)
    try:
        dich.unlink(missing_ok=True)          # VACUUM INTO đòi đích chưa tồn tại
        conn.execute("VACUUM INTO ?", (str(dich),))
    finally:
        conn.close()


def _sao_cay(nguon: Path, dich: Path) -> None:
    if nguon.is_dir():
        shutil.copytree(nguon, dich, dirs_exist_ok=True)
    else:
        dich.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(nguon, dich)


def _sao_qdrant(store: dict, dich: Path) -> str:
    """Trigger snapshot qua API rồi copy file mới nhất từ snapshots_path local."""
    url = store.get("url", "http://127.0.0.1:6343")
    r = httpx.post(f"{url}/snapshots", timeout=120)
    r.raise_for_status()
    ten = r.json()["result"]["name"]
    nguon = Path(store["duong"]) / ten
    _sao_cay(nguon, dich / ten)
    return ten


def sao_luu_store(store: dict, dich_goc: Path) -> dict:
    """Backup MỘT store; lỗi trả trong kết quả — một store hỏng không giết cả đợt."""
    ket_qua = {"app": store["app"], "ten": store["ten"], "loai": store["loai"],
               "trang_thai": "ok", "luc": datetime.now().isoformat(timespec="seconds")}
    try:
        nguon = ROOT / store["duong"] if not Path(store["duong"]).is_absolute() \
            else Path(store["duong"])
        dich = dich_goc / store["app"] / store["ten"]
        if store["loai"] == "qdrant":
            ket_qua["snapshot"] = _sao_qdrant(store, dich)
        elif not nguon.exists():
            ket_qua["trang_thai"] = "thieu-nguon"
        elif store["loai"] == "sqlite":
            _sao_sqlite(nguon, dich / (nguon.stem + ".snapshot.db"))
        elif store["loai"] in ("kho-file", "json", "csv", "file-khoa"):
            _sao_cay(nguon, dich)
        else:
            ket_qua["trang_thai"] = f"loai-la:{store['loai']}"
    except Exception as e:  # noqa: BLE001 — backup phải chạy hết danh sách
        ket_qua["trang_thai"] = f"loi: {e}"
    return ket_qua


def chay_backup(dich_goc: Path | str | None = None,
                manifest: Path | None = None) -> list[dict]:
    dich_goc = Path(dich_goc or os.environ.get("BACKUP_DIR", "D:/OUTLIERY-v2-backup"))
    dich_goc.mkdir(parents=True, exist_ok=True)
    bao_cao = [sao_luu_store(s, dich_goc) for s in _doc_manifest(manifest)]
    with open(dich_goc / "ket-qua.jsonl", "a", encoding="utf-8") as f:
        for dong in bao_cao:
            f.write(json.dumps(dong, ensure_ascii=False) + "\n")
    return bao_cao


def khoi_phuc_sqlite(snapshot: Path, dich: Path) -> None:
    """Restore = chép snapshot (file db hoàn chỉnh từ VACUUM INTO) về chỗ cũ.
    GHI ĐÈ — chỉ chạy khi chủ đích khôi phục."""
    dich.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(snapshot, dich)


if __name__ == "__main__":
    for dong in chay_backup():
        print(f"[{dong['trang_thai']:>12}] {dong['app']}/{dong['ten']}")
