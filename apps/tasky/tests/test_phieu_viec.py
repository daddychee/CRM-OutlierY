# -*- coding: utf-8 -*-
"""§16 — phiếu việc: Goal hiện đủ chữ, thêm việc là NÚT chứ không box cứng.

Owner 25/08: "Ô Goal vẫn chưa hiển thị rõ hết text — Goal phải rất rõ ràng";
"Nút thêm việc phải ở trên cùng… box thêm việc không nên là box cứng mà chỉ là
nút bấm, khi nhấn thì box mềm hiện ra".
"""
import pytest
from fastapi.testclient import TestClient

from src import main, muc_tieu as mt, tuan

MGR = {"ten": "huytq", "level": 4, "bo_phan": "Vận hành", "ho_ten": "Quốc Huy"}
NV = {"ten": "hant", "level": 2, "bo_phan": "Vận hành", "ho_ten": "Thu Hà"}
H_MGR = {"X-Remote-User": "huytq", "X-Remote-Level": "4",
         "X-Remote-Dept": "V%E1%BA%ADn%20h%C3%A0nh",
         "X-Remote-Actions": "vao,giao_viec,xac_nhan_ket_qua,bao_cao_bo_phan",
         "X-Remote-Apps": "tasky"}
_c = TestClient(main.app)

TEN_DAI = "Định hướng kinh doanh tháng 9/2026 cho toàn khối vận hành và nội dung"


@pytest.fixture()
def _so(monkeypatch):
    monkeypatch.setattr(main.nhan_su, "ds_nguoi", lambda: ([
        {"ten": "huytq", "level": 4, "bo_phan": "Vận hành", "ho_ten": "Quốc Huy"},
        {"ten": "hant", "level": 2, "bo_phan": "Vận hành", "ho_ten": "Thu Hà"}], ""))


def test_the_goal_hien_du_ten_khong_cat_bang_ellipsis(_so):
    mt.tao(MGR, TEN_DAI, "kq")
    r = _c.get("/muc-tieu", headers=H_MGR)
    # so trong ĐÚNG thẻ tab — 'class="mt-tab' còn khớp cả dải 'mt-tabs' bao ngoài
    the = r.text.split('<button class="mt-tab')[1].split("</button>")[0]
    assert TEN_DAI in the                       # tên vào HTML nguyên vẹn
    css = r.text.split(".mt-tab .ten{")[1].split("}")[0]
    assert "line-clamp" in css and "text-overflow:ellipsis" not in css


def test_them_viec_la_nut_mo_ra_khong_phai_box_cung(_so):
    mt.tao(MGR, "Goal A", "kq")
    r = _c.get("/muc-tieu", headers=H_MGR)
    assert '<details class="them-viec">' in r.text     # đóng sẵn, bấm mới bung
    assert '<div class="them-viec">' not in r.text


def test_nut_them_viec_nam_TREN_danh_sach_viec(ma, _so):
    m = mt.tao(MGR, "Goal A", "kq")
    tuan.them_viec_muc_tieu(ma, MGR, "Rà 10 video", "x", m["id"])
    r = _c.get("/muc-tieu", headers=H_MGR)
    assert r.text.index('<details class="them-viec"') < r.text.index("Rà 10 video")


@pytest.fixture()
def ma():
    return tuan.ma_tuan()


# ---------- lõi: mô tả + tài liệu đính kèm ----------

OWNER = {"ten": "bot", "level": 5, "bo_phan": "Ban quản trị"}
NGOAI = {"ten": "ducm", "level": 2, "bo_phan": "Vận hành", "ho_ten": "Minh Đức"}


def _viec(ma):
    return tuan.them_viec_giao(ma, MGR, NV, "Dựng 6 video", "san_xuat")


def test_nguoi_giao_bo_sung_mo_ta_sau_khi_da_giao(ma):
    v = _viec(ma)
    tuan.sua_viec(ma, v["id"], MGR, mo_ta="Ưu tiên 3 video kênh Life In US")
    assert tuan._tim(tuan.doc_tuan(ma), v["id"])["mo_ta"].startswith("Ưu tiên 3")


