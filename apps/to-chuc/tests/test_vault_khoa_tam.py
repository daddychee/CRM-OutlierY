# -*- coding: utf-8 -*-
"""GĐ3 — VAULT: khóa tạm sau nhiều lần sai mật khẩu chủ (05/09/2026).

LỖ A4 (rà 05/09): `mo_bang_master` chỉ ghi audit khi sai rồi `return False` — thử
lại vô hạn. Rào cản duy nhất là scrypt (~150ms). Trên Internet, script chạy song
song nhiều luồng sẽ dò được mật khẩu chủ yếu.

Tệ hơn: scrypt maxmem 128MB × nhiều request song song = **DoS cạn RAM**. Và
`_kiem_safekey` duyệt CẢ SỔ, chạy scrypt cho từng bản ghi → 10 lần scrypt mỗi
request = đòn bẩy DoS ~1.5 giây CPU.

Luật: sai liên tiếp N lần → khóa tạm, thời gian TĂNG DẦN. Mở đúng → xóa bộ đếm.
"""
import pytest

from src import vault


@pytest.fixture(autouse=True)
def _sach(tmp_path, monkeypatch):
    monkeypatch.setenv("VAULT_DIR", str(tmp_path / "vault"))
    vault.khoa()
    vault.xoa_bo_dem_sai()
    yield
    vault.khoa()
    vault.xoa_bo_dem_sai()


def _tao():
    vault.tao_vault("mat-khau-chu-du-dai", "owner_a")


def test_sai_du_nguong_thi_khoa_tam():
    _tao()
    for _ in range(vault.SO_LAN_SAI_TOI_DA):
        assert vault.mo_bang_master("sai-mat-khau", "owner_a") is False
    # Lần kế tiếp bị chặn TRƯỚC khi chạy scrypt — kể cả mật khẩu ĐÚNG
    with pytest.raises(PermissionError):
        vault.mo_bang_master("mat-khau-chu-du-dai", "owner_a")


def test_mo_dung_xoa_bo_dem():
    _tao()
    vault.mo_bang_master("sai", "owner_a")
    assert vault.mo_bang_master("mat-khau-chu-du-dai", "owner_a") is True
    assert vault.so_lan_sai("owner_a") == 0


def test_bo_dem_theo_tung_nguoi():
    """owner_a gõ sai không được làm owner_b bị khóa lây."""
    _tao()
    for _ in range(vault.SO_LAN_SAI_TOI_DA):
        vault.mo_bang_master("sai", "owner_a")
    assert vault.mo_bang_master("mat-khau-chu-du-dai", "owner_b") is True
