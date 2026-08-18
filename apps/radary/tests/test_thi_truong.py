# -*- coding: utf-8 -*-
"""Pool theo THỊ TRƯỜNG (docs/RADARY_THI_TRUONG.md, user chốt 18/08/2026):
pool gắn đúng MỘT thị trường từ danh mục đế (dropdown kiểm Ở SERVER), pool cũ
gán bổ sung có vết, TÁCH POOL chuyển kênh GIỮ LỊCH SỬ (video/tick/nhịp kênh
đi theo; events append-only ở lại; nhịp pool đích tính từ lúc chuyển)."""
import time

import pytest


# ---------- tạo pool: thị trường bắt buộc + kiểm ở server ----------

def test_tao_pool_bat_buoc_thi_truong_v3(org_moi, goi, mock_tt):
    r = goi("POST", "/api/workspaces", json={"name": "Life in X — US"})
    assert r.status_code == 422 and "THỊ TRƯỜNG" in r.json()["detail"]
    r = goi("POST", "/api/workspaces", json={"name": "x", "market": "TT-LA-LAM"})
    assert r.status_code == 422                       # giá trị ngoài danh mục đế — chặn ở server
    r = goi("POST", "/api/workspaces",
            json={"name": "Life in X — US", "market": "TT-US"})
    assert r.status_code == 201 and r.json()["market"] == "TT-US"
    ds = goi("GET", "/api/workspaces").json()
    assert [(w["market"], w["market_ten"]) for w in ds] == [("TT-US", "US")]


def test_tao_pool_502_khi_gateway_chet(org_moi, goi, monkeypatch):
    from radary import thi_truong_v3

    def _chet(lam_moi=False):
        raise RuntimeError("chưa lấy được danh mục thị trường từ OUTLIERY (URLError)")
    monkeypatch.setattr(thi_truong_v3, "danh_sach", _chet)
    r = goi("POST", "/api/workspaces", json={"name": "x", "market": "TT-US"})
    assert r.status_code == 502 and "OUTLIERY" in r.json()["detail"]
    r = goi("GET", "/api/thi-truong")
    assert r.status_code == 502


def test_standalone_khong_doi_hanh_vi(org_moi, goi, monkeypatch):
    """Hồi quy: ngoài V3 (không TRUST_PROXY) tạo pool không cần market như cũ.
    (Route đọc env mỗi request nên monkeypatch per-test ăn ngay; auth SSO đã
    chạy trước đó không liên quan — dùng session cookie thì không có, nên phải
    giữ TRUST_PROXY cho auth và chỉ tắt trong _v3 của route: ở đây tắt cả —
    dùng đường đăng nhập thường.)"""
    from radary import auth as rauth, db
    monkeypatch.delenv("RADARY_TRUST_PROXY")
    # không SSO → tạo user + session thật (đường V2)
    conn = db.connect()
    with conn:
        conn.execute("INSERT INTO users(email, name, password_hash, created_ts) "
                     "VALUES('v2@t', 'v2', ?, 0)", (rauth.hash_password("mk"),))
        uid = conn.execute("SELECT id FROM users WHERE email='v2@t'").fetchone()["id"]
        conn.execute("INSERT INTO members(org_id, user_id, role) VALUES(?,?, 'leader')",
                     (org_moi, uid))
    token = rauth.create_session(conn, uid)
    conn.close()

    import asyncio

    import httpx

    from radary.api import app

    async def run():
        tr = httpx.ASGITransport(app=app, client=("127.0.0.1", 52001))
        async with httpx.AsyncClient(transport=tr, base_url="http://t",
                                     cookies={rauth.COOKIE: token}) as cl:
            r1 = await cl.post("/api/workspaces", json={"name": "pool cu"})
            r2 = await cl.get("/api/thi-truong")
            return r1, r2
    r1, r2 = asyncio.run(run())
    assert r1.status_code == 201 and r1.json()["market"] == ""
    assert r2.status_code == 200 and r2.json() == []   # standalone: danh mục rỗng, UI tự ẩn


