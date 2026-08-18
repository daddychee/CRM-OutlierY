# -*- coding: utf-8 -*-
"""Niche Research vào V3 (APPS.md app 3) — adapter SSO Actions-first + LÀM GỌN:
quản trị nội bộ (Settings/.env key · users/invites/vai) đóng 404 khi SSO KỂ CẢ
vai admin; nguồn khóa DUY NHẤT là két OUTLIERY (không fallback .env); scheduler
watch tắt được qua env (V3 chống đốt đôi quota với hệ thật C:\\)."""
import asyncio
import json

import httpx
import pytest

import khoa_v3
import server as srv


class _Req:
    """Request giả đủ cho _vai_tu_sso/_get_role (không dựng HTTP thật)."""
    class _C:
        def __init__(self, host):
            self.host = host

    def __init__(self, headers=None, ip="127.0.0.1"):
        self.headers = headers or {}
        self.client = self._C(ip)


def _vai(monkeypatch, headers, ip="127.0.0.1", bat="1"):
    monkeypatch.setenv("NICHE_TRUST_PROXY", bat)
    return srv._vai_tu_sso(_Req(headers, ip))


# ---------- adapter Actions-first (Permissions v2) ----------

def test_actions_uu_tien(monkeypatch):
    assert _vai(monkeypatch, {"X-Remote-Actions": "quan_tri"}) == "admin"
    assert _vai(monkeypatch, {"X-Remote-Actions": "tao,toan_quyen,quan_tri"}) == "admin"
    assert _vai(monkeypatch, {"X-Remote-Actions": "tao,toan_quyen"}) == "manager"
    assert _vai(monkeypatch, {"X-Remote-Actions": "tao"}) == "leader"
    assert _vai(monkeypatch, {"X-Remote-Actions": ""}) == "seo"      # rỗng fail-closed
    assert _vai(monkeypatch, {"X-Remote-Actions": "kpi,them_video"}) == "seo"
    # có Actions thì Role bị bỏ qua — Actions là nguồn sự thật
    assert _vai(monkeypatch, {"X-Remote-Actions": "", "X-Remote-Role": "admin"}) == "seo"


def test_fallback_role_danh_phap_moi(monkeypatch):
    assert _vai(monkeypatch, {"X-Remote-Role": "admin"}) == "admin"
    assert _vai(monkeypatch, {"X-Remote-Role": "manager"}) == "manager"
    assert _vai(monkeypatch, {"X-Remote-Role": "leader"}) == "leader"
    assert _vai(monkeypatch, {"X-Remote-Role": "viewer"}) == "seo"
    assert _vai(monkeypatch, {"X-Remote-Role": "owner"}) == "seo"    # vai cũ hết giá trị
    assert _vai(monkeypatch, {}) == "seo"                            # user trắng không nổ


def test_chi_none_khi_tat_hoac_khong_loopback(monkeypatch):
    assert _vai(monkeypatch, {"X-Remote-Role": "admin"}, bat="0") is None
    assert _vai(monkeypatch, {"X-Remote-Role": "admin"}, ip="192.168.1.9") is None


def test_sso_bat_khong_roi_ve_nguon_quyen_cu(monkeypatch):
    """SSO bật: _get_role KHÔNG BAO GIỜ đọc ADMIN_USERS/users.json (bản cũ vai
    lạ → None → ADMIN_USERS rỗng = ai cũng admin — đã bịt bằng DEFAULT seo)."""
    monkeypatch.setenv("NICHE_TRUST_PROXY", "1")
    r = _Req({"X-Remote-User": "ai-do", "X-Remote-Role": "vai-la"})
    assert srv._get_role(r) == "seo"


# ---------- LÀM GỌN: đóng quản trị 404 kể cả admin (HTTP thật qua ASGI) ----------

_ADMIN = {"X-Remote-User": "sep", "X-Remote-Actions": "tao,toan_quyen,quan_tri"}


