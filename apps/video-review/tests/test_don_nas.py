# -*- coding: utf-8 -*-
"""Test mở thư mục NAS + DỌN file sau review (ngoại lệ có kiểm soát của luật chỉ-đọc).

Sáu chốt chặn phải chứng minh được bằng test, vì đây là đường DUY NHẤT trong hệ
xóa thật file của công ty — sai một chốt là mất bản dựng không có thùng rác.
"""
import csv

import pytest
from fastapi.testclient import TestClient

from src import don_nas, kho_video
from src.main import app
from tests.test_routes import h


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def tap(client):
    """Thư mục tập LI037 trên NAS giả: 2 bản dựng + phụ đề + 1 file dự án."""
    goc = kho_video.nas_dir()
    d = goc / "Life In" / "US" / "LI037"
    d.mkdir(parents=True)
    (d / "LI037 fix lần 1.mp4").write_bytes(b"v" * 4096)
    (d / "LI037 fix lần 2.mp4").write_bytes(b"v" * 2048)
    (d / "LI037 fix lần 2.srt").write_text("1", encoding="utf-8")
    (d / "LI037.prproj").write_bytes(b"p" * 10)      # dự án Premiere — KHÔNG được xóa
    r = client.post("/api-vr/nas-lien-ket",
                    data={"duong": "Life In/US/LI037/LI037 fix lần 1.mp4"}, headers=h())
    assert r.status_code == 200
    return d


def test_liet_ke_thu_muc_kem_co_va_co_quyen(client, tap):
    du = client.get("/api-vr/nas-thu-muc/VR-0001", headers=h()).json()
    theo_ten = {m["ten"]: m for m in du["muc"]}
    assert set(theo_ten) == {"LI037 fix lần 1.mp4", "LI037 fix lần 2.mp4",
                             "LI037 fix lần 2.srt", "LI037.prproj"}
    assert theo_ten["LI037 fix lần 1.mp4"]["dang_dung"] is True     # đang có trong app
    assert theo_ten["LI037 fix lần 2.mp4"]["dang_dung"] is False
    assert theo_ten["LI037.prproj"]["xoa_duoc"] is False            # file dự án: không đụng
    assert theo_ten["LI037 fix lần 2.srt"]["xoa_duoc"] is True
    assert du["tong_byte"] == 4096 + 2048 + 1 + 10
    assert du["co_quyen_xoa"] is False                              # level 2 không có cờ xoa


def test_chua_approved_thi_chua_duoc_don(client, tap):
    """Tập chưa nghiệm thu → Manager cũng không xóa được file nào."""
    r = client.post("/api-vr/nas-xoa-file",
                    data={"duong": "Life In/US/LI037/LI037 fix lần 2.mp4",
                          "xac_nhan": "LI037 fix lần 2.mp4"}, headers=_mgr())
    assert r.status_code == 403 and "Approved" in r.json()["detail"]
    assert (tap / "LI037 fix lần 2.mp4").is_file()


def test_xoa_can_co_cua_manager(client, tap):
    _nghiem_thu()
    du = {"duong": "Life In/US/LI037/LI037 fix lần 2.mp4", "xac_nhan": "LI037 fix lần 2.mp4"}
    assert client.post("/api-vr/nas-xoa-file", data=du, headers=h()).status_code == 403
    assert client.post("/api-vr/nas-xoa-file", data=du,
                       headers=h(actions="duyet")).status_code == 403
    assert (tap / "LI037 fix lần 2.mp4").is_file()                  # chưa ai xóa được
    r = client.post("/api-vr/nas-xoa-file", data=du, headers=h(level=4, actions="duyet,xoa"))
    assert r.status_code == 200 and r.json()["byte"] == 2048
    assert not (tap / "LI037 fix lần 2.mp4").exists()


def _mgr():
    return h(ten="quanly", level=4, actions="duyet,xoa")


def _nghiem_thu(ma="VR-0001"):
    """Chốt 7: chỉ dọn được khi tập ĐÃ có bản Approved (user chốt 20/08)."""
    kho_video.doi_trang_thai(ma, "da_duyet")


def test_khong_xoa_duoc_file_ngoai_video_va_phu_de(client, tap):
    _nghiem_thu()
    r = client.post("/api-vr/nas-xoa-file",
                    data={"duong": "Life In/US/LI037/LI037.prproj",
                          "xac_nhan": "LI037.prproj"}, headers=_mgr())
    assert r.status_code == 403
    assert (tap / "LI037.prproj").is_file()


def test_ten_xac_nhan_lech_thi_tu_choi(client, tap):
    _nghiem_thu()
    """Danh sách tải từ trước, file đã đổi → tên echo không khớp → DỪNG."""
    r = client.post("/api-vr/nas-xoa-file",
                    data={"duong": "Life In/US/LI037/LI037 fix lần 2.mp4",
                          "xac_nhan": "LI037 fix lần 1.mp4"}, headers=_mgr())
    assert r.status_code == 422
    assert (tap / "LI037 fix lần 2.mp4").is_file()


