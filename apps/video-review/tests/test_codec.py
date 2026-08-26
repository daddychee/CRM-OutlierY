# -*- coding: utf-8 -*-
"""Test lưới codec — sự cố 20/08 'chỉ có tiếng, không có hình' (file H.265).

Trình duyệt không giải mã HEVC thì phát TIẾNG, hình đen, và KHÔNG bắn sự kiện
lỗi nào — hỏng lặng lẽ. App phải tự dò codec mà báo, ở cả 3 chỗ: lúc thêm,
trong danh sách, trên trang xem.
"""
import pytest
from fastapi.testclient import TestClient

from src import kho_video
from src.main import app
from tests.test_routes import _them, h, tao_file_nas


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def test_canh_bao_chi_cho_codec_khong_phat_duoc():
    assert kho_video.canh_bao_codec("h264") == ""
    assert kho_video.canh_bao_codec("av1") == ""       # Chrome giải mã được AV1
    assert kho_video.canh_bao_codec("") == ""          # chưa dò được → KHÔNG báo bừa
    assert kho_video.canh_bao_codec("hevc") == "H.265 (HEVC)"
    assert kho_video.canh_bao_codec("prores") == "ProRes"
    assert kho_video.canh_bao_codec("codec_la") == "CODEC_LA"


def test_thieu_ffprobe_thi_im_lang_chu_khong_bao_bua(monkeypatch, tmp_path):
    monkeypatch.setenv("VR_FFPROBE", "")
    monkeypatch.setattr(kho_video.shutil, "which", lambda *a, **k: None)
    f = tmp_path / "a.mp4"
    f.write_bytes(b"v")
    assert kho_video.doc_codec(f) == ""


def test_them_file_hevc_bao_ngay_va_hien_khap_noi(client, monkeypatch):
    monkeypatch.setattr(kho_video, "doc_codec", lambda p: "hevc")
    rel = tao_file_nas()
    r = client.post("/api-vr/nas-lien-ket", data={"duong": rel}, headers=h())
    assert r.status_code == 200 and r.json()["canh_codec"] == "H.265 (HEVC)"
    assert kho_video.lay_video("VR-0001")["codec"] == "hevc"
    assert "won't play" in client.get("/danh-sach", headers=h()).text
    assert "cannot show the picture" in client.get("/xem/VR-0001", headers=h()).text


def test_file_h264_khong_bi_bao_oan(client, monkeypatch):
    monkeypatch.setattr(kho_video, "doc_codec", lambda p: "h264")
    _them(client)
    assert "won't play" not in client.get("/danh-sach", headers=h()).text
    assert "cannot show the picture" not in client.get("/xem/VR-0001", headers=h()).text


def test_ban_ghi_doi_cu_do_luoi_mot_lan_roi_nho(client, monkeypatch):
    """Bản ghi thêm trước 20/08 chưa có codec: dò lần đầu lúc mở danh sách rồi ghi
    vào sổ — lần sau không gọi ffprobe nữa (đừng dò 8 file mỗi lần vào trang)."""
    monkeypatch.setattr(kho_video, "doc_codec", lambda p: "")
    _them(client)
    assert kho_video.lay_video("VR-0001")["codec"] == ""
    dem = {"n": 0}

    def do(p):
        dem["n"] += 1
        return "hevc"

    monkeypatch.setattr(kho_video, "doc_codec", do)
    assert "won't play" in client.get("/danh-sach", headers=h()).text
    assert dem["n"] == 1 and kho_video.lay_video("VR-0001")["codec"] == "hevc"
    client.get("/danh-sach", headers=h())
    assert dem["n"] == 1                      # đã nhớ, không dò lại


def test_mat_file_thi_khong_do_codec(client, monkeypatch):
    """File không còn trên NAS → cảnh báo 'file missing', đừng gọi ffprobe vô ích."""
    _them(client)
    v = kho_video.lay_video("VR-0001")
    kho_video.duong_video(v).unlink()
    monkeypatch.setattr(kho_video, "doc_codec", lambda p: pytest.fail("không được dò"))
    assert "file missing" in client.get("/danh-sach", headers=h()).text


def test_file_dang_duoc_ghi_thi_chan_tai_cua(client, monkeypatch):
    """Sự cố 26/08: liên kết lúc Windows còn chép → file trên NAS đứt giữa chừng,
    reviewer xem tới phút thứ 2 mới chết. Chặn ngay lúc thêm."""
    monkeypatch.setattr(kho_video, "dang_bi_ghi", lambda p: True)
    rel = tao_file_nas()
    r = client.post("/api-vr/nas-lien-ket", data={"duong": rel}, headers=h())
    assert r.status_code == 409 and "chép chưa xong" in r.json()["detail"]
    assert kho_video.danh_sach_video() == []          # không ghi sổ bản dựng dở


def test_quet_hong_luc_them_va_hien_canh_bao(client, monkeypatch):
    monkeypatch.setattr(kho_video, "quet_hong", lambda p, **k: "01:50")
    rel = tao_file_nas()
    r = client.post("/api-vr/nas-lien-ket", data={"duong": rel}, headers=h())
    assert r.status_code == 200 and r.json()["hong"] == "01:50"
    assert kho_video.lay_video("VR-0001")["hong"] == "01:50"
    assert "file damaged" in client.get("/danh-sach", headers=h()).text
    assert "is damaged on the NAS" in client.get("/xem/VR-0001", headers=h()).text


def test_quet_lai_theo_yeu_cau_xoa_canh_bao_khi_sach(client, monkeypatch):
    """Chép lại file lành rồi quét lại → cảnh báo phải tự rút, không bắt xóa bản ghi."""
    monkeypatch.setattr(kho_video, "quet_hong", lambda p, **k: "02:00")
    rel = tao_file_nas()
    client.post("/api-vr/nas-lien-ket", data={"duong": rel}, headers=h())
    monkeypatch.setattr(kho_video, "quet_hong", lambda p, **k: "")
    r = client.post("/api-vr/quet-hong/VR-0001", headers=h(ten="ai-cung-duoc"))
    assert r.status_code == 200 and r.json()["hong"] == ""
    assert kho_video.lay_video("VR-0001")["hong"] == ""
    assert "file damaged" not in client.get("/danh-sach", headers=h()).text


def test_thieu_ffmpeg_thi_khong_ket_luan_bua(monkeypatch, tmp_path):
    monkeypatch.setenv("VR_FFMPEG", "")
    monkeypatch.setattr(kho_video.shutil, "which", lambda *a, **k: None)
    monkeypatch.setattr(kho_video, "ffprobe", lambda: None)
    f = tmp_path / "a.mp4"
    f.write_bytes(b"v")
    assert kho_video.quet_hong(f) == ""
