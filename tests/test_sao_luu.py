# -*- coding: utf-8 -*-
"""Test P4: log chuẩn + backup manifest + DIỄN TẬP RESTORE (tự động hóa ngay
trong test — backup chưa từng restore thử là backup trên niềm tin)."""
import json
import sqlite3

import httpx
import pytest

from nen.common import nhat_ky, sao_luu


# ---------- log chuẩn ----------

def test_nhat_ky_ghi_dung_duong_nam_thang(tmp_path, monkeypatch):
    monkeypatch.setenv("LOGS_DIR", str(tmp_path))
    nhat_ky.ghi("ai-agent", "owner", "nap_tai_lieu", "KD-2026-XYZ")
    files = list(tmp_path.rglob("*.log"))
    assert len(files) == 1
    assert files[0].parent.parent.parent.name == "ai-agent"   # <app>/<năm>/<tháng>
    dong = json.loads(files[0].read_text(encoding="utf-8").strip())
    assert dong["hanh_dong"] == "nap_tai_lieu" and dong["user"] == "owner"


# ---------- backup + restore ----------

def _manifest(tmp_path, stores):
    f = tmp_path / "apps.json"
    f.write_text(json.dumps({"du_lieu_nen": stores, "apps": []}), encoding="utf-8")
    return f


def test_sqlite_backup_va_dien_tap_restore(tmp_path):
    db = tmp_path / "vi_du.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE t (x)")
    conn.executemany("INSERT INTO t VALUES (?)", [(1,), (2,), (3,)])
    conn.commit()   # GIỮ CONNECTION MỞ — chứng minh VACUUM INTO chạy trên db sống

    mf = _manifest(tmp_path, [{"ten": "vi-du", "loai": "sqlite", "duong": str(db)}])
    bc = sao_luu.chay_backup(tmp_path / "backup", mf)
    assert bc[0]["trang_thai"] == "ok"

    conn.execute("INSERT INTO t VALUES (4)")   # dữ liệu đổi SAU backup
    conn.commit()
    conn.close()

    snapshot = tmp_path / "backup" / "nen" / "vi-du" / "vi_du.snapshot.db"
    sao_luu.khoi_phuc_sqlite(snapshot, db)     # DIỄN TẬP RESTORE
    c2 = sqlite3.connect(db)
    assert c2.execute("SELECT COUNT(*) FROM t").fetchone()[0] == 3  # point-in-time
    c2.close()


def test_kho_file_copy_du(tmp_path):
    kho = tmp_path / "kho" / "2026" / "08"
    kho.mkdir(parents=True)
    (kho / "bao-cao.xlsx").write_bytes(b"du lieu")
    mf = _manifest(tmp_path, [{"ten": "kho", "loai": "kho-file",
                               "duong": str(tmp_path / "kho")}])
    bc = sao_luu.chay_backup(tmp_path / "backup", mf)
    assert bc[0]["trang_thai"] == "ok"
    assert (tmp_path / "backup" / "nen" / "kho" / "2026" / "08"
            / "bao-cao.xlsx").read_bytes() == b"du lieu"


def test_loi_mot_store_khong_giet_ca_dot(tmp_path):
    mf = _manifest(tmp_path, [
        {"ten": "thieu", "loai": "sqlite", "duong": str(tmp_path / "khong-co.db")},
        {"ten": "la", "loai": "kieu-la", "duong": str(tmp_path)},
    ])
    bc = sao_luu.chay_backup(tmp_path / "backup", mf)
    assert bc[0]["trang_thai"] == "thieu-nguon"
    assert bc[1]["trang_thai"].startswith("loai-la")
    assert (tmp_path / "backup" / "ket-qua.jsonl").exists()   # sổ backup luôn ghi


def test_manifest_that_co_store_nen():
    stores = sao_luu._doc_manifest()
    ten = {s["ten"] for s in stores if s["app"] == "nen"}
    assert {"iam-db", "ket-db", "ket-khoa", "qdrant"} <= ten


def test_qdrant_snapshot_tich_hop(tmp_path):
    """Chạy khi Qdrant test :6343 đang sống (start-all) — trigger snapshot THẬT."""
    try:
        if httpx.get("http://127.0.0.1:6343/readyz", timeout=2).status_code != 200:
            pytest.skip("qdrant test khong chay")
    except httpx.HTTPError:
        pytest.skip("qdrant test khong chay")
    store = {"app": "nen", "ten": "qdrant", "loai": "qdrant",
             "duong": "data/qdrant/storage/snapshots",
             "url": "http://127.0.0.1:6343"}
    kq = sao_luu.sao_luu_store(store, tmp_path / "backup")
    assert kq["trang_thai"] == "ok"
    assert (tmp_path / "backup" / "nen" / "qdrant" / kq["snapshot"]).exists()


def test_giu_snapshot_moi_nhat_don_ban_cu(tmp_path):
    """Snapshot Qdrant là bản ĐẦY ĐỦ, không dọn thì phình mãi (23/08/2026: 119 bản
    = 118GB trong khi kho thật 1,1GB). Giữ N bản mới nhất, xóa kèm .checksum."""
    import time
    from nen.common.sao_luu import giu_snapshot_moi_nhat
    for i in range(6):
        f = tmp_path / f"full-snapshot-{i}.snapshot"
        f.write_bytes(b"x")
        f.with_name(f.name + ".checksum").write_text("c", encoding="utf-8")
        time.sleep(0.01)                      # mtime tăng dần → bản 5 là mới nhất
    da_xoa = giu_snapshot_moi_nhat(tmp_path, 2)
    con = sorted(f.name for f in tmp_path.glob("*.snapshot"))
    assert con == ["full-snapshot-4.snapshot", "full-snapshot-5.snapshot"]
    assert len(da_xoa) == 4
    assert sorted(f.name for f in tmp_path.glob("*.checksum")) == [
        "full-snapshot-4.snapshot.checksum", "full-snapshot-5.snapshot.checksum"]
    # gọi lại khi đã đủ ít → không xóa thêm gì; giu=0 là lệnh vô nghĩa, phải trơ
    assert giu_snapshot_moi_nhat(tmp_path, 2) == []
    assert giu_snapshot_moi_nhat(tmp_path, 0) == []
    assert len(list(tmp_path.glob("*.snapshot"))) == 2
