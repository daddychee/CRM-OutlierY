# -*- coding: utf-8 -*-
"""§17 bước 2 — board kanban: cột theo trục, kéo thẻ có kiểm quyền.

Nguyên tắc: board KHÔNG đẻ luật mới. Mỗi nước kéo ứng đúng một hàm đã có
(nhan_viec / bao_xong / xac_nhan_viec / tra_lai / chuyen_vao_goal / gan_nguoi),
luật của hàm đó là luật cuối cùng.
"""
import pytest

from src import muc_tieu as mt
from src import tuan

MGR = {"ten": "huytq", "level": 4, "bo_phan": "Vận hành", "ho_ten": "Quốc Huy"}
NV = {"ten": "hant", "level": 2, "bo_phan": "Vận hành", "ho_ten": "Thu Hà"}
NV2 = {"ten": "ducm", "level": 2, "bo_phan": "Vận hành", "ho_ten": "Minh Đức"}
OWNER = {"ten": "bot", "level": 5, "bo_phan": "Ban quản trị"}


@pytest.fixture()
def ma():
    return tuan.ma_tuan()


# ---------- dựng cột ----------

def test_cot_trang_thai_du_bon_khau(ma):
    g = mt.tao(MGR, "G", "kq")
    a = tuan.them_viec_giao(ma, MGR, NV, "A", "x", muc_tieu_id=g["id"])
    b = tuan.them_viec_giao(ma, MGR, NV, "B", "x", muc_tieu_id=g["id"])
    tuan.nhan_viec(ma, b["id"], NV)
    ds = tuan.doc_tuan(ma)["viec"]
    cot = {c["ma"]: [v["tieu_de"] for v in c["viec"]] for c in tuan.cot_theo_trang_thai(ds)}
    assert cot["chua_nhan"] == ["A"] and cot["dang_lam"] == ["B"]
    assert cot["bao_xong"] == [] and cot["xac_nhan"] == []


def test_cot_goal_moi_goal_mot_cot_va_giu_thu_tu_truyen_vao(ma):
    g1 = mt.tao(MGR, "Goal 1", "kq")
    g2 = mt.tao(MGR, "Goal 2", "kq")
    tuan.them_viec_giao(ma, MGR, NV, "A", "x", muc_tieu_id=g2["id"])
    cot = tuan.cot_theo_goal(tuan.doc_tuan(ma)["viec"], [g1, g2])
    assert [c["ten"] for c in cot] == ["Goal 1", "Goal 2"]
    assert cot[0]["viec"] == [] and cot[1]["viec"][0]["tieu_de"] == "A"


def test_viec_chua_thuoc_goal_nao_van_co_cot_rieng(ma):
    tuan.them_viec_tu(ma, NV, "Việc lẻ cũ", "x")
    cot = tuan.cot_theo_goal(tuan.doc_tuan(ma)["viec"], [])
    assert [c["ten"] for c in cot] == ["Chưa thuộc Goal nào"]


def test_cot_nguoi_chua_giao_dung_dau(ma):
    g = mt.tao(MGR, "G", "kq")
    tuan.them_viec_muc_tieu(ma, MGR, "Chưa giao", "x", g["id"])
    tuan.them_viec_giao(ma, MGR, NV, "Của Hà", "x", muc_tieu_id=g["id"])
    cot = tuan.cot_theo_nguoi(tuan.doc_tuan(ma)["viec"], {"hant": "Thu Hà"})
    assert [c["ten"] for c in cot] == ["Chưa giao", "Thu Hà"]


def test_truc_la_thi_ve_trang_thai(ma):
    tuan.them_viec_giao(ma, MGR, NV, "A", "x")
    assert [c["ma"] for c in tuan.dung_cot(tuan.doc_tuan(ma)["viec"], "linh tinh")] \
        == ["chua_nhan", "dang_lam", "bao_xong", "xac_nhan"]


# ---------- luật kéo thẻ ----------