# ---------- gán thị trường cho pool có trước tính năng ----------

def test_gan_thi_truong_pool_cu_co_vet(org_moi, goi, mock_tt):
    from radary import db
    conn = db.connect()
    with conn:
        ws = db.create_workspace(conn, org_moi, "Life in X")    # pool cũ — market ''
    conn.close()
    r = goi("PATCH", f"/api/workspaces/{ws}/market", vai="viewer",
            json={"market": "TT-SPAIN"})
    assert r.status_code == 403                                  # viewer chỉ xem
    r = goi("PATCH", f"/api/workspaces/{ws}/market", json={"market": "TT-SPAIN"})
    assert r.status_code == 200 and r.json()["market"] == "TT-SPAIN"
    conn = db.connect()
    assert conn.execute("SELECT market FROM workspaces WHERE id=?",
                        (ws,)).fetchone()["market"] == "TT-SPAIN"
    ev = conn.execute("SELECT payload FROM events WHERE workspace_id=? "
                      "AND kind='config_change'", (ws,)).fetchall()
    conn.close()
    assert any("TT-SPAIN" in e["payload"] for e in ev)           # đổi cấu hình phải có vết


# ---------- tách pool: chuyển kênh giữ lịch sử ----------

def _seed_hai_pool(org):
    """ws1 có kênh UC-A (2 video, ticks, nhịp kênh, snap) + kênh UC-B; ws2 trống."""
    from radary import db
    conn = db.connect()
    with conn:
        w1 = db.create_workspace(conn, org, "Life in X", market="TT-US")
        w2 = db.create_workspace(conn, org, "Life in X — ES", market="TT-SPAIN")
        conn.execute("INSERT INTO channels(workspace_id, yt_id, title) VALUES(?,?,?)",
                     (w1, "UC-A", "Kenh A"))
        conn.execute("INSERT INTO channels(workspace_id, yt_id, title) VALUES(?,?,?)",
                     (w1, "UC-B", "Kenh B"))
        for vid, ch in (("v1", "UC-A"), ("v2", "UC-A"), ("v3", "UC-B")):
            conn.execute("INSERT INTO videos(workspace_id, yt_id, channel_yt_id, "
                         "channel_title, title, pub_ts) VALUES(?,?,?,?,?,1)",
                         (w1, vid, ch, "Kenh " + ch[-1], "video " + vid))
        v1 = conn.execute("SELECT id FROM videos WHERE yt_id='v1'").fetchone()["id"]
        conn.execute("INSERT INTO ticks(video_id, ts, views) VALUES(?, 1, 100)", (v1,))
        conn.execute("INSERT INTO ticks(video_id, ts, views) VALUES(?, 2, 250)", (v1,))
        # nhịp kênh giữ vĩnh viễn — 2 bucket; ws2 sẵn 1 bucket TRÙNG tên+bucket (ca cộng dồn)
        conn.execute("INSERT INTO channel_stats VALUES(?, 1000, 'Kenh A', 50)", (w1,))
        conn.execute("INSERT INTO channel_stats VALUES(?, 2000, 'Kenh A', 70)", (w1,))
        conn.execute("INSERT INTO channel_stats VALUES(?, 1000, 'Kenh A', 5)", (w2,))
        conn.execute("INSERT INTO channel_snap VALUES(?, '2026-08-01', 'UC-A', 10, 1000, 3, 1)", (w1,))
        db.kv_set(conn, w1, "board", {"cohorts": [{"videos": [
            {"yt_id": "v1"}, {"yt_id": "v3"}], "size": 2}], "allages": [{"yt_id": "v2"}]})
    conn.close()
    return w1, w2


