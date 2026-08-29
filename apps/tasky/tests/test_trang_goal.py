# -*- coding: utf-8 -*-
"""§17 — Tasky tách ba mục Goal / Task / Report (Owner chốt 26/08).

Trang Goal chỉ theo dõi MỤC TIÊU: overview + danh sách. Việc con chuyển sang
mục Task.
"""
from datetime import date, timedelta

import pytest

from src import muc_tieu as mt
from src import tuan

MGR = {"ten": "huytq", "level": 4, "bo_phan": "Vận hành", "ho_ten": "Quốc Huy"}
NV = {"ten": "hant", "level": 2, "bo_phan": "Vận hành", "ho_ten": "Thu Hà"}


@pytest.fixture()
def ma():
    return tuan.ma_tuan()


def _han(n):
    return (date.today() + timedelta(days=n)).isoformat()


def _goal_xong(ma, ten="G"):
    """Goal có đúng một việc đã nghiệm thu."""
    g = mt.tao(MGR, ten, "kq")
    v = tuan.them_viec_giao(ma, MGR, NV, ten + "-việc", "x", muc_tieu_id=g["id"])
    tuan.nhan_viec(ma, v["id"], NV)
    tuan.bao_xong(ma, v["id"], NV)
    tuan.xac_nhan_viec(ma, v["id"], MGR)
    return g


# ---------- overview ----------

def test_tong_quan_dem_dung_tung_trang_thai(ma):
    mt.tao(MGR, "Chưa có việc nào", "kq")               # đang chạy, 0 việc
    g2 = mt.tao(MGR, "Đang làm dở", "kq")
    tuan.them_viec_giao(ma, MGR, NV, "V", "x", muc_tieu_id=g2["id"])
    _goal_xong(ma, "Xong hết chờ chốt")                 # xong hết → chờ chốt
    g4 = _goal_xong(ma, "Đã chốt đạt")
    mt.chot_ket_qua(g4["id"], MGR, mt.DAT)

    tq = mt.tong_quan(mt.doc_tat_ca())
    assert tq["tong"] == 4
    assert tq["dang_chay"] == 2 and tq["cho_chot"] == 1 and tq["dat"] == 1
    assert tq["chua_co_viec"] == 1                      # Goal bị bỏ quên
    assert tq["viec_tong"] == 3 and tq["viec_xong"] == 2


def test_chua_co_viec_nao_thi_khong_bia_ti_le():
    mt.tao(MGR, "Goal rỗng", "kq")
    assert mt.tong_quan(mt.doc_tat_ca())["ti_le"] is None


def test_dem_goal_tre_han(ma):
    mt.tao(MGR, "Trễ", "kq", han=_han(-2))
    mt.tao(MGR, "Còn hạn", "kq", han=_han(9))
    assert mt.tong_quan(mt.doc_tat_ca())["tre_han"] == 1


# ---------- sắp xếp + cần để ý ----------

def _cay(han_map):
    ra = []
    for ten, con in han_map.items():
        ra.append({"id": ten, "tieu_de": ten, "trang_thai": mt.DANG_CHAY,
                   "con_han": con, "canh_bao": [], "luc_tao": "2026-08-0" + str(len(ra) + 1),
                   "tien_do": {"tong": 2, "xong": 0}})
    return ra


def test_goal_da_chot_luon_xuong_duoi():
    cay = _cay({"A": 5, "B": 1})
    cay[0]["trang_thai"] = mt.DAT
    assert [g["tieu_de"] for g in mt.sap_xep_goal(cay)] == ["B", "A"]


def test_sap_theo_gan_han_goal_khong_han_xuong_cuoi():
    cay = _cay({"A": 9, "B": None, "C": 2})
    assert [g["tieu_de"] for g in mt.sap_xep_goal(cay)] == ["C", "A", "B"]


def test_can_de_y_gom_goal_sap_chay_va_goal_bo_quen():
    cay = _cay({"Xa": 30, "Gấp": 2, "Bỏ quên": 30})
    cay[2]["tien_do"] = {"tong": 0, "xong": 0}
    gap, thuong = mt.can_de_y(cay)
    assert sorted(g["tieu_de"] for g in gap) == ["Bỏ quên", "Gấp"]
    assert [g["tieu_de"] for g in thuong] == ["Xa"]