def test_chi_nguoi_duoc_giao_moi_keo_sang_dang_lam(ma):
    v = tuan.them_viec_giao(ma, MGR, NV, "A", "x")
    assert tuan.keo_duoc(v, "trang_thai", "dang_lam", NV)[0] is True
    assert tuan.keo_duoc(v, "trang_thai", "dang_lam", NV2)[0] is False
    assert tuan.keo_duoc(v, "trang_thai", "dang_lam", MGR)[0] is False   # leader không nhận hộ


def test_chi_leader_moi_keo_sang_da_nghiem_thu(ma):
    v = tuan.them_viec_giao(ma, MGR, NV, "A", "x")
    tuan.nhan_viec(ma, v["id"], NV)
    tuan.bao_xong(ma, v["id"], NV)
    v = tuan._tim(tuan.doc_tuan(ma), v["id"])
    assert tuan.keo_duoc(v, "trang_thai", "xac_nhan", MGR)[0] is True
    assert tuan.keo_duoc(v, "trang_thai", "xac_nhan", NV)[0] is False    # tự nghiệm thu việc mình


def test_khong_nhay_coc_tu_chua_nhan_sang_bao_xong(ma):
    v = tuan.them_viec_giao(ma, MGR, NV, "A", "x")
    assert tuan.keo_duoc(v, "trang_thai", "bao_xong", NV)[0] is False


def test_keo_doi_goal_va_giao_lai_chi_nguoi_giao(ma):
    v = tuan.them_viec_giao(ma, MGR, NV, "A", "x")
    assert tuan.keo_duoc(v, "goal", "mt-2", MGR)[0] is True
    assert tuan.keo_duoc(v, "goal", "mt-2", NV)[0] is False
    assert tuan.keo_duoc(v, "nguoi", "ducm", MGR)[0] is True
    assert tuan.keo_duoc(v, "nguoi", "ducm", NV)[0] is False
    assert tuan.keo_duoc(v, "nguoi", "ducm", OWNER)[0] is True


def test_khong_keo_duoc_thi_co_LY_DO_cho_nguoi_dung_doc(ma):
    v = tuan.them_viec_giao(ma, MGR, NV, "A", "x")
    duoc, vi_sao = tuan.keo_duoc(v, "trang_thai", "xac_nhan", NV)
    assert duoc is False and "nghiệm thu" in vi_sao


# ---------- giao lại người (trục Người) ----------

def test_giao_lai_khi_chua_ai_bat_tay_vao(ma):
    v = tuan.them_viec_giao(ma, MGR, NV, "A", "x")
    tuan.gan_lai_nguoi(ma, v["id"], MGR, NV2)
    x = tuan._tim(tuan.doc_tuan(ma), v["id"])
    assert x["nguoi"] == "ducm" and x["trang_thai"] == tuan.CHO_NHAN


def test_go_nguoi_ve_cot_chua_giao(ma):
    v = tuan.them_viec_giao(ma, MGR, NV, "A", "x")
    tuan.gan_lai_nguoi(ma, v["id"], MGR, None)
    x = tuan._tim(tuan.doc_tuan(ma), v["id"])
    assert x["nguoi"] == "" and x["trang_thai"] == tuan.CHUA_GIAO


def test_viec_dang_lam_do_khong_bi_giao_thang_cho_nguoi_khac(ma):
    """Xóa trắng công người đang làm mà họ không biết — phải Trả lại trước."""
    v = tuan.them_viec_giao(ma, MGR, NV, "A", "x")
    tuan.nhan_viec(ma, v["id"], NV)
    with pytest.raises(ValueError):
        tuan.gan_lai_nguoi(ma, v["id"], MGR, NV2)
    v = tuan._tim(tuan.doc_tuan(ma), v["id"])
    assert tuan.keo_duoc(v, "nguoi", "ducm", MGR)[0] is False


def test_giao_lai_van_theo_luat_giao_viec(ma):
    """Không nới quyền: vẫn chỉ giao được cho cấp dưới trong bộ phận mình."""
    v = tuan.them_viec_giao(ma, MGR, NV, "A", "x")
    ngoai = {"ten": "kd1", "level": 2, "bo_phan": "Kinh doanh"}
    with pytest.raises(PermissionError):
        tuan.gan_lai_nguoi(ma, v["id"], MGR, ngoai)


# ---------- route thả thẻ ----------

