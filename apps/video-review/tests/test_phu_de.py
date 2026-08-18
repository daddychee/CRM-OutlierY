# -*- coding: utf-8 -*-
"""Test phụ đề .srt/.vtt — chuyển VTT, quyền CHỈ CHÍNH CHỦ, 3 đường gắn."""
import io

import pytest
from fastapi.testclient import TestClient

from src import kho_video, nap_nas
from src.main import app
from tests.test_routes import _up, h

SRT = ("1\n00:00:01,000 --> 00:00:03,500\nXin chào\n\n"
       "2\n00:00:04,000 --> 00:00:06,000\nĐây là phụ đề\n")


@pytest.fixture()
def client():
    nap_nas._TAC_VU.clear()
    with TestClient(app) as c:
        yield c


def _gan(client, ma="VR-0001", ten_file="a.srt", noi_dung=SRT, **hd):
    return client.post(f"/api-vr/phu-de/{ma}", headers=h(**hd),
                       files={"file": (ten_file, io.BytesIO(noi_dung.encode("utf-8")),
                                       "text/plain")})


def test_srt_sang_vtt():
    vtt = kho_video.srt_sang_vtt(SRT)
    assert vtt.startswith("WEBVTT")
    assert "00:00:01.000 --> 00:00:03.500" in vtt   # phẩy mili-giây → chấm
    assert "Xin chào" in vtt
    assert kho_video.srt_sang_vtt(vtt) == vtt       # đã VTT → trả nguyên, không đúp header


def test_chi_chinh_chu_duoc_gan_va_go(client):
    _up(client)   # nguoi_tao = an
    # Leader có cờ duyet cũng KHÔNG được (user chốt: người up video tự lo phụ đề)
    assert _gan(client, ten="chi", actions="duyet").status_code == 403
    assert _gan(client).status_code == 200
    # ai xem được video thì đọc được phụ đề — trả WebVTT đã chuyển
    r = client.get("/api-vr/phu-de/VR-0001", headers=h(ten="binh"))
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/vtt")
    assert "WEBVTT" in r.text and "00:00:01.000" in r.text and "Xin chào" in r.text
    assert client.post("/api-vr/phu-de/VR-0001/xoa",
                       headers=h(ten="chi", actions="duyet")).status_code == 403
    assert client.post("/api-vr/phu-de/VR-0001/xoa", headers=h()).status_code == 200
    assert client.get("/api-vr/phu-de/VR-0001", headers=h()).status_code == 404


def test_gan_kiem_file(client):
    _up(client)
    assert _gan(client, ten_file="a.txt").status_code == 422
    assert _gan(client, noi_dung="khong phai phu de").status_code == 422
    assert client.get("/api-vr/phu-de/VR-9999", headers=h()).status_code == 404


def test_trang_xem_co_track_khi_co_phu_de(client):
    _up(client)
    assert "<track" not in client.get("/xem/VR-0001", headers=h()).text
    _gan(client)
    trang = client.get("/xem/VR-0001", headers=h()).text
    assert '<track kind="subtitles"' in trang
    assert "Replace subs" in trang                  # nút chính chủ đổi nhãn
    # người khác xem: có track nhưng KHÔNG có nút gắn/gỡ
    trang2 = client.get("/xem/VR-0001", headers=h(ten="binh")).text
    assert '<track kind="subtitles"' in trang2 and "Replace subs" not in trang2


def test_upload_form_kem_phu_de(client):
    r = client.post("/upload-video", data={"ten": "x"},
                    files={"file": ("a.mp4", io.BytesIO(b"v" * 10), "video/mp4"),
                           "phu_de": ("a.srt", io.BytesIO(SRT.encode("utf-8")), "text/plain")},
                    headers=h(), follow_redirects=False)
    assert r.status_code == 303
    assert client.get("/api-vr/phu-de/VR-0001", headers=h()).status_code == 200
    # phụ đề rác → 422 NGAY TẠI CỬA, video KHÔNG được tạo (không ghi sổ nửa vời)
    r2 = client.post("/upload-video", data={},
                     files={"file": ("b.mp4", io.BytesIO(b"v"), "video/mp4"),
                            "phu_de": ("b.srt", io.BytesIO(b"rac"), "text/plain")},
                     headers=h(), follow_redirects=False)
    assert r2.status_code == 422
    assert kho_video.lay_video("VR-0002") is None


def test_nas_tu_nhat_srt_cung_ten(client, tmp_path, monkeypatch):
    goc = tmp_path / "nas"
    (goc / "xuat").mkdir(parents=True)
    (goc / "xuat" / "tap1.mp4").write_bytes(b"v" * 100)
    (goc / "xuat" / "tap1.srt").write_text(SRT, encoding="utf-8")
    monkeypatch.setenv("VR_NAS_DIR", str(goc))
    tid = client.post("/api-vr/nas-nap", data={"duong": "xuat/tap1.mp4"},
                      headers=h()).json()["task_id"]
    tt = client.get(f"/api-vr/nas-tien-do/{tid}", headers=h()).json()
    assert tt["trang_thai"] == "xong"
    r = client.get(f"/api-vr/phu-de/{tt['ma']}", headers=h())
    assert r.status_code == 200 and "Xin chào" in r.text
    assert (goc / "xuat" / "tap1.srt").is_file()    # file gốc NAS không bị đụng