def test_move_channels_giu_lich_su(org_moi, goi, mock_tt):
    from radary import db
    w1, w2 = _seed_hai_pool(org_moi)
    body = {"to_ws": w2, "yt_ids": ["UC-A"], "confirm": True}
    assert goi("POST", f"/api/workspaces/{w1}/channels/move", vai="leader",
               json=body).status_code == 403           # dời dữ liệu lớn = manager trở lên
    r = goi("POST", f"/api/workspaces/{w1}/channels/move", vai="manager",
            json={**body, "confirm": False})
    assert r.status_code == 422                        # bắt buộc xác nhận
    r = goi("POST", f"/api/workspaces/{w1}/channels/move", vai="manager", json=body)
    assert r.status_code == 200
    kq = r.json()
    assert kq["moved"] == ["UC-A"] and kq["moved_videos"] == 2

    conn = db.connect()
    # kênh + video sang đích; kênh B ở lại
    assert conn.execute("SELECT workspace_id FROM channels WHERE yt_id='UC-A'").fetchone()[0] == w2
    assert conn.execute("SELECT workspace_id FROM channels WHERE yt_id='UC-B'").fetchone()[0] == w1
    assert {r2["yt_id"] for r2 in conn.execute(
        "SELECT yt_id FROM videos WHERE workspace_id=?", (w2,))} == {"v1", "v2"}
    # ticks bám video_id — còn nguyên
    v1 = conn.execute("SELECT id FROM videos WHERE yt_id='v1'").fetchone()["id"]
    assert conn.execute("SELECT COUNT(*) FROM ticks WHERE video_id=?", (v1,)).fetchone()[0] == 2
    # nhịp kênh đi theo: bucket trùng cộng dồn (50+5), bucket mới chuyển nguyên
    cs = {r2["bucket_ts"]: r2["dviews"] for r2 in conn.execute(
        "SELECT bucket_ts, dviews FROM channel_stats WHERE workspace_id=? AND ch='Kenh A'", (w2,))}
    assert cs == {1000: 55, 2000: 70}
    assert conn.execute("SELECT COUNT(*) FROM channel_stats WHERE workspace_id=? "
                        "AND ch='Kenh A'", (w1,)).fetchone()[0] == 0
    assert conn.execute("SELECT workspace_id FROM channel_snap WHERE ch_yt_id='UC-A'").fetchone()[0] == w2
    # events pool_change cả 2 bên (append-only, sử liệu)
    for w in (w1, w2):
        assert conn.execute("SELECT COUNT(*) FROM events WHERE workspace_id=? "
                            "AND kind='pool_change'", (w,)).fetchone()[0] == 1
    # board nguồn dọn NGAY video của kênh chuyển đi — v3 (kênh B) ở lại
    board = db.kv_get(conn, w1, "board", None)
    conn.close()
    assert [v["yt_id"] for v in board["cohorts"][0]["videos"]] == ["v3"]
    assert board["cohorts"][0]["size"] == 1 and board["allages"] == []


def test_move_chan_ca_loi(org_moi, goi, mock_tt):
    from radary import db
    w1, w2 = _seed_hai_pool(org_moi)
    g = lambda body: goi("POST", f"/api/workspaces/{w1}/channels/move",
                         vai="manager", json=body)
    assert g({"to_ws": w1, "yt_ids": ["UC-A"], "confirm": True}).status_code == 422  # đích = nguồn
    assert g({"to_ws": w2, "yt_ids": ["UC-LA"], "confirm": True}).status_code == 404  # kênh không có
    # kênh đã có ở đích → 409, không ghi gì
    conn = db.connect()
    with conn:
        conn.execute("INSERT INTO channels(workspace_id, yt_id, title) VALUES(?,?,?)",
                     (w2, "UC-A", "Kenh A ban dich"))
    conn.close()
    assert g({"to_ws": w2, "yt_ids": ["UC-A"], "confirm": True}).status_code == 409
    conn = db.connect()
    assert conn.execute("SELECT COUNT(*) FROM channels WHERE workspace_id=? AND yt_id='UC-A'",
                        (w1,)).fetchone()[0] == 1       # nguồn còn nguyên
    conn.close()