def test_goal_da_chot_khong_vao_can_de_y():
    cay = _cay({"A": -5})
    cay[0]["trang_thai"] = mt.KHONG_DAT
    gap, thuong = mt.can_de_y(cay)
    assert gap == [] and len(thuong) == 1


# ---------- §17c: bấm đúp Goal → cửa sổ nổi ngay tại trang ----------

from fastapi.testclient import TestClient          # noqa: E402
from src import main                               # noqa: E402

_c = TestClient(main.app)
H_MGR = {"X-Remote-User": "huytq", "X-Remote-Level": "4",
         "X-Remote-Dept": "V%E1%BA%ADn%20h%C3%A0nh",
         "X-Remote-Actions": "vao,giao_viec,xac_nhan_ket_qua,bao_cao_bo_phan",
         "X-Remote-Apps": "tasky"}


@pytest.fixture()
def _so(monkeypatch):
    monkeypatch.setattr(main.nhan_su, "ds_nguoi", lambda: ([
        {"ten": "huytq", "level": 4, "bo_phan": "Vận hành", "ho_ten": "Quốc Huy"},
        {"ten": "hant", "level": 2, "bo_phan": "Vận hành", "ho_ten": "Thu Hà"}], ""))


def test_moi_goal_co_mot_cua_so_noi(ma, _so):
    """Owner 26/08: bấm đúp Goal phải mở popup NGAY TẠI TRANG, không nhảy màn khác."""
    g = mt.tao(MGR, "Goal A", "kq")
    tuan.them_viec_giao(ma, MGR, NV, "Việc trong Goal", "x", muc_tieu_id=g["id"])
    r = _c.get("/muc-tieu", headers=H_MGR)
    assert 'dialog class="mt-modal" data-goal-modal="%s"' % g["id"] in r.text
    assert 'data-goal="%s"' % g["id"] in r.text          # thẻ trỏ tới đúng dialog
    assert "showModal" in r.text
    assert "Việc trong Goal" in r.text                   # xem việc ngay trong popup


def test_the_goal_khong_co_duong_dieu_huong_nao(ma, _so):
    """Owner 26/08: bỏ nút 'Task →' — bấm đúp là làm được mọi thứ ngay tại trang,
    nút sang màn rời là thứ duy nhất còn đưa người dùng ra 'khối cũ'."""
    mt.tao(MGR, "Goal A", "kq")
    r = _c.get("/muc-tieu", headers=H_MGR)
    the = r.text.split('<article class="g-the')[1].split("</article>")[0]
    assert 'href="/task' not in the and "sang-task" not in r.text


def test_goal_da_chot_thi_popup_chi_doc(ma, _so):
    g = mt.tao(MGR, "Goal A", "kq")
    mt.chot_ket_qua(g["id"], MGR, mt.DAT)
    r = _c.get("/muc-tieu", headers=H_MGR)
    hop = r.text.split('data-goal-modal="%s"' % g["id"])[1].split("</dialog>")[0]
    assert 'name="tieu_de"' not in hop and 'action="/muc-tieu/mau"' not in hop


def test_nguoi_khong_duoc_sua_thi_popup_khong_co_o_sua(ma, _so):
    """Người khác bộ phận xem được Goal thì cũng không sửa được từ popup."""
    g = mt.tao(MGR, "Goal A", "kq")
    h_kd = {**H_MGR, "X-Remote-User": "kd4", "X-Remote-Dept": "Kinh%20doanh"}
    r = _c.get("/muc-tieu", headers=h_kd)
    if 'data-goal-modal="%s"' % g["id"] in r.text:
        hop = r.text.split('data-goal-modal="%s"' % g["id"])[1].split("</dialog>")[0]
        assert 'name="tieu_de"' not in hop and "data-xoa-goal" not in hop


def test_popup_goal_khong_hep_hon_popup_viec(_so):
    """Owner 26/08: popup Goal phải to như popup việc bên Task, đừng thu lại."""
    import re
    css = _c.get("/muc-tieu", headers=H_MGR).text
    rong = dict(re.findall(r"dialog\.(mt-modal|phieu-viec)\{width:min\((\d+)px", css))
    assert int(rong["mt-modal"]) >= int(rong["phieu-viec"]), rong


