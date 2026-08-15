"""Test lịch sử hội thoại per-user (Mảnh D1) — lưu JSON + trang xem lại + Owner giám sát."""

import os

os.environ["MOCK_MODE"] = "true"  # ép mock TRƯỚC khi import app

from pathlib import Path

from fastapi.testclient import TestClient

from src.main import app
from src.lich_su import doc_lich_su, luu_luot

# V2: claims từ gateway thay users.txt — bảng bộ phận×level giữ nguyên ý cũ.
from claims_v2 import client_claims, client_khach

HO_SO = {"sep": ("Kinh doanh", 5), "nv": ("Kinh doanh", 2), "nv2": ("IT", 2)}


def _users_file(tmp_path, monkeypatch, noi_dung=None):
    """V2: không còn USERS_FILE — giữ chữ ký để call-site cũ nguyên vẹn (no-op)."""


def _dang_nhap(ten, mk="mk"):
    return client_claims(app, ten, *HO_SO[ten])


def _thu_muc():
    return Path(os.environ["LICH_SU_DIR"])  # conftest trỏ vào tmp riêng mỗi test


def test_luu_va_doc_dung_luot():
    luu_luot("an", "hỏi 1", "đáp 1", ["KD-1"], "2026-07-19T10:00:00")
    luu_luot("an", "hỏi 2", "đáp 2", [], "2026-07-19T10:05:00")

    cac_luot = doc_lich_su("an")
    assert len(cac_luot) == 2                      # 2 lượt liên tiếp — không mất lượt cũ
    assert cac_luot[0] == {"hoi": "hỏi 1", "dap": "đáp 1",
                           "doc_codes": ["KD-1"], "thoi_gian": "2026-07-19T10:00:00",
                           "chua_tra_loi_duoc": False}  # nền YC4/YC7
    assert cac_luot[1]["hoi"] == "hỏi 2"           # thứ tự cũ → mới
    assert doc_lich_su("nguoi-khac") == []


def test_ten_la_khong_thoat_khoi_thu_muc():
    luu_luot("../../hack", "h", "d", [], "2026-07-19T10:00:00")
    luu_luot("a/b\\c", "h", "d", [], "2026-07-19T10:00:00")

    cac_file = list(_thu_muc().glob("*.json"))
    assert len(cac_file) == 2                      # cả 2 file nằm TRONG LICH_SU_DIR
    assert not (_thu_muc().parent / "hack.json").exists()  # không thoát ra ngoài
    assert doc_lich_su("../../hack")[0]["hoi"] == "h"      # đọc lại vẫn đúng user đó


def test_route_hoi_luu_lich_su_user_that(tmp_path, monkeypatch):
    _users_file(tmp_path, monkeypatch)
    c = _dang_nhap("nv")

    c.post("/hoi", data={"question": "quy trình đăng video?"})
    cac_luot = doc_lich_su("nv")
    assert len(cac_luot) == 1
    assert cac_luot[0]["hoi"] == "quy trình đăng video?"
    assert cac_luot[0]["doc_codes"]                # có mã tài liệu từ sources (cho D2)
    assert cac_luot[0]["thoi_gian"]


def test_route_stream_luu_ca_cau_tra_loi_ghep(tmp_path, monkeypatch):
    _users_file(tmp_path, monkeypatch)
    c = _dang_nhap("nv")

    r = c.post("/hoi-dap/stream", data={"question": "quy trình đăng video?", "history": "[]"})
    assert r.status_code == 200

    cac_luot = doc_lich_su("nv")
    assert len(cac_luot) == 1
    assert "[MOCK" in cac_luot[0]["dap"]           # answer ghép từ các token mock
    assert cac_luot[0]["doc_codes"]


def test_khach_thieu_bo_phan_khong_luu():
    c = client_khach(app)  # V2: claims thiếu bộ phận ≈ khách hệ cũ
    c.post("/hoi", data={"question": "x"})
    c.post("/hoi-dap/stream", data={"question": "x", "history": "[]"})
    assert not _thu_muc().exists() or not list(_thu_muc().glob("*"))  # không file rác


def test_trang_lich_su_cua_minh_va_khong_thay_nguoi_khac(tmp_path, monkeypatch):
    _users_file(tmp_path, monkeypatch)
    # dùng doc_code THẬT trong kho mock mà nv (KD level 2) được xem — D2 sẽ không ẩn
    luu_luot("nv", "câu hỏi của nv", "đáp nv", ["KD-2025-0011"], "2026-07-19T09:00:00")
    luu_luot("nv2", "câu hỏi của nv2", "đáp nv2", [], "2026-07-19T09:01:00")

    c = _dang_nhap("nv")
    r = c.get("/lich-su")
    assert r.status_code == 200
    assert "câu hỏi của nv" in r.text
    assert "câu hỏi của nv2" not in r.text         # trang của mình không lẫn của người khác

    assert c.get("/lich-su/nv2").status_code == 403  # user thường xem người khác → chặn
    assert c.get("/lich-su/nv").status_code == 200   # tự xem chính mình qua URL → OK


