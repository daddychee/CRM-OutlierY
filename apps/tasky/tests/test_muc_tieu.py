# -*- coding: utf-8 -*-
"""B10.2 — lõi mục tiêu (FLOW-v3 §12).

Hai luật ghim ở đây: tiến độ đếm việc đã NGHIỆM THU (không trọng số), và xong hết
việc KHÔNG tự thành "đạt" — Manager phải kết luận.
"""
import pytest

from src import muc_tieu as mt
from src import tuan

MGR = {"ten": "huytq", "level": 4, "bo_phan": "Vận hành"}
MGR_KD = {"ten": "ngocpb", "level": 4, "bo_phan": "Kinh doanh"}
LEADER = {"ten": "vh3", "level": 3, "bo_phan": "Vận hành"}
NV = {"ten": "hant", "level": 2, "bo_phan": "Vận hành"}
OWNER = {"ten": "bot", "level": 5, "bo_phan": "Ban quản trị"}


def _mt(user=MGR, tieu_de="Tăng AVD kênh Life In", kq="AVD ≥ 45%", han="", tu=""):
    return mt.tao(user, tieu_de, kq, han, tu)


def _viec_xong(ma, m, tieu_de="Việc A"):
    """Một việc đi trọn vòng tới nghiệm thu, gắn vào mục tiêu."""
    v = tuan.them_viec_giao(ma, MGR, NV, tieu_de, "Dựng video", muc_tieu_id=m["id"])
    tuan.nhan_viec(ma, v["id"], NV)
    tuan.bao_xong(ma, v["id"], NV)
    tuan.xac_nhan_viec(ma, v["id"], MGR)
    return v


# ---------- ai được đặt mục tiêu ----------

def test_manager_dat_duoc_muc_tieu():
    m = _mt()
    assert m["trang_thai"] == mt.DANG_CHAY and m["bo_phan"] == "Vận hành"


def test_leader_khong_dat_duoc_muc_tieu():
    """Owner chốt: công việc bắt đầu từ Manager. Leader vẫn giao việc lẻ như cũ."""
    with pytest.raises(PermissionError):
        _mt(user=LEADER)


def test_nhan_vien_khong_dat_duoc():
    with pytest.raises(PermissionError):
        _mt(user=NV)


def test_thieu_ket_qua_can_dat_thi_bi_chan():
    """Mục tiêu không nêu kết quả thì sau này không chốt được — chặn ngay từ cửa."""
    with pytest.raises(ValueError):
        mt.tao(MGR, "Làm cho tốt hơn", "   ")


def test_thieu_ten_bi_chan():
    with pytest.raises(ValueError):
        mt.tao(MGR, "  ", "AVD ≥ 45%")


def test_han_sai_dinh_dang_bao_loi():
    with pytest.raises(ValueError):
        _mt(han="cuối tháng")


# ---------- tiến độ đếm theo việc nghiệm thu ----------

def test_chua_co_viec_thi_tien_do_la_None_khong_phai_0():
    m = _mt()
    t = mt.tien_do(m["id"])
    assert t["phan_tram"] is None and t["tong"] == 0 and t["xong_het"] is False


def test_tien_do_dem_viec_da_nghiem_thu(monkeypatch):
    ma = tuan.ma_tuan()
    m = _mt()
    _viec_xong(ma, m, "Việc 1")
    tuan.them_viec_giao(ma, MGR, NV, "Việc 2", "Dựng video", muc_tieu_id=m["id"])
    t = mt.tien_do(m["id"])
    assert (t["xong"], t["tong"], t["phan_tram"]) == (1, 2, 50)


def test_bao_xong_chua_lam_tien_do_nhuc_nhich():
    """Nấc 2 giữ nguyên: báo xong khác nghiệm thu."""
    ma = tuan.ma_tuan()
    m = _mt()
    v = tuan.them_viec_giao(ma, MGR, NV, "Việc A", "Dựng video", muc_tieu_id=m["id"])
    tuan.nhan_viec(ma, v["id"], NV)
    tuan.bao_xong(ma, v["id"], NV)
    assert mt.tien_do(m["id"])["phan_tram"] == 0


