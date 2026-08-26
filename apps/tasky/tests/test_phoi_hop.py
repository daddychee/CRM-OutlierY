# -*- coding: utf-8 -*-
"""B8 — phối hợp NGANG giữa hai bộ phận (Owner chốt 24/08).

Ba luật: gửi được cho quản lý L3+ bộ phận KHÁC chênh ≤1 bậc · bên nhận toàn quyền
nhận/từ chối rồi tự làm hoặc chẻ việc con · BÊN YÊU CẦU nghiệm thu, bên làm không
tự ký cho mình. Công tính cho bên làm, bên nhờ chỉ theo dõi.
"""
import pytest
from fastapi.testclient import TestClient

from src import main, thong_bao as tb, tuan
from src.main import app

client = TestClient(app)

SO = [{"ten": "kd4", "level": 4, "bo_phan": "Kinh doanh", "ho_ten": "Quản lý KD"},
      {"ten": "vh4", "level": 4, "bo_phan": "Vận hành", "ho_ten": "Quản lý VH"},
      {"ten": "vh3", "level": 3, "bo_phan": "Vận hành", "ho_ten": "Leader VH"},
      {"ten": "vh2", "level": 2, "bo_phan": "Vận hành", "ho_ten": "Nhân viên VH"},
      {"ten": "kd2", "level": 2, "bo_phan": "Kinh doanh", "ho_ten": "Nhân viên KD"},
      {"ten": "bot", "level": 5, "bo_phan": "Ban quản trị", "ho_ten": "Owner"}]
KD4 = {"ten": "kd4", "level": 4, "bo_phan": "Kinh doanh"}
VH4 = {"ten": "vh4", "level": 4, "bo_phan": "Vận hành"}
VH3 = {"ten": "vh3", "level": 3, "bo_phan": "Vận hành"}
VH2 = {"ten": "vh2", "level": 2, "bo_phan": "Vận hành"}
KD2 = {"ten": "kd2", "level": 2, "bo_phan": "Kinh doanh"}

H_KD4 = {"X-Remote-User": "kd4", "X-Remote-Level": "4", "X-Remote-Dept": "Kinh%20doanh",
         "X-Remote-Actions": "vao,giao_viec,xac_nhan_ket_qua,bao_cao_bo_phan",
         "X-Remote-Apps": "tasky"}
H_VH4 = {"X-Remote-User": "vh4", "X-Remote-Level": "4", "X-Remote-Dept": "V%E1%BA%ADn%20h%C3%A0nh",
         "X-Remote-Actions": "vao,giao_viec,xac_nhan_ket_qua,bao_cao_bo_phan",
         "X-Remote-Apps": "tasky"}


@pytest.fixture(autouse=True)
def _so_gia(monkeypatch):
    monkeypatch.setattr(main.nhan_su, "ds_nguoi", lambda: (list(SO), ""))


@pytest.fixture()
def ma():
    return tuan.ma_tuan()


# ---------- luật ai gửi được cho ai ----------

def test_quan_ly_hai_bo_phan_ngang_cap_gui_duoc():
    assert tuan.duoc_yeu_cau_phoi_hop(KD4, VH4) is True


def test_chenh_mot_bac_van_gui_duoc():
    """Manager KD nhờ Leader VH — khác bộ phận nên vẫn là yêu cầu, không phải lệnh."""
    assert tuan.duoc_yeu_cau_phoi_hop(KD4, VH3) is True


def test_chenh_hai_bac_thi_khong():
    assert tuan.duoc_yeu_cau_phoi_hop(KD4, VH2) is False


def test_nhan_vien_khong_gui_duoc_yeu_cau_phoi_hop():
    assert tuan.duoc_yeu_cau_phoi_hop(KD2, VH4) is False


def test_cung_bo_phan_thi_di_duong_giao_viec_thuong():
    assert tuan.duoc_yeu_cau_phoi_hop(VH4, VH3) is False


def test_api_chan_gui_sai_luat(ma):
    r = client.post("/api-tasky/phoi-hop", headers=H_KD4,
                    data={"nguoi": "vh2", "tieu_de": "x", "loai_viec": "y", "tuan_xem": ma})
    assert r.status_code == 403


def test_dropdown_chi_hien_quan_ly_bo_phan_khac(ma):
    """Form phối hợp nay nằm TRONG Goal (25/08) — kiểm trong đúng dropdown đó."""
    from src import muc_tieu as mt_lo
    g = mt_lo.tao(KD4, "Goal KD", "kết quả")
    r = client.get("/task?goal=" + g["id"], headers=H_KD4)
    khoi = r.text.split("data-ph-nguoi")[1].split("</select>")[0]
    assert "Quản lý VH" in khoi and "Leader VH" in khoi
    assert "Nhân viên VH" not in khoi     # cách 2 bậc
    assert "Nhân viên KD" not in khoi     # cùng bộ phận thì giao thường
    assert "Nhân viên KD" in r.text       # vẫn có ở ô chọn người giao việc


