# -*- coding: utf-8 -*-
"""GĐ3 — VAULT: trạng thái mở gắn với NGƯỜI MỞ (05/09/2026).

LỖ A3 (rà 05/09, sổ `docs/bao-mat-internet.md`): `_DEK`/`_HET_HAN` là biến
module-level, `_dek_dang_mo()` chỉ hỏi "vault có đang mở không", KHÔNG hỏi AI mở.

Hệ cho phép NHIỀU Owner (`iam.py:191`). Nên: Owner A nhập mật khẩu chủ mở két →
trong 600 giây, Owner B (hoặc ai chiếm được phiên của một Owner bất kỳ) lặp
`POST /vault/xem` đọc SẠCH mọi mật khẩu **mà không cần biết mật khẩu chủ**.
Audit có ghi tên kẻ đó — nhưng là ghi nhận SAU KHI MẤT.

→ Cửa thứ hai (mật khẩu chủ) trên thực tế bị vô hiệu với mọi Owner không phải
người mở. Vault chỉ còn MỘT cửa = phiên đăng nhập.

Luật đúng: DEK chỉ phục vụ CHÍNH người đã nhập mật khẩu chủ.
"""
import pytest

from src import vault


@pytest.fixture(autouse=True)
def _kho_sach(tmp_path, monkeypatch):
    monkeypatch.setenv("VAULT_DIR", str(tmp_path / "vault"))
    vault.khoa()
    yield
    vault.khoa()


def _tao():
    return vault.tao_vault("mat-khau-chu-du-dai", "owner_a")


def test_nguoi_mo_doc_duoc(tmp_path):
    _tao()
    assert vault.mo_bang_master("mat-khau-chu-du-dai", "owner_a") is True
    assert vault.doc_muc(ai="owner_a") is not None


def test_OWNER_KHAC_khong_doc_duoc_ket_dang_mo(tmp_path):
    """TRỌNG TÂM: trước bản vá, owner_b đọc sạch két do owner_a mở."""
    _tao()
    vault.mo_bang_master("mat-khau-chu-du-dai", "owner_a")
    assert vault.doc_muc(ai="owner_b") is None, \
        "Owner khác vẫn đọc được két do người khác mở"


def test_owner_khac_khong_xem_duoc_mat_khau(tmp_path):
    _tao()
    vault.mo_bang_master("mat-khau-chu-du-dai", "owner_a")
    vault.them_hoac_sua_muc("owner_a", "", "google", "Tài khoản A",
                            "a@x.com", "mk-bi-mat", "")
    muc = vault.doc_muc(ai="owner_a")
    with pytest.raises(PermissionError):
        vault.xem_mat_khau("owner_b", muc[0]["id"])


def test_owner_khac_khong_them_sua_xoa_duoc(tmp_path):
    _tao()
    vault.mo_bang_master("mat-khau-chu-du-dai", "owner_a")
    with pytest.raises(PermissionError):
        vault.them_hoac_sua_muc("owner_b", "", "google", "X", "u", "p", "")


def test_owner_b_tu_mo_thi_doc_duoc(tmp_path):
    """Không siết quá tay: owner_b biết mật khẩu chủ thì vẫn dùng được."""
    _tao()
    vault.mo_bang_master("mat-khau-chu-du-dai", "owner_a")
    assert vault.mo_bang_master("mat-khau-chu-du-dai", "owner_b") is True
    assert vault.doc_muc(ai="owner_b") is not None
