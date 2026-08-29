# -*- coding: utf-8 -*-
"""§18 — bấm thông báo phải mở ĐÚNG danh sách việc (Owner 29/08).

Trước đó mọi thông báo đều ném sang /bao-cao-tuan, không kèm việc nào.
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


def test_loc_qua_han_chi_lay_viec_con_song(ma):
    a = tuan.them_viec_giao(ma, MGR, NV, "Trễ", "x", han=_han(-3))
    tuan.them_viec_giao(ma, MGR, NV, "Còn hạn", "x", han=_han(5))
    xong = tuan.them_viec_giao(ma, MGR, NV, "Trễ mà xong rồi", "x", han=_han(-9))
    tuan.nhan_viec(ma, xong["id"], NV); tuan.bao_xong(ma, xong["id"], NV)
    tuan.xac_nhan_viec(ma, xong["id"], MGR)
    ds = tuan.loc_viec(tuan.doc_tuan(ma)["viec"], "qua_han")
    assert [v["tieu_de"] for v in ds] == ["Trễ"]


def test_loc_cho_xac_nhan_theo_QUYEN_cua_nguoi_xem(ma):
    v = tuan.them_viec_giao(ma, MGR, NV, "Báo xong rồi", "x")
    tuan.nhan_viec(ma, v["id"], NV); tuan.bao_xong(ma, v["id"], NV)
    ds = tuan.doc_tuan(ma)["viec"]
    assert len(tuan.loc_viec(ds, "cho_xac_nhan", MGR)) == 1
    khac = {"ten": "ducm", "level": 2, "bo_phan": "Vận hành"}
    assert tuan.loc_viec(ds, "cho_xac_nhan", khac) == []      # không phải việc mình giao


def test_loc_gap_va_bi_tu_choi(ma):
    tuan.them_viec_giao(ma, MGR, NV, "Việc gấp", "x", gap=True)
    tc = tuan.them_viec_giao(ma, MGR, NV, "Bị từ chối", "x")
    tuan.tu_choi_viec(ma, tc["id"], NV, "bận rồi")
    ds = tuan.doc_tuan(ma)["viec"]
    assert [v["tieu_de"] for v in tuan.loc_viec(ds, "gap")] == ["Việc gấp"]
    assert [v["tieu_de"] for v in tuan.loc_viec(ds, "bi_tu_choi")] == ["Bị từ chối"]


def test_loc_la_thi_tra_nguyen_danh_sach(ma):
    tuan.them_viec_giao(ma, MGR, NV, "A", "x")
    ds = tuan.doc_tuan(ma)["viec"]
    assert tuan.loc_viec(ds, "linh tinh") == ds


# ---------- board mở đúng danh sách ----------

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


def test_bam_thong_bao_mo_dung_danh_sach_viec(ma, _so):
    """Owner 29/08: bấm 'việc quá hạn' phải thấy CHÍNH những việc đó."""
    tuan.them_viec_giao(ma, MGR, NV, "Trễ hạn rồi", "x", han=_han(-4))
    tuan.them_viec_giao(ma, MGR, NV, "Còn hạn", "x", han=_han(6))
    r = _c.get("/task?can=qua_han", headers=H_MGR)
    assert "Trễ hạn rồi" in r.text and "Còn hạn" not in r.text
    thanh = r.text.split('<form class="quay"')[1].split("</form>")[0]
    assert 'value="qua_han" selected' in thanh          # dropdown nói rõ đang lọc gì
    assert "1 việc quá hạn" in thanh


def test_thong_bao_tro_vao_board_chu_khong_phai_trang_bao_cao(ma, _so):
    from src import thong_bao as tb
    v = tuan.them_viec_giao(ma, MGR, NV, "Báo xong rồi", "x")
    tuan.nhan_viec(ma, v["id"], NV); tuan.bao_xong(ma, v["id"], NV)
    ds = tb.cua_leader(ma, MGR, [NV])
    duong = {m["chu"]: m["duong"] for m in ds}
    assert duong["1 việc chờ bạn xác nhận"] == "/task?can=cho_xac_nhan"
    # Mọi thông báo VỀ VIỆC đều mở board đã lọc; chỉ "người chưa đóng tuần" mới
    # thuộc về trang Báo cáo (nó nói về NGƯỜI, không phải một danh sách việc).
    for chu, d in duong.items():
        assert d.startswith("/task?can=") or "đóng tuần" in chu, (chu, d)


def test_bo_loc_thi_ve_board_day_du(ma, _so):
    tuan.them_viec_giao(ma, MGR, NV, "Trễ hạn rồi", "x", han=_han(-4))
    tuan.them_viec_giao(ma, MGR, NV, "Còn hạn", "x", han=_han(6))
    r = _c.get("/task", headers=H_MGR)
    assert "Trễ hạn rồi" in r.text and "Còn hạn" in r.text
    # không lọc → dropdown về "Mọi trạng thái", không mục nào được chọn sẵn
    khoi = r.text.split('name="can"')[1].split("</select>")[0]
    assert "selected" not in khoi


# ---------- ô tổng hợp cho quản lý ----------

def test_tong_hop_quan_dem_dung(ma, _so):
    """Owner 29/08: 'chưa có tổng hợp số liệu việc tuần này'."""
    a = tuan.them_viec_giao(ma, MGR, NV, "Trễ", "x", han=_han(-2))
    b = tuan.them_viec_giao(ma, MGR, NV, "Báo xong", "x")
    tuan.nhan_viec(ma, b["id"], NV); tuan.bao_xong(ma, b["id"], NV)
    c = tuan.them_viec_giao(ma, MGR, NV, "Xong hẳn", "x")
    tuan.nhan_viec(ma, c["id"], NV); tuan.bao_xong(ma, c["id"], NV)
    tuan.xac_nhan_viec(ma, c["id"], MGR)
    th = tuan.tong_hop_quan(ma, [NV], MGR)
    assert th["so_viec"] == 3 and th["xong"] == 1 and th["ti_le"] == 33
    assert th["qua_han"] == 1 and th["cho_xac_nhan"] == 1 and th["chua_nhan"] == 1


def test_quan_khong_co_viec_thi_khong_bia_ti_le(ma, _so):
    assert tuan.tong_hop_quan(ma, [NV], MGR)["ti_le"] is None


def test_man_viec_cua_toi_co_o_tong_hop_cho_quan_ly(ma, _so):
    """Owner 29/08: quản lý mở màn này thấy 4 ô cá nhân toàn 0 — cần hàng ô về
    quân mình, và mỗi số phải BẤM ĐƯỢC để mở đúng danh sách việc."""
    tuan.them_viec_giao(ma, MGR, NV, "Trễ", "x", han=_han(-2))
    r = _c.get("/tasky", headers=H_MGR)
    assert 'class="tk-so quan"' in r.text and "Bộ phận tôi quản" in r.text
    assert 'href="/task?can=qua_han"' in r.text
    assert 'href="/task?can=cho_xac_nhan"' in r.text
    assert "Việc của riêng tôi" in r.text


def test_nhan_vien_khong_thay_o_tong_hop_quan(ma, _so):
    """Nhân viên không quản ai — không vẽ hàng ô đó."""
    H_NV = {**H_MGR, "X-Remote-User": "hant", "X-Remote-Level": "2",
            "X-Remote-Actions": "vao"}
    r = _c.get("/tasky", headers=H_NV)
    assert 'class="tk-so quan"' not in r.text


def test_board_co_dropdown_loc_trang_thai(ma, _so):
    """Owner 29/08: 6 bộ lọc phải chọn được ngay trên thanh công cụ, không chỉ
    vào được từ thông báo."""
    r = _c.get("/task", headers=H_MGR)
    thanh = r.text.split('<form class="quay"')[1].split("</form>")[0]
    assert 'name="can"' in thanh
    for k in ("qua_han", "cho_xac_nhan", "chua_nhan", "gap", "bi_tu_choi", "viec_ket"):
        assert 'value="%s"' % k in thanh, k


def test_dropdown_giu_lua_chon_dang_loc(ma, _so):
    tuan.them_viec_giao(ma, MGR, NV, "Trễ", "x", han=_han(-2))
    thanh = _c.get("/task?can=qua_han", headers=H_MGR).text \
        .split('<form class="quay"')[1].split("</form>")[0]
    assert 'value="qua_han" selected' in thanh


def test_doi_truc_van_giu_bo_loc(ma, _so):
    """Bấm 'Nhóm theo' là submit cùng form — bộ lọc đang chọn không được rơi mất."""
    tuan.them_viec_giao(ma, MGR, NV, "Trễ", "x", han=_han(-2))
    tuan.them_viec_giao(ma, MGR, NV, "Còn hạn", "x", han=_han(5))
    r = _c.get("/task?can=qua_han&truc=nguoi", headers=H_MGR)
    assert "Trễ" in r.text and "Còn hạn" not in r.text
    thanh = r.text.split('<form class="quay"')[1].split("</form>")[0]
    assert 'value="qua_han" selected' in thanh
