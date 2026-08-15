"""Test CHẤM CÔNG (01/08/2026, user chốt "agent off tính là giờ out") — giờ vào =
tín hiệu ĐẦU ngày (điểm hứng lay_user, không phụ thuộc sự kiện đăng nhập); giờ ra =
tín hiệu CUỐI (request thật / nhịp tim / beacon đóng app); throttle 60s trừ tín hiệu
chủ đích; van trung thực: không có mặt → '—', khách chế độ mở không chấm.

DI TRÚ V2: đăng nhập → CLAIMS gateway; điểm hứng giờ nằm ở lay_user của app to-chuc
(mọi request có claims). BỎ test tín hiệu /dang-xuat — nút Đăng xuất thuộc gateway
(việc treo: gateway gọi ghi nhận 'dang_xuat' khi xóa phiên). BỎ test trang /nhan-su
(về IAM) — bảng chấm công giờ nằm trong /kpi, test ở test_kpi.py."""

from datetime import datetime

from fastapi.testclient import TestClient

from src import cham_cong as cc
from src.main import app


def _login(ten, level=4):
    return TestClient(app, headers={"X-Remote-User": ten,
                                    "X-Remote-Level": str(level),
                                    "X-Remote-Role": "manager"})


def test_module_vao_ra_throttle_va_nguon():
    t0 = datetime(2026, 8, 1, 8, 0, 0)
    cc.ghi_nhan("nv", luc=t0)
    n = cc.doc_ngay("2026-08-01")["nv"]
    assert n["vao"] == "08:00:00" and n["ra"] == "08:00:00"
    # 30s sau, tín hiệu thường → throttle KHÔNG ghi đĩa
    cc.ghi_nhan("nv", luc=datetime(2026, 8, 1, 8, 0, 30))
    assert cc.doc_ngay("2026-08-01")["nv"]["ra"] == "08:00:00"
    # 2 phút sau → ghi; GIỜ VÀO GIỮ NGUYÊN, giờ ra tiến lên
    cc.ghi_nhan("nv", luc=datetime(2026, 8, 1, 8, 2, 0))
    n = cc.doc_ngay("2026-08-01")["nv"]
    assert n["vao"] == "08:00:00" and n["ra"] == "08:02:00"
    # tín hiệu CHỦ ĐÍCH (đóng app) trong 60s vẫn ghi NGAY + nguồn đúng
    cc.ghi_nhan("nv", "dong_app", luc=datetime(2026, 8, 1, 8, 2, 10))
    n = cc.doc_ngay("2026-08-01")["nv"]
    assert n["ra"] == "08:02:10" and n["nguon_ra"] == "Đóng app"
    assert cc.tong_gio(n["vao"], n["ra"]) == "0g02"
    # sang NGÀY KHÁC là cặp vào/ra mới, ngày cũ không đổi
    cc.ghi_nhan("nv", luc=datetime(2026, 8, 2, 9, 0, 0))
    assert cc.doc_ngay("2026-08-02")["nv"]["vao"] == "09:00:00"
    assert cc.doc_ngay("2026-08-01")["nv"]["vao"] == "08:00:00"
    # khách (chế độ mở/dev) không chấm; tổng giờ thiếu dữ liệu → '' không bịa
    cc.ghi_nhan("khách", luc=t0)
    assert "khách" not in cc.doc_ngay("2026-08-01")
    assert cc.tong_gio(None, "08:00:00") == "" and cc.tong_gio("x", "y") == ""


def test_request_thuong_tu_cham_gio_vao():
    """Điểm hứng lay_user: chỉ cần MỞ TRANG bất kỳ (có claims) là có giờ vào —
    không phụ thuộc sự kiện đăng nhập (đăng nhập giờ là việc của gateway)."""
    _login("nv").get("/kpi")
    hom_nay = datetime.now().strftime("%Y-%m-%d")
    assert cc.doc_ngay(hom_nay)["nv"]["vao"]


def test_diem_hung_chay_ca_khi_route_loi():
    """Depends(lay_user) chạy TRƯỚC handler — trang 404 (NAS chưa cấu hình) vẫn
    chấm hiện diện, đúng tinh thần 'mọi request có danh tính đều là tín hiệu'."""
    c = _login("nv2", level=1)
    assert c.get("/nas").status_code == 404          # NAS_DUONG_DAN chưa cấu hình
    hom_nay = datetime.now().strftime("%Y-%m-%d")
    assert cc.doc_ngay(hom_nay)["nv2"]["vao"]


def test_nhip_thoat_va_chua_dang_nhap():
    c = _login("nv", level=1)
    assert c.post("/api/nhip").status_code == 204
    assert c.post("/api/nhip-thoat").status_code == 204          # beacon đóng app
    hom_nay = datetime.now().strftime("%Y-%m-%d")
    assert cc.doc_ngay(hom_nay)["nv"]["nguon_ra"] == "Đóng app"
    # chưa có claims → không ghi được (fetch POST → 401)
    assert TestClient(app).post("/api/nhip").status_code == 401
