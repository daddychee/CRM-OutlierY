"""Test route ĐỀ XUẤT đoạn từ video YouTube (Owner). Giả lập mạng (monkeypatch lay_transcript)
+ writer (mock) để tất định — KHÔNG gọi YouTube/LLM thật. CHƯA nạp kho ở route này."""

import json
import os

os.environ["MOCK_MODE"] = "true"

from fastapi.testclient import TestClient

import src.nap_youtube as ny
from src.main import app, client, doc_catalog, qa

_TRANSCRIPT = [{"text": "chọn một ngách thật nhỏ để dễ lên top", "start": 0, "duration": 3}]
_THO = "<<<TRICH>>>\nchọn một ngách thật nhỏ để dễ lên top\n<<<LYDO>>>\nchiến lược ngách\n<<<HET>>>"


def _login(tmp_path, monkeypatch, dong):
    # V2: claims thay users.txt — 'dong' giữ khuôn cũ ten:mk:bo_phan:level, parse ra claims
    from claims_v2 import client_claims
    ten, _, bo_phan, level = dong.strip().splitlines()[0].split(":")
    return client_claims(app, ten, bo_phan, int(level))


def test_owner_de_xuat_doan_verbatim(tmp_path, monkeypatch):
    monkeypatch.setattr(ny, "lay_transcript", lambda vid, ngon_ngu=("vi", "en"): _TRANSCRIPT)
    monkeypatch.setattr(qa.writer, "generate", lambda s, u: _THO)
    r = _login(tmp_path, monkeypatch, "chu:mk:Kinh doanh:5\n").post(
        "/nguon/youtube/de-xuat", data={"url": "https://youtu.be/XyZ_9"})
    assert r.status_code == 200
    j = r.json()
    assert j["video_id"] == "XyZ_9"
    assert j["cac_doan"] == [{"trich": "chọn một ngách thật nhỏ để dễ lên top",
                              "dich": "", "ly_do": "chiến lược ngách"}]


def test_video_khong_phu_de_tra_422(tmp_path, monkeypatch):
    def no(*a, **k):
        raise RuntimeError("no transcript")
    monkeypatch.setattr(ny, "lay_transcript", no)
    r = _login(tmp_path, monkeypatch, "chu:mk:Kinh doanh:5\n").post(
        "/nguon/youtube/de-xuat", data={"url": "https://youtu.be/XyZ_9"})
    assert r.status_code == 422       # lỗi lấy phụ đề → báo rõ, không vỡ
    assert "phụ đề" in r.json()["detail"]


def test_loi_model_khong_bao_nham_phu_de(tmp_path, monkeypatch):
    """25/07: Z.ai hết tiền từng bị báo 'không lấy được phụ đề' → user đi sửa cookies oan.
    Phụ đề OK + writer lỗi → thông điệp phải chỉ đúng tầng MODEL (key/số dư), không đổ cho phụ đề."""
    monkeypatch.setattr(ny, "lay_transcript", lambda vid, ngon_ngu=("vi", "en"): _TRANSCRIPT)
    def chet(*a, **k):
        raise RuntimeError("Error code: 429 - Insufficient balance")
    monkeypatch.setattr(qa.writer, "generate", chet)
    r = _login(tmp_path, monkeypatch, "chu:mk:Kinh doanh:5\n").post(
        "/nguon/youtube/de-xuat", data={"url": "https://youtu.be/XyZ_9"})
    assert r.status_code == 422
    assert "SỐ DƯ" in r.json()["detail"] and "Phụ đề đã lấy ĐƯỢC" in r.json()["detail"]


def test_nhan_vien_bi_tu_choi(tmp_path, monkeypatch):
    r = _login(tmp_path, monkeypatch, "nv:mk:Kinh doanh:2\n").post(
        "/nguon/youtube/de-xuat", data={"url": "https://youtu.be/XyZ_9"})
    assert r.status_code == 403       # yeu_cau_quan_ly chặn ở SERVER (L2 < Manager)


def test_manager_duoc_dung_nguon_ngoai(tmp_path, monkeypatch):
    """31/07/2026 user chốt: Nguồn ngoài mở cho MANAGER+ (trước chỉ Owner) — mục nằm
    ở pane Monitoring để Manager thêm được nguồn."""
    c = _login(tmp_path, monkeypatch, "ql:mk:Kinh doanh:4\n")
    assert c.get("/nguon-ngoai").status_code == 200
    monkeypatch.setattr(ny, "lay_transcript", lambda vid, ngon_ngu=("vi", "en"): _TRANSCRIPT)
    monkeypatch.setattr(qa.writer, "generate", lambda s, u: _THO)
    r = c.post("/nguon/youtube/de-xuat", data={"url": "https://youtu.be/XyZ_9"})
    assert r.status_code == 200 and r.json()["cac_doan"]