def test_owner_giam_sat_xem_nguoi_khac(tmp_path, monkeypatch):
    _users_file(tmp_path, monkeypatch)
    luu_luot("nv2", "nv2 hỏi gì đó", "đáp", ["KD-9"], "2026-07-19T09:00:00")

    c = _dang_nhap("sep")
    r = c.get("/lich-su/nv2")                               # YC4: tầng 1 — list phiên
    assert r.status_code == 200
    assert "nv2 hỏi gì đó" in r.text                        # preview lượt gần nhất
    assert "giám sát" in r.text.lower()                     # có nhãn chế độ giám sát
    r2 = c.get("/lich-su/nv2/phien/mac-dinh")               # tầng 2 — chi tiết nguyên bản
    assert "nv2 hỏi gì đó" in r2.text and "KD-9" in r2.text


def test_lich_su_rong_hien_thong_bao(tmp_path, monkeypatch):
    _users_file(tmp_path, monkeypatch)
    r = _dang_nhap("nv").get("/lich-su")
    assert "Chưa có cuộc trò chuyện nào" in r.text          # YC4: chữ trang list phiên


# ---- MẢNH D2: ẩn lượt vượt quyền khi CHÍNH CHỦ xem ----

def _gieo_lich_su_nv():
    """4 lượt cho nv (Kinh doanh, level 2): giữ / ẩn theo luật quyền hiện tại."""
    luu_luot("nv", "câu về công khai", "đáp", ["KD-2025-0011"], "2026-07-19T09:00:00")   # min 1 → GIỮ
    luu_luot("nv", "câu về chiến lược giá", "đáp mật", ["KD-2026-0099"], "2026-07-19T09:01:00")  # Mật min 4 → ẨN
    luu_luot("nv", "câu kho không có", "Tài liệu chưa nêu...", [], "2026-07-19T09:02:00")  # rỗng → GIỮ
    luu_luot("nv", "câu về tài liệu đã xóa", "đáp cũ", ["KD-DA-XOA-9999"], "2026-07-19T09:03:00")  # mất khỏi kho → ẨN


def test_d2_chinh_chu_an_luot_vuot_quyen(tmp_path, monkeypatch):
    _users_file(tmp_path, monkeypatch)
    _gieo_lich_su_nv()

    c = _dang_nhap("nv")
    assert c.get("/lich-su").status_code == 200
    r = c.get("/lich-su/phien/mac-dinh")         # YC4: nội dung lượt nằm ở tầng 2
    assert r.status_code == 200
    assert "câu về công khai" in r.text          # min 1 ≤ 2 → giữ
    assert "câu kho không có" in r.text          # doc_codes rỗng → giữ
    assert "câu về chiến lược giá" not in r.text  # Mật min 4 > 2 → ẩn CẢ LƯỢT
    assert "đáp mật" not in r.text               # cả câu trả lời cũng biến mất
    assert "câu về tài liệu đã xóa" not in r.text  # doc đã xóa khỏi kho → ẩn an toàn


def test_d2_tu_xem_qua_url_cung_bi_loc(tmp_path, monkeypatch):
    """Không có đường lách: /lich-su/<chính mình> vẫn áp lọc như /lich-su."""
    _users_file(tmp_path, monkeypatch)
    _gieo_lich_su_nv()
    c = _dang_nhap("nv")
    assert c.get("/lich-su/nv").status_code == 200          # tầng 1 của chính mình OK
    r = c.get("/lich-su/nv/phien/mac-dinh")                 # tầng 2 qua URL người-khác
    assert "câu về chiến lược giá" not in r.text and "câu về công khai" in r.text


def test_d2_owner_giam_sat_thay_nguyen_ban(tmp_path, monkeypatch):
    """Owner xem người khác: KHÔNG lọc — thấy cả lượt vượt quyền lẫn lượt doc đã xóa."""
    _users_file(tmp_path, monkeypatch)
    _gieo_lich_su_nv()

    r = _dang_nhap("sep").get("/lich-su/nv/phien/mac-dinh")  # YC4: chi tiết ở tầng 2
    assert r.status_code == 200
    for cau in ("câu về công khai", "câu về chiến lược giá",
                "câu kho không có", "câu về tài liệu đã xóa"):
        assert cau in r.text  # đủ CẢ 4 lượt, nguyên bản


def test_d2_luot_tron_nhieu_doc_1_ma_vuot_quyen_la_an():
    """Đơn vị: lượt trích [công khai + Mật] → 1 mã vượt quyền là ẩn cả lượt; batch tra 1 lần."""
    from src.lich_su import loc_theo_quyen
    from src.vector_client import QdrantClientWrapper

    nv2 = {"ten": "nv", "bo_phan": "Kinh doanh", "level": 2}
    cac_luot = [
        {"hoi": "a", "dap": "x", "doc_codes": ["KD-2025-0011"], "thoi_gian": "t"},
        {"hoi": "b", "dap": "y", "doc_codes": ["KD-2025-0011", "KD-2026-0099"], "thoi_gian": "t"},
    ]
    giu = loc_theo_quyen(cac_luot, nv2, QdrantClientWrapper(mock=True))
    assert [l["hoi"] for l in giu] == ["a"]  # lượt b ẩn vì dính KD-2026-0099 (Mật min 4)