# ---------- bên nhận toàn quyền ----------

def test_gui_yeu_cau_thi_o_trang_thai_cho_phoi_hop(ma):
    v = tuan.yeu_cau_phoi_hop(ma, KD4, VH4, "Dựng 3 video cho chiến dịch", "Dựng video")
    assert v["trang_thai"] == tuan.CHO_PHOI_HOP and v["nguon"] == "phoi_hop"
    assert v["nguoi"] == "vh4" and v["bo_phan_gui"] == "Kinh doanh"


def test_ben_nhan_tu_choi_duoc_va_phai_ghi_ly_do(ma):
    v = tuan.yeu_cau_phoi_hop(ma, KD4, VH4, "Dựng 3 video", "Dựng video")
    with pytest.raises(ValueError):
        tuan.tu_choi_viec(ma, v["id"], VH4, "")
    d = tuan.tu_choi_viec(ma, v["id"], VH4, "Tuần này đang chạy 8 video Life In")
    assert d["trang_thai"] == tuan.TU_CHOI


def test_ben_gui_khong_ep_duoc_ben_nhan(ma):
    """Người gửi KHÔNG có quyền trên người nhận — không tự nhận hộ được."""
    v = tuan.yeu_cau_phoi_hop(ma, KD4, VH4, "Dựng 3 video", "Dựng video")
    with pytest.raises(PermissionError):
        tuan.nhan_viec(ma, v["id"], KD4)


def test_chua_dong_y_thi_chua_viet_checklist(ma):
    v = tuan.yeu_cau_phoi_hop(ma, KD4, VH4, "Dựng 3 video", "Dựng video")
    with pytest.raises(ValueError):
        tuan.them_buoc(ma, v["id"], VH4, "Bước 1")


# ---------- nhận rồi: tự làm hoặc phân phối ----------

def test_nhan_roi_tu_lam(ma):
    v = tuan.yeu_cau_phoi_hop(ma, KD4, VH4, "Dựng 3 video", "Dựng video")
    tuan.nhan_viec(ma, v["id"], VH4)
    tuan.them_buoc(ma, v["id"], VH4, "Dựng thô")
    assert tuan.viec_cua(ma, "vh4")[0]["trang_thai"] == tuan.DANG_LAM


def test_nhan_roi_phan_phoi_cho_nguoi_bo_phan_minh(ma):
    v = tuan.yeu_cau_phoi_hop(ma, KD4, VH4, "Dựng 3 video", "Dựng video")
    tuan.nhan_viec(ma, v["id"], VH4)
    con = tuan.them_viec_giao(ma, VH4, VH2, "Dựng tập 1", "Dựng video", tu_yeu_cau=v["id"])
    assert con["tu_yeu_cau"] == v["id"]
    assert [c["id"] for c in tuan.viec_con(ma, v["id"])] == [con["id"]]


def test_phan_phoi_van_theo_luat_giao_viec_thuong(ma):
    """Nhận việc phối hợp KHÔNG cho quyền giao sang bộ phận khác."""
    v = tuan.yeu_cau_phoi_hop(ma, KD4, VH4, "Dựng 3 video", "Dựng video")
    tuan.nhan_viec(ma, v["id"], VH4)
    with pytest.raises(PermissionError):
        tuan.them_viec_giao(ma, VH4, KD2, "Việc lạc", "Dựng video", tu_yeu_cau=v["id"])


def test_giao_viec_con_qua_api(ma):
    v = tuan.yeu_cau_phoi_hop(ma, KD4, VH4, "Dựng 3 video", "Dựng video")
    tuan.nhan_viec(ma, v["id"], VH4)
    r = client.post("/api-tasky/giao", headers=H_VH4,
                    data={"nguoi": "vh2", "tieu_de": "Dựng tập 1", "loai_viec": "Dựng video",
                          "tu_yeu_cau": v["id"], "tuan_xem": ma})
    assert r.status_code == 200 and len(tuan.viec_con(ma, v["id"])) == 1


# ---------- nghiệm thu: BÊN YÊU CẦU ----------

def test_ben_lam_khong_tu_nghiem_thu_duoc(ma):
    v = tuan.yeu_cau_phoi_hop(ma, KD4, VH4, "Dựng 3 video", "Dựng video")
    tuan.nhan_viec(ma, v["id"], VH4)
    tuan.bao_xong(ma, v["id"], VH4)
    with pytest.raises(PermissionError):
        tuan.xac_nhan_viec(ma, v["id"], VH4)      # dù VH4 là L4 và là chủ việc