def _goi(method, path, headers=None, **kw):
    async def _run():
        transport = httpx.ASGITransport(app=srv.app, client=("127.0.0.1", 50000))
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
            return await c.request(method, path, headers=headers or {}, **kw)
    return asyncio.run(_run())


CUA_QUAN_TRI = [
    ("GET", "/api/settings"), ("POST", "/api/settings"),
    ("GET", "/api/users"), ("POST", "/api/invite"),
    ("DELETE", "/api/invite/ABCD1234"), ("DELETE", "/api/users/ai-do"),
    ("POST", "/api/users/ai-do/role"), ("POST", "/api/users/ai-do/password"),
    ("GET", "/api/register"), ("POST", "/api/register"),
]


def test_cua_quan_tri_dong_404_ke_ca_admin(monkeypatch):
    monkeypatch.setenv("NICHE_TRUST_PROXY", "1")
    assert srv._vai_tu_sso(_Req(_ADMIN)) == "admin"      # vai nội bộ vẫn admin…
    for method, path in CUA_QUAN_TRI:                    # …nhưng mọi cửa vẫn đóng
        r = _goi(method, path, headers=_ADMIN, json={})
        assert r.status_code == 404, (method, path, r.status_code)
    assert "OUTLIERY" in srv.THONG_DIEP_QT
    r = _goi("GET", "/api/settings", headers=_ADMIN)
    assert "OUTLIERY" in r.json()["detail"]              # thông điệp chỉ đường


def test_van_hanh_khong_bi_dong_va_phan_vai_dung(monkeypatch):
    """Vận hành giữ nguyên khi SSO: seo bị chặn tạo (403 — KHÔNG phải 404),
    leader qua cửa tạo, manager mới xóa được (404 vì dự án không tồn tại =
    ĐÃ QUA gate quyền)."""
    monkeypatch.setenv("NICHE_TRUST_PROXY", "1")
    seo = {"X-Remote-User": "nv", "X-Remote-Actions": ""}
    leader = {"X-Remote-User": "ld", "X-Remote-Actions": "tao"}
    manager = {"X-Remote-User": "ql", "X-Remote-Actions": "tao,toan_quyen"}

    assert _goi("GET", "/api/health").json()["ok"] is True
    assert _goi("GET", "/api/projects", headers=seo).status_code == 200
    assert _goi("POST", "/api/projects", headers=seo,
                json={"name": "x"}).status_code == 403
    assert _goi("DELETE", "/api/projects/khong-co", headers=leader).status_code == 403
    assert _goi("DELETE", "/api/projects/khong-co", headers=manager).status_code == 404
    r = _goi("POST", "/api/projects", headers=leader, json={"name": "smoke-test-xoa"})
    assert r.status_code == 200
    assert _goi("DELETE", "/api/projects/smoke-test-xoa",
                headers=manager).status_code == 200      # dọn sạch dấu test


def test_scheduler_tat_duoc_qua_env(monkeypatch):
    """NICHE_SCHEDULER=0 (start-all V3) → KHÔNG mọc thread watch — chống đốt
    đôi quota với hệ thật C:\\ đang tự watch cùng dự án."""
    goi = []
    monkeypatch.setattr(srv.threading, "Thread",
                        lambda *a, **k: goi.append(k) or _ThreadGia())
    monkeypatch.setenv("NICHE_SCHEDULER", "0")
    srv._start_watch_scheduler()
    assert goi == []
    monkeypatch.setenv("NICHE_SCHEDULER", "1")
    srv._start_watch_scheduler()
    assert len(goi) == 1


class _ThreadGia:
    def start(self):
        pass


# ---------- nguồn khóa = KÉT (không fallback .env) ----------

def test_khoa_tu_ket_khong_fallback(monkeypatch):
    monkeypatch.setenv("NICHE_TRUST_PROXY", "1")
    assert khoa_v3.bat() is True
    monkeypatch.setenv("GATEWAY_URL", "http://127.0.0.1:1")   # gateway chết
    with pytest.raises(RuntimeError) as e:
        khoa_v3.khoa_theo_viec("quet_kenh")
    assert "OUTLIERY" in str(e.value)
    monkeypatch.setenv("NICHE_TRUST_PROXY", "0")
    assert khoa_v3.bat() is False                             # V2 mode: két nghỉ