def test_viec_bi_huy_khong_lam_hong_mau_so():
    ma = tuan.ma_tuan()
    m = _mt()
    _viec_xong(ma, m, "Việc 1")
    bo = tuan.them_viec_giao(ma, MGR, NV, "Việc bỏ", "Dựng video", muc_tieu_id=m["id"])
    tuan.huy_viec(ma, bo["id"], MGR, "không cần nữa")
    assert mt.tien_do(m["id"])["phan_tram"] == 100


def test_viec_gom_qua_NHIEU_TUAN(monkeypatch):
    """Mục tiêu sống xuyên tuần — việc rải ở hai tuần vẫn gom về một cây."""
    ma = tuan.ma_tuan()
    sau = tuan.tuan_lien_ke(ma, 1)
    m = _mt()
    _viec_xong(ma, m, "Việc tuần này")
    tuan.them_viec_giao(sau, MGR, NV, "Việc tuần sau", "Dựng video", muc_tieu_id=m["id"])
    t = mt.tien_do(m["id"])
    assert t["tong"] == 2 and t["xong"] == 1


# ---------- xong hết việc KHÔNG tự thành đạt ----------

def test_xong_het_viec_van_chua_phai_dat():
    ma = tuan.ma_tuan()
    m = _mt()
    _viec_xong(ma, m)
    t = mt.tien_do(m["id"])
    assert t["xong_het"] is True and t["phan_tram"] == 100
    assert mt.doc_tat_ca()[0]["trang_thai"] == mt.DANG_CHAY   # máy KHÔNG tự phán đạt


def test_manager_chot_dat():
    m = _mt()
    d = mt.chot_ket_qua(m["id"], MGR, mt.DAT)
    assert d["trang_thai"] == mt.DAT and d["nguoi_chot"] == "huytq"


def test_chua_dat_tron_thi_bat_ghi_nhan_xet():
    """Số liệu không nói được vì sao — người chốt phải nói."""
    m = _mt()
    with pytest.raises(ValueError):
        mt.chot_ket_qua(m["id"], MGR, mt.MOT_PHAN, "")
    d = mt.chot_ket_qua(m["id"], MGR, mt.MOT_PHAN, "Làm đủ việc nhưng AVD chỉ lên 41%")
    assert d["trang_thai"] == mt.MOT_PHAN and "41%" in d["ket_luan"]


def test_ket_qua_ngoai_tap_bi_chan():
    m = _mt()
    with pytest.raises(ValueError):
        mt.chot_ket_qua(m["id"], MGR, "gan_dat", "x")


def test_manager_bo_phan_khac_khong_chot_duoc():
    m = _mt()
    with pytest.raises(PermissionError):
        mt.chot_ket_qua(m["id"], MGR_KD, mt.DAT)


def test_owner_chot_duoc_moi_muc_tieu():
    m = _mt()
    assert mt.chot_ket_qua(m["id"], OWNER, mt.DAT)["trang_thai"] == mt.DAT


def test_chot_hai_lan_bi_chan():
    m = _mt()
    mt.chot_ket_qua(m["id"], MGR, mt.DAT)
    with pytest.raises(ValueError):
        mt.chot_ket_qua(m["id"], MGR, mt.KHONG_DAT, "đổi ý")


def test_chot_nham_thi_mo_lai_duoc():
    m = _mt()
    mt.chot_ket_qua(m["id"], MGR, mt.DAT)
    mt.mo_lai(m["id"], MGR)
    assert mt.doc_tat_ca()[0]["trang_thai"] == mt.DANG_CHAY


def test_dang_chay_thi_khong_mo_lai():
    m = _mt()
    with pytest.raises(ValueError):
        mt.mo_lai(m["id"], MGR)


# ---------- nhiệm vụ Owner → mục tiêu Manager ----------

def test_muc_tieu_dung_tu_nhiem_vu_giu_lien_ket_nguoc():
    """Owner giao nhiệm vụ → Manager dựng thành mục tiêu; Owner theo dõi được."""
    ma = tuan.ma_tuan()
    nv = tuan.them_viec_giao(ma, OWNER, MGR, "Nâng chất lượng giữ chân video Mỹ", "Định hướng")
    m = _mt(tu=nv["id"])
    assert m["tu_nhiem_vu"] == nv["id"]
    assert [x["id"] for x in mt.doc_tat_ca() if x["tu_nhiem_vu"] == nv["id"]] == [m["id"]]


