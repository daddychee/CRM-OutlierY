# -*- coding: utf-8 -*-
"""Test route Video Review — claims + RBAC cờ hành động + upload + Range từng khúc."""
import io
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient

from src import kho_video
from src.main import app


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def h(ten="an", level=2, actions="", dept="Vận hành Sản xuất"):
    """Claims như gateway tiêm (Dept URL-encode — khuôn di trú chuẩn P5.1)."""
    return {"X-Remote-User": ten, "X-Remote-Level": str(level),
            "X-Remote-Dept": quote(dept), "X-Remote-Actions": actions}


def _up(client, ten="ban dung 1", noi_dung=b"x" * 64, duoi=".mp4", **hd):
    return client.post("/upload-video", data={"ten": ten},
                       files={"file": (f"a{duoi}", io.BytesIO(noi_dung), "video/mp4")},
                       headers=h(**hd), follow_redirects=False)


def test_health_khong_can_claims(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["app"] == "video-review"


def test_khong_claims_bi_401(client):
    for duong in ["/danh-sach", "/xem/VR-0001", "/media/VR-0001", "/api-vr/binh-luan/VR-0001"]:
        assert client.get(duong).status_code == 401, duong


def test_upload_ghi_kho_va_hien_danh_sach(client):
    r = _up(client, ten="Tập 1")
    assert r.status_code == 303 and r.headers["location"] == "/xem/VR-0001"
    v = kho_video.lay_video("VR-0001")
    assert (kho_video.kho_dir() / v["duong"]).is_file()
    assert v["kich_thuoc"] == 64
    trang = client.get("/danh-sach", headers=h())
    assert trang.status_code == 200 and "Tập 1" in trang.text


def test_upload_chan_duoi_la_va_qua_tran(client, monkeypatch):
    assert _up(client, duoi=".exe").status_code == 422
    monkeypatch.setenv("VR_MAX_FORM_MB", "1")   # trần RIÊNG đường form một phát
    r = _up(client, noi_dung=b"x" * (1024 * 1024 + 1))
    assert r.status_code == 413
    # file tạm vượt trần phải được dọn — kho không còn file .tam nào
    assert not list(kho_video.kho_dir().rglob("*.tam"))


def test_danh_sach_trang_thai_hien_thi_cho_review(client):
    """Video up lên CHƯA ai bình luận = Awaiting review; có bình luận = In review;
    Approved giữ nhãn thật (logic hiển thị user chốt 18/08)."""
    _up(client, ten="chưa ai xem")
    _up(client, ten="đã có góp ý")
    _up(client, ten="đã duyệt")
    kho_video.them_binh_luan("VR-0002", "binh", "note")
    kho_video.doi_trang_thai("VR-0003", "da_duyet")
    trang = client.get("/danh-sach", headers=h()).text
    assert 'data-tt="cho_review"' in trang and "Awaiting review" in trang
    assert 'data-tt="dang_review"' in trang
    assert 'data-tt="da_duyet"' in trang
    # bình luận đã giải vẫn tính là "đã có người review" — không rơi lại cho_review
    bl = kho_video.ds_binh_luan("VR-0002")[0]
    kho_video.giai_binh_luan(bl["id"], "binh", False)
    assert 'data-tt="dang_review"' in client.get("/danh-sach", headers=h()).text


def test_trang_xem_nhung_binh_luan(client):
    _up(client)
    kho_video.them_binh_luan("VR-0001", "an", "note <script>alert(1)</script>", ts_giay=3)
    r = client.get("/xem/VR-0001", headers=h())
    assert r.status_code == 200
    assert "<script>alert(1)" not in r.text          # |tojson phải escape — script-safe
    assert client.get("/xem/VR-9999", headers=h()).status_code == 404


def test_media_range_tung_khuc(client, monkeypatch):
    monkeypatch.setenv("VR_KHUC_MB", "1")
    _up(client, noi_dung=b"a" * (2 * 1024 * 1024))    # 2MB, khúc 1MB
    # mở đầu không giới hạn cuối → bị CẮT còn 1 khúc (proxy không phình RAM)
    r = client.get("/media/VR-0001", headers={**h(), "Range": "bytes=0-"})
    assert r.status_code == 206
    assert r.headers["content-range"] == f"bytes 0-{1024*1024-1}/{2*1024*1024}"
    assert len(r.content) == 1024 * 1024
    # khúc giữa chừng đúng offset; range ngoài file → 416
    r2 = client.get("/media/VR-0001", headers={**h(), "Range": f"bytes={2*1024*1024-3}-"})
    assert r2.status_code == 206 and len(r2.content) == 3
    assert client.get("/media/VR-0001",
                      headers={**h(), "Range": "bytes=9999999-"}).status_code == 416
    # không Range (nút tải về) → trọn file 200
    r3 = client.get("/media/VR-0001", headers=h())
    assert r3.status_code == 200 and len(r3.content) == 2 * 1024 * 1024


def test_api_binh_luan_vong_doi(client):
    _up(client)
    r = client.post("/api-vr/binh-luan", headers=h(),
                    json={"video_ma": "VR-0001", "noi_dung": "cắt 0:03", "ts_giay": 3.2,
                          "ve": {"w": 1, "h": 1, "net": [{"mau": "#ff5f56", "diem": [[0, 0], [1, 1]]}]}})
    assert r.status_code == 200
    bl_id = r.json()["id"]
    assert client.get("/api-vr/binh-luan/VR-0001", headers=h()).json()[0]["ts_giay"] == 3.2
    # người khác level thường không giải được; chính chủ được
    assert client.post(f"/api-vr/binh-luan/{bl_id}/giai", headers=h(ten="binh")).status_code == 403
    assert client.post(f"/api-vr/binh-luan/{bl_id}/giai", headers=h()).status_code == 200
    # leader (cờ duyet) mở lại + xóa được dù không phải chính chủ
    assert client.post(f"/api-vr/binh-luan/{bl_id}/mo-lai",
                       headers=h(ten="chi", actions="duyet")).status_code == 200
    assert client.post(f"/api-vr/binh-luan/{bl_id}/xoa",
                       headers=h(ten="chi", actions="duyet")).status_code == 200
    assert client.post("/api-vr/binh-luan", headers=h(),
                       json={"video_ma": "VR-0001", "noi_dung": "  "}).status_code == 422


def test_trang_thai_can_co_duyet(client):
    _up(client)
    du = {"ma": "VR-0001", "trang_thai": "da_duyet"}
    assert client.post("/api-vr/trang-thai", data=du, headers=h()).status_code == 403
    assert client.post("/api-vr/trang-thai", data=du,
                       headers=h(actions="duyet")).status_code == 200
    assert kho_video.lay_video("VR-0001")["trang_thai"] == "da_duyet"
    assert client.post("/api-vr/trang-thai", data={"ma": "VR-0001", "trang_thai": "da_xoa"},
                       headers=h(actions="duyet")).status_code == 422  # gỡ đi đường xoa riêng


def test_xoa_video_can_co_xoa_va_la_go_mem(client):
    _up(client)
    assert client.post("/api-vr/xoa-video", data={"ma": "VR-0001"},
                       headers=h(actions="duyet")).status_code == 403
    assert client.post("/api-vr/xoa-video", data={"ma": "VR-0001"},
                       headers=h(level=4, actions="duyet,xoa")).status_code == 200
    # gỡ mềm: trang + media 404 nhưng FILE còn trong kho (còn đường cứu)
    assert client.get("/xem/VR-0001", headers=h()).status_code == 404
    assert client.get("/media/VR-0001", headers=h()).status_code == 404
    v = kho_video.lay_video("VR-0001")
    assert (kho_video.kho_dir() / v["duong"]).is_file()
