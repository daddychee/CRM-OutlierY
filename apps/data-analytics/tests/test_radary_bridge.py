# -*- coding: utf-8 -*-
"""Test cầu pool RadarY (phương án 2, 19/08) — HTTP giả lập, không đụng RadarY thật."""
import json

import pytest
from fastapi.testclient import TestClient

from src import dashboard, niche_run, radary_bridge
from src.main import app

CLAIMS_L3 = {"X-Remote-User": "leader", "X-Remote-Level": "3"}


class _Resp:
    def __init__(self, data):
        self._d = data

    def raise_for_status(self):
        pass

    def json(self):
        return self._d


def test_ds_pool_loc_dung_ngach_thi_truong(monkeypatch):
    monkeypatch.setattr(radary_bridge.requests, "get", lambda url, **kw: _Resp([
        {"id": 1, "name": "US Pool", "ngach": "N-LIFE-IN", "market": "TT-US", "channels": 40},
        {"id": 2, "name": "ES Pool", "ngach": "N-LIFE-IN", "market": "TT-SPAIN", "channels": 22},
        {"id": 3, "name": "Khac", "ngach": "N-KHAC", "market": "TT-US", "channels": 9},
        {"id": 4, "name": "Chua gan", "ngach": None, "market": None, "channels": 5},
    ]))
    ds = radary_bridge.ds_pool({"ten": "t", "level": 3}, "N-LIFE-IN", "TT-US")
    assert ds == [{"id": 1, "name": "US Pool", "channels": 40}]


def test_kenh_cua_pool_chi_active_dung_khuon(monkeypatch):
    monkeypatch.setattr(radary_bridge.requests, "get", lambda url, **kw: _Resp([
        {"yt_id": "UCa", "title": "Kenh A", "active": 1},
        {"yt_id": "UCb", "title": "", "active": 1},          # thiếu title → dùng yt_id
        {"yt_id": "UCc", "title": "Tat", "active": 0},       # kênh tắt → loại
    ]))
    dong = radary_bridge.kenh_cua_pool({"ten": "t", "level": 3}, 1)
    assert dong == ["Kenh A | https://www.youtube.com/channel/UCa",
                    "UCb | https://www.youtube.com/channel/UCb"]


@pytest.fixture()
def client(tmp_path, monkeypatch):
    map_path = tmp_path / "map.json"
    map_path.write_text(json.dumps({}), encoding="utf-8")
    monkeypatch.setenv("NICHE_PROJECTS_MAP", str(map_path))
    monkeypatch.setenv("NICHE_PROJECTS_DIR", str(tmp_path / "projects"))
    monkeypatch.setattr(dashboard, "_ds_ngach",
                        lambda: [{"ma": "N-TEST", "ten_chuan": "LIFE IN",
                                  "thi_truong_cua": ["TT-ES"]}])
    monkeypatch.setattr(dashboard, "_ten_thi_truong", lambda: {"TT-ES": "Spain"})
    return TestClient(app)


def test_route_niche_pool(client, monkeypatch):
    monkeypatch.setattr(dashboard, "_lay_user", dashboard._lay_user)  # giữ nguyên
    from src import radary_bridge as rb
    monkeypatch.setattr(rb, "ds_pool",
                        lambda user, ngach, tt: [{"id": 7, "name": "Pool ES", "channels": 22}])
    r = client.get("/niche/pool", headers=CLAIMS_L3, params={"ngach": "N-TEST", "tt": "TT-ES"})
    assert r.status_code == 200 and r.json()["pools"][0]["name"] == "Pool ES"


def test_tao_report_tu_pool_ws(client, monkeypatch):
    """UI phương án 2: gửi pool_ws → server lấy kênh từ RadarY rồi đổ vào luật
    cộng dồn như pool text (một đường xử lý, hai nguồn)."""
    from src import radary_bridge as rb
    monkeypatch.setattr(rb, "kenh_cua_pool",
                        lambda user, ws: ["A | https://www.youtube.com/channel/UCa",
                                          "B | https://www.youtube.com/channel/UCb"])
    goi = {}

    def _post(url, **kw):
        goi["url"] = url
        goi["pool"] = kw.get("files", {}).get("competitors", (None, b""))[1].decode("utf-8")
        return _Resp({"status": "started"})
    monkeypatch.setattr(niche_run.requests, "post", _post)
    r = client.post("/niche/tao-report", headers=CLAIMS_L3,
                    data={"ngach_ma": "N-TEST", "thi_truong_ma": "TT-ES", "pool_ws": "7"})
    assert r.status_code == 200 and r.json()["them_kenh"] == 2
    assert "UCa" in goi["pool"] and "UCb" in goi["pool"]


def test_tao_report_pool_ws_radary_chet_502(client, monkeypatch):
    from src import radary_bridge as rb

    def _no(user, ws):
        raise radary_bridge.requests.ConnectionError("refused")
    monkeypatch.setattr(rb, "kenh_cua_pool", _no)
    r = client.post("/niche/tao-report", headers=CLAIMS_L3,
                    data={"ngach_ma": "N-TEST", "thi_truong_ma": "TT-ES", "pool_ws": "7"})
    assert r.status_code == 502 and "pool RadarY" in r.json()["detail"]
