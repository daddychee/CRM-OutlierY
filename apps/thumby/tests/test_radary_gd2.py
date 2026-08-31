# -*- coding: utf-8 -*-
"""GĐ2 — video đang nổ cùng chủ đề từ RadarY (đọc chỉ-đọc). Test trên DB GIẢ
trong tmp (lệ không-nghiệm-thu-trên-hệ-thật); env RADARY_DB/RADARY_THUMBS
đọc LÚC GỌI HÀM nên monkeypatch ăn ngay."""
import sqlite3
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src import radary_reader as rr
from src.main import app

client = TestClient(app)
CLAIMS = {"X-Remote-User": "nv-kd", "X-Remote-Level": "2"}
NGAY = 86400


@pytest.fixture()
def kho_gia(tmp_path, monkeypatch):
    db = tmp_path / "radary.db"
    c = sqlite3.connect(db)
    c.executescript(
        "CREATE TABLE workspaces (id INTEGER PRIMARY KEY, name TEXT);"
        "CREATE TABLE videos (id INTEGER PRIMARY KEY, workspace_id INT, yt_id TEXT,"
        " channel_yt_id TEXT, channel_title TEXT, title TEXT, pub_ts REAL,"
        " duration_s REAL, tier INT, fail INT, pushed INT, last_vph REAL,"
        " confirm_due REAL, dead INT DEFAULT 0, thumb_ck TEXT);"
        "CREATE TABLE ticks (video_id INT, ts REAL, views REAL);")
    gio = time.time()
    c.execute("INSERT INTO workspaces VALUES (1, 'LIFE IN')")
    vid = [
        # (id, ws, yt_id, kênh, title, tuổi_ngày, dur, vph, dead, ck)
        (1, 1, "aaaaaaaaaaa", "Cabin Diaries", "Living Alone in a Forest Cabin — Winter", 10, 900, 5000, 0, "deadbeef01"),
        (2, 1, "bbbbbbbbbbb", "Wild North", "My First 100 Days in a Forest Cabin", 20, 1200, 9000, 0, None),
        (3, 1, "ccccccccccc", "Off Grid", "Forest Cabin Build From Scratch", 30, 700, 2000, 0, None),
        (4, 1, "ddddddddddd", "Storm Watch", "Two Large Storms Are Coming", 5, 600, 30000, 0, None),  # lạc chủ đề
        (5, 1, "eeeeeeeeeee", "Old Cabin", "Forest Cabin Tour", 90, 500, 8000, 0, None),              # quá 60 ngày
        (6, 1, "fffffffffff", "Dead Ch", "Forest Cabin Alone Again", 15, 500, 7000, 1, None),         # dead
    ]
    for i, ws, yt, kenh, tit, tuoi, dur, vph, dead, ck in vid:
        c.execute("INSERT INTO videos VALUES (?,?,?,?,?,?,?,?,0,0,0,?,0,?,?)",
                  (i, ws, yt, "ch_" + yt, kenh, tit, gio - tuoi * NGAY, dur, vph, dead, ck))
    c.execute("INSERT INTO ticks VALUES (1, ?, 120000)", (gio,))
    c.execute("INSERT INTO ticks VALUES (1, ?, 90000)", (gio - NGAY,))  # lấy tick MỚI NHẤT
    c.commit(); c.close()
    thumbs = tmp_path / "thumbs" / "1"
    thumbs.mkdir(parents=True)
    (thumbs / "aaaaaaaaaaa_deadbeef01.jpg").write_bytes(b"\xff\xd8gia-jpg")
    monkeypatch.setenv("RADARY_DB", str(db))
    monkeypatch.setenv("RADARY_THUMBS", str(tmp_path / "thumbs"))
    return tmp_path


def test_diem_khop_mot_tu_don_chua_du():
    """1 từ đơn trùng ('storm') KHÔNG đủ nói cùng chủ đề; cụm 2 từ trùng là đủ."""
    assert rr.diem_khop("Giant Storm Hits Texas", "Two Large Storms Are Coming") == 0
    assert rr.diem_khop("Alone in a Forest Cabin for 100 Days",
                        "My First 100 Days in a Forest Cabin") > 0


