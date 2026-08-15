"""Test trang NAS công ty (01-05/08/2026): chỉ hiện khi ĐÃ cấu hình NAS_DUONG_DAN
(không chìa đường dẫn giả); mọi người có claims đều xem được; nút copy phải có đường
lui execCommand (LAN HTTP không có clipboard API — bài học sự cố chat 01/08);
ổ NAS_RIENG_MANAGER ẩn hẳn với cấp thấp; smb:// quote tên share có dấu cách.

DI TRÚ V2: đăng nhập → CLAIMS gateway; bỏ các assert sidebar /lich-su /hoi-dap
(trang của app tri-thuc, không thuộc app này). Mạch nas_sync (tài khoản Windows
đồng bộ) chưa mang sang — trang luôn chạy nhánh copy/map-ổ như hệ cũ lúc chưa bật
đồng bộ; /nas/cai-dat/{so} vẫn phát .bat (file tự hỏi mật khẩu, không chứa gì mật)."""

from fastapi.testclient import TestClient

from src.main import app


def _login(ten="nv", level=1):
    return TestClient(app, headers={"X-Remote-User": ten,
                                    "X-Remote-Level": str(level),
                                    "X-Remote-Role": "viewer"})


def test_chua_cau_hinh_thi_an_han():
    c = _login()
    assert c.get("/nas").status_code == 404          # không có gì để chỉ đường


def test_cau_hinh_roi_moi_nguoi_deu_thay(monkeypatch):
    monkeypatch.setenv("NAS_DUONG_DAN", r"\\192.168.1.99\kho-chung")
    c = _login()                                     # level 1 — thấp nhất vẫn thấy
    b = c.get("/nas").text
    assert r"\\192.168.1.99\kho-chung" in b          # đường dẫn thật hiện to rõ
    assert "Map network drive" in b                  # hướng dẫn map ổ
    assert "execCommand" in b                        # copy có đường lui (LAN HTTP)
    # kết nối cho máy Mac — smb:// dựng từ IP + tên share, nút mở Finder + ⌘K dự phòng
    assert "smb://192.168.1.99/kho-chung" in b
    assert "Kết nối trên Mac" in b and "⌘K" in b
    # có web UI thì thêm nút mở
    monkeypatch.setenv("NAS_WEB", "http://192.168.1.99:5000")
    assert "http://192.168.1.99:5000" in c.get("/nas").text


def test_o_rieng_manager_an_voi_cap_thap(monkeypatch):
    """05/08/2026: NAS_RIENG_MANAGER liệt kê tên ổ CHỈ Manager+ (level>=4) mới thấy
    thẻ — ẩn HẲN giao diện, không chỉ khóa nút."""
    monkeypatch.setenv("NAS_DUONG_DAN",
                       r"\\192.168.1.250\NAS1;\\192.168.1.250\Video")
    monkeypatch.setenv("NAS_RIENG_MANAGER", "NAS1")
    b = _login("nv", 1).get("/nas").text
    assert "NAS1" not in b and r"\\192.168.1.250\Video" in b   # ẩn hẳn, không lộ tên

    b2 = _login("mgr", 4).get("/nas").text
    assert "NAS1" in b2 and r"\\192.168.1.250\Video" in b2     # Manager thấy cả hai


def test_smb_quote_ten_share_co_khoang_trang(monkeypatch):
    """Tên share thật có dấu cách (vd 'OutlierY Nas 1') — smb:// phải quote đúng,
    không thì Mac dán vào Finder bị cắt cụt ở dấu cách."""
    monkeypatch.setenv("NAS_DUONG_DAN",
                       r"\\192.168.1.250\OutlierY Nas 1;\\192.168.1.250\Video")
    b = _login().get("/nas").text
    assert "smb://192.168.1.250/OutlierY%20Nas%201" in b
    assert "smb://192.168.1.250/Video" in b


def test_bat_cai_dat_dung_o_va_khong_chua_mat_khau(monkeypatch):
    """/nas/cai-dat/{so} phát file .bat gắn ổ: đúng chữ ổ, đúng tài khoản in sẵn,
    KHÔNG bao giờ chứa mật khẩu (cmdkey /pass tự hỏi lúc chạy)."""
    monkeypatch.setenv("NAS_DUONG_DAN",
                       r"\\192.168.1.250\NAS1;\\192.168.1.250\Video")
    c = _login("thanh", 2)
    r = c.get("/nas/cai-dat/1")
    assert r.status_code == 200
    b = r.text
    assert "net use Z:" in b                          # ổ thứ 2 → chữ Z (YZXWVU)
    assert r"192.168.1.250\thanh" in b                # tài khoản cá nhân hóa
    assert "/pass" in b and "mat khau" in b.lower()   # tự hỏi, không nhúng
    assert c.get("/nas/cai-dat/9").status_code == 404 # ổ không tồn tại


def test_chua_dang_nhap_khong_xem_duoc(monkeypatch):
    monkeypatch.setenv("NAS_DUONG_DAN", r"\\192.168.1.99\kho-chung")
    r = TestClient(app).get("/nas", follow_redirects=False)
    assert r.status_code == 401   # V2: thiếu claims gateway → 401 (login là việc gateway)
