# -*- coding: utf-8 -*-
"""can_dong_goi — KHÔNG đòi đóng gói lại khi snapshot đã chứa bản mới (sự cố 11/09/2026).

SỰ CỐ: mở dashboard OLD NEWBIE lúc 21:07 → trang TỰ chạy lại chuỗi đóng gói (4 lời gọi
LLM, ~7 phút) và ghi đè báo cáo tốt bằng bản kém hơn (3 khối NGHĨA → 2). Nguyên nhân:
can_dong_goi so với mtime của THƯ MỤC snapshot; snapshot cùng ngày ghi đè file trong thư
mục CÓ SẴN, mà ghi đè file thì mtime thư mục KHÔNG đổi → đo thật: thư mục 19:11:14 trong
khi file bên trong đã 21:10:07 → luôn True → mỗi lần mở trang lại đóng gói.

Luật ghim: so với NỘI DUNG snapshot (file mới nhất bên trong), không phải mtime thư mục.
"""
import json
import os
import time

from src import niche_run


def _du_an(tmp_path, monkeypatch, thu_muc_snap_cu: bool):
    goc = tmp_path / "projects"
    d = goc / "Proj_X"
    (d / "Report").mkdir(parents=True)
    snap = d / "snapshots" / "2026-09-11"
    snap.mkdir(parents=True)
    (d / "snapshots" / "index.json").write_text(
        json.dumps([{"id": "2026-09-11", "artifacts": [],
                     "bao_cao": ["BAO-CAO-8-PHASE.html"]}]), encoding="utf-8")
    monkeypatch.setenv("NICHE_PROJECTS_DIR", str(goc))
    bao_cao = d / "Report" / "BAO-CAO-8-PHASE.html"
    bao_cao.write_text("x", encoding="utf-8")
    ban_sao = snap / "BAO-CAO-8-PHASE.html"
    ban_sao.write_text("x", encoding="utf-8")
    t = time.time()
    os.utime(bao_cao, (t, t))
    os.utime(ban_sao, (t, t))          # snapshot.py chép kiểu giữ nguyên mtime nguồn
    if thu_muc_snap_cu:                # đúng hình dạng sự cố: thư mục có từ lần đóng gói trước
        os.utime(snap, (t - 7200, t - 7200))
    return d


def test_snapshot_da_chua_ban_moi_thi_khong_dong_goi_lai(tmp_path, monkeypatch):
    _du_an(tmp_path, monkeypatch, thu_muc_snap_cu=True)
    assert niche_run.can_dong_goi("Proj_X") is False


def test_bao_cao_moi_hon_snapshot_thi_van_dong_goi(tmp_path, monkeypatch):
    """Ca đối chứng: pipeline vừa dựng báo cáo SAU snapshot → vẫn phải đóng gói."""
    d = _du_an(tmp_path, monkeypatch, thu_muc_snap_cu=True)
    t = time.time() + 300
    os.utime(d / "Report" / "BAO-CAO-8-PHASE.html", (t, t))
    assert niche_run.can_dong_goi("Proj_X") is True
