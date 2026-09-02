"""HỆ KIỂM LOGIC ai-agent (02/09/2026) — cửa kiểm GET /api/kiem/{ma}.

Owner chốt "16 logic = 16 sơ đồ": mỗi logic nghiệp vụ một mã kiểm CHỈ-ĐỌC,
0 quota; canary tầng nền gọi rồi so kỳ vọng khai ngoài code. Route trả SỐ ĐO
THẬT, không tự phán đúng/sai.
"""
import os

os.environ["MOCK_MODE"] = "true"

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
    """Cửa kiểm chỉ mở cho loopback — cùng khuôn /api/so-goi."""
    ngoai = TestClient(app, client=("192.168.1.9", 1))
    assert ngoai.get("/api/kiem/viet-lai-cau").status_code == 404


def test_rbac_ma_tran_khop_luat():
    """RBAC một nguồn sự thật: ma trận user × chunk chạy qua _duoc_xem —
    van chống bịa quyền. Ca then chốt: min_level THIẾU → ẨN với user thật."""
    b = _kiem("rbac-ma-tran")
    assert b["so_ca"] >= 12
    assert b["so_sai"] == 0
    assert b["thieu_min_level_an"] is True
    assert b["owner_thay_tat"] is True


def test_van_kho_rong_khong_goi_model():
    """Van chống bịa lớp 1: kho trả 0 chunk → câu cố định, KHÔNG gọi model."""
    b = _kiem("van-kho-rong")
    assert b["tra_loi_co_dinh"] is True and b["so_lan_goi_model"] == 0


def test_viet_lai_cau_hoi_dung_ca():
    """Viết lại câu hỏi đa lượt: câu ngắn phụ thuộc ngữ cảnh → viết lại;
    câu dài tự đứng → KHÔNG tốn lượt model."""
    b = _kiem("viet-lai-cau")
    assert b["so_ca"] >= 3 and b["so_sai"] == 0


def test_mac_dinh_loc_noi_bo():
    """Hỏi–đáp thường PHẢI lọc tang_nguon=noi_bo — thiếu là tài liệu ngoài
    lẫn vào mọi câu trả lời mà không gắn nhãn (sai lặng lẽ)."""
    b = _kiem("mac-dinh-noi-bo")
    assert b["co_loc_noi_bo"] is True
    assert b["co_loc_hieu_luc"] is True


def test_qa_ke_thua_quyen():
    """Tài liệu -QA phải trùng KHỚP 4 cột quyền của tài liệu gốc."""
    b = _kiem("qa-ke-thua-quyen")
    assert b["so_lech"] == 0