# ─────────────── DUYỆT → nạp kho tầng ngoai ───────────────

def _duyet_data(**thay):
    d = {"url": "https://youtu.be/XyZ_9", "nguon_ten": "Danny Why",
         "cac_doan": json.dumps([{"trich": "chọn một ngách thật nhỏ để dễ lên top", "ly_do": "ngách"}]),
         "department": "Kinh doanh", "access_level": "Công khai nội bộ", "min_level": "1"}
    d.update(thay)
    return d


def test_owner_duyet_nap_kho_ngoai(tmp_path, monkeypatch):
    client._mock_chunks.clear(); client._mock_payload.clear()
    r = _login(tmp_path, monkeypatch, "chu:mk:Kinh doanh:5\n").post(
        "/nguon/youtube/duyet", data=_duyet_data())
    assert r.status_code == 200 and r.json()["ok"]
    assert r.json()["doc_code"] == "YT-XyZ_9"
    row = next(d for d in doc_catalog() if d["Mã tài liệu"] == "YT-XyZ_9")
    assert row["Tầng nguồn"] == "ngoai" and row["Tên nguồn"] == "Danny Why"
    assert client.dem_chunk_doc_code("YT-XyZ_9") >= 1        # đã nạp Qdrant


def test_duyet_khong_doan_nao_422(tmp_path, monkeypatch):
    r = _login(tmp_path, monkeypatch, "chu:mk:Kinh doanh:5\n").post(
        "/nguon/youtube/duyet", data=_duyet_data(cac_doan="[]"))
    assert r.status_code == 422       # chưa chọn đoạn → không nạp


def test_duyet_non_owner_403(tmp_path, monkeypatch):
    r = _login(tmp_path, monkeypatch, "nv:mk:Kinh doanh:2\n").post(
        "/nguon/youtube/duyet", data=_duyet_data())
    assert r.status_code == 403


# ─────────────── 🍪 COOKIES — box dán qua UI (Owner, write-only) ───────────────

_CK = ("# Netscape HTTP Cookie File\n"
       ".youtube.com\tTRUE\t/\tTRUE\t9999999999\tSID\tabc\n")


def test_owner_luu_va_go_cookies(tmp_path, monkeypatch):
    c = _login(tmp_path, monkeypatch, "chu:mk:Kinh doanh:5\n")
    r = c.post("/nguon/cookies", data={"noi_dung": _CK})
    assert r.status_code == 200 and r.json()["so_dong"] == 1
    assert "abc" not in r.text                                    # write-only: không trả lại nội dung
    r2 = c.get("/nguon-ngoai")
    assert "1 dòng youtube.com" in r2.text and "abc" not in r2.text  # trang chỉ hiện TRẠNG THÁI
    assert c.post("/nguon/cookies/xoa").status_code == 200
    assert "chưa có" in c.get("/nguon-ngoai").text


def test_luu_cookies_nham_file_422(tmp_path, monkeypatch):
    r = _login(tmp_path, monkeypatch, "chu:mk:Kinh doanh:5\n").post(
        "/nguon/cookies", data={"noi_dung": "không phải cookies"})
    assert r.status_code == 422


def test_cookies_non_owner_403(tmp_path, monkeypatch):
    c = _login(tmp_path, monkeypatch, "nv:mk:Kinh doanh:2\n")
    assert c.post("/nguon/cookies", data={"noi_dung": _CK}).status_code == 403
    assert c.post("/nguon/cookies/xoa").status_code == 403


def test_trang_nguon_ngoai_owner_render(tmp_path, monkeypatch):
    r = _login(tmp_path, monkeypatch, "chu:mk:Kinh doanh:5\n").get("/nguon-ngoai")
    assert r.status_code == 200
    assert 'id="nut-de-xuat"' in r.text and 'id="nut-duyet"' in r.text  # render không lỗi Jinja


def test_trang_nguon_ngoai_non_owner_403(tmp_path, monkeypatch):
    r = _login(tmp_path, monkeypatch, "nv:mk:Kinh doanh:2\n").get("/nguon-ngoai")
    assert r.status_code == 403