def test_popup_co_du_thu_man_cu_co(ma, _so):
    """Owner 26/08: popup phải bằng cái màn cũ, không được rơi mất phần nào —
    vòng tiến độ, khối chốt kết quả, chọn màu, danh sách việc, đường sang board."""
    g = mt.tao(MGR, "Goal A", "kq")
    v = tuan.them_viec_giao(ma, MGR, NV, "Việc 1", "x", muc_tieu_id=g["id"])
    tuan.nhan_viec(ma, v["id"], NV)
    tuan.bao_xong(ma, v["id"], NV)
    tuan.xac_nhan_viec(ma, v["id"], MGR)          # xong hết việc → hiện khối chốt
    r = _c.get("/muc-tieu", headers=H_MGR)
    hop = r.text.split('data-goal-modal="%s"' % g["id"])[1].split("</dialog>")[0]
    assert 'class="vong"' in hop and "stroke-dashoffset" in hop
    assert 'data-chot="%s"' % g["id"] in hop and 'data-kq="dat"' in hop
    assert 'action="/muc-tieu/mau"' in hop
    assert "Việc 1" in hop and 'href="/task?goal=%s"' % g["id"] in hop


def test_goal_da_chot_co_nut_mo_lai_trong_popup(_so):
    g = mt.tao(MGR, "Goal A", "kq")
    mt.chot_ket_qua(g["id"], MGR, mt.MOT_PHAN, "làm được nửa")
    r = _c.get("/muc-tieu", headers=H_MGR)
    hop = r.text.split('data-goal-modal="%s"' % g["id"])[1].split("</dialog>")[0]
    assert "Đã chốt: Một phần" in hop and "làm được nửa" in hop
    assert 'data-mo-lai="%s"' % g["id"] in hop


def test_popup_them_duoc_viec_ngay_tai_do(_so):
    """Popup phải làm được MỌI việc của màn cũ — kể cả thêm việc, nếu không thì
    vẫn phải nhảy sang board."""
    g = mt.tao(MGR, "Goal A", "kq")
    r = _c.get("/muc-tieu", headers=H_MGR)
    hop = r.text.split('data-goal-modal="%s"' % g["id"])[1].split("</dialog>")[0]
    assert 'class="them-viec"' in hop and 'data-che="%s"' % g["id"] in hop
    assert "data-che-ten" in hop and "data-chon-ai" in hop        # tên việc + giao ai
    assert "Thu Hà" in hop                                       # dropdown cấp dưới


def test_popup_hien_BOARD_4_COT_nhu_man_task(ma, _so):
    """Owner 26/08 (chốt lại): bấm đúp Goal phải ra ĐÚNG giao diện màn /task —
    đầu Goal + nút thêm việc + board 4 cột — chỉ khác là không rời trang."""
    g = mt.tao(MGR, "Goal A", "kq")
    a = tuan.them_viec_giao(ma, MGR, NV, "Chờ nhận", "x", muc_tieu_id=g["id"])
    b = tuan.them_viec_giao(ma, MGR, NV, "Đang làm dở", "x", muc_tieu_id=g["id"])
    tuan.nhan_viec(ma, b["id"], NV)
    hop = _c.get("/muc-tieu", headers=H_MGR).text         .split('data-goal-modal="%s"' % g["id"])[1].split("</dialog>")[0]
    assert 'class="board trong-modal"' in hop
    for cot in ("chua_nhan", "dang_lam", "bao_xong", "xac_nhan"):
        assert 'data-cot="%s"' % cot in hop, cot
    assert hop.index("Chờ nhận") < hop.index("Đang làm dở")     # đúng cột, đúng thứ tự


def test_popup_co_nut_them_viec(_so):
    """Owner: 'thậm chí còn chưa có nút thêm việc'."""
    g = mt.tao(MGR, "Goal A", "kq")
    hop = _c.get("/muc-tieu", headers=H_MGR).text         .split('data-goal-modal="%s"' % g["id"])[1].split("</dialog>")[0]
    assert 'class="them-viec"' in hop and 'data-che="%s"' % g["id"] in hop
    assert "Thêm việc để đạt Goal này" in hop
    assert hop.index("them-viec") < hop.index('class="board')   # nút nằm TRÊN board


