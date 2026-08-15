"""Test VAULT — kho tài khoản số mã hóa (31/07/2026).

Ghim các bất biến bảo mật: bản rõ KHÔNG BAO GIỜ chạm đĩa; mở cần đúng mật khẩu chủ;
safekey dùng MỘT lần cứu vault; chỉ Owner vào route; mọi thao tác nhạy cảm có vết audit.

DI TRÚ V2: đăng nhập → CLAIMS gateway (Owner = X-Remote-Level 5). VAULT_DIR trỏ tmp +
khóa DEK trước/sau mỗi test do conftest lo. BỎ 2 test đường /khoi-phuc (đặt lại mật
khẩu ĐĂNG NHẬP Owner bằng safekey — đường công khai đó đổi sổ user nên thuộc
IAM/gateway, chưa mang sang; hàm vault.dat_lai_mat_khau_owner vẫn nằm trong module
nhưng không route nào gọi — giữ nguyên chờ gateway nối)."""

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import src.vault as vault
from src.main import app

MASTER = "mat-khau-chu-du-dai-12"


def _login(ten, level):
    return TestClient(app, headers={"X-Remote-User": ten,
                                    "X-Remote-Level": str(level),
                                    "X-Remote-Role": "owner" if level == 5 else "viewer"})


# ═══ Lõi crypto ═══

def test_tao_vault_cap_10_safekey_dung_dinh_dang():
    keys = vault.tao_vault(MASTER, "sep")
    assert len(keys) == 10 and len(set(keys)) == 10
    for k in keys:
        phan = k.split("-")
        assert len(phan) == 4 and all(len(p) == 5 for p in phan)
        assert not set(k) & set("01OIL")          # bảng chữ tránh ký tự dễ chép nhầm
    assert vault.da_tao() and vault.so_safekey_con_lai() == 10
    with pytest.raises(ValueError):
        vault.tao_vault(MASTER, "sep")             # không tạo đè


def test_mat_khau_chu_ngan_bi_chan():
    with pytest.raises(ValueError):
        vault.tao_vault("ngan", "sep")


def test_ban_ro_khong_bao_gio_cham_dia():
    vault.tao_vault(MASTER, "sep")
    assert vault.mo_bang_master(MASTER, "sep")
    vault.them_hoac_sua_muc("sep", "", "google", "Kênh A", "keno@gmail.com",
                            "mk-bi-mat-XYZ", "ghi chú thường")
    tren_dia = (Path(os.environ["VAULT_DIR"]) / "vault.enc").read_bytes()
    assert b"mk-bi-mat-XYZ" not in tren_dia        # mật khẩu mục
    assert b"keno@gmail.com" not in tren_dia       # cả tài khoản cũng trong bản mã
    assert MASTER.encode() not in tren_dia         # mật khẩu chủ càng không


def test_mo_sai_mat_khau_chu_that_bai_va_co_audit():
    vault.tao_vault(MASTER, "sep")
    assert not vault.mo_bang_master("sai-mat-khau-chu-x", "sep")
    assert not vault.dang_mo()
    audit = (Path(os.environ["VAULT_DIR"]) / "audit.csv").read_text(encoding="utf-8-sig")
    assert "mo_vault_SAI_mat_khau" in audit


def test_them_sua_xoa_xem_muc_du_vong():
    vault.tao_vault(MASTER, "sep")
    vault.mo_bang_master(MASTER, "sep")
    id = vault.them_hoac_sua_muc("sep", "", "proxy", "Proxy US-1", "1.2.3.4:8080",
                                 "mk-proxy", "")
    # khóa rồi mở lại — dữ liệu bền qua chu kỳ khóa/mở
    vault.khoa()
    assert vault.doc_muc() is None                 # khóa → không đọc được
    vault.mo_bang_master(MASTER, "sep")
    assert vault.xem_mat_khau("sep", id) == "mk-proxy"
    # sửa nhưng bỏ trống mật khẩu = GIỮ mật khẩu cũ
    vault.them_hoac_sua_muc("sep", id, "proxy", "Proxy US-1 đổi tên", "1.2.3.4:8080", "", "note")
    assert vault.xem_mat_khau("sep", id) == "mk-proxy"
    vault.xoa_muc("sep", id)
    assert vault.doc_muc() == []