def test_ben_yeu_cau_nghiem_thu(ma):
    v = tuan.yeu_cau_phoi_hop(ma, KD4, VH4, "Dựng 3 video", "Dựng video")
    tuan.nhan_viec(ma, v["id"], VH4)
    tuan.bao_xong(ma, v["id"], VH4)
    assert tuan.xac_nhan_viec(ma, v["id"], KD4)["trang_thai"] == tuan.XAC_NHAN


def test_ben_yeu_cau_tra_lai_duoc(ma):
    v = tuan.yeu_cau_phoi_hop(ma, KD4, VH4, "Dựng 3 video", "Dựng video")
    tuan.nhan_viec(ma, v["id"], VH4)
    tuan.bao_xong(ma, v["id"], VH4)
    tuan.tra_lai_viec(ma, v["id"], KD4, "Thiếu phụ đề")
    assert tuan.viec_cua(ma, "vh4")[0]["trang_thai"] == tuan.DANG_LAM


# ---------- tính công cho bên làm ----------

def test_cong_tinh_cho_ben_lam_khong_tinh_ben_nho(ma):
    v = tuan.yeu_cau_phoi_hop(ma, KD4, VH4, "Dựng 3 video", "Dựng video")
    tuan.nhan_viec(ma, v["id"], VH4)
    tuan.bao_xong(ma, v["id"], VH4)
    tuan.xac_nhan_viec(ma, v["id"], KD4)
    assert tuan.thong_ke_nguoi(ma, "vh4")["ti_le"] == 100
    assert tuan.thong_ke_nguoi(ma, "vh4")["phoi_hop"] == 1
    assert tuan.thong_ke_nguoi(ma, "kd4")["ti_le"] is None      # bên nhờ không ăn theo số


def test_yeu_cau_bi_tu_choi_khong_vao_mau_so_ben_nhan(ma):
    v = tuan.yeu_cau_phoi_hop(ma, KD4, VH4, "Dựng 3 video", "Dựng video")
    tuan.tu_choi_viec(ma, v["id"], VH4, "Đang quá tải")
    t = tuan.thong_ke_nguoi(ma, "vh4")
    assert t["so_viec"] == 0 and t["bi_tu_choi"] == 1


# ---------- thông báo hai phía ----------

def test_ben_nhan_duoc_bao_co_yeu_cau(ma):
    tuan.yeu_cau_phoi_hop(ma, KD4, VH4, "Dựng 3 video", "Dựng video")
    ds = tb.cua_toi(ma, VH4)
    assert any("yêu cầu phối hợp" in m["chu"] for m in ds)


def test_ben_gui_duoc_bao_khi_bi_tu_choi_va_khi_cho_nghiem_thu(ma):
    v = tuan.yeu_cau_phoi_hop(ma, KD4, VH4, "Việc A", "Dựng video")
    tuan.tu_choi_viec(ma, v["id"], VH4, "Quá tải")
    assert any("bị bộ phận kia từ chối" in m["chu"] for m in tb.cua_leader(ma, KD4, SO))

    v2 = tuan.yeu_cau_phoi_hop(ma, KD4, VH4, "Việc B", "Dựng video")
    tuan.nhan_viec(ma, v2["id"], VH4)
    tuan.bao_xong(ma, v2["id"], VH4)
    assert any("chờ bạn nghiệm thu" in m["chu"] for m in tb.cua_leader(ma, KD4, SO))


# ---------- hiển thị ----------

def test_man_viec_hien_nhom_phoi_hop_rieng(ma):
    tuan.yeu_cau_phoi_hop(ma, KD4, VH4, "Dựng 3 video cho chiến dịch", "Dựng video")
    r = client.get("/tasky", headers=H_VH4)
    assert "Phối hợp liên bộ phận" in r.text and "Chờ bạn đồng ý phối hợp" in r.text
    assert "Đồng ý phối hợp" in r.text


def test_ben_gui_theo_doi_duoc_trang_thai(ma):
    """Yêu cầu gửi từ trong Goal thì gắn vào Goal — theo dõi ngay trong cây đó."""
    from src import muc_tieu as mt_lo
    g = g = mt_lo.tao(KD4, "Goal KD", "kết quả")
    v = tuan.yeu_cau_phoi_hop(ma, KD4, VH4, "Dựng 3 video", "Dựng video",
                              muc_tieu_id=g["id"])
    tuan.tu_choi_viec(ma, v["id"], VH4, "Đang chạy 8 video Life In")
    r = client.get("/task?goal=" + g["id"], headers=H_KD4)
    assert "từ chối" in r.text and "Đang chạy 8 video Life In" in r.text
