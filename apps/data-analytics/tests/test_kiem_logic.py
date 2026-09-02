# -*- coding: utf-8 -*-
"""HỆ KIỂM LOGIC data-analytics (02/09/2026) — cửa kiểm GET /api/kiem/{ma}.

Rà lại 02/09 (Owner: "chạy lại từng app để không bỏ sót") phát hiện app chỉ có
2 kịch bản canary, cả hai đều đọc cờ hạ tầng — KHÔNG logic nghiệp vụ nào được
canh, trong khi engine là nơi ra PHÁN QUYẾT cho người dùng.

Sáu mã dưới đây đóng các logic sai-lặng-lẽ nặng nhất. Engine thuần Python nên
mọi phép kiểm là 0 quota / 0 tiền tự nhiên.
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
    """Cửa kiểm chỉ mở cho loopback — cùng khuôn radary/ai-agent."""
    ngoai = TestClient(app, client=("192.168.1.9", 1))
    assert ngoai.get("/api/kiem/phan-quyet-huu-han").status_code == 404


def test_phan_quyet_huu_han():
    """7 phán quyết là tập ĐÓNG: engine không được sinh giá trị ngoài tập.
    Quét mọi tổ hợp 4 trục × 4 trạng thái — 'cỗ máy đẻ luật' là rủi ro thật khi
    ai đó thêm nhánh return mới."""
    b = _kiem("phan-quyet-huu-han")
    assert b["so_to_hop"] >= 200
    assert b["so_ngoai_tap"] == 0
    assert b["thieu_du_lieu_luon_dung"] is True


def test_anh_xa_he_so_don_vi():
    """Hệ số %→tỷ lệ: sai là MỌI ngưỡng lệch 100 lần, không luật nào khớp,
    báo cáo trắng mà HTTP vẫn 200. Report EN và VN phải ra cùng biến."""
    b = _kiem("anh-xa-don-vi")
    assert b["ctr_dung_don_vi"] is True
    assert b["en_va_vn_cung_bien"] is True


def test_van_mau_nho():
    """Van chống bịa cỡ mẫu ĐỘNG max(100, 10% median): video 40 view không
    được chấm — phán quyết trên nhiễu thống kê là bịa có vẻ khoa học."""
    b = _kiem("van-mau-nho")
    assert b["so_ca"] >= 5 and b["so_sai"] == 0


def test_baseline_khai_nguon():
    """Baseline 3 lớp phải KHAI nguồn đang so + lùi đúng khi nhóm thiếu mẫu —
    không khai thì LLM viết 'so với kênh' trong khi số là nhóm độ dài."""
    b = _kiem("baseline-nguon")
    assert b["so_ca"] >= 3 and b["so_sai"] == 0
    assert b["luon_khai_nguon"] is True


def test_che_do_chi_so_khong_ro_phan_quyet():
    """Kênh chưa monetize → chế độ chỉ-số: TUYỆT ĐỐI không phán quyết, không
    gọi LLM. Rò một phán quyết là đưa lời khuyên trên dữ liệu vô nghĩa."""
    b = _kiem("che-do-chi-so")
    assert b["che_do"] == "chi_so"
    assert b["so_phan_quyet_ro_ri"] == 0


def test_so_sanh_ky_chan_chong_lan():
    """Bẫy cửa sổ trượt: 2 report 28 ngày cách nhau 1 tuần chồng 21 ngày —
    so ngây thơ ra 'tăng trưởng' hoàn toàn ảo mà không dấu hiệu nào là sai."""
    b = _kiem("so-sanh-ky")
    assert b["so_ca"] >= 4 and b["so_sai"] == 0
    assert b["bat_duoc_chong_lan"] is True