def test_nguoi_lam_khong_sua_de_bai(ma):
    v = _viec(ma)
    with pytest.raises(PermissionError):
        tuan.sua_viec(ma, v["id"], NV, tieu_de="Việc khác hẳn")


def test_viec_tu_them_thi_chinh_chu_sua_duoc(ma):
    v = tuan.them_viec_tu(ma, NV, "Tự học dựng", "hoc")
    tuan.sua_viec(ma, v["id"], NV, mo_ta="Xem 2 khóa")
    assert tuan._tim(tuan.doc_tuan(ma), v["id"])["mo_ta"] == "Xem 2 khóa"


def test_ca_hai_ben_dinh_duoc_tai_lieu_nguoi_ngoai_thi_khong(ma):
    v = _viec(ma)
    tuan.them_tai_lieu(ma, v["id"], MGR, "https://nas/ke-hoach.xlsx", "Kế hoạch")
    tuan.them_tai_lieu(ma, v["id"], NV, "https://drive/ban-dung", "Bản dựng")
    assert len(tuan._tim(tuan.doc_tuan(ma), v["id"])["tai_lieu"]) == 2
    with pytest.raises(PermissionError):
        tuan.them_tai_lieu(ma, v["id"], NGOAI, "https://x/y")


def test_chan_duong_dan_chay_duoc_script(ma):
    v = _viec(ma)
    for xau in ("javascript:alert(1)", "data:text/html,<script>", "chỗ nào đó"):
        with pytest.raises(ValueError):
            tuan.them_tai_lieu(ma, v["id"], MGR, xau)


def test_go_tai_lieu_chi_nguoi_dinh_hoac_nguoi_giao(ma):
    v = _viec(ma)
    tl = tuan.them_tai_lieu(ma, v["id"], NV, "https://drive/ban-dung")
    with pytest.raises(PermissionError):
        tuan.xoa_tai_lieu(ma, v["id"], NGOAI, tl["id"])
    tuan.xoa_tai_lieu(ma, v["id"], MGR, tl["id"])          # người giao gỡ được
    assert tuan._tim(tuan.doc_tuan(ma), v["id"])["tai_lieu"] == []


def test_viec_cu_khong_co_truong_moi_van_chay(ma):
    """Sổ tuần đã có trên máy công ty không mang 2 khóa này — không được vỡ."""
    v = _viec(ma)
    so = tuan.doc_tuan(ma)
    x = tuan._tim(so, v["id"])
    x.pop("mo_ta"), x.pop("tai_lieu")
    tuan._ghi_tuan(so)
    tuan.them_tai_lieu(ma, v["id"], MGR, "https://a/b")
    tuan.sua_viec(ma, v["id"], MGR, mo_ta="bù sau")
    assert len(tuan._tim(tuan.doc_tuan(ma), v["id"])["tai_lieu"]) == 1


# ---------- giao diện phiếu ----------

def test_phieu_hien_mo_ta_va_tai_lieu_da_dinh(ma, _so):
    m = mt.tao(MGR, "Goal A", "kq")
    v = tuan.them_viec_giao(ma, MGR, NV, "Dựng 6 video", "san_xuat", muc_tieu_id=m["id"])
    tuan.sua_viec(ma, v["id"], MGR, mo_ta="Ưu tiên kênh Life In US")
    tuan.them_tai_lieu(ma, v["id"], MGR, "https://nas.vn/ke-hoach.xlsx", "Kế hoạch T9")
    r = _c.get("/muc-tieu", headers=H_MGR)
    assert "Ưu tiên kênh Life In US" in r.text
    assert 'href="https://nas.vn/ke-hoach.xlsx"' in r.text and "Kế hoạch T9" in r.text
    assert 'action="/tasky/viec/tai-lieu"' in r.text


