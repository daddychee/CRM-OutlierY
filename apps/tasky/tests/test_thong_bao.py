# -*- coding: utf-8 -*-
"""B7 — thông báo trong hệ: 4 sự kiện Owner chọn + mức độ bằng màu."""
from datetime import date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from src import main, thong_bao as tb, tuan
from src.main import app

client = TestClient(app)

SO = [{"ten": "huytq", "level": 3, "bo_phan": "Vận hành", "ho_ten": "Trần Quốc Huy"},
      {"ten": "hant", "level": 2, "bo_phan": "Vận hành", "ho_ten": "Nguyễn Thu Hà"}]
LEADER = {"ten": "huytq", "level": 3, "bo_phan": "Vận hành"}
NHANVIEN = {"ten": "hant", "level": 2, "bo_phan": "Vận hành"}
HA_H = {"X-Remote-User": "hant", "X-Remote-Level": "2", "X-Remote-Dept": "V%E1%BA%ADn%20h%C3%A0nh",
        "X-Remote-Actions": "vao", "X-Remote-Apps": "tasky"}
LEADER_H = {"X-Remote-User": "huytq", "X-Remote-Level": "3", "X-Remote-Dept": "V%E1%BA%ADn%20h%C3%A0nh",
            "X-Remote-Actions": "vao,giao_viec,xac_nhan_ket_qua,bao_cao_bo_phan",
            "X-Remote-Apps": "tasky"}


@pytest.fixture(autouse=True)
def _so_gia(monkeypatch):
    monkeypatch.setattr(main.nhan_su, "ds_nguoi", lambda: (list(SO), ""))


@pytest.fixture()
def ma():
    return tuan.ma_tuan()


def _lui_gio(ma, id_viec, gio):
    """Kéo lùi luc_tao của một việc để thử ngưỡng quá hạn."""
    so = tuan.doc_tuan(ma)
    for v in so["viec"]:
        if v["id"] == id_viec:
            v["luc_tao"] = (datetime.now() - timedelta(hours=gio)).isoformat(timespec="seconds")
    tuan._ghi_tuan(so)


# ---------- sự kiện 1: giao việc mới ----------

@pytest.fixture()
def giua_tuan(monkeypatch):
    """Ghim hôm nay = THỨ TƯ của tuần đang xem.

    Không có fixture này thì hai test dưới đỏ vào thứ Sáu → Chủ nhật, khi mục
    "Sắp hết tuần" bật thêm — đỏ vì LỊCH MÁY chứ không vì code sai (dính thật
    29/08/2026, thứ Bảy)."""
    that = tb.date

    class _Ngay(that):
        @classmethod
        def today(cls):
            tu, _ = tuan.khoang_tuan(tuan.ma_tuan())
            return that.fromisoformat(tu) + timedelta(days=2)

    monkeypatch.setattr(tb, "date", _Ngay)


def test_viec_moi_giao_la_muc_tin(ma, giua_tuan):
    tuan.them_viec_giao(ma, LEADER, NHANVIEN, "Dựng 6 video", "Dựng video")
    ds = tb.cua_toi(ma, NHANVIEN)
    assert [m["muc_do"] for m in ds] == [tb.TIN]
    assert "1 việc mới được giao" in ds[0]["chu"]


def test_giao_qua_mot_ngay_chua_nhan_thanh_muc_cap(ma):
    v = tuan.them_viec_giao(ma, LEADER, NHANVIEN, "Dựng 6 video", "Dựng video")
    _lui_gio(ma, v["id"], 30)
    ds = tb.cua_toi(ma, NHANVIEN)
    assert ds[0]["muc_do"] == tb.CAP and "quá 1 ngày" in ds[0]["chu"]


def test_nhan_viec_roi_thi_het_bao(ma, giua_tuan):
    v = tuan.them_viec_giao(ma, LEADER, NHANVIEN, "Dựng 6 video", "Dựng video")
    tuan.nhan_viec(ma, v["id"], NHANVIEN)
    assert tb.cua_toi(ma, NHANVIEN) == []


def test_nguong_qua_han_doi_duoc_bang_env(ma, monkeypatch):
    monkeypatch.setenv("TASKY_GIO_CHO_NHAN", "1")
    v = tuan.them_viec_giao(ma, LEADER, NHANVIEN, "Dựng 6 video", "Dựng video")
    _lui_gio(ma, v["id"], 2)
    assert tb.cua_toi(ma, NHANVIEN)[0]["muc_do"] == tb.CAP


# ---------- sự kiện 2: báo xong / từ chối ----------

def test_bao_xong_thi_leader_duoc_bao(ma):
    v = tuan.them_viec_giao(ma, LEADER, NHANVIEN, "Việc A", "Dựng video")
    tuan.nhan_viec(ma, v["id"], NHANVIEN)
    tuan.bao_xong(ma, v["id"], NHANVIEN)
    ds = tb.cua_leader(ma, LEADER, SO)
    assert ds[0]["muc_do"] == tb.LUU_Y and "chờ bạn xác nhận" in ds[0]["chu"]


def test_tu_choi_thi_leader_duoc_bao_de_giao_lai(ma):
    v = tuan.them_viec_giao(ma, LEADER, NHANVIEN, "Việc B", "Dựng video")
    tuan.tu_choi_viec(ma, v["id"], NHANVIEN, "Đang gánh 3 việc gấp")
    ds = tb.cua_leader(ma, LEADER, SO)
    assert any("bị từ chối" in m["chu"] and m["muc_do"] == tb.LUU_Y for m in ds)


