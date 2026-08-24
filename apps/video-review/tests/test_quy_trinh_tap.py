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


def test_xoa_cung_tap_quet_sach_so_va_giu_file_neu_khong_tich(client, khoi):
    """Nút 'Delete permanently' ở nhóm Approved: bản ghi + bình luận biến mất khỏi
    sổ (khác gỡ mềm). KHÔNG tích ô file thì file trên NAS vẫn còn."""
    kho_video.them_binh_luan("VR-0001", "an", "note 1", ts_giay=2)
    kho_video.them_binh_luan("VR-0001", "binh", "note 2")
    kho_video.doi_trang_thai("VR-0002", "da_duyet")
    r = client.post("/api-vr/xoa-cung-tap",
                    data={"ma_tap": "LI001", "xac_nhan": "LI001"}, headers=_mgr())
    assert r.status_code == 200
    du = r.json()
    assert du["so_ban_ghi"] == 2 and du["so_binh_luan"] == 2 and du["nas"] is None
    assert kho_video.lay_video("VR-0001") is None       # xóa CỨNG, không phải gỡ mềm
    assert kho_video.ds_binh_luan("VR-0001") == []
    assert (khoi / "LI001.mp4").is_file()               # không tích ô → file còn nguyên
    f = kho_video.kho_dir().parent / "db" / "nhat_ky_xoa_ban_ghi.csv"
    dong = list(csv.DictReader(f.read_text(encoding="utf-8-sig").splitlines()))
    assert [d["ma_video"] for d in dong] == ["VR-0001", "VR-0002"]
    assert dong[0]["so_binh_luan"] == "2" and dong[0]["ma_tap"] == "LI001"


def test_xoa_cung_kem_file_thi_don_ca_khoi(client, khoi):
    kho_video.doi_trang_thai("VR-0002", "da_duyet")
    r = client.post("/api-vr/xoa-cung-tap",
                    data={"ma_tap": "LI001", "xac_nhan": "LI001", "xoa_file": "1"},
                    headers=_mgr())
    assert r.status_code == 200 and r.json()["nas"]["so_file"] == 2
    assert not khoi.exists()
    assert (khoi.parent / "LI001_master.mp4").is_file()   # master vẫn không bị đụng
    assert kho_video.cac_video_cua_tap("LI001") == []


def test_xoa_cung_can_approved_va_dung_ma_va_quyen(client, khoi):
    du = {"ma_tap": "LI001", "xac_nhan": "LI001"}
    assert client.post("/api-vr/xoa-cung-tap", data=du, headers=_mgr()).status_code == 403
    kho_video.doi_trang_thai("VR-0002", "da_duyet")
    assert client.post("/api-vr/xoa-cung-tap", data=du, headers=h()).status_code == 403
    assert client.post("/api-vr/xoa-cung-tap",
                       data={"ma_tap": "LI001", "xac_nhan": "LI002"},
                       headers=_mgr()).status_code == 422
    assert len(kho_video.cac_video_cua_tap("LI001")) == 2   # chưa mất bản ghi nào


def test_xoa_cung_quet_ca_ban_ghi_da_go_mem(client, khoi):
    """Bản đã gỡ mềm trước đó vẫn phải bị quét — không để lại bản ghi ẩn cùng tập."""
    kho_video.doi_trang_thai("VR-0001", "da_xoa")
    kho_video.doi_trang_thai("VR-0002", "da_duyet")
    r = client.post("/api-vr/xoa-cung-tap",
                    data={"ma_tap": "LI001", "xac_nhan": "LI001"}, headers=_mgr())
    assert r.status_code == 200 and r.json()["so_ban_ghi"] == 2
    assert kho_video.cac_video_cua_tap("LI001") == []


def test_nut_xoa_cung_chi_hien_o_tap_da_duyet(client, khoi):
    # soi CLASS của nút, không soi chữ — chữ còn nằm trong khối <script> luôn có mặt
    NUT = 'class="nut nho nguy xoa-cung-nut"'      # markup nút, không phải chuỗi trong <script>
    assert NUT not in client.get("/danh-sach", headers=_mgr()).text
    kho_video.doi_trang_thai("VR-0002", "da_duyet")
    assert NUT in client.get("/danh-sach", headers=_mgr()).text
    assert NUT not in client.get("/danh-sach", headers=h()).text


