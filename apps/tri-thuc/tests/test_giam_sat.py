"""Test YC5 — cây giám sát tri thức: RBAC Manager-theo-bộ-phận / Owner-tất-cả,
trạng thái phiên ✅/⚠️, không rò nội dung trả lời."""

import os

os.environ["MOCK_MODE"] = "true"

from fastapi.testclient import TestClient

from src.main import app
from src.kho_thieu import ghi_cau_kho_thieu
from src.lich_su import luu_luot

# V2: claims từ gateway thay users.txt — bảng bộ phận×level giữ nguyên ý cũ.
from claims_v2 import client_claims

HO_SO = {"sep": ("Kinh doanh", 5), "ql_kd": ("Kinh doanh", 4),
         "nv_kd": ("Kinh doanh", 2), "ql_vh": ("Vận hành - Sản xuất", 4),
         "nv_vh": ("Vận hành - Sản xuất", 2)}


def _users(tmp_path, monkeypatch):
    """V2: không còn USERS_FILE — giữ chữ ký để call-site cũ nguyên vẹn (no-op)."""


def _login(ten):
    return client_claims(app, ten, *HO_SO[ten])


def _gieo():
    luu_luot("nv_kd", "câu kho thiếu KD?", "Tài liệu chưa nêu cụ thể điều này.",
             [], "T1", phien_id="ph-canh")                       # ⚠️ chưa đáp
    luu_luot("nv_kd", "đăng video?", "Đăng khung 19h [KD-2026-0042].",
             ["KD-2026-0042"], "T2", phien_id="ph-ok")           # ✅ đã đáp
    luu_luot("nv_vh", "câu bên VH?", "đáp VH", [], "T3", phien_id="ph-vh")
    # V2: cây giám sát dựng từ NGƯỜI CÓ LỊCH SỬ (app hết sổ user riêng) — gieo thêm
    # 1 lượt cho ql_vh để giữ nguyên ý test "Owner thấy tất cả mọi bộ phận".
    luu_luot("ql_vh", "câu của quản lý VH?", "đáp", [], "T4", phien_id="ph-qlvh")
    ghi_cau_kho_thieu("câu kho thiếu KD?", "Kinh doanh", [], "T1")  # nhánh lỗ hổng kho


def test_manager_khong_con_vao_duoc(tmp_path, monkeypatch):
    """31/07/2026 user ĐỔI LUẬT: Hoạt động team chuyển sang khối Management — CHỈ Owner
    xem (trước Manager thấy bộ phận mình)."""
    _users(tmp_path, monkeypatch)
    _gieo()
    assert _login("ql_kd").get("/giam-sat").status_code == 403
    assert _login("ql_vh").get("/giam-sat").status_code == 403


def test_owner_thay_tat_ca(tmp_path, monkeypatch):
    _users(tmp_path, monkeypatch)
    _gieo()
    r = _login("sep").get("/giam-sat")
    assert "nv_kd" in r.text and "nv_vh" in r.text and "ql_vh" in r.text


def test_nhan_vien_thuong_403(tmp_path, monkeypatch):
    _users(tmp_path, monkeypatch)
    assert _login("nv_kd").get("/giam-sat").status_code == 403


def test_trang_thai_phien_va_khong_ro_noi_dung_tra_loi(tmp_path, monkeypatch):
    _users(tmp_path, monkeypatch)
    _gieo()
    r = _login("sep").get("/giam-sat")             # 31/07: chỉ Owner vào được
    # phiên chưa đáp mang ⚠️, phiên đã đáp mang ✅ (cả 2 đều của nv_kd)
    assert "⚠️" in r.text and "✅" in r.text
    assert "câu kho thiếu KD?" in r.text                # câu hỏi hiện trong cây
    # KHÔNG show nội dung trả lời trong cây (user chốt — chống rò tài liệu)
    assert "Đăng khung 19h" not in r.text
    # Thu gọn 31/07/2026 (phương án A): giám sát chỉ TÓM TẮT lỗ hổng kho + link sang
    # /kho-thieu — nút Bổ sung tài liệu sống ở đó, một chức năng một chỗ
    assert 'href="/kho-thieu"' in r.text
    assert "Bổ sung tài liệu" in _login("ql_kd").get("/kho-thieu").text


# ---- dọn menu + gom nhóm ngay trong Giám sát (tái dùng YC7) ----

from src.kho_thieu import doc_nhom


def test_gom_nhom_da_don_ve_kho_thieu(tmp_path, monkeypatch):
    """Thu gọn 31/07/2026 (phương án A): form gom KHÔNG còn nhúng ở Giám sát — xử lý
    lỗ hổng kho sống MỘT nơi /kho-thieu; route ve=giam-sat giữ nguyên (bookmark cũ)."""
    _users(tmp_path, monkeypatch)
    _gieo()
    r = _login("sep").get("/giam-sat")                  # 31/07: giám sát chỉ Owner
    assert 'action="/kho-thieu/gom"' not in r.text      # trang giám sát hết form gom
    assert "câu kho chưa trả lời được" in r.text        # nhưng vẫn TÓM TẮT số câu chờ
    c = _login("ql_kd")                                 # gom nhóm vẫn việc của Manager+
    r2 = c.post("/kho-thieu/gom", follow_redirects=False,
                data={"ten_chu_de": "Nhóm từ giám sát", "cau": ["câu kho thiếu KD?"],
                      "ve": "giam-sat"})
    assert r2.status_code == 303
    assert r2.headers["location"] == "/giam-sat"        # route cũ vẫn quay về Giám sát
    assert doc_nhom()[0]["ten_chu_de"] == "Nhóm từ giám sát"   # cùng file nhóm YC7
    assert "Nhóm từ giám sát" in c.get("/kho-thieu").text      # nhóm hiện ở nơi duy nhất


def test_gom_khong_co_ve_van_ve_kho_thieu(tmp_path, monkeypatch):
    """Form cũ ở /kho-thieu không gửi 've' → hành vi cũ giữ nguyên."""
    _users(tmp_path, monkeypatch)
    r = _login("ql_kd").post("/kho-thieu/gom", follow_redirects=False,
                             data={"ten_chu_de": "x", "cau": ["y"]})
    assert r.headers["location"] == "/kho-thieu"


def test_menu_gon_giu_lich_su_bo_kho_thieu(tmp_path, monkeypatch):
    _users(tmp_path, monkeypatch)
    r = _login("ql_kd").get("/hoi-dap")
    # OUTLIERY: tab Monitoring cho Manager+ có Harvest/Monitoring/Team Add-ins;
    # Home luôn có lối lịch sử. Ý nghĩa test = phân quyền menu + route (giữ nguyên).
    assert 'data-pane="mon"' in r.text and "lịch sử" in r.text.lower()

    c_nv = _login("nv_kd")
    r_nv = c_nv.get("/hoi-dap")
    assert 'data-pane="mon"' not in r_nv.text          # tab quản trị ẩn với level thấp
    assert "lịch sử" in r_nv.text.lower()               # vẫn có lối xem lịch sử của mình
    assert c_nv.get("/lich-su").status_code == 200      # lịch sử mình: vào được
    assert c_nv.get("/giam-sat").status_code == 403     # giám sát: chặn
    # route /kho-thieu GIỮ NGUYÊN cho bookmark/link cũ — chỉ bỏ khỏi menu
    assert _login("ql_kd").get("/kho-thieu").status_code == 200
