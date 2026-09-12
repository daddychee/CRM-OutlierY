# -*- coding: utf-8 -*-
"""Test cầu chạy pipeline ngách — HTTP + snapshot đều giả lập, không đụng service thật."""
import json
import time

import pytest
from fastapi.testclient import TestClient

from src import dashboard, niche_run
from src.main import app

CLAIMS_L3 = {"X-Remote-User": "leader", "X-Remote-Level": "3"}
CLAIMS_L2 = {"X-Remote-User": "nv", "X-Remote-Level": "2"}


class _Resp:
    def __init__(self, data):
        self._d = data

    def raise_for_status(self):
        pass

    def json(self):
        return self._d


@pytest.fixture()
def client(tmp_path, monkeypatch):
    map_path = tmp_path / "map.json"
    map_path.write_text(json.dumps({"N-TEST": {"TT-US": "Proj_US"}}), encoding="utf-8")
    monkeypatch.setenv("NICHE_PROJECTS_MAP", str(map_path))
    # trạng thái sạch giữa các test (registry chống-snapshot-đúp là module-level)
    niche_run._da_snapshot.clear()
    niche_run._dang_dong_goi.clear()
    return TestClient(app)


def test_chay_can_leader(client, monkeypatch):
    monkeypatch.setattr(niche_run.requests, "post",
                        lambda url, **kw: _Resp({"status": "resumed"}))
    assert client.post("/niche/chay/Proj_US", headers=CLAIMS_L2).status_code == 403
    r = client.post("/niche/chay/Proj_US", headers=CLAIMS_L3)
    assert r.status_code == 200 and r.json()["status"] == "resumed"


def test_project_ngoai_so_404(client):
    assert client.post("/niche/chay/LaProject", headers=CLAIMS_L3).status_code == 404
    assert client.get("/niche/chay/LaProject/trang-thai", headers=CLAIMS_L3).status_code == 404


def _cho_nen_xong(project: str = "Proj_US", giay: float = 3.0) -> None:
    """Đóng gói chạy NỀN từ 12/09 — test chờ thread xong rồi mới đối chiếu."""
    het = time.perf_counter() + giay
    while niche_run.dang_dong_goi(project) and time.perf_counter() < het:
        time.sleep(0.02)


def test_xong_thi_snapshot_dung_mot_lan(client, monkeypatch):
    goi = []
    monkeypatch.setattr(niche_run.requests, "get",
                        lambda url, **kw: _Resp({"running": False, "has_report": True}))
    monkeypatch.setattr(niche_run, "_snapshot", lambda p: goi.append(p) or True)
    r1 = client.get("/niche/chay/Proj_US/trang-thai", headers=CLAIMS_L3).json()
    _cho_nen_xong()
    r2 = client.get("/niche/chay/Proj_US/trang-thai", headers=CLAIMS_L3).json()
    # Hợp đồng đổi 12/09: đóng gói chạy NỀN nên poll không còn biết lúc nào xong —
    # 'done_moi' nhường chỗ cho 'dang_dong_goi' (thứ UI cần để hiện tiến độ).
    # Không ghim cờ ở r1: _snapshot giả chạy tức thì nên thread nền có thể xong
    # trước lời return (race vô hại). Việc "bật cờ trong lúc đóng gói" do
    # test_niche_run_dong_goi_nen ghim bằng _snapshot chậm thật.
    assert set(r1) == {"running", "has_report", "dang_dong_goi"}
    assert r1["running"] is False and r1["has_report"] is True
    assert r2["dang_dong_goi"] is False and goi == ["Proj_US"]    # đóng gói đúng 1 lần


def test_chay_lai_mo_cua_snapshot_moi(client, monkeypatch):
    monkeypatch.setattr(niche_run.requests, "get",
                        lambda url, **kw: _Resp({"running": False, "has_report": True}))
    monkeypatch.setattr(niche_run.requests, "post",
                        lambda url, **kw: _Resp({"status": "resumed"}))
    goi = []
    monkeypatch.setattr(niche_run, "_snapshot", lambda p: goi.append(p) or True)
    client.get("/niche/chay/Proj_US/trang-thai", headers=CLAIMS_L3)      # snapshot lần 1
    _cho_nen_xong()
    client.post("/niche/chay/Proj_US", headers=CLAIMS_L3)                # chạy mới → reset
    client.get("/niche/chay/Proj_US/trang-thai", headers=CLAIMS_L3)      # snapshot lần 2
    _cho_nen_xong()
    assert goi == ["Proj_US", "Proj_US"]