def test_ghi_chu_cua_chinh_nguoi_up_khong_tinh_la_da_review(client, khoi):
    """Sự cố 24/08: nhân sự up xong nhắn kèm một câu → mục nhảy sang In review sau
    20 giây, leader mất hẳn cờ Awaiting. 'Đã review' phải là bình luận của NGƯỜI KHÁC."""
    trang = client.get("/danh-sach", headers=h()).text
    assert trang.count('<tr data-tt="cho_review"') == 2          # 2 bản, chưa ai xem
    # hieuvn (người up VR-0001 trong fixture là 'an') tự ghi chú cho leader
    kho_video.them_binh_luan("VR-0001", "an", "anh xem giúp em đoạn cuối nhé")
    kho_video.them_binh_luan("VR-0001", "an", "em hết CapCut Pro")
    trang2 = client.get("/danh-sach", headers=h()).text
    assert trang2.count('<tr data-tt="cho_review"') == 2         # VẪN đang chờ review
    assert "Awaiting review" in trang2
    # leader vào xem và góp ý → lúc này mới là In review
    kho_video.them_binh_luan("VR-0001", "leader", "nhạc to quá", ts_giay=12)
    trang3 = client.get("/danh-sach", headers=h()).text
    assert trang3.count('<tr data-tt="cho_review"') == 1
    assert trang3.count('<tr data-tt="dang_review"') == 1


def test_ban_sua_moi_lam_song_lai_co_awaiting_cua_tap(client, khoi):
    """Tập đã có round 1 được review xong; up round 2 thì cả NHÓM phải kêu Awaiting
    trở lại — nếu không leader không biết có bản mới cần xem."""
    kho_video.them_binh_luan("VR-0001", "leader", "sửa đoạn mở", ts_giay=3)   # round 1 đã xem
    d = kho_video.nas_dir() / "Life In" / "US" / "LI001" / "Feedback"
    (d / "LI001.2.mp4").write_bytes(b"v" * 100)
    client.post("/api-vr/nas-lien-ket",
                data={"duong": "Life In/US/LI001/Feedback/LI001.2.mp4"}, headers=h())
    trang = client.get("/danh-sach", headers=h()).text
    nhom = trang[trang.index('data-tap="LI001"'):]
    nhom = nhom[:nhom.index("</summary>")]
    assert "Awaiting review" in nhom          # nhóm kêu Awaiting vì có bản chưa ai xem
    # leader xem NỐT bản mới (VR-0003 = LI001.2) → cả tập mới hết kêu
    kho_video.them_binh_luan("VR-0002", "leader", "ok bản 1", ts_giay=1)
    kho_video.them_binh_luan("VR-0003", "leader", "ok bản 2", ts_giay=1)
    nhom2 = client.get("/danh-sach", headers=h()).text
    nhom2 = nhom2[nhom2.index('data-tap="LI001"'):]
    assert "Awaiting review" not in nhom2[:nhom2.index("</summary>")]


def test_chi_dung_ten_Feedback_moi_la_khoi_don_duoc(client):
    """User chốt 24/08: giữ MỘT quy ước 'Feedback'. Viết tắt 'FB' (LI086 từng dùng)
    vẫn gom đúng tập nhưng KHÔNG được coi là khối feedback → không có nút dọn cả
    thư mục, phải đổi tên trên NAS cho đúng."""
    goc = kho_video.nas_dir()
    (goc / "Life In" / "US" / "LI086" / "FB").mkdir(parents=True)
    (goc / "Life In" / "US" / "LI086" / "FB" / "LI086_1.mp4").write_bytes(b"v")
    client.post("/api-vr/nas-lien-ket",
                data={"duong": "Life In/US/LI086/FB/LI086_1.mp4"}, headers=h())
    v = kho_video.lay_video("VR-0001")
    assert kho_video.ma_tap(v) == "LI086"          # vẫn gom đúng tập
    assert kho_video.thu_muc_feedback(v) == ""     # nhưng không phải khối feedback
    kho_video.doi_trang_thai("VR-0001", "da_duyet")
    trang = client.get("/danh-sach", headers=_mgr()).text
    assert 'class="nut nho nguy don-nut"' not in trang
    # và server chặn thẳng nếu ai đó gọi API trỏ vào thư mục FB
    r = client.post("/api-vr/nas-xoa-feedback",
                    data={"duong": "Life In/US/LI086/FB", "ma_tap": "LI086"}, headers=_mgr())
    assert r.status_code == 403