# ═══ Safekey: cứu vault, DÙNG MỘT LẦN ═══

def test_safekey_cuu_vault_va_vo_hieu_sau_dung():
    keys = vault.tao_vault(MASTER, "sep")
    vault.mo_bang_master(MASTER, "sep")
    vault.them_hoac_sua_muc("sep", "", "email", "Mail chính", "a@b.c", "mk-mail", "")
    vault.khoa()
    # quên mật khẩu chủ → 1 safekey đặt được mật khẩu chủ MỚI, dữ liệu còn nguyên
    assert vault.khoi_phuc_master(keys[0], "mat-khau-chu-moi-cung-dai", "sep")
    assert not vault.mo_bang_master(MASTER, "sep")                  # mật khẩu cũ hết tác dụng
    assert vault.mo_bang_master("mat-khau-chu-moi-cung-dai", "sep")
    muc = vault.doc_muc()
    assert len(muc) == 1 and vault.xem_mat_khau("sep", muc[0]["id"]) == "mk-mail"
    # key đó vô hiệu vĩnh viễn, còn 9
    assert vault.so_safekey_con_lai() == 9
    assert not vault.khoi_phuc_master(keys[0], "mat-khau-chu-moi-nua-x", "sep")


# ═══ Route + RBAC (claims) ═══

def test_chi_owner_vao_vault():
    assert _login("nv", 2).get("/vault").status_code == 403
    assert _login("ql", 4).get("/vault").status_code == 403    # Manager cũng KHÔNG — Owner tuyệt đối
    r = _login("sep", 5).get("/vault")
    assert r.status_code == 200 and "Vault chưa được khởi tạo" in r.text
    # thiếu claims gateway → 401
    assert TestClient(app).get("/vault").status_code == 401


def test_luong_route_tao_mo_them_xem():
    c = _login("sep", 5)
    r = c.post("/vault/tao", data={"master": MASTER, "master2": MASTER})
    assert r.text.count("-") >= 30                 # 10 safekey × 3 dấu gạch hiện MỘT lần
    c.post("/vault/mo", data={"master": MASTER})
    c.post("/vault/muc", data={"id": "", "nhom": "adsense", "ten": "AdSense chính",
                               "tai_khoan": "ads@x.com", "mat_khau": "mk-ads", "ghi_chu": ""})
    trang = c.get("/vault").text
    assert "AdSense chính" in trang and "mk-ads" not in trang   # trang KHÔNG nhúng mật khẩu
    muc = vault.doc_muc()
    r2 = c.post("/vault/xem", data={"id": muc[0]["id"]})
    assert r2.json()["mat_khau"] == "mk-ads"
    audit = (Path(os.environ["VAULT_DIR"]) / "audit.csv").read_text(encoding="utf-8-sig")
    assert "xem_mat_khau" in audit and "AdSense chính" in audit


def test_route_khoi_phuc_master_va_khoa():
    c = _login("sep", 5)
    r = c.post("/vault/tao", data={"master": MASTER, "master2": MASTER})
    # lấy safekey đầu từ trang vừa tạo (hiện đúng một lần)
    import re
    keys = re.findall(r"[2-9A-HJ-NP-TV-Z]{5}(?:-[2-9A-HJ-NP-TV-Z]{5}){3}", r.text)
    assert len(keys) == 10
    c.post("/vault/mo", data={"master": MASTER})
    assert c.post("/vault/khoa", follow_redirects=False).status_code == 303
    assert not vault.dang_mo()
    # quên mật khẩu chủ → safekey đặt mật khẩu mới qua route
    r2 = c.post("/vault/khoi-phuc-master",
                data={"safekey": keys[0], "master_moi": "mat-khau-moi-du-dai-1",
                      "master_moi2": "mat-khau-moi-du-dai-1"}, follow_redirects=False)
    assert r2.status_code == 303
    assert vault.so_safekey_con_lai() == 9
