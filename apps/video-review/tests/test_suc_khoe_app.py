# -*- coding: utf-8 -*-
"""B3 giám sát lan sang video-review (31/08/2026) — /api/suc-khoe.

- `nas`: video KHÔNG nằm trong app — VR_NAS_DIR rời là thêm/xem video chết.
- `ffprobe`: thiếu thì app chỉ bỏ bước dò codec (thiết kế 20/08) → canh_bao,
  KHÔNG loi; nhưng phải thấy được vì VR_FFPROBE đang trỏ C:\\OutlierY (di sản,
  xóa ~22/09) — ngày đó module này tự đỏ nhắc chuyển ffmpeg.
"""
from fastapi.testclient import TestClient

from src.main import app

tc = TestClient(app)


def _mo_dun():
    r = tc.get("/api/suc-khoe")
    assert r.status_code == 200
    b = r.json()
    assert b["app"] == "video-review"
    return {m["ten"]: m for m in b["mo_dun"]}


def test_nas_chua_khai_canh_bao(monkeypatch):
    monkeypatch.delenv("VR_NAS_DIR", raising=False)
    md = _mo_dun()
    assert md["nas"]["trang_thai"] == "canh_bao"


def test_nas_khai_ma_mat_la_loi(tmp_path, monkeypatch):
    monkeypatch.setenv("VR_NAS_DIR", str(tmp_path / "bay-hoi"))
    md = _mo_dun()
    assert md["nas"]["trang_thai"] == "loi"


def test_nas_song_va_ffprobe_thieu(tmp_path, monkeypatch):
    monkeypatch.setenv("VR_NAS_DIR", str(tmp_path))
    monkeypatch.setenv("VR_FFPROBE", str(tmp_path / "khong-co.exe"))
    monkeypatch.setenv("PATH", str(tmp_path))  # chặn ffprobe trong PATH thật
    md = _mo_dun()
    assert md["nas"]["trang_thai"] == "ok"
    assert md["ffprobe"]["trang_thai"] == "canh_bao"
    assert "codec" in md["ffprobe"]["chi_tiet"]


def test_ffprobe_co_la_ok(tmp_path, monkeypatch):
    exe = tmp_path / "ffprobe.exe"
    exe.write_bytes(b"x")
    monkeypatch.setenv("VR_FFPROBE", str(exe))
    md = _mo_dun()
    assert md["ffprobe"]["trang_thai"] == "ok"