# ---------- phạm vi xem ----------

def test_manager_chi_thay_muc_tieu_bo_phan_minh():
    _mt()
    mt.tao(MGR_KD, "Chốt 3 ngách mới", "3 ngách vào pool US")
    assert [m["tieu_de"] for m in mt.trong_pham_vi(MGR)] == ["Tăng AVD kênh Life In"]
    assert len(mt.trong_pham_vi(MGR_KD)) == 1


def test_owner_thay_tat_ca():
    _mt()
    mt.tao(MGR_KD, "Chốt 3 ngách mới", "3 ngách vào pool US")
    assert len(mt.trong_pham_vi(OWNER)) == 2


def test_co_quyen_toan_cong_ty_thi_thay_tat():
    _mt()
    mt.tao(MGR_KD, "Chốt 3 ngách", "3 ngách")
    assert len(mt.trong_pham_vi(MGR, toan_cong_ty=True)) == 2


# ---------- hạn ----------

def test_con_han_am_la_qua_han():
    from datetime import date, timedelta
    m = _mt(han=(date.today() - timedelta(days=3)).isoformat())
    assert mt.con_han(m) == -3


def test_khong_dat_han_thi_None():
    assert mt.con_han(_mt()) is None


# ---------- sổ ----------

def test_so_hong_khong_lam_vo_app(tmp_path):
    (tmp_path / "db").mkdir(exist_ok=True)
    (tmp_path / "db" / "muc-tieu.json").write_text("{hỏng", encoding="utf-8")
    assert mt.doc_tat_ca() == []