def test_cua_so_du_rong_cho_BON_COT(_so):
    """Cột thứ 4 không được rơi ra ngoài mép — đo bằng số, không bằng cảm giác."""
    import re
    css = _c.get("/muc-tieu", headers=H_MGR).text
    rong = int(re.search(r"dialog\.mt-modal\{width:min\((\d+)px", css).group(1))
    cot = int(re.search(r"\.board\.trong-modal \.cot\{flex:0 0 (\d+)px", css).group(1))
    khe = int(re.search(r"\.board\.trong-modal\{gap:(\d+)px", css).group(1))
    dem = int(re.search(r"\.mt-modal-noi\{padding:\d+px (\d+)px", css).group(1))
    assert 4 * cot + 3 * khe + 2 * dem <= rong, (4 * cot + 3 * khe + 2 * dem, rong)


def test_dau_goal_KHONG_lap_o_board_task(ma, _so):
    """Owner 26/08: 'đã có khối hình 1, không cần duplicate thêm ở task'."""
    g = mt.tao(MGR, "Goal A", "kq")
    r = _c.get("/task?goal=" + g["id"], headers=H_MGR)
    assert 'class="mt-dau' not in r.text            # đầu Goal đầy đủ chỉ ở popup
    assert 'data-xoa-goal="' not in r.text and 'action="/muc-tieu/mau"' not in r.text
    assert 'class="goal-gon"' in r.text             # còn dòng nhắc gọn
    assert 'href="/muc-tieu?mo=%s"' % g["id"] in r.text


def test_duong_mo_san_popup_tu_board(_so):
    """Bấm 'Mở Goal' ở board → về trang Goal và popup mở sẵn."""
    g = mt.tao(MGR, "Goal A", "kq")
    r = _c.get("/muc-tieu?mo=" + g["id"], headers=H_MGR)
    kh = r.text.split('data-goal-modal="%s"' % g["id"])[1].split(">")[0]
    assert "data-mo-san" in kh


def test_popup_goal_co_nut_xac_nhan_xong_viec(ma, _so):
    """Owner 29/08: người làm phải xác nhận xong việc — kể cả trong popup Goal.

    Trang Goal chỉ mở cho Manager+ (nhân sự làm việc ở mục Task), nên ở đây kiểm
    ca Manager TỰ LÀM việc của mình."""
    g = mt.tao(MGR, "Goal A", "kq")
    v = tuan.them_viec_giao(ma, MGR, MGR, "Việc tôi tự làm", "x", muc_tieu_id=g["id"])
    tuan.nhan_viec(ma, v["id"], MGR)
    hop = _c.get("/muc-tieu", headers=H_MGR).text         .split('data-goal-modal="%s"' % g["id"])[1].split("</dialog>")[0]
    assert 'data-lam="bao-xong" data-viec="%s"' % v["id"] in hop
    assert 'data-lam="xac-nhan"' not in hop      # chưa báo xong thì chưa nghiệm thu


def test_popup_goal_khong_cho_bao_xong_HO_nguoi_khac(ma, _so):
    """Không nới quyền: leader không bấm 'Đã xong' thay nhân sự."""
    g = mt.tao(MGR, "Goal A", "kq")
    v = tuan.them_viec_giao(ma, MGR, NV, "Việc của Hà", "x", muc_tieu_id=g["id"])
    tuan.nhan_viec(ma, v["id"], NV)
    hop = _c.get("/muc-tieu", headers=H_MGR).text         .split('data-goal-modal="%s"' % g["id"])[1].split("</dialog>")[0]
    assert 'data-lam="bao-xong"' not in hop


def test_khong_dung_alert_trinh_duyet(_so):
    """Lệ của hệ: báo lỗi tại chỗ, không dùng hộp thoại chặn của trình duyệt."""
    js = _c.get("/muc-tieu", headers=H_MGR).text.rsplit("<script>", 2)[1]
    assert "alert(" not in js and "confirm(" not in js
