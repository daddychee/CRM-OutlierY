# -*- coding: utf-8 -*-
"""Test route Video Review — claims + RBAC cờ hành động + liên kết NAS + Range từng khúc."""
import itertools
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


_DEM = itertools.count(1)


def tao_file_nas(noi_dung=b"x" * 64, duoi=".mp4", thu_muc="xuat") -> str:
    """Đặt một file vào NAS giả, trả ĐƯỜNG TƯƠNG ĐỐI để liên kết."""
    goc = kho_video.nas_dir()
    d = goc / thu_muc if thu_muc else goc
    d.mkdir(parents=True, exist_ok=True)
    f = d / f"ban-dung-{next(_DEM)}{duoi}"
    f.write_bytes(noi_dung)
    return f.relative_to(goc.resolve()).as_posix()


def _them(client, ten="ban dung 1", noi_dung=b"x" * 64, duoi=".mp4", **hd):
    """Thêm video = liên kết file có sẵn trên NAS (không upload byte nào)."""
    rel = tao_file_nas(noi_dung, duoi)
    return client.post("/api-vr/nas-lien-ket", data={"duong": rel, "ten": ten},
                       headers=h(**hd))


def test_health_khong_can_claims(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["app"] == "video-review"


def test_khong_claims_bi_401(client):
    for duong in ["/danh-sach", "/xem/VR-0001", "/media/VR-0001", "/api-vr/binh-luan/VR-0001"]:
        assert client.get(duong).status_code == 401, duong


def test_lien_ket_khong_chep_file_vao_app(client):
    """Bất biến 20/08: sổ chỉ TRỎ tới file NAS — kho app không sinh bản sao nào."""
    r = _them(client, ten="Tập 1")
    assert r.status_code == 200 and r.json()["ma"] == "VR-0001"
    v = kho_video.lay_video("VR-0001")
    assert v["nguon"] == "nas" and v["kich_thuoc"] == 64
    assert kho_video.duong_video(v).is_file()
    assert not list(kho_video.kho_dir().rglob("*.mp4"))   # KHÔNG chép vào app
    trang = client.get("/danh-sach", headers=h())
    assert trang.status_code == 200 and "Tập 1" in trang.text


def test_lien_ket_chan_duoi_la_file_ma_va_them_trung(client):
    rel = tao_file_nas(b"x", ".exe")
    assert client.post("/api-vr/nas-lien-ket", data={"duong": rel},
                       headers=h()).status_code == 422
    assert client.post("/api-vr/nas-lien-ket", data={"duong": "xuat/khong-co.mp4"},
                       headers=h()).status_code == 404
    rel2 = tao_file_nas()
    assert client.post("/api-vr/nas-lien-ket", data={"duong": rel2},
                       headers=h()).status_code == 200
    r = client.post("/api-vr/nas-lien-ket", data={"duong": rel2}, headers=h())
    assert r.status_code == 409 and "VR-0001" in r.json()["detail"]
    assert len(kho_video.danh_sach_video()) == 1


def test_danh_sach_trang_thai_hien_thi_cho_review(client):
    """Video mới thêm CHƯA ai bình luận = Awaiting review; có bình luận = In review;
    Approved giữ nhãn thật (logic hiển thị user chốt 18/08)."""
    _them(client, ten="chưa ai xem")
    _them(client, ten="đã có góp ý")
    _them(client, ten="đã duyệt")
    kho_video.them_binh_luan("VR-0002", "binh", "note")
    kho_video.doi_trang_thai("VR-0003", "da_duyet")
    trang = client.get("/danh-sach", headers=h()).text
    assert 'data-tt="cho_review"' in trang and "Awaiting review" in trang
    assert 'data-tt="dang_review"' in trang
    assert 'data-tt="da_duyet"' in trang
    bl = kho_video.ds_binh_luan("VR-0002")[0]
    kho_video.giai_binh_luan(bl["id"], "binh", False)
    assert 'data-tt="dang_review"' in client.get("/danh-sach", headers=h()).text


def test_trang_xem_nhung_binh_luan(client):
    _them(client)
    kho_video.them_binh_luan("VR-0001", "an", "note <script>alert(1)</script>", ts_giay=3)
    r = client.get("/xem/VR-0001", headers=h())
    assert r.status_code == 200
    assert "<script>alert(1)" not in r.text          # |tojson phải escape — script-safe
    assert client.get("/xem/VR-9999", headers=h()).status_code == 404


def test_media_range_tung_khuc(client, monkeypatch):
    monkeypatch.setenv("VR_KHUC_MB", "1")
    _them(client, noi_dung=b"a" * (2 * 1024 * 1024))  # 2MB trên NAS, khúc 1MB
    r = client.get("/media/VR-0001", headers={**h(), "Range": "bytes=0-"})
    assert r.status_code == 206
    assert r.headers["content-range"] == f"bytes 0-{1024*1024-1}/{2*1024*1024}"
    assert len(r.content) == 1024 * 1024
    r2 = client.get("/media/VR-0001", headers={**h(), "Range": f"bytes={2*1024*1024-3}-"})
    assert r2.status_code == 206 and len(r2.content) == 3
    assert client.get("/media/VR-0001",
                      headers={**h(), "Range": "bytes=9999999-"}).status_code == 416
    r3 = client.get("/media/VR-0001", headers=h())
    assert r3.status_code == 200 and len(r3.content) == 2 * 1024 * 1024


def test_file_nas_bien_mat_thi_bao_ro_khong_no(client):
    """Bản dựng bị xóa/đổi tên trên NAS: danh sách + trang xem vẫn mở, có cảnh báo;
    chỉ /media mới 404. Bình luận không mất theo."""
    _them(client, ten="mat file")
    v = kho_video.lay_video("VR-0001")
    kho_video.them_binh_luan("VR-0001", "an", "giữ lại note", ts_giay=1)
    kho_video.duong_video(v).unlink()
    assert "file missing" in client.get("/danh-sach", headers=h()).text
    xem = client.get("/xem/VR-0001", headers=h())
    assert xem.status_code == 200 and "Source file not found" in xem.text
    assert client.get("/media/VR-0001", headers=h()).status_code == 404
    assert kho_video.ds_binh_luan("VR-0001")[0]["noi_dung"] == "giữ lại note"


def test_file_nas_bi_ghi_de_thi_canh_bao_lech_moc(client):
    """Editor xuất bản mới ĐÈ cùng tên → mốc giây bình luận cũ lệch: phải cảnh báo."""
    _them(client)
    v = kho_video.lay_video("VR-0001")
    kho_video.duong_video(v).write_bytes(b"y" * 999)     # bản khác, cùng tên
    assert "file changed" in client.get("/danh-sach", headers=h()).text
    assert "File changed on the NAS" in client.get("/xem/VR-0001", headers=h()).text


def test_api_binh_luan_vong_doi(client):
    _them(client)
    r = client.post("/api-vr/binh-luan", headers=h(),
                    json={"video_ma": "VR-0001", "noi_dung": "cắt 0:03", "ts_giay": 3.2,
                          "ve": {"w": 1, "h": 1, "net": [{"mau": "#ff5f56", "diem": [[0, 0], [1, 1]]}]}})
    assert r.status_code == 200
    bl_id = r.json()["id"]
    assert client.get("/api-vr/binh-luan/VR-0001", headers=h()).json()[0]["ts_giay"] == 3.2
    assert client.post(f"/api-vr/binh-luan/{bl_id}/giai", headers=h(ten="binh")).status_code == 403
    assert client.post(f"/api-vr/binh-luan/{bl_id}/giai", headers=h()).status_code == 200
    assert client.post(f"/api-vr/binh-luan/{bl_id}/mo-lai",
                       headers=h(ten="chi", actions="duyet")).status_code == 200
    assert client.post(f"/api-vr/binh-luan/{bl_id}/xoa",
                       headers=h(ten="chi", actions="duyet")).status_code == 200
    assert client.post("/api-vr/binh-luan", headers=h(),
                       json={"video_ma": "VR-0001", "noi_dung": "  "}).status_code == 422


def test_trang_thai_can_co_duyet(client):
    _them(client)
    du = {"ma": "VR-0001", "trang_thai": "da_duyet"}
    assert client.post("/api-vr/trang-thai", data=du, headers=h()).status_code == 403
    assert client.post("/api-vr/trang-thai", data=du,
                       headers=h(actions="duyet")).status_code == 200
    assert kho_video.lay_video("VR-0001")["trang_thai"] == "da_duyet"
    assert client.post("/api-vr/trang-thai", data={"ma": "VR-0001", "trang_thai": "da_xoa"},
                       headers=h(actions="duyet")).status_code == 422  # gỡ đi đường xoa riêng


def test_xoa_video_can_co_xoa_va_khong_dung_file_nas(client):
    _them(client)
    v = kho_video.lay_video("VR-0001")
    assert client.post("/api-vr/xoa-video", data={"ma": "VR-0001"},
                       headers=h(actions="duyet")).status_code == 403
    assert client.post("/api-vr/xoa-video", data={"ma": "VR-0001"},
                       headers=h(level=4, actions="duyet,xoa")).status_code == 200
    # gỡ mềm: trang + media 404 nhưng FILE TRÊN NAS còn nguyên (app chỉ đọc)
    assert client.get("/xem/VR-0001", headers=h()).status_code == 404
    assert client.get("/media/VR-0001", headers=h()).status_code == 404
    assert kho_video.duong_video(v).is_file()