def test_dinh_tai_lieu_bang_form_va_bao_loi_khi_dan_bay(ma, _so):
    m = mt.tao(MGR, "Goal A", "kq")
    v = tuan.them_viec_giao(ma, MGR, NV, "Dựng 6 video", "san_xuat", muc_tieu_id=m["id"])
    ve = "/muc-tieu?chon=" + m["id"]
    r = _c.post("/tasky/viec/tai-lieu", headers=H_MGR, follow_redirects=False,
                data={"id": v["id"], "dia_chi": "https://a.vn/x", "ten": "Brief",
                      "tuan_xem": ma, "ve": ve})
    assert r.status_code == 303 and "loi=" not in r.headers["location"]
    r = _c.post("/tasky/viec/tai-lieu", headers=H_MGR, follow_redirects=False,
                data={"id": v["id"], "dia_chi": "javascript:alert(1)",
                      "tuan_xem": ma, "ve": ve})
    assert "loi=" in r.headers["location"]           # nói thẳng, không nuốt lặng lẽ
    assert len(tuan._tim(tuan.doc_tuan(ma), v["id"])["tai_lieu"]) == 1


def test_go_viec_bang_form_thuan(ma, _so):
    m = mt.tao(MGR, "Goal A", "kq")
    v = tuan.them_viec_muc_tieu(ma, MGR, "Việc gõ nhầm", "x", m["id"])
    r = _c.post("/tasky/viec/xoa", headers=H_MGR, follow_redirects=False,
                data={"id": v["id"], "tuan_xem": ma, "ve": "/muc-tieu"})
    assert r.status_code == 303
    assert tuan.doc_tuan(ma)["viec"] == []


def test_viec_dang_lam_thi_khong_go_trang_bao_loi(ma, _so):
    m = mt.tao(MGR, "Goal A", "kq")
    v = tuan.them_viec_giao(ma, MGR, NV, "Dựng 6 video", "san_xuat", muc_tieu_id=m["id"])
    tuan.nhan_viec(ma, v["id"], NV)
    H_NV = {**H_MGR, "X-Remote-User": "hant", "X-Remote-Level": "2",
            "X-Remote-Actions": "vao"}
    r = _c.post("/tasky/viec/xoa", headers=H_NV, follow_redirects=False,
                data={"id": v["id"], "tuan_xem": ma, "ve": "/tasky"})
    assert "loi=" in r.headers["location"]
    assert len(tuan.doc_tuan(ma)["viec"]) == 1        # công của người ta còn nguyên


def test_them_viec_kem_mo_ta_va_tai_lieu_ngay_luc_tao(ma, _so):
    m = mt.tao(MGR, "Goal A", "kq")
    r = _c.post("/api-tasky/muc-tieu/che-viec", headers=H_MGR,
                data={"muc_tieu_id": m["id"], "tieu_de": "Rà 10 video",
                      "loai_viec": "nghien_cuu", "nguoi": "hant", "tuan_xem": ma,
                      "mo_ta": "3 kênh đối thủ", "tai_lieu": "https://a.vn/list"})
    assert r.status_code == 200
    v = tuan.doc_tuan(ma)["viec"][0]
    assert v["mo_ta"] == "3 kênh đối thủ" and len(v["tai_lieu"]) == 1


def test_tai_lieu_dan_bay_khong_lam_hong_viec_vua_tao(ma, _so):
    m = mt.tao(MGR, "Goal A", "kq")
    r = _c.post("/api-tasky/muc-tieu/che-viec", headers=H_MGR,
                data={"muc_tieu_id": m["id"], "tieu_de": "Rà 10 video",
                      "loai_viec": "nghien_cuu", "tuan_xem": ma,
                      "tai_lieu": "chỗ nào đó"})
    assert r.status_code == 200 and "canh_bao" in r.json()
    assert tuan.doc_tuan(ma)["viec"][0]["tieu_de"] == "Rà 10 video"


def test_bao_loi_dinh_tai_lieu_hien_len_trang_khong_nuot(_so):
    r = _c.get("/muc-tieu?loi=Ch%E1%BB%89+nh%E1%BA%ADn+link+http", headers=H_MGR)
    assert "Chỉ nhận link http" in r.text
