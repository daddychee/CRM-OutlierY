# -*- coding: utf-8 -*-
"""PlannerY đấu vào khối đế (25/08/2026) — hai cửa đọc LOOPBACK của gateway:
danh sách người (sổ IAM) + kênh nhà (danh bạ). App phụ không giữ sổ người/kênh
(hiến pháp mục 5 luật 4 + DE.md luật 2); khuôn test_radary_thi_truong."""
import asyncio

import bcrypt
import httpx
import pytest

from nen.common import danh_ba
from nen.iam import iam

_gensalt_goc = bcrypt.gensalt


@pytest.fixture()
def so_sach(tmp_path, monkeypatch):
    monkeypatch.setenv("IAM_DB", str(tmp_path / "iam.db"))
    monkeypatch.setenv("DANH_BA_DB", str(tmp_path / "danh_ba.db"))
    monkeypatch.setattr(bcrypt, "gensalt", lambda rounds=12: _gensalt_goc(4))
    conn = iam.ket_noi()
    chu = iam.claims_cua(iam.tao_tai_khoan(conn, None, "owner", "mk-owner",
                                           "Ban quản trị", 5, phai_doi_mk=False))
    ngoc = iam.tao_nguoi(conn, chu, "Trần Hồng Ngọc", "Vận hành - Sản xuất",
                         "Content (Kịch bản)")
    duong = iam.tao_nguoi(conn, chu, "Nguyễn Tùng Dương", "Vận hành - Sản xuất",
                          "Editor (Dựng video)")
    iam.tao_tai_khoan(conn, chu, "ngocth", "mk-ngoc", "Vận hành - Sản xuất", 2,
                      nguoi_ma=ngoc["ma"])
    # đã thôi việc: đế vẫn phát ra kèm trạng thái để app biết mà dọn lịch
    iam.sua_nguoi(conn, chu, duong["ma"], trang_thai="nghi")
    conn.close()

    dconn = danh_ba.ket_noi()
    ng = danh_ba.them_ngach(dconn, "Life In")
    tt = danh_ba.them_thi_truong(dconn, "US", "English")
    kenh = danh_ba.them_kenh(dconn, "Outland", ng, tt)
    khai_tu = danh_ba.them_kenh(dconn, "Kênh Cũ", ng, tt)
    danh_ba.khai_tu_kenh(dconn, khai_tu)
    danh_ba.dat_lien_ket(dconn, kenh, "plannery", "ch_mrj42kzn0")
    dconn.commit()
    dconn.close()
    return {"ngoc": ngoc["ma"], "duong": duong["ma"], "ngach": ng,
            "kenh": kenh, "khai_tu": khai_tu}


def _goi(duong, client_addr=("127.0.0.1", 50000)):
    from nen.gateway.main import app as gateway_app

    async def run():
        tr = httpx.ASGITransport(app=gateway_app, client=client_addr)
        async with httpx.AsyncClient(transport=tr, base_url="http://t") as cl:
            return await cl.get(duong)
    return asyncio.run(run())


def test_planner_id_dan_xuat_tu_ma_ho_so():
    """Khóa nối là MÃ, không phải họ tên (bẫy map-theo-tên 05/08). Công thức phải
    khớp to-chuc/KPI và plan.json đang chạy: NS-005 → ns_ns005."""
    assert iam.planner_id_cua("NS-005") == "ns_ns005"
    assert iam.planner_id_cua("") == ""


def test_cua_nhan_su_tra_nguoi_kem_khoa_noi_va_nguoi_da_nghi(so_sach):
    r = _goi("/api/nhan-su/danh-sach")
    assert r.status_code == 200
    ds = {n["ma"]: n for n in r.json()["nguoi"]}
    assert ds[so_sach["ngoc"]]["planner_id"] == "ns_" + so_sach["ngoc"].replace("-", "").lower()
    assert ds[so_sach["ngoc"]]["tai_khoan"] == "ngocth"
    assert ds[so_sach["ngoc"]]["vi_tri"] == "Content (Kịch bản)"
    # người đã thôi việc VẪN ra kèm trạng thái — app cần biết ai còn kẹt trong lịch
    assert ds[so_sach["duong"]]["trang_thai"] == "nghi"
    # hồ sơ chưa cấp tài khoản không bị giấu (mỗi dòng là một con người)
    assert ds[so_sach["duong"]]["tai_khoan"] == ""


def test_cua_nhan_su_khong_lo_du_lieu_nhay_cam(so_sach):
    """Cửa vận hành: không có CCCD/địa chỉ/ngày sinh/sđt — dữ liệu nhạy cảm chỉ đi
    đường riêng có vết từng lượt xem (lệ CCCD 16/08)."""
    mau = _goi("/api/nhan-su/danh-sach").json()["nguoi"][0]
    assert not ({"cccd", "cccd_che", "dia_chi", "ngay_sinh", "sdt"} & set(mau))


def test_cua_kenh_tra_ngach_va_lien_ket_app(so_sach):
    r = _goi("/api/danh-ba/kenh")
    assert r.status_code == 200
    ds = {k["ma"]: k for k in r.json()}
    assert ds[so_sach["kenh"]]["ten"] == "Outland"
    assert ds[so_sach["kenh"]]["ngach_ma"] == so_sach["ngach"]
    assert ds[so_sach["kenh"]]["ngach_ten"] == "Life In"
    assert ds[so_sach["kenh"]]["lien_ket"]["plannery"] == "ch_mrj42kzn0"
    # kênh khai tử VẪN ra kèm trạng thái: app đang trỏ nó phải hiện đúng tên,
    # ẩn khỏi ô chọn là luật của app
    assert ds[so_sach["khai_tu"]]["trang_thai"] == "khai_tu"


def test_hai_cua_chi_phuc_vu_loopback(so_sach):
    assert _goi("/api/nhan-su/danh-sach", ("192.168.1.50", 5000)).status_code == 403
    assert _goi("/api/danh-ba/kenh", ("192.168.1.50", 5000)).status_code == 403