def test_chan_duong_ngoai_goc_nas(client, tap, tmp_path):
    _nghiem_thu()
    ngoai = tmp_path / "ngoai.mp4"
    ngoai.write_bytes(b"v")
    for xau in ["../../../ngoai.mp4", str(ngoai)]:
        r = client.post("/api-vr/nas-xoa-file",
                        data={"duong": xau, "xac_nhan": "ngoai.mp4"}, headers=_mgr())
        assert r.status_code == 404, xau
    assert ngoai.is_file()


def test_xoa_file_dang_dung_thi_go_mem_ban_ghi_va_giu_binh_luan(client, tap):
    kho_video.them_binh_luan("VR-0001", "an", "cắt đoạn mở đầu", ts_giay=4)
    _nghiem_thu()
    r = client.post("/api-vr/nas-xoa-file",
                    data={"duong": "Life In/US/LI037/LI037 fix lần 1.mp4",
                          "xac_nhan": "LI037 fix lần 1.mp4"}, headers=_mgr())
    assert r.status_code == 200 and r.json()["ma_go"] == "VR-0001"
    assert kho_video.lay_video("VR-0001")["trang_thai"] == "da_xoa"   # rời danh sách
    assert kho_video.danh_sach_video() == []
    assert kho_video.ds_binh_luan("VR-0001")[0]["noi_dung"] == "cắt đoạn mở đầu"


def test_nhat_ky_ghi_truoc_khi_xoa_va_chi_them(client, tap):
    _nghiem_thu()
    for ten in ("LI037 fix lần 2.mp4", "LI037 fix lần 2.srt"):
        client.post("/api-vr/nas-xoa-file",
                    data={"duong": "Life In/US/LI037/" + ten, "xac_nhan": ten}, headers=_mgr())
    f = kho_video.kho_dir().parent / "db" / "nhat_ky_xoa_nas.csv"
    dong = list(csv.DictReader(f.read_text(encoding="utf-8-sig").splitlines()))
    assert [d["duong_nas"].rsplit("/", 1)[-1] for d in dong] == ["LI037 fix lần 2.mp4",
                                                                "LI037 fix lần 2.srt"]
    assert dong[0]["nguoi"] == "quanly" and dong[0]["byte"] == "2048"


def test_nhat_ky_van_con_dau_vet_khi_xoa_hong(client, tap, monkeypatch):
    _nghiem_thu()
    """Ghi nhật ký TRƯỚC rồi mới unlink: xóa hỏng giữa chừng vẫn còn dấu vết."""
    def hong(self):
        raise OSError("file đang mở giả lập")
    monkeypatch.setattr("pathlib.Path.unlink", hong)
    r = client.post("/api-vr/nas-xoa-file",
                    data={"duong": "Life In/US/LI037/LI037 fix lần 2.mp4",
                          "xac_nhan": "LI037 fix lần 2.mp4"}, headers=_mgr())
    assert r.status_code == 404
    f = kho_video.kho_dir().parent / "db" / "nhat_ky_xoa_nas.csv"
    assert "LI037 fix lần 2.mp4" in f.read_text(encoding="utf-8-sig")


def test_duong_unc_chi_hien_khi_khai(client, tap, monkeypatch):
    B = chr(92)
    unc = B * 2 + "192.168.1.250" + B + "Video"
    monkeypatch.setenv("VR_NAS_UNC", "")
    assert don_nas.duong_unc("Life In/US/LI037") == ""
    monkeypatch.setenv("VR_NAS_UNC", unc)
    assert don_nas.duong_unc("Life In/US/LI037") == unc + B + "Life In" + B + "US" + B + "LI037"
    trang = client.get("/xem/VR-0001", headers=h()).text
    assert "192.168.1.250" in trang and "Copy path" in trang


def test_gom_theo_tap_tren_danh_sach(client, tap):
    """Hai bản của cùng một tập phải nằm chung MỘT nhóm, không đẻ 2 dòng rời."""
    client.post("/api-vr/nas-lien-ket",
                data={"duong": "Life In/US/LI037/LI037 fix lần 2.mp4"}, headers=h())
    goc = kho_video.nas_dir()
    (goc / "Life In" / "US" / "LI049").mkdir(parents=True)
    (goc / "Life In" / "US" / "LI049" / "LI049_Round 3.mp4").write_bytes(b"v")
    client.post("/api-vr/nas-lien-ket",
                data={"duong": "Life In/US/LI049/LI049_Round 3.mp4"}, headers=h())
    trang = client.get("/danh-sach", headers=h()).text
    assert trang.count('data-tap="LI037"') == 1 and trang.count('data-tap="LI049"') == 1
    assert "2 cuts" in trang and "1 cut<" in trang
