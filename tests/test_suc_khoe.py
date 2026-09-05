# -*- coding: utf-8 -*-
"""B1 giám sát sức khỏe (31/08/2026) — hợp đồng 2 tầng:

- `/health` (liveness, giữ nguyên) — app sống hay chết.
- `suc_khoe` (tùy chọn trong apps.json, vd `/api/suc-khoe`) — app TỰ KHAI trạng
  thái từng MODULE bên trong: {app, phien_ban, trang_thai, mo_dun:[{ten,
  trang_thai: ok|canh_bao|loi, chi_tiet}]}. App không khai → hành vi cũ y nguyên.

Khuôn helper nen/common/suc_khoe.py: check nổ exception KHÔNG được giết endpoint
— nó chính là dữ liệu ("loi"). Gateway _do_dich_vu gom về cho tab Applications.
"""
import asyncio
import importlib.util
import threading
import time
from pathlib import Path

import bcrypt
import pytest
import uvicorn
from fastapi import FastAPI
from fastapi.testclient import TestClient

from nen.common import suc_khoe
from nen.iam import iam

ROOT = Path(__file__).resolve().parents[1]
_gensalt_goc = bcrypt.gensalt


# ---------- helper nen/common/suc_khoe.py ----------

def test_gop_trang_thai_lay_muc_xau_nhat():
    assert suc_khoe.gop_trang_thai([]) == "ok"
    assert suc_khoe.gop_trang_thai([{"trang_thai": "ok"}]) == "ok"
    assert suc_khoe.gop_trang_thai(
        [{"trang_thai": "ok"}, {"trang_thai": "canh_bao"}]) == "canh_bao"
    assert suc_khoe.gop_trang_thai(
        [{"trang_thai": "canh_bao"}, {"trang_thai": "loi"},
         {"trang_thai": "ok"}]) == "loi"


def test_bao_cao_kiem_no_exception_thanh_loi_khong_giet_endpoint():
    """Van cốt lõi: một module hỏng (raise) phải thành trang_thai='loi' kèm lý do,
    các module còn lại vẫn được kiểm — endpoint sức khỏe không bao giờ 500."""
    def _ok():
        return "ok", "kết nối tốt"

    def _no():
        raise ConnectionError("Qdrant không trả lời")

    bc = suc_khoe.bao_cao("app-thu", "1.0", [("kho-vector", _no), ("catalog", _ok)])
    assert bc["app"] == "app-thu" and bc["phien_ban"] == "1.0"
    assert bc["trang_thai"] == "loi"
    theo_ten = {m["ten"]: m for m in bc["mo_dun"]}
    assert theo_ten["kho-vector"]["trang_thai"] == "loi"
    assert "Qdrant" in theo_ten["kho-vector"]["chi_tiet"]
    assert theo_ten["catalog"]["trang_thai"] == "ok"


def test_bao_cao_trang_thai_la_phai_thanh_loi():
    """Check trả trạng thái ngoài bộ ok/canh_bao/loi → coi là 'loi' (chống khai bừa
    làm template/tổng hợp vỡ lặng lẽ)."""
    bc = suc_khoe.bao_cao("app-thu", "1.0", [("x", lambda: ("xanh_le", "?"))])
    assert bc["mo_dun"][0]["trang_thai"] == "loi"


# ---------- app-mau là khuôn mẫu của hợp đồng ----------