def test_tach_tu_gop_so_nhieu_than_trong():
    """storms→storm (≥5 ký tự) nhưng 'news' (4) không thành 'new' — đo thật
    31/08: 'Tropical Storms' không khớp 'Tropical Storm' vì số nhiều."""
    assert rr.diem_khop("Tropical Storm Forming", "Tropical Storms Are Forming") > 0
    assert "news" in rr._tach_tu("breaking news today")


def test_cung_chu_de_loc_va_xep(kho_gia):
    kq = rr.video_cung_chu_de("I Lived Alone in a Forest Cabin for 100 Days", 1)
    assert kq["du"] is True
    ids = [v["yt_id"] for v in kq["videos"]]
    # lạc chủ đề (storm) / quá 60 ngày / dead: TUYỆT ĐỐI không lọt
    assert "ddddddddddd" not in ids and "eeeeeeeeeee" not in ids and "fffffffffff" not in ids
    # cùng chủ đề thì "đang nổ" quyết thứ hạng: vph 9000 đứng trước 5000
    assert ids[0] == "bbbbbbbbbbb"
    v1 = next(v for v in kq["videos"] if v["yt_id"] == "aaaaaaaaaaa")
    assert v1["views"] == 120000                       # tick MỚI NHẤT, không phải cũ
    assert v1["thumb"] == "/thumby-thumb/1/aaaaaaaaaaa_deadbeef01.jpg"  # file tồn tại
    v2 = next(v for v in kq["videos"] if v["yt_id"] == "bbbbbbbbbbb")
    assert v2["thumb"] == ""                           # không ck → client fallback i.ytimg


def test_van_chong_bia_it_hon_3_khop(kho_gia):
    """Chủ đề chỉ khớp 1 video → du=False kèm lý do — KHÔNG độn video lạc."""
    kq = rr.video_cung_chu_de("Forest Cabin Build From Scratch", 1)
    if len(kq["videos"]) < rr.TOI_THIEU_KHOP:
        assert kq["du"] is False and kq["ly_do"]
    kq2 = rr.video_cung_chu_de("Crypto Trading Bot Tutorial", 1)
    assert kq2["du"] is False and kq2["videos"] == []


def test_api_can_danh_tinh_va_title_ngan(kho_gia):
    assert client.get("/thumby-api/pools").status_code == 401
    assert client.get("/thumby-api/cung-chu-de?ws=1&title=abcdefghij").status_code == 401
    r = client.get("/thumby-api/pools", headers=CLAIMS)
    assert r.status_code == 200 and r.json()["pools"][0]["ten"] == "LIFE IN"
    r = client.get("/thumby-api/cung-chu-de?ws=1&title=ngan", headers=CLAIMS)
    assert r.status_code == 200 and r.json()["du"] is False


def test_thumb_route_chi_doc_va_chan_traversal(kho_gia):
    r = client.get("/thumby-thumb/1/aaaaaaaaaaa_deadbeef01.jpg", headers=CLAIMS)
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg"
    # tên ngoài khuôn / trèo thư mục / thiếu claims → 404/401 lặng lẽ
    assert client.get("/thumby-thumb/1/..%2Fradary.db", headers=CLAIMS).status_code == 404
    assert client.get("/thumby-thumb/1/radary.db", headers=CLAIMS).status_code == 404
    assert client.get("/thumby-thumb/1/aaaaaaaaaaa_deadbeef01.jpg").status_code == 401


def test_may_khong_co_radary_noi_thang(tmp_path, monkeypatch):
    monkeypatch.setenv("RADARY_DB", str(tmp_path / "khong-ton-tai.db"))
    r = client.get("/thumby-api/pools", headers=CLAIMS)
    assert r.status_code == 200 and r.json()["pools"] == [] and r.json()["loi"]
