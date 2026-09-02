# -*- coding: utf-8 -*-
"""HỆ KIỂM LOGIC tasky (02/09/2026) — cửa kiểm GET /api/kiem/{ma}.

Rà 02/09 (Owner: "chạy lại từng app để không bỏ sót"): tasky có 42 route mà
CHỈ MỘT kịch bản canary — và kịch bản đó dùng `!= loi` trên module chỉ hạ
`canh_bao` nên VĨNH VIỄN XANH. Tức cả app thực tế không được canh dòng nào.

Bảy mã dưới đóng các logic sai-lặng-lẽ nặng nhất: luật quyền (ai giao được cho
ai), van chống bịa tỉ lệ (0% giả làm hỏng đánh giá nhân sự), và chặn tệp thực
thi. Tất cả là hàm thuần → 0 quota, không đụng sổ thật.
"""
from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app, client=("127.0.0.1", 50000))


def _kiem(ma):
    r = client.get(f"/api/kiem/{ma}")
    assert r.status_code == 200, r.text
    return r.json()


def test_ma_la_404():
    assert client.get("/api/kiem/khong-co").status_code == 404


def test_khong_loopback_404():
    ngoai = TestClient(app, client=("192.168.1.9", 1))
    assert ngoai.get("/api/kiem/luat-giao-viec").status_code == 404


def test_luat_giao_viec():
    """Level cao giao level thấp CÙNG bộ phận; ngang cấp KHÔNG giao được nhau.
    Lỏng → người bộ phận khác giao việc chéo, không ai chịu trách nhiệm."""
    b = _kiem("luat-giao-viec")
    assert b["so_ca"] >= 6 and b["so_sai"] == 0


def test_phoi_hop_ngang():
    """Phối hợp ngang: cả hai L3+, KHÁC bộ phận, chênh ≤1 bậc. Sai → nhân viên
    thường 'yêu cầu' người bộ phận khác = đường giao việc lách luật."""
    b = _kiem("phoi-hop-ngang")
    assert b["so_ca"] >= 5 and b["so_sai"] == 0


def test_van_chong_bia_ti_le():
    """Mẫu số rỗng → ti_le = None, KHÔNG phải 0%. Trả 0% thì người chưa được
    giao việc nào bị chấm '0% hoàn thành' — đánh giá nhân sự sai."""
    b = _kiem("van-ti-le")
    assert b["mau_so_rong_la_none"] is True
    assert b["dashboard_rong_la_none"] is True


def test_nghiem_thu_dung_nguoi():
    """Chỉ người GIAO nghiệm thu; việc phối hợp thì BÊN YÊU CẦU ký — bên làm
    không tự ký cho mình, nếu không việc luôn 'hoàn thành'."""
    b = _kiem("nghiem-thu-dung-nguoi")
    assert b["so_ca"] >= 4 and b["so_sai"] == 0


def test_chan_tep_thuc_thi():
    """Chặn 18 đuôi chạy được + trần dung lượng. Lọt .exe/.ps1 → Tasky thành
    đường phát tán mã độc nội bộ."""
    b = _kiem("chan-tep")
    assert b["so_ca"] >= 5 and b["so_sai"] == 0
    assert b["chan_duong_dan"] is True


def test_han_sai_noi_thang():
    """Hạn sai định dạng → báo lỗi, KHÔNG âm thầm bỏ. Bỏ qua thì người giao
    tưởng đã đặt hạn mà thật ra không có hạn nào."""
    b = _kiem("han-hop-le")
    assert b["so_ca"] >= 3 and b["so_sai"] == 0


def test_muc_tieu_khong_tu_dat():
    """Xong hết việc KHÔNG tự thành 'đạt' — người chốt, máy không tự. Máy tự
    chốt = mục tiêu công ty tự hoàn thành trên giấy."""
    b = _kiem("muc-tieu-nguoi-chot")
    assert b["tien_do_rong_la_none"] is True
    assert b["bat_ket_qua_can_dat"] is True