def _nap_app_mau():
    spec = importlib.util.spec_from_file_location(
        "app_mau_suc_khoe", ROOT / "apps" / "app-mau" / "src" / "main.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.app


def test_app_mau_co_endpoint_suc_khoe_dung_khuon():
    client = TestClient(_nap_app_mau())
    r = client.get("/api/suc-khoe")
    assert r.status_code == 200
    b = r.json()
    assert b["app"] == "app-mau"
    assert b["trang_thai"] in ("ok", "canh_bao", "loi")
    assert isinstance(b["mo_dun"], list) and b["mo_dun"]
    for m in b["mo_dun"]:
        assert set(m) >= {"ten", "trang_thai", "chi_tiet"}


# ---------- gateway gom sức khỏe sâu ----------

@pytest.fixture(scope="module")
def app_stub():
    """App giả: /health sống + /api/suc-khoe có 1 module canh_bao — chạy uvicorn
    thread cổng ephemeral (khuôn app_mau_server của test_gateway)."""
    stub = FastAPI()

    @stub.get("/health")
    async def health():
        return {"trang_thai": "ok", "app": "stub"}

    @stub.get("/api/suc-khoe")
    async def sk():
        return suc_khoe.bao_cao("stub", "0.1", [
            ("kho-vector-gia", lambda: ("canh_bao", "catalog 10 mà kho 3 point")),
            ("catalog-gia", lambda: ("ok", "đọc được")),
        ])

    server = uvicorn.Server(uvicorn.Config(
        stub, host="127.0.0.1", port=0, log_level="warning"))
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    for _ in range(50):
        if server.started:
            break
        time.sleep(0.1)
    assert server.started, "stub khong khoi dong duoc"
    cong = server.servers[0].sockets[0].getsockname()[1]
    yield cong
    server.should_exit = True
    t.join(timeout=5)


def _hop_dong_stub(cong, co_suc_khoe=True):
    muc = {"slug": "stub", "ten": "Stub App", "cong": cong, "health": "/health",
           "tien_to": [], "du_lieu": []}
    if co_suc_khoe:
        muc["suc_khoe"] = "/api/suc-khoe"
    return [muc]


def test_do_dich_vu_gom_muc_va_mo_dun_tu_app_co_khai(app_stub, monkeypatch):
    from nen.gateway import main as gw
    monkeypatch.setattr(gw, "doc_hop_dong", lambda: _hop_dong_stub(app_stub))
    ds = {d["ten"]: d for d in asyncio.run(gw._do_dich_vu())}
    stub = ds["Stub App"]
    assert stub["song"] is True
    assert stub["muc"] == "canh_bao"
    ten_mo_dun = [m["ten"] for m in stub["mo_dun"]]
    assert "kho-vector-gia" in ten_mo_dun


def test_do_dich_vu_tra_kem_cong_va_slug(app_stub, monkeypatch):
    """UI command center ghép app ↔ trạm đo lỗi (khóa = cổng) — dịch vụ phải
    tự khai cong/slug, không bắt UI đoán."""
    from nen.gateway import main as gw
    monkeypatch.setattr(gw, "doc_hop_dong", lambda: _hop_dong_stub(app_stub))
    ds = {d["ten"]: d for d in asyncio.run(gw._do_dich_vu())}
    assert ds["Stub App"]["cong"] == app_stub and ds["Stub App"]["slug"] == "stub"
    assert ds["Qdrant (kho vector)"]["slug"] is None


def test_do_dich_vu_app_khong_khai_giu_hanh_vi_cu(app_stub, monkeypatch):
    """Hồi quy: app chưa khai suc_khoe → chỉ liveness, muc=None, không gọi thêm."""
    from nen.gateway import main as gw
    monkeypatch.setattr(gw, "doc_hop_dong",
                        lambda: _hop_dong_stub(app_stub, co_suc_khoe=False))
    ds = {d["ten"]: d for d in asyncio.run(gw._do_dich_vu())}
    stub = ds["Stub App"]
    assert stub["song"] is True and stub["muc"] is None and stub["mo_dun"] == []


def test_do_dich_vu_khai_ma_khong_tra_loi_thanh_loi(monkeypatch):
    """App khai suc_khoe nhưng endpoint chết/404 → muc='loi' (khai mà không giữ
    lời là bệnh, không được im lặng), liveness vẫn đo riêng."""
    from nen.gateway import main as gw
    # cổng 1 chắc chắn không có gì nghe → cả health lẫn suc_khoe đều chết
    monkeypatch.setattr(gw, "doc_hop_dong", lambda: _hop_dong_stub(1))
    ds = {d["ten"]: d for d in asyncio.run(gw._do_dich_vu())}
    stub = ds["Stub App"]
    assert stub["song"] is False and stub["muc"] == "loi"


# ---------- trang /general/applications hiện module ----------

@pytest.fixture()
def owner_client(tmp_path, monkeypatch):
    monkeypatch.setenv("IAM_DB", str(tmp_path / "iam.db"))
    monkeypatch.setattr(bcrypt, "gensalt", lambda rounds=12: _gensalt_goc(4))
    conn = iam.ket_noi()
    iam.tao_tai_khoan(conn, None, "owner-test", "MatKhau123", "Ban quản trị", 5,
                      phai_doi_mk=False)
    conn.close()
    from nen.gateway.main import app as gateway_app
    client = TestClient(gateway_app, follow_redirects=False)
    client.post("/login", data={"ten": "owner-test", "mat_khau": "MatKhau123"})
    return client


def test_trang_applications_ve_huu_redirect_command_center(app_stub, monkeypatch,
                                                           owner_client):
    """Owner chốt 01/09: Command Center bao trọn Applications — trang cũ nghỉ
    hưu, bookmark cũ redirect; dữ liệu module vẫn đủ qua API tổng-hợp."""
    from nen.gateway import main as gw
    monkeypatch.setattr(gw, "doc_hop_dong", lambda: _hop_dong_stub(app_stub))
    r = owner_client.get("/general/applications")
    assert r.status_code == 303
    assert r.headers["location"] == "/general/command-center"
    b = owner_client.get("/general/api/giam-sat/tong-hop").json()
    stub = {d["ten"]: d for d in b["dich_vu"]}["Stub App"]
    assert any(m["ten"] == "kho-vector-gia" for m in stub["mo_dun"])


# ---------- plannery: sức khỏe sâu (B3 lan dần) ----------

def _spin_plannery(tmp_path, monkeypatch):
    monkeypatch.setenv("PLANNER_DATA_DIR", str(tmp_path))
    monkeypatch.syspath_prepend(str(ROOT / "apps" / "plannery"))
    spec = importlib.util.spec_from_file_location(
        "plannery_server_sk2", ROOT / "apps" / "plannery" / "server.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    from http.server import ThreadingHTTPServer
    sv = ThreadingHTTPServer(("127.0.0.1", 0), mod.Handler)
    t = threading.Thread(target=sv.serve_forever, daemon=True)
    t.start()
    return sv, t


def test_plannery_suc_khoe_plan_ok_va_hong(tmp_path, monkeypatch):
    """plan-json là dữ liệu VÀNG của plannery: đọc được → ok kèm số người/dự án
    + _rev; file hỏng → loi (lịch cả team trắng); chưa có → canh_bao nói thẳng.
    App tự đủ (repo riêng) nên KHÔNG import nen.* — khuôn suc_khoe là HỢP ĐỒNG
    JSON, không phải import bắt buộc."""
    import httpx
    (tmp_path / "plan.json").write_text(
        '{"_rev": 7, "people": [{"id": "a"}], "projects": []}', encoding="utf-8")
    sv, t = _spin_plannery(tmp_path, monkeypatch)
    try:
        cong = sv.server_address[1]
        b = httpx.get(f"http://127.0.0.1:{cong}/api/suc-khoe", timeout=3).json()
        assert b["app"] == "plannery" and b["trang_thai"] == "ok"
        md = {m["ten"]: m for m in b["mo_dun"]}
        assert "_rev 7" in md["plan-json"]["chi_tiet"]
        # plan hỏng → loi (đọc SỐNG mỗi lần gọi, không cần restart)
        (tmp_path / "plan.json").write_text("{hong", encoding="utf-8")
        b = httpx.get(f"http://127.0.0.1:{cong}/api/suc-khoe", timeout=3).json()
        assert b["trang_thai"] == "loi"
    finally:
        sv.shutdown()
        t.join(timeout=5)


# ---------- sửa health lệch: plannery dùng /api/me (auth) làm health ----------

def test_plannery_co_endpoint_health_that(tmp_path, monkeypatch):
    """`health` trong hợp đồng phải là LIVENESS thật — /api/me là endpoint auth,
    đổi luật auth là trang giám sát báo chết oan. Spin server stdlib thật trên
    cổng ephemeral, GET /health phải 200 đúng khuôn liveness."""
    monkeypatch.setenv("PLANNER_DATA_DIR", str(tmp_path))
    monkeypatch.syspath_prepend(str(ROOT / "apps" / "plannery"))
    spec = importlib.util.spec_from_file_location(
        "plannery_server_sk", ROOT / "apps" / "plannery" / "server.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    from http.server import ThreadingHTTPServer
    sv = ThreadingHTTPServer(("127.0.0.1", 0), mod.Handler)
    t = threading.Thread(target=sv.serve_forever, daemon=True)
    t.start()
    try:
        import httpx
        r = httpx.get(f"http://127.0.0.1:{sv.server_address[1]}/health", timeout=3)
        assert r.status_code == 200
        b = r.json()
        assert b["trang_thai"] == "ok" and b["app"] == "plannery"
    finally:
        sv.shutdown()
        t.join(timeout=5)