# ---------- New report nhánh Niche ----------

def _mock_danh_ba(monkeypatch):
    monkeypatch.setattr(dashboard, "_ds_ngach",
                        lambda: [{"ma": "N-TEST", "ten_chuan": "LIFE IN",
                                  "thi_truong_cua": ["TT-ES"]}])
    monkeypatch.setattr(dashboard, "_ten_thi_truong", lambda: {"TT-ES": "Spain"})


def _bat_post(monkeypatch):
    goi = {}
    def _post(url, **kw):
        goi["url"] = url
        goi["data"] = kw.get("data")
        files = kw.get("files") or {}
        if "competitors" in files:
            goi["pool"] = files["competitors"][1].decode("utf-8")
        return _Resp({"status": "started"})
    monkeypatch.setattr(niche_run.requests, "post", _post)
    return goi


def test_tao_report_moi_sinh_project_va_map(client, tmp_path, monkeypatch):
    _mock_danh_ba(monkeypatch)
    monkeypatch.setenv("NICHE_PROJECTS_DIR", str(tmp_path / "projects"))
    goi = _bat_post(monkeypatch)
    r = client.post("/niche/tao-report", headers=CLAIMS_L3,
                    data={"ngach_ma": "N-TEST", "thi_truong_ma": "TT-ES",
                          "pool": "https://youtube.com/channel/UCx1\nhttps://youtube.com/channel/UCx2"})
    assert r.status_code == 200
    d = r.json()
    assert d["project"] == "LifeIn_SPAIN" and d["them_kenh"] == 2
    assert goi["url"].endswith("/api/run") and goi["data"]["name"] == "LifeIn_SPAIN"
    assert "UCx2" in goi["pool"]
    # 4 cờ pipeline mặc định (kiểm 18/08): comment BẬT, LLM BẬT, deepdive/force tắt
    assert goi["data"]["skip_comments"] == "false" and goi["data"]["llm"] == "true"
    assert goi["data"]["deepdive"] == "false" and goi["data"]["force"] == "false"
    # sổ ánh xạ đã có mục mới (fixture client trỏ NICHE_PROJECTS_MAP vào tmp)
    import json as _json
    mapping = _json.loads((tmp_path / ".." / "map.json").resolve().read_text(encoding="utf-8")) \
        if False else _json.loads(open(dashboard._duong_map(), encoding="utf-8").read())
    assert mapping["N-TEST"]["TT-ES"] == "LifeIn_SPAIN"


def test_tao_report_pool_cong_don_khong_trung(client, tmp_path, monkeypatch):
    _mock_danh_ba(monkeypatch)
    pdir = tmp_path / "projects" / "LifeIn_SPAIN"
    pdir.mkdir(parents=True)
    (pdir / "competitors.txt").write_text("A | https://youtube.com/channel/UCcu\n", encoding="utf-8")
    monkeypatch.setenv("NICHE_PROJECTS_DIR", str(tmp_path / "projects"))
    goi = _bat_post(monkeypatch)
    r = client.post("/niche/tao-report", headers=CLAIMS_L3,
                    data={"ngach_ma": "N-TEST", "thi_truong_ma": "TT-ES",
                          "pool": "A | https://youtube.com/channel/UCcu\nhttps://youtube.com/channel/UCmoi"})
    assert r.status_code == 200 and r.json()["them_kenh"] == 1        # dòng cũ không đếm lại
    assert goi["pool"].count("UCcu") == 1 and "UCmoi" in goi["pool"]  # cộng dồn, không nhân đôi


def test_tao_report_chuyen_4_co_pipeline(client, tmp_path, monkeypatch):
    """Form New Research gửi 4 tùy chọn — route phải chuyển NGUYÊN sang service
    (user 18/08: ngoài pool, pipeline chỉ còn đúng 4 tùy chọn này)."""
    _mock_danh_ba(monkeypatch)
    monkeypatch.setenv("NICHE_PROJECTS_DIR", str(tmp_path / "projects"))
    goi = _bat_post(monkeypatch)
    r = client.post("/niche/tao-report", headers=CLAIMS_L3,
                    data={"ngach_ma": "N-TEST", "thi_truong_ma": "TT-ES",
                          "pool": "https://youtube.com/channel/UCx1",
                          "skip_comments": "true", "llm": "false",
                          "deepdive": "true", "force": "true"})
    assert r.status_code == 200
    assert goi["data"]["skip_comments"] == "true" and goi["data"]["llm"] == "false"
    assert goi["data"]["deepdive"] == "true" and goi["data"]["force"] == "true"


