# -*- coding: utf-8 -*-
"""HỆ KIỂM LOGIC video-review (02/09/2026) — cửa kiểm GET /api/kiem/{ma}.

Rà 02/09: app có 24 route mà chỉ 2 kịch bản, cả hai đo HẠ TẦNG — không phép nào
chạm nghiệp vụ. Sai một chốt ở đây là MẤT BẢN GỐC trên kho công ty (NAS không có
Recycle Bin) hoặc leader mất tín hiệu bản dựng đang chờ duyệt.
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
    assert ngoai.get("/api/kiem/canh-bao-codec").status_code == 404


def test_van_tay_chi_tin_dung_luong():
    """mtime lệch một mình = lành tính (sự cố 26/08); dung lượng khác mới báo."""
    b = _kiem("van-tay-dung-luong")
    assert b["mtime_lech_khong_bao"] is True
    assert b["dung_luong_khac_thi_bao"] is True


def test_ngoai_goc_bi_chan():
    b = _kiem("ngoai-goc-404")
    assert b["so_ca"] >= 3 and b["so_sai"] == 0


def test_canh_bao_h265():
    """hevc lọt vào CODEC_PHAT_DUOC = tắt cảnh báo toàn hệ, canary hạ tầng mù."""
    b = _kiem("canh-bao-codec")
    assert b["so_sai"] == 0 and b["hevc_khong_trong_bang"] is True


def test_xoa_an_toan():
    b = _kiem("xoa-an-toan")
    assert b["khong_xoa_du_an_dung"] is True
    assert b["feedback_dung_mot_ten"] is True
    assert b["dung_3_nac"] is True


def test_phat_206_khuc():
    b = _kiem("phat-206-khuc")
    assert b["trong_tran"] is True
