# -*- coding: utf-8 -*-
"""Test quy trình tập của team (user chốt 20/08/2026):

  <tập>/Feedback/  ←  nhân sự up bản duyệt (LI001, bản sửa LI001.1, LI001.2…)
  Awaiting review → In review → Approved
  Tập có bản Approved = xong → LÚC ĐÓ mới được dọn cả khối Feedback.
"""
import csv

import pytest
from fastapi.testclient import TestClient

from src import kho_video
from src.main import app
from tests.test_routes import h


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def khoi(client):
    """LI001/Feedback/ có bản gốc + bản sửa 1 (đúng quy ước đặt tên của team)."""
    d = kho_video.nas_dir() / "Life In" / "US" / "LI001" / "Feedback"
    d.mkdir(parents=True)
    (d / "LI001.mp4").write_bytes(b"v" * 900)
    (d / "LI001.1.mp4").write_bytes(b"v" * 700)
    (kho_video.nas_dir() / "Life In" / "US" / "LI001" / "LI001_master.mp4").write_bytes(b"m")
    for t in ("LI001.mp4", "LI001.1.mp4"):
        r = client.post("/api-vr/nas-lien-ket",
                        data={"duong": "Life In/US/LI001/Feedback/" + t}, headers=h())
        assert r.status_code == 200
    return d


def _mgr():
    return h(ten="quanly", level=4, actions="duyet,xoa")


def test_ban_goc_va_ban_sua_ve_cung_mot_tap(client, khoi):
    trang = client.get("/danh-sach", headers=h()).text
    assert trang.count('data-tap="LI001"') == 1 and "2 cuts" in trang
    v = kho_video.lay_video("VR-0002")
    assert kho_video.ma_tap(v) == "LI001"
    assert kho_video.thu_muc_feedback(v) == "Life In/US/LI001/Feedback"


def test_chi_con_ba_buoc_duyet(client, khoi):
    """'Changes requested' đã nghỉ hưu — gửi lên bị từ chối tại cửa."""
    assert client.post("/api-vr/trang-thai", data={"ma": "VR-0001", "trang_thai": "can_sua"},
                       headers=h(actions="duyet")).status_code == 422
    trang = client.get("/xem/VR-0001", headers=h(actions="duyet")).text
    assert "Request changes" not in trang and "Approve" in trang
    assert client.post("/api-vr/trang-thai", data={"ma": "VR-0001", "trang_thai": "da_duyet"},
                       headers=h(actions="duyet")).status_code == 200
    assert "Reopen review" in client.get("/xem/VR-0001", headers=h(actions="duyet")).text


def test_chua_approved_thi_khong_hien_nut_don(client, khoi):
    trang = client.get("/danh-sach", headers=_mgr()).text
    assert "Clean up feedback folder" not in trang
    kho_video.doi_trang_thai("VR-0002", "da_duyet")
    trang2 = client.get("/danh-sach", headers=_mgr()).text
    assert "Clean up feedback folder" in trang2 and "episode signed off" in trang2
    # nhân viên thường không bao giờ thấy nút dọn
    assert "Clean up feedback folder" not in client.get("/danh-sach", headers=h()).text


def test_don_ca_khoi_feedback_khi_tap_da_xong(client, khoi):
    kho_video.them_binh_luan("VR-0001", "an", "sửa cảnh mở", ts_giay=3)
    kho_video.doi_trang_thai("VR-0002", "da_duyet")
    r = client.post("/api-vr/nas-xoa-feedback",
                    data={"duong": "Life In/US/LI001/Feedback", "ma_tap": "LI001"},
                    headers=_mgr())
    assert r.status_code == 200
    du = r.json()
    assert du["so_file"] == 2 and du["byte"] == 1600 and set(du["ma_go"]) == {"VR-0001", "VR-0002"}
    assert not khoi.exists()                                   # cả khối biến mất
    assert (khoi.parent / "LI001_master.mp4").is_file()        # bản master KHÔNG bị đụng
    assert kho_video.danh_sach_video() == []                   # danh sách sạch
    assert kho_video.ds_binh_luan("VR-0001")[0]["noi_dung"] == "sửa cảnh mở"
    f = kho_video.kho_dir().parent / "db" / "nhat_ky_xoa_nas.csv"
    dong = list(csv.DictReader(f.read_text(encoding="utf-8-sig").splitlines()))
    assert len(dong) == 2 and all(d["nguoi"] == "quanly" for d in dong)


def test_chua_approved_thi_khong_don_duoc_khoi(client, khoi):
    r = client.post("/api-vr/nas-xoa-feedback",
                    data={"duong": "Life In/US/LI001/Feedback", "ma_tap": "LI001"},
                    headers=_mgr())
    assert r.status_code == 403 and "Approved" in r.json()["detail"]
    assert (khoi / "LI001.mp4").is_file()


def test_khong_bao_gio_xoa_duoc_thu_muc_tap(client, khoi):
    """Chốt sống còn: chỉ thư mục TÊN 'Feedback' mới xóa được — thư mục tập chứa
    bản master của team thì có approved cũng không đụng tới."""
    kho_video.doi_trang_thai("VR-0002", "da_duyet")
    for duong in ["Life In/US/LI001", "Life In/US", "Life In"]:
        r = client.post("/api-vr/nas-xoa-feedback",
                        data={"duong": duong, "ma_tap": "LI001"}, headers=_mgr())
        assert r.status_code == 403, duong
    assert (khoi.parent / "LI001_master.mp4").is_file()


def test_ma_tap_xac_nhan_lech_thi_dung(client, khoi):
    kho_video.doi_trang_thai("VR-0002", "da_duyet")
    r = client.post("/api-vr/nas-xoa-feedback",
                    data={"duong": "Life In/US/LI001/Feedback", "ma_tap": "LI002"},
                    headers=_mgr())
    assert r.status_code == 422
    assert (khoi / "LI001.mp4").is_file()


def test_ban_ghi_doi_cu_khong_co_nut_don_ca_khoi(client):
    """Bản ghi trỏ THẲNG thư mục tập (trước 20/08) không có khối Feedback nào →
    tuyệt đối không hiện đường dọn cả thư mục."""
    d = kho_video.nas_dir() / "Life In" / "US" / "LI037"
    d.mkdir(parents=True)
    (d / "LI037 fix lần 1.mp4").write_bytes(b"v")
    client.post("/api-vr/nas-lien-ket",
                data={"duong": "Life In/US/LI037/LI037 fix lần 1.mp4"}, headers=h())
    kho_video.doi_trang_thai("VR-0001", "da_duyet")
    assert "Clean up feedback folder" not in client.get("/danh-sach", headers=_mgr()).text