from fastapi.testclient import TestClient          # noqa: E402
from src import main                               # noqa: E402

_c = TestClient(main.app)
H_MGR = {"X-Remote-User": "huytq", "X-Remote-Level": "4",
         "X-Remote-Dept": "V%E1%BA%ADn%20h%C3%A0nh",
         "X-Remote-Actions": "vao,giao_viec,xac_nhan_ket_qua,bao_cao_bo_phan",
         "X-Remote-Apps": "tasky"}
H_NV = {**H_MGR, "X-Remote-User": "hant", "X-Remote-Level": "2",
        "X-Remote-Actions": "vao"}


@pytest.fixture()
def _so(monkeypatch):
    monkeypatch.setattr(main.nhan_su, "ds_nguoi", lambda: ([
        {"ten": "huytq", "level": 4, "bo_phan": "Vận hành", "ho_ten": "Quốc Huy"},
        {"ten": "hant", "level": 2, "bo_phan": "Vận hành", "ho_ten": "Thu Hà"},
        {"ten": "ducm", "level": 2, "bo_phan": "Vận hành", "ho_ten": "Minh Đức"}], ""))


def _tha(id_viec, truc, cot, ma, h):
    return _c.post("/api-tasky/keo", headers=h,
                   data={"id": id_viec, "truc": truc, "cot": cot, "tuan_xem": ma})


def test_tha_the_goi_dung_ham_nghiep_vu(ma, _so):
    v = tuan.them_viec_giao(ma, MGR, NV, "A", "x")
    assert _tha(v["id"], "trang_thai", "dang_lam", ma, H_NV).status_code == 200
    assert tuan._tim(tuan.doc_tuan(ma), v["id"])["trang_thai"] == tuan.DANG_LAM
    assert _tha(v["id"], "trang_thai", "bao_xong", ma, H_NV).status_code == 200
    assert _tha(v["id"], "trang_thai", "xac_nhan", ma, H_MGR).status_code == 200
    assert tuan._tim(tuan.doc_tuan(ma), v["id"])["trang_thai"] == tuan.XAC_NHAN


def test_tha_sai_quyen_bi_chan_o_SERVER(ma, _so):
    """Không lách được bằng cách kéo: server kiểm lại, không tin UI."""
    v = tuan.them_viec_giao(ma, MGR, NV, "A", "x")
    tuan.nhan_viec(ma, v["id"], NV)
    tuan.bao_xong(ma, v["id"], NV)
    r = _tha(v["id"], "trang_thai", "xac_nhan", ma, H_NV)      # tự nghiệm thu việc mình
    assert r.status_code == 403
    assert tuan._tim(tuan.doc_tuan(ma), v["id"])["trang_thai"] == tuan.BAO_XONG


def test_tha_sang_cot_nguoi_la_giao_lai(ma, _so):
    v = tuan.them_viec_giao(ma, MGR, NV, "A", "x")
    assert _tha(v["id"], "nguoi", "ducm", ma, H_MGR).status_code == 200
    assert tuan._tim(tuan.doc_tuan(ma), v["id"])["nguoi"] == "ducm"


def test_board_hien_du_cot_va_the(ma, _so):
    g = mt.tao(MGR, "Goal A", "kq")
    tuan.them_viec_giao(ma, MGR, NV, "Việc board", "x", muc_tieu_id=g["id"])
    r = _c.get("/task?goal=" + g["id"], headers=H_MGR)
    assert 'class="board"' in r.text and "Việc board" in r.text
    assert 'data-cot="chua_nhan"' in r.text


def test_doi_truc_sang_goal_thi_cot_la_ten_goal(ma, _so):
    g = mt.tao(MGR, "Goal Alpha", "kq")
    tuan.them_viec_giao(ma, MGR, NV, "V", "x", muc_tieu_id=g["id"])
    r = _c.get("/task?truc=goal", headers=H_MGR)
    assert 'data-cot="%s"' % g["id"] in r.text and "Goal Alpha" in r.text