def test_tao_report_pool_trong_400_va_quyen(client, monkeypatch):
    _mock_danh_ba(monkeypatch)
    assert client.post("/niche/tao-report", headers=CLAIMS_L2,
                       data={"ngach_ma": "N-TEST", "thi_truong_ma": "TT-ES", "pool": "x"}
                       ).status_code == 403
    r = client.post("/niche/tao-report", headers=CLAIMS_L3,
                    data={"ngach_ma": "N-TEST", "thi_truong_ma": "TT-ES", "pool": ""})
    assert r.status_code == 400 and "pool đang trống" in r.json()["detail"]


def test_kiem_api_truoc_researching(client, monkeypatch):
    """Bước 1 sau Run analysis (user chốt 19/08): check khóa KÉT khả dụng — đủ thì
    ok, thiếu thì liệt kê việc thiếu; response TUYỆT ĐỐI không lộ key."""
    cap = {"quet_kenh": {"khoa": [{"key": "AIza-bi-mat"}]}, "phan_tich": {"khoa": []}}
    monkeypatch.setattr(niche_run.requests, "get", lambda url, **kw: _Resp(cap))
    r = client.get("/niche/kiem-api", headers=CLAIMS_L3, params={"llm": "true"})
    assert r.status_code == 200
    d = r.json()
    assert d["ok"] is False and d["thieu"] == ["llm"]
    assert d["chi_tiet"]["youtube"] is True
    r2 = client.get("/niche/kiem-api", headers=CLAIMS_L3)      # không bật llm → đủ
    assert r2.json()["ok"] is True and r2.json()["thieu"] == []
    assert "AIza" not in r.text and "AIza" not in r2.text      # không lộ key


def test_kiem_api_gateway_chet_502(client, monkeypatch):
    def _no(url, **kw):
        raise niche_run.requests.ConnectionError("refused")
    monkeypatch.setattr(niche_run.requests, "get", _no)
    r = client.get("/niche/kiem-api", headers=CLAIMS_L3)
    assert r.status_code == 502 and "KÉT" in r.json()["detail"]


def test_tu_dong_goi_khi_run_xong_ma_chua_snapshot(tmp_path, monkeypatch):
    """Sự cố 19/08 (Space/Spain): run xong nhưng tab đã đóng → không ai đóng gói,
    dashboard im lặng. can_dong_goi phải phát hiện + tinh_trang phải nói được
    lần chạy tới đâu."""
    monkeypatch.setenv("NICHE_PROJECTS_DIR", str(tmp_path))
    d = tmp_path / "Proj_X"
    (d / "Report").mkdir(parents=True)
    (d / "niche-data").mkdir()
    (d / "Report" / "competitors_report.xlsx").write_bytes(b"x")
    assert niche_run.can_dong_goi("Proj_X") is True          # có report, chưa snapshot
    # có snapshot MỚI HƠN report → hết việc
    snap = d / "snapshots" / "2026-08-19"
    snap.mkdir(parents=True)
    (d / "snapshots" / "index.json").write_text(
        json.dumps([{"id": "2026-08-19", "artifacts": [], "bao_cao": []}]), encoding="utf-8")
    assert niche_run.can_dong_goi("Proj_X") is False
    # tình trạng đọc từ đĩa: nói được đã xong + đuôi log + lỗi
    (d / "niche-data" / "stdout.log").write_text(
        ">>> [19/20] plan\nTraceback (most recent call last):\n"
        "✓ Pipeline done — report: x.xlsx\n", encoding="utf-8")
    t = niche_run.tinh_trang("Proj_X")
    assert t["co_log"] and t["xong"] is True and t["duoi"]
    assert any("Traceback" in x for x in t["loi"])
    assert niche_run.tinh_trang("KhongCo")["co_log"] is False


def test_service_chet_502(client, monkeypatch):
    def _no(url, **kw):
        raise niche_run.requests.ConnectionError("refused")
    monkeypatch.setattr(niche_run.requests, "post", _no)
    r = client.post("/niche/chay/Proj_US", headers=CLAIMS_L3)
    assert r.status_code == 502 and "không phản hồi" in r.json()["detail"]
