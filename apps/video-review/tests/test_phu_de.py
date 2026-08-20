# -*- coding: utf-8 -*-
"""Test phụ đề .srt/.vtt — chuyển VTT, quyền CHỈ CHÍNH CHỦ, hai nguồn app/NAS."""
import io

import pytest
from fastapi.testclient import TestClient

from src import kho_video
from src.main import app
from tests.test_routes import _them, h

SRT = ("1\n00:00:01,000 --> 00:00:03,500\nXin chào\n\n"
       "2\n00:00:04,000 --> 00:00:06,000\nĐây là phụ đề\n")


@pytest.fixture()
def client():
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
    _them(client)   # nguoi_tao = an
    # Leader có cờ duyet cũng KHÔNG được (user chốt: người đăng video tự lo phụ đề)
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


def test_phu_de_gan_tu_app_khong_ghi_len_nas(client):
    """Bất biến: NAS chỉ đọc — phụ đề gắn từ app nằm trong kho app, cạnh video
    trên NAS tuyệt đối không mọc file mới."""
    _them(client)
    v = kho_video.lay_video("VR-0001")
    goc_nas = kho_video.duong_video(v)
    assert _gan(client).status_code == 200
    assert (kho_video.kho_dir() / "phu-de" / "VR-0001.srt").is_file()
    assert list(goc_nas.parent.glob("*.srt")) == []
    assert kho_video.phu_de_tim(v)[1] == "app"


def test_gan_kiem_file(client):
    _them(client)
    assert _gan(client, ten_file="a.txt").status_code == 422
    assert _gan(client, noi_dung="khong phai phu de").status_code == 422
    assert client.get("/api-vr/phu-de/VR-9999", headers=h()).status_code == 404


def test_trang_xem_co_track_khi_co_phu_de(client):
    _them(client)
    assert "<track" not in client.get("/xem/VR-0001", headers=h()).text
    _gan(client)
    trang = client.get("/xem/VR-0001", headers=h()).text
    assert '<track kind="subtitles"' in trang
    assert "Replace subs" in trang                  # nút chính chủ đổi nhãn
    # người khác xem: có track nhưng KHÔNG có nút gắn/gỡ
    trang2 = client.get("/xem/VR-0001", headers=h(ten="binh")).text
    assert '<track kind="subtitles"' in trang2 and "Replace subs" not in trang2


def test_srt_canh_video_tren_nas_duoc_doc_thang(client):
    """Anh em để tap1.srt cạnh tap1.mp4 trên NAS → app đọc trực tiếp, không chép."""
    goc = kho_video.nas_dir()
    (goc / "xuat").mkdir(parents=True, exist_ok=True)
    (goc / "xuat" / "tap1.mp4").write_bytes(b"v" * 100)
    (goc / "xuat" / "tap1.srt").write_text(SRT, encoding="utf-8")
    ma = client.post("/api-vr/nas-lien-ket", data={"duong": "xuat/tap1.mp4"},
                     headers=h()).json()["ma"]
    r = client.get(f"/api-vr/phu-de/{ma}", headers=h())
    assert r.status_code == 200 and "Xin chào" in r.text
    v = kho_video.lay_video(ma)
    assert kho_video.phu_de_tim(v)[1] == "nas"
    # app KHÔNG được xóa file trên NAS → nút gỡ ẩn, route trả 409 nói rõ
    trang = client.get(f"/xem/{ma}", headers=h()).text
    assert "subs read from the NAS folder" in trang
    assert 'id="nut-pd-xoa"' not in trang        # nút gỡ ẩn (chuỗi trong JS không tính)
    assert client.post(f"/api-vr/phu-de/{ma}/xoa", headers=h()).status_code == 409
    assert (goc / "xuat" / "tap1.srt").is_file()    # file gốc NAS không bị đụng


def test_phu_de_gan_tu_app_thang_ban_canh_nas(client):
    """Người đăng gắn bản mới từ app → phải thấy bản mới, không phải bản cũ trên NAS."""
    goc = kho_video.nas_dir()
    (goc / "xuat").mkdir(parents=True, exist_ok=True)
    (goc / "xuat" / "tap2.mp4").write_bytes(b"v" * 100)
    (goc / "xuat" / "tap2.srt").write_text(SRT, encoding="utf-8")
    ma = client.post("/api-vr/nas-lien-ket", data={"duong": "xuat/tap2.mp4"},
                     headers=h()).json()["ma"]
    moi = SRT.replace("Xin chào", "Bản mới gắn từ app")
    assert _gan(client, ma=ma, noi_dung=moi).status_code == 200
    r = client.get(f"/api-vr/phu-de/{ma}", headers=h())
    assert "Bản mới gắn từ app" in r.text and "Xin chào" not in r.text
