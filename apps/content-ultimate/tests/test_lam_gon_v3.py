# -*- coding: utf-8 -*-
"""LÀM GỌN Content Ultimate (Owner 16/08, khuôn RadarY): quản trị nội bộ (API key
· cấu hình LLM · tài khoản/mời/vai) ĐÓNG 404 khi SSO kể cả vai admin — tab Quản
lý (vận hành) giữ; nguồn khóa DUY NHẤT là két OUTLIERY (không fallback .env)."""
import json

import pytest

import contentultimate.server as srv
from contentultimate import khoa_v3


class _H:
    """Handler giả đủ cho các hàm gate (không dựng HTTP server thật)."""
    def __init__(self, headers=None, ip="127.0.0.1"):
        self.headers = headers or {}
        self.client_address = (ip, 1234)


_ADMIN = {"X-Remote-User": "sep", "X-Remote-Actions": "sua,quan_tri"}


def test_cua_quan_tri_dong_khi_sso_ke_ca_admin(monkeypatch):
    monkeypatch.setenv("CU_TRUST_PROXY", "1")
    h = _H(_ADMIN)
    assert srv._vai_sso(h) == "admin"          # vai nội bộ vẫn là admin…
    assert srv._is_admin(h) is True
    assert srv._sso_quan_tri_dong(h) is True   # …nhưng cửa quản trị vẫn đóng
    assert "OUTLIERY" in srv.THONG_DIEP_QT
    monkeypatch.setenv("CU_TRUST_PROXY", "0")
    assert srv._sso_quan_tri_dong(_H(_ADMIN)) is False   # V2 mode: mở như cũ


def test_route_quan_tri_deu_co_chot_sso():
    """7 cửa quản trị (GET/POST settings · invites · POST users) phải gọi
    _sso_quan_tri_dong TRƯỚC khi kiểm _is_admin — ghim bằng số lần gọi."""
    src = (srv.__file__ and open(srv.__file__, encoding="utf-8").read())
    assert src.count("_sso_quan_tri_dong(self)") == 8   # 7 route + 1 thẻ UI /manage
    assert src.count('SETTINGS_CARD if (_is_admin(self)') == 1   # thẻ Cài đặt ẩn


def test_van_hanh_khong_bi_dong(monkeypatch):
    """Tab Quản lý = VẬN HÀNH: leader vẫn vào được khi SSO (không bị guard)."""
    monkeypatch.setenv("CU_TRUST_PROXY", "1")
    h = _H({"X-Remote-User": "leader1", "X-Remote-Actions": "sua"})
    assert srv._vai_sso(h) == "leader" and srv._can_manage(h) is True
    assert srv._is_admin(h) is False            # nhưng KHÔNG phải admin


def test_khoa_tu_ket_khong_fallback(monkeypatch):
    monkeypatch.setenv("CU_TRUST_PROXY", "1")
    assert khoa_v3.bat() is True
    monkeypatch.setenv("GATEWAY_URL", "http://127.0.0.1:1")   # gateway chết
    with pytest.raises(RuntimeError) as e:
        khoa_v3.khoa_theo_viec("lay_comment")
    assert "OUTLIERY" in str(e.value)
    with pytest.raises(RuntimeError):
        khoa_v3._goi_ket()


def test_env_ket_anh_xa_dung_bien(monkeypatch):
    class _R:
        def __init__(s, d): s._d = json.dumps(d).encode()
        def read(s): return s._d
        def __enter__(s): return s
        def __exit__(s, *a): return False

    du_lieu = {
        "viet_kich_ban": {"khoa": [{"id": "api-001", "key": "sk-glm", "loai": "llm",
                                    "nha": "glm"}], "model": "glm-5.2"},
        "lay_transcript": {"khoa": [{"id": "api-002", "key": "tr-key",
                                     "loai": "transcript", "nha": ""}]},
        "lay_comment": {"khoa": [{"id": "api-003", "key": "yt-1", "loai": "youtube"},
                                 {"id": "api-004", "key": "yt-2", "loai": "youtube"}]},
        "phan_tich_outline": {"khoa": []},          # chưa cấp → bỏ qua, không nổ
    }
    monkeypatch.setattr(khoa_v3.urllib.request, "urlopen",
                        lambda url, timeout=5: _R(du_lieu))
    env = khoa_v3.env_ket()
    assert env["GLM_API_KEY"] == "sk-glm" and env["GLM_MODEL"] == "glm-5.2"
    assert env["LLM_PROVIDER"] == "glm"
    assert env["TRANSCRIPT_API_KEY"] == "tr-key"
    assert env["YOUTUBE_API_KEY"] == "yt-1"
    assert khoa_v3.khoa_theo_viec("lay_comment") == ["yt-1", "yt-2"]   # xoay vòng đủ khóa


def test_diem_doc_khoa_khong_con_doc_env_khi_v3():
    """4 điểm đọc khóa đều rẽ qua khoa_v3 khi V3 (ghim bằng mã nguồn — chạy thật
    cần gateway + pipeline nặng)."""
    from pathlib import Path
    goc = Path(srv.__file__).resolve().parents[1]
    for f, dau in [("oe/llm.py", "khoa_v3.env_ket() if khoa_v3.bat()"),
                   ("voiceprofile/llm.py", "if khoa_v3.bat():"),
                   ("oe/transcript.py", "if khoa_v3.bat():"),
                   ("oe/s5_server.py", 'khoa_v3.khoa_theo_viec("lay_comment")')]:
        assert dau in (goc / f).read_text(encoding="utf-8"), f