def test_the_khong_keo_duoc_thi_khong_draggable(ma, _so):
    """UI khóa sẵn thẻ mình không có quyền kéo — đỡ bấm rồi mới báo lỗi."""
    g = mt.tao(MGR, "G", "kq")
    v = tuan.them_viec_giao(ma, MGR, NV, "A", "x", muc_tieu_id=g["id"])
    duong = "/task?goal=" + g["id"]                   # cùng một trục: trạng thái
    the = _c.get(duong, headers=H_NV).text.split('data-viec="%s"' % v["id"])[1].split(">")[0]
    assert 'draggable="true"' in the                  # NV nhận được việc của mình
    the2 = _c.get(duong, headers=H_MGR).text.split('data-viec="%s"' % v["id"])[1].split(">")[0]
    assert 'draggable="false"' in the2                # leader không nhận hộ


def test_truc_mac_dinh_theo_vai(ma, _so):
    """Nhân viên nhìn theo KHÂU (việc của tôi ở đâu); quản lý xem toàn cảnh thì
    theo Goal — mở sẵn đúng trục hợp vai, đỡ phải bấm."""
    g = mt.tao(MGR, "Goal A", "kq")
    tuan.them_viec_giao(ma, MGR, NV, "A", "x", muc_tieu_id=g["id"])
    assert 'data-cot="chua_nhan"' in _c.get("/task", headers=H_NV).text
    assert 'data-cot="%s"' % g["id"] in _c.get("/task", headers=H_MGR).text
    # mở đúng một Goal thì cả hai đều nhìn theo khâu
    assert 'data-cot="chua_nhan"' in _c.get("/task?goal=" + g["id"], headers=H_MGR).text


def test_quan_ly_xem_moi_goal_van_thay_viec_CHUA_GAN_GOAL(ma, _so):
    """Việc cũ chưa gắn Goal không được biến mất — còn thấy mới gom vào Goal được."""
    tuan.them_viec_giao(ma, MGR, NV, "Việc chưa gắn Goal", "x")
    r = _c.get("/task?truc=goal", headers=H_MGR)
    assert "Việc chưa gắn Goal" in r.text and "Chưa thuộc Goal nào" in r.text


def test_quan_ly_khong_thay_viec_ngoai_tam(ma, _so, monkeypatch):
    """Board 'Mọi Goal' vẫn lọc quyền ở SERVER, không đổ hết việc công ty ra."""
    ngoai = {"ten": "kd9", "level": 2, "bo_phan": "Kinh doanh"}
    sep = {"ten": "kdmgr", "level": 4, "bo_phan": "Kinh doanh"}
    tuan.them_viec_giao(ma, sep, ngoai, "Việc bộ phận khác", "x")
    tuan.them_viec_giao(ma, MGR, NV, "Việc của tôi giao", "x")
    r = _c.get("/task?truc=goal", headers=H_MGR)
    assert "Việc của tôi giao" in r.text and "Việc bộ phận khác" not in r.text


def test_board_dung_tron_be_ngang(ma, _so):
    """Owner 26/08: 'app vẫn chỉ hiển thị ở giữa'. Cột kanban cần trọn bề ngang."""
    r = _c.get("/task", headers=H_MGR)
    assert '<div class="noi-dung rong">' in r.text
    assert ".noi-dung.rong{max-width:100%}" in r.text
    # trang thường KHÔNG bị nới theo
    assert '<div class="noi-dung ">' in _c.get("/muc-tieu", headers=H_MGR).text


def test_nut_them_viec_o_cuoi_cot_chi_khi_cot_la_GOAL(ma, _so):
    """Kiểu Trello: thêm việc ở cuối cột. Chỉ có nghĩa khi cột = một Goal."""
    g = mt.tao(MGR, "Goal A", "kq")
    tuan.them_viec_giao(ma, MGR, NV, "V", "x", muc_tieu_id=g["id"])
    r = _c.get("/task?truc=goal", headers=H_MGR)
    assert 'href="/task?goal=%s">+ Thêm việc' % g["id"] in r.text
    moc = 'class="them-cuoi"'
    assert moc not in _c.get("/task?truc=trang_thai", headers=H_MGR).text
    assert moc not in _c.get("/task?truc=goal", headers=H_NV).text   # NV không giao việc