def test_moi_thao_tac_de_lai_vet(tmp_path):
    import json
    m = _mt()
    mt.chot_ket_qua(m["id"], MGR, mt.DAT)
    dong = [json.loads(d) for d in
            (tmp_path / "db" / "nhat-ky.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [d["hanh_dong"] for d in dong] == ["tao_muc_tieu", "chot_muc_tieu"]


# ---------- việc chẻ ra mà chưa giao ai (§12) ----------

def test_che_viec_chua_giao_ai():
    ma = tuan.ma_tuan()
    m = _mt()
    v = tuan.them_viec_muc_tieu(ma, MGR, "Rà 10 video đối thủ", "Nghiên cứu", m["id"])
    assert v["trang_thai"] == tuan.CHUA_GIAO and v["nguoi"] == ""
    assert [x["id"] for x in tuan.chua_giao(ma, m["id"])] == [v["id"]]


def test_viec_chua_giao_van_dem_vao_tong_cua_muc_tieu():
    """Cây phải nói thật rằng mục tiêu còn 1 việc chưa ai làm."""
    ma = tuan.ma_tuan()
    m = _mt()
    tuan.them_viec_muc_tieu(ma, MGR, "Việc chưa giao", "Nghiên cứu", m["id"])
    t = mt.tien_do(m["id"])
    assert t["tong"] == 1 and t["xong"] == 0 and t["chua_giao"] == 1


def test_viec_chua_giao_khong_vao_ti_le_cua_ai():
    ma = tuan.ma_tuan()
    m = _mt()
    tuan.them_viec_muc_tieu(ma, MGR, "Việc chưa giao", "Nghiên cứu", m["id"])
    assert tuan.thong_ke_nguoi(ma, "hant")["ti_le"] is None


def test_gan_nguoi_van_qua_luat_giao_viec():
    ma = tuan.ma_tuan()
    m = _mt()
    v = tuan.them_viec_muc_tieu(ma, MGR, "Việc X", "Nghiên cứu", m["id"])
    with pytest.raises(PermissionError):
        tuan.gan_nguoi(ma, v["id"], MGR, {"ten": "kd2", "level": 2, "bo_phan": "Kinh doanh"})
    d = tuan.gan_nguoi(ma, v["id"], MGR, NV)
    assert d["trang_thai"] == tuan.CHO_NHAN and d["nguoi"] == "hant"


def test_gan_nguoi_hai_lan_bi_chan():
    ma = tuan.ma_tuan()
    m = _mt()
    v = tuan.them_viec_muc_tieu(ma, MGR, "Việc X", "Nghiên cứu", m["id"])
    tuan.gan_nguoi(ma, v["id"], MGR, NV)
    with pytest.raises(ValueError):
        tuan.gan_nguoi(ma, v["id"], MGR, NV)


def test_che_viec_thieu_muc_tieu_bi_chan():
    ma = tuan.ma_tuan()
    with pytest.raises(ValueError):
        tuan.them_viec_muc_tieu(ma, MGR, "Việc lạc", "Nghiên cứu", "")


# ---------- gom nhóm + cảnh báo cho màn cây ----------

def _che(ma, m, ten="Việc mới"):
    return tuan.them_viec_muc_tieu(ma, MGR, ten, "Nghiên cứu", m["id"])


def test_ba_nhom_dung_muc_can_hanh_dong():
    ma = tuan.ma_tuan()
    m = _mt()
    _che(ma, m, "Chưa giao")                                   # → cần xử lý
    tuan.them_viec_giao(ma, MGR, NV, "Chờ nhận", "x", muc_tieu_id=m["id"])   # → cần xử lý
    dl = tuan.them_viec_giao(ma, MGR, NV, "Đang làm", "x", muc_tieu_id=m["id"])
    tuan.nhan_viec(ma, dl["id"], NV)                           # → đang chạy
    _viec_xong(ma, m, "Đã xong")                               # → xong

    n = mt.nhom_viec(mt.viec_cua_muc_tieu(m["id"]))
    assert len(n["can_xu_ly"]) == 2 and len(n["dang_chay"]) == 1 and len(n["xong"]) == 1


def test_viec_dang_lam_ma_qua_han_thi_nhay_len_nhom_can_xu_ly():
    from datetime import date, timedelta
    ma = tuan.ma_tuan()
    m = _mt()
    v = tuan.them_viec_giao(ma, MGR, NV, "Trễ", "x", muc_tieu_id=m["id"],
                            han=(date.today() - timedelta(days=1)).isoformat())
    tuan.nhan_viec(ma, v["id"], NV)
    n = mt.nhom_viec(mt.viec_cua_muc_tieu(m["id"]))
    assert len(n["can_xu_ly"]) == 1 and n["dang_chay"] == []


def test_canh_bao_gom_dung_thu_va_luon_co_chu():
    ma = tuan.ma_tuan()
    m = _mt()
    _che(ma, m, "Chưa giao 1")
    _che(ma, m, "Chưa giao 2")
    tuan.them_viec_giao(ma, MGR, NV, "Chờ nhận", "x", muc_tieu_id=m["id"])
    cb = mt.canh_bao(m, mt.viec_cua_muc_tieu(m["id"]))
    chu = [c["chu"] for c in cb]
    assert "2 chưa giao" in chu and "1 chưa nhận" in chu
    assert all(c["chu"] and c["muc_do"] in ("cap", "luu_y") for c in cb)


def test_muc_tieu_tre_han_thi_canh_bao():
    from datetime import date, timedelta
    m = _mt(han=(date.today() - timedelta(days=2)).isoformat())
    assert any("Trễ hạn 2 ngày" == c["chu"] for c in mt.canh_bao(m, []))


def test_viec_da_xong_khong_sinh_canh_bao():
    """Không dọa người ta bằng việc đã nghiệm thu."""
    ma = tuan.ma_tuan()
    m = _mt()
    _viec_xong(ma, m)
    assert mt.canh_bao(m, mt.viec_cua_muc_tieu(m["id"])) == []


def test_gom_viec_moi_muc_tieu_trong_mot_luot():
    """Trang cây đọc sổ MỘT lần cho tất cả mục tiêu, không quét lại theo từng cái."""
    ma = tuan.ma_tuan()
    a, b = _mt(tieu_de="MT A"), _mt(tieu_de="MT B")
    _che(ma, a, "Việc A1")
    _che(ma, b, "Việc B1")
    tuan.them_viec_tu(ma, NV, "Việc lẻ không thuộc mục tiêu", "x")
    gom = mt.viec_theo_muc_tieu()
    assert set(gom) == {a["id"], b["id"]}
    assert [v["tieu_de"] for v in gom[a["id"]]] == ["Việc A1"]


# ---------- trang cây ----------

from fastapi.testclient import TestClient          # noqa: E402
from src import main                               # noqa: E402

_client = TestClient(main.app)
H_MGR = {"X-Remote-User": "huytq", "X-Remote-Level": "4", "X-Remote-Dept": "V%E1%BA%ADn%20h%C3%A0nh",
         "X-Remote-Actions": "vao,giao_viec,xac_nhan_ket_qua,bao_cao_bo_phan",
         "X-Remote-Apps": "tasky"}
H_NV = {"X-Remote-User": "hant", "X-Remote-Level": "2", "X-Remote-Dept": "V%E1%BA%ADn%20h%C3%A0nh",
        "X-Remote-Actions": "vao", "X-Remote-Apps": "tasky"}


@pytest.fixture()
def _so_gia(monkeypatch):
    monkeypatch.setattr(main.nhan_su, "ds_nguoi", lambda: ([
        {"ten": "huytq", "level": 4, "bo_phan": "Vận hành", "ho_ten": "Trần Quốc Huy"},
        {"ten": "hant", "level": 2, "bo_phan": "Vận hành", "ho_ten": "Nguyễn Thu Hà"}], ""))


def test_nhan_vien_khong_vao_duoc_man_muc_tieu():
    assert _client.get("/muc-tieu", headers=H_NV).status_code == 403


def test_trang_hien_cay_va_canh_bao(_so_gia):
    """Từ 26/08 việc con + cảnh báo chi tiết nằm ở mục Task (trang Goal chỉ tổng quan)."""
    ma = tuan.ma_tuan()
    m = _mt()
    _che(ma, m, "Rà 10 video đối thủ")
    r = _client.get("/task", headers=H_MGR)
    assert r.status_code == 200
    assert "Tăng AVD kênh Life In" in r.text and "AVD ≥ 45%" in r.text
    assert "1 chưa giao" in r.text and "Rà 10 video đối thủ" in r.text


def test_tao_muc_tieu_qua_api(_so_gia):
    r = _client.post("/api-tasky/muc-tieu", headers=H_MGR,
                     data={"tieu_de": "Ra 8 video", "ket_qua": "8 video đúng lịch"})
    assert r.status_code == 200 and len(mt.doc_tat_ca()) == 1


def test_che_viec_va_gan_nguoi_qua_api(_so_gia):
    ma = tuan.ma_tuan()
    m = _mt()
    r = _client.post("/api-tasky/muc-tieu/che-viec", headers=H_MGR,
                     data={"muc_tieu_id": m["id"], "tieu_de": "Việc X",
                           "loai_viec": "Nghiên cứu", "tuan_xem": ma})
    assert r.status_code == 200
    v = tuan.chua_giao(ma, m["id"])[0]
    r2 = _client.post("/api-tasky/muc-tieu/gan-nguoi", headers=H_MGR,
                      data={"id": v["id"], "nguoi": "hant", "tuan_xem": ma})
    assert r2.status_code == 200 and tuan.viec_cua(ma, "hant")[0]["trang_thai"] == tuan.CHO_NHAN


def test_chot_qua_api_bat_nhan_xet(_so_gia):
    m = _mt()
    r = _client.post("/api-tasky/muc-tieu/chot", headers=H_MGR,
                     data={"id": m["id"], "ket_qua": "mot_phan"})
    assert r.status_code == 400 and "nhận xét" in r.json()["detail"]


def test_sidebar_co_muc_con_muc_tieu(_so_gia):
    r = _client.get("/muc-tieu", headers=H_MGR)
    assert 'href="/muc-tieu"' in r.text and "Goal</a>" in r.text


# ---------- nối hai đầu: màn việc ↔ mục tiêu ----------

def test_the_viec_hien_chip_muc_tieu_kem_tien_do(_so_gia):
    ma = tuan.ma_tuan()
    m = _mt()
    tuan.them_viec_giao(ma, MGR, NV, "Feedback 6 script", "x", muc_tieu_id=m["id"])
    _viec_xong(ma, m, "Việc đã xong")
    r = _client.get("/tasky", headers=H_NV)
    assert "Goal: Tăng AVD kênh Life In" in r.text and "1/2 việc" in r.text


def test_viec_khong_thuoc_muc_tieu_thi_khong_co_chip(_so_gia):
    ma = tuan.ma_tuan()
    tuan.them_viec_tu(ma, NV, "Việc lẻ", "x")
    r = _client.get("/tasky", headers=H_NV)
    assert "muc-tieu?chon=" not in r.text


def test_manager_thay_nhiem_vu_cho_dung_thanh_muc_tieu(_so_gia):
    ma = tuan.ma_tuan()
    tuan.them_viec_giao(ma, OWNER, MGR, "Nâng chất lượng giữ chân video Mỹ", "Định hướng")
    r = _client.get("/tasky", headers=H_MGR)
    assert "Nhiệm vụ chờ bạn dựng thành Goal" in r.text
    assert "Nâng chất lượng giữ chân video Mỹ" in r.text


def test_nhan_vien_khong_thay_khoi_dung_muc_tieu(_so_gia):
    """Nhân sự không đặt mục tiêu — khối này không được hiện với họ."""
    ma = tuan.ma_tuan()
    tuan.them_viec_giao(ma, MGR, NV, "Việc thường", "x")
    r = _client.get("/tasky", headers=H_NV)
    assert "Nhiệm vụ chờ bạn dựng thành Goal" not in r.text


def test_dung_xong_thi_nhiem_vu_het_nam_trong_danh_sach_cho(_so_gia):
    ma = tuan.ma_tuan()
    nv = tuan.them_viec_giao(ma, OWNER, MGR, "Nhiệm vụ A", "Định hướng")
    assert "dựng thành Goal" in _client.get("/tasky", headers=H_MGR).text
    mt.tao(MGR, "Nhiệm vụ A", "kết quả X", tu_nhiem_vu=nv["id"])
    assert "dựng thành Goal" not in _client.get("/tasky", headers=H_MGR).text


# ---------- xóa Goal (Owner yêu cầu 25/08) ----------

def test_xoa_goal_chua_co_viec():
    m = _mt()
    kq = mt.xoa(m["id"], MGR)
    assert mt.doc_tat_ca() == [] and kq["so_viec_xoa"] == 0


def test_xoa_goal_xoa_luon_viec_con():
    """Owner chốt 25/08: nút này để dọn Goal test/nhầm — không để lại việc lẻ rác."""
    ma = tuan.ma_tuan()
    m = _mt()
    tuan.them_viec_giao(ma, MGR, NV, "Việc con 1", "x", muc_tieu_id=m["id"])
    tuan.them_viec_muc_tieu(ma, MGR, "Việc con 2", "x", m["id"])
    kq = mt.xoa(m["id"], MGR)
    assert kq["so_viec_xoa"] == 2 and tuan.viec_cua(ma, "hant") == []


def test_xoa_goal_khong_dung_toi_viec_le_khac():
    ma = tuan.ma_tuan()
    m = _mt()
    tuan.them_viec_giao(ma, MGR, NV, "Thuộc Goal", "x", muc_tieu_id=m["id"])
    tuan.them_viec_giao(ma, MGR, NV, "Việc lẻ", "x")
    mt.xoa(m["id"], MGR)
    assert [v["tieu_de"] for v in tuan.viec_cua(ma, "hant")] == ["Việc lẻ"]


def test_viec_con_dang_lam_van_xoa_duoc_theo_goal():
    """Việc TỰ THÊM / đang làm của quân mình: Manager dọn được cùng Goal."""
    ma = tuan.ma_tuan()
    m = _mt()
    v = tuan.them_viec_giao(ma, MGR, NV, "Đang làm dở", "x", muc_tieu_id=m["id"])
    tuan.nhan_viec(ma, v["id"], NV)
    with pytest.raises(PermissionError) as e:
        mt.xoa(m["id"], MGR)
    assert "Đang làm dở" in str(e.value)      # nói rõ việc nào chặn
    tuan.huy_viec(ma, v["id"], MGR, "dọn Goal test")
    assert mt.xoa(m["id"], MGR)["so_viec_xoa"] == 1


def test_owner_don_duoc_goal_test_du_viec_dang_lam():
    """Ca thật của Owner: Goal test có việc đang làm dở, cần xóa sạch một nhát."""
    ma = tuan.ma_tuan()
    m = _mt()
    v = tuan.them_viec_giao(ma, MGR, NV, "Đang làm dở", "x", muc_tieu_id=m["id"])
    tuan.nhan_viec(ma, v["id"], NV)
    assert mt.xoa(m["id"], OWNER)["so_viec_xoa"] == 1
    assert mt.doc_tat_ca() == [] and tuan.viec_cua(ma, "hant") == []


def test_viec_con_da_nghiem_thu_thi_chi_owner_xoa_duoc_goal():
    ma = tuan.ma_tuan()
    m = _mt()
    _viec_xong(ma, m, "Đã nghiệm thu")
    with pytest.raises(PermissionError):
        mt.xoa(m["id"], MGR)
    assert mt.xoa(m["id"], OWNER)["so_viec_xoa"] == 1
    assert tuan.viec_cua(ma, "hant") == []


def test_nua_chung_gay_thi_khong_xoa_gi_ca():
    """Kiểm quyền TỪNG việc TRƯỚC khi xóa — Goal mất mà việc còn là tệ hơn."""
    ma = tuan.ma_tuan()
    m = _mt()
    tuan.them_viec_muc_tieu(ma, MGR, "Xóa được", "x", m["id"])
    v = tuan.them_viec_giao(ma, MGR, NV, "Chặn lại", "x", muc_tieu_id=m["id"])
    tuan.nhan_viec(ma, v["id"], NV)
    with pytest.raises(PermissionError):
        mt.xoa(m["id"], MGR)
    assert len(mt.doc_tat_ca()) == 1 and len(tuan.doc_tuan(ma)["viec"]) == 2


def test_xoa_ca_viec_o_tuan_khac():
    ma = tuan.ma_tuan()
    sau = tuan.tuan_lien_ke(ma, 1)
    m = _mt()
    tuan.them_viec_giao(ma, MGR, NV, "Tuần này", "x", muc_tieu_id=m["id"])
    tuan.them_viec_giao(sau, MGR, NV, "Tuần sau", "x", muc_tieu_id=m["id"])
    assert mt.xoa(m["id"], MGR)["so_viec_xoa"] == 2
    assert tuan.viec_cua(sau, "hant") == []


def test_manager_bo_phan_khac_khong_xoa_duoc():
    m = _mt()
    with pytest.raises(PermissionError):
        mt.xoa(m["id"], MGR_KD)


def test_goal_da_chot_chi_owner_xoa_duoc():
    m = _mt()
    mt.chot_ket_qua(m["id"], MGR, mt.DAT)
    with pytest.raises(PermissionError) as e:
        mt.xoa(m["id"], MGR)
    assert "báo cáo" in str(e.value)
    mt.xoa(m["id"], OWNER)
    assert mt.doc_tat_ca() == []


def test_nhat_ky_giu_nguyen_ban_goal_bi_xoa(tmp_path):
    import json
    m = _mt(tieu_de="Goal quan trọng")
    mt.xoa(m["id"], MGR)
    dong = [json.loads(d) for d in
            (tmp_path / "db" / "nhat-ky.jsonl").read_text(encoding="utf-8").splitlines()]
    assert dong[-1]["hanh_dong"] == "xoa_muc_tieu"
    assert dong[-1]["ban_goc"]["tieu_de"] == "Goal quan trọng"


def test_nut_xoa_goal_hien_tren_trang(_so_gia):
    m = _mt()
    r = _client.get("/task", headers=H_MGR)
    assert 'data-xoa-goal="%s"' % m["id"] in r.text


def test_xoa_goal_qua_api_xoa_luon_viec_con(_so_gia):
    ma = tuan.ma_tuan()
    m = _mt()
    tuan.them_viec_giao(ma, MGR, NV, "Việc con", "x", muc_tieu_id=m["id"])
    r = _client.post("/api-tasky/muc-tieu/xoa", headers=H_MGR, data={"id": m["id"]})
    assert r.status_code == 200 and r.json()["du_lieu"]["so_viec_xoa"] == 1
    assert tuan.viec_cua(ma, "hant") == []


# ---------- màu nhãn cho Goal (Owner 25/08) ----------

def test_dat_mau_cho_goal():
    m = _mt()
    assert mt.dat_mau(m["id"], MGR, "cam")["mau"] == "cam"
    assert mt.dat_mau(m["id"], MGR, "")["mau"] == ""      # gỡ màu


def test_mau_ngoai_bang_bi_chan():
    """Không cho nhập hex tự do — sẽ đẻ ra màu trùng nền hoặc trùng màu cảnh báo."""
    m = _mt()
    with pytest.raises(ValueError):
        mt.dat_mau(m["id"], MGR, "#ff0000")


def test_manager_bo_phan_khac_khong_doi_mau():
    m = _mt()
    with pytest.raises(PermissionError):
        mt.dat_mau(m["id"], MGR_KD, "lam")


def test_mau_khong_dung_vao_nghia_trang_thai(_so_gia):
    """Goal tô màu vẫn giữ nguyên chip cảnh báo — màu nhãn không thay nghĩa."""
    ma = tuan.ma_tuan()
    m = _mt()
    mt.dat_mau(m["id"], MGR, "hong")
    tuan.them_viec_muc_tieu(ma, MGR, "Chưa giao ai", "x", m["id"])
    r = _client.get("/task", headers=H_MGR)
    assert "1 chưa giao" in r.text


# ---------- màu bằng FORM (không phụ thuộc JS) + dọn việc cũ ----------

def test_doi_mau_bang_form_post(_so_gia):
    """Owner báo bấm màu không ăn HAI lần liền → bỏ JS, dùng form POST + 303."""
    m = _mt()
    r = _client.post("/muc-tieu/mau", headers=H_MGR,
                     data={"id": m["id"], "mau": "cam"}, follow_redirects=False)
    assert r.status_code == 303 and mt.doc_tat_ca()[0]["mau"] == "cam"


def test_form_mau_ve_dung_goal_dang_xem(_so_gia):
    m = _mt()
    r = _client.post("/muc-tieu/mau", headers=H_MGR,
                     data={"id": m["id"], "mau": "luc"}, follow_redirects=False)
    assert r.headers["location"] == "/muc-tieu?chon=" + m["id"]


def test_nut_mau_la_the_button_trong_form(_so_gia):
    """Không còn phụ thuộc JS: nút màu phải là submit của form thật."""
    _mt()
    r = _client.get("/task", headers=H_MGR)
    assert 'action="/muc-tieu/mau"' in r.text and 'type="submit" name="mau"' in r.text


def test_don_viec_cu_xoa_viec_ngoai_goal(_so_gia):
    ma = tuan.ma_tuan()
    g = _mt()
    tuan.them_viec_giao(ma, MGR, NV, "Việc thuộc Goal", "x", muc_tieu_id=g["id"])
    tuan.them_viec_giao(ma, MGR, NV, "Việc cũ 1", "x")
    tuan.them_viec_giao(ma, MGR, NV, "Việc cũ 2", "x")
    h_owner = dict(H_MGR); h_owner["X-Remote-User"] = "bot"; h_owner["X-Remote-Level"] = "5"
    r = _client.post("/muc-tieu/don-viec-cu", headers=h_owner, follow_redirects=False)
    assert r.status_code == 303 and "da_don=2" in r.headers["location"]
    assert [v["tieu_de"] for v in tuan.viec_cua(ma, "hant")] == ["Việc thuộc Goal"]


def test_chi_owner_don_duoc_viec_cu(_so_gia):
    assert _client.post("/muc-tieu/don-viec-cu", headers=H_MGR).status_code == 403