def test_leader_khong_thay_viec_ngoai_pham_vi_minh(ma):
    """ds_nguoi do route lọc — lõi không tự đoán ai quản ai."""
    tuan.them_viec_giao(ma, LEADER, NHANVIEN, "Việc C", "Dựng video")
    tuan.nhan_viec(ma, tuan.viec_cua(ma, "hant")[0]["id"], NHANVIEN)
    tuan.bao_xong(ma, tuan.viec_cua(ma, "hant")[0]["id"], NHANVIEN)
    assert tb.cua_leader(ma, LEADER, []) == []


# ---------- sự kiện 3: nhắc cuối tuần ----------

def test_nhac_cuoi_tuan_chi_tu_thu_sau(ma, monkeypatch):
    tuan.them_viec_giao(ma, LEADER, NHANVIEN, "Việc D", "Dựng video")
    thu_hai = date.fromisoformat(tuan.khoang_tuan(ma)[0])
    monkeypatch.setattr(tb, "_cuoi_tuan", lambda m, h=None: False)
    assert not any("Sắp hết tuần" in m["chu"] for m in tb.cua_toi(ma, NHANVIEN))
    monkeypatch.setattr(tb, "_cuoi_tuan", lambda m, h=None: True)
    assert any("Sắp hết tuần" in m["chu"] for m in tb.cua_toi(ma, NHANVIEN))
    assert thu_hai.weekday() == 0        # mã tuần đúng là thứ Hai đầu tuần


def test_cuoi_tuan_tinh_theo_dung_tuan_dang_xem(ma):
    """Xem tuần cũ / tuần sau thì KHÔNG nhắc — nhắc nhầm còn tệ hơn không nhắc."""
    thu_sau = date.fromisoformat(tuan.khoang_tuan(ma)[0]) + timedelta(days=4)
    assert tb._cuoi_tuan(ma, thu_sau) is True
    assert tb._cuoi_tuan(tuan.tuan_lien_ke(ma, 1), thu_sau) is False


def test_cuoi_tuan_leader_duoc_nhac_dong_tuan(ma, monkeypatch):
    monkeypatch.setattr(tb, "_cuoi_tuan", lambda m, h=None: True)
    tuan.them_viec_giao(ma, LEADER, NHANVIEN, "Việc E", "Dựng video")
    assert any("chưa đóng tuần" in m["chu"] for m in tb.cua_leader(ma, LEADER, SO))


# ---------- sự kiện 4: việc kẹt ----------

def test_viec_ket_la_muc_cap_o_ca_hai_phia(ma):
    v = tuan.them_viec_giao(ma, LEADER, NHANVIEN, "Chạy thử QC", "Quy trình nội bộ")
    m1 = tuan.doi_sang_tuan_sau(ma, v["id"], LEADER, "lần 1")
    t2 = tuan.tuan_lien_ke(ma, 1)
    m2 = tuan.doi_sang_tuan_sau(t2, m1["id"], LEADER, "lần 2")
    t3 = tuan.tuan_lien_ke(ma, 2)
    assert m2["so_lan_doi"] == 2
    assert any(m["muc_do"] == tb.CAP and "kẹt" in m["chu"] for m in tb.cua_toi(t3, NHANVIEN))
    assert any(m["muc_do"] == tb.CAP and "kẹt" in m["chu"] for m in tb.cua_leader(t3, LEADER, SO))


# ---------- huy hiệu ----------

def test_huy_hieu_lay_muc_cao_nhat_va_cong_don_so(ma):
    tom = tb.tom_tat([{"muc_do": tb.TIN, "so": 2}, {"muc_do": tb.CAP, "so": 1},
                      {"muc_do": tb.LUU_Y, "so": 3}])
    assert tom == {"so": 6, "muc_do": tb.CAP}


def test_khong_co_gi_thi_khong_ve_huy_hieu_so_0():
    assert tb.tom_tat([]) == {"so": 0, "muc_do": ""}


# ---------- hiển thị ----------

def test_trang_hien_khoi_can_chu_y_va_huy_hieu(ma):
    v = tuan.them_viec_giao(ma, LEADER, NHANVIEN, "Dựng 6 video", "Dựng video")
    _lui_gio(ma, v["id"], 30)
    r = client.get("/tasky", headers=HA_H)
    assert 'class="bao"' in r.text and "quá 1 ngày" in r.text
    assert 'class="tk-badge cap"' in r.text


def test_khong_co_thong_bao_thi_khong_ve_khoi(ma):
    r = client.get("/tasky", headers=HA_H)
    # so trên CHỖ DÙNG, không so tên class trần (CSS luôn có .tk-badge)
    assert 'class="bao"' not in r.text and 'class="tk-badge' not in r.text


def test_leader_thay_ca_thong_bao_cua_minh_va_cua_quan(ma):
    v = tuan.them_viec_giao(ma, LEADER, NHANVIEN, "Việc F", "Dựng video")
    tuan.nhan_viec(ma, v["id"], NHANVIEN)
    tuan.bao_xong(ma, v["id"], NHANVIEN)
    r = client.get("/bao-cao-tuan?pham_vi=bo-phan", headers=LEADER_H)
    assert "Chờ bạn xử lý" in r.text and "Việc F" in r.text