def test_env_llm_anh_xa_dung_danh_phap_llm_provider(monkeypatch):
    class _R:
        def __init__(s, d): s._d = json.dumps(d).encode()
        def read(s): return s._d
        def __enter__(s): return s
        def __exit__(s, *a): return False

    du_lieu = {
        "quet_kenh": {"khoa": [{"id": "api-001", "key": "AIza-yt-1", "loai": "youtube"},
                               {"id": "api-002", "key": "AIza-yt-2", "loai": "youtube"}]},
        "phan_tich": {"khoa": [{"id": "api-003", "key": "sk-glm-x", "loai": "llm",
                                "nha": "glm"}], "model": "glm-5.2"},
        "lay_transcript": {"khoa": [{"id": "api-004", "key": "tr-x",
                                     "loai": "transcript", "nha": ""}]},
    }
    monkeypatch.setattr(khoa_v3.urllib.request, "urlopen",
                        lambda url, timeout=5: _R(du_lieu))
    cap = khoa_v3._goi_ket()
    assert khoa_v3.khoa_theo_viec("quet_kenh", cap) == ["AIza-yt-1", "AIza-yt-2"]
    env = khoa_v3.env_llm(cap)
    assert env == {"LLM_PROVIDER": "glm", "GLM_API_KEY": "sk-glm-x",
                   "GLM_MODEL": "glm-5.2"}
    assert khoa_v3.env_transcript(cap) == {"TRANSCRIPT_API_KEY": "tr-x"}
    # nhà claude → danh pháp anthropic của scripts/llm_provider.py
    du_lieu["phan_tich"] = {"khoa": [{"id": "api-005", "key": "sk-ant-x",
                                      "loai": "llm", "nha": "claude"}]}
    env = khoa_v3.env_llm(khoa_v3._goi_ket())
    assert env == {"LLM_PROVIDER": "anthropic", "ANTHROPIC_API_KEY": "sk-ant-x"}
    # việc chưa cấp khóa → lỗi rõ, không bịa provider
    du_lieu["phan_tich"] = {"khoa": []}
    with pytest.raises(RuntimeError):
        khoa_v3.env_llm(khoa_v3._goi_ket())


def test_bom_khoa_youtube_dedup(tmp_path):
    """Khóa két bơm vào competitors.txt (pipeline đọc key từ CHÍNH file input —
    thiết kế V2); key đã có trong file thì không ghi lại."""
    d = tmp_path / "du-an"
    d.mkdir()
    (d / "competitors.txt").write_text(
        "https://youtube.com/@kenh1\nAIza-da-co-trong-file\n", encoding="utf-8")
    srv._bom_khoa_youtube(d, ["AIza-da-co-trong-file", "AIza-moi-tu-ket"])
    txt = (d / "competitors.txt").read_text(encoding="utf-8")
    assert txt.count("AIza-da-co-trong-file") == 1        # dedup
    assert "AIza-moi-tu-ket" in txt
    srv._bom_khoa_youtube(d, ["AIza-moi-tu-ket"])         # lần 2 không nhân đôi
    assert (d / "competitors.txt").read_text(encoding="utf-8").count("AIza-moi-tu-ket") == 1


def test_du_lieu_tro_data_dir_qua_env():
    """MỌI đường dữ liệu (projects + data) trỏ NICHE_DATA_DIR (conftest đặt tmp)
    — không hardcode cạnh code; V2 không đặt env thì nằm cạnh code như cũ."""
    import os
    goc = os.environ["NICHE_DATA_DIR"]
    assert str(srv.PROJECTS) == str(srv.Path(goc) / "projects")
    assert str(srv.DATA_PATH) == str(srv.Path(goc) / "data")
    assert srv.PROJECTS.is_dir() and srv.DATA_PATH.is_dir()
