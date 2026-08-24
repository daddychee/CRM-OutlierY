# -*- coding: utf-8 -*-
"""Test nen/common/nas_sync.py — DI TRÚ từ agent-app hệ cũ (src/nas_sync.py),
đơn giản hơn MỘT điểm có chủ đích: dong_bo_nen() nhận `nhom` làm THAM SỐ (bên
gọi — gateway — đã tính qua iam.co_quyen), module này không biết gì về IAM.

An toàn là luật số 1: KHÔNG BAO GIỜ để test gọi subprocess thật (tạo/đổi tài
khoản Windows) — mọi test tự monkeypatch subprocess.run trước khi gọi hàm nào
có thể bắn PowerShell.
"""
import os
import subprocess

import bcrypt
import pytest

from nen.common import nas_sync


@pytest.fixture(autouse=True)
def _sach(tmp_path, monkeypatch):
    """Mỗi test một đời 'tiến trình' sạch + sổ trỏ tmp + CHẶN subprocess thật
    làm mặc định — test nào cần thì tự monkeypatch đè bằng fake của nó."""
    monkeypatch.setenv("NAS_SO_DUONG", str(tmp_path / "nas-dong-bo.json"))
    monkeypatch.setenv("NAS_DONG_BO", "false")
    nas_sync._da_dong_bo_phien.clear()

    def _no(*a, **k):  # pragma: no cover - chỉ nổ khi test quên mock
        raise AssertionError("Test không được gọi subprocess thật!")
    monkeypatch.setattr(nas_sync.subprocess, "run", _no)
    yield
    nas_sync._da_dong_bo_phien.clear()


def _fake_run(ghi, returncode=0, stderr=""):
    def run(args, env=None, **k):
        ghi.append({"args": args, "env": dict(env or {})})
        return subprocess.CompletedProcess(args, returncode, stdout="", stderr=stderr)
    return run


# ---- công tắc + hàng rào tên ----

def test_cong_tac_tat_la_no_op():
    nas_sync._dong_bo("ngocht", "Mk12345", nas_sync.NHOM_CHI_THEM)  # run=nổ → qua là đúng
    nas_sync.dong_bo_nen("ngocht", "Mk12345", nas_sync.NHOM_CHI_THEM)
    assert nas_sync.trang_thai("ngocht") == "tat"
    assert not nas_sync._duong_so().exists()


def test_ten_he_thong_bi_chan(monkeypatch):
    monkeypatch.setenv("NAS_DONG_BO", "true")
    ghi = []
    monkeypatch.setattr(nas_sync.subprocess, "run", _fake_run(ghi))
    for ten in ["Administrator", "GUEST", "nhanvien", "có dấu", "a b", ":x",
                "1batdau", "", "dai-qua-hai-muoi-ky-tu-x"]:
        nas_sync._dong_bo(ten, "Mk12345", nas_sync.NHOM_CHI_THEM)
    assert ghi == []


# ---- lõi đồng bộ ----

def test_dong_bo_ok_mat_khau_khong_len_command_line(monkeypatch):
    monkeypatch.setenv("NAS_DONG_BO", "true")
    ghi = []
    monkeypatch.setattr(nas_sync.subprocess, "run", _fake_run(ghi))

    nas_sync._dong_bo("ngocht", "Mk12345", nas_sync.NHOM_CHI_THEM)
    nas_sync._dong_bo("namtn", "Mk67890", nas_sync.NHOM_TOAN_QUYEN)

    assert len(ghi) == 2
    assert ghi[0]["env"]["OUTLIERY_NAS_NHOM"] == nas_sync.NHOM_CHI_THEM
    assert ghi[1]["env"]["OUTLIERY_NAS_NHOM"] == nas_sync.NHOM_TOAN_QUYEN
    # Mật khẩu đi qua ENV, TUYỆT ĐỐI không nằm trên command line
    for goi, mk in zip(ghi, ["Mk12345", "Mk67890"]):
        assert goi["env"]["OUTLIERY_NAS_MK"] == mk
        assert mk not in " ".join(goi["args"])
    so = nas_sync._doc_so()
    assert so["ngocht"]["trang_thai"] == "ok"
    assert so["ngocht"]["nhom"] == nas_sync.NHOM_CHI_THEM
    assert bcrypt.checkpw(b"Mk12345", so["ngocht"]["hash"].encode())
    assert nas_sync.trang_thai("ngocht") == "ok"


def test_khong_goi_lai_khi_mat_khau_va_nhom_khong_doi(monkeypatch):
    monkeypatch.setenv("NAS_DONG_BO", "true")
    ghi = []
    monkeypatch.setattr(nas_sync.subprocess, "run", _fake_run(ghi))
    nas_sync._dong_bo("ngocht", "Mk12345", nas_sync.NHOM_CHI_THEM)
    nas_sync._dong_bo("ngocht", "Mk12345", nas_sync.NHOM_CHI_THEM)   # lặp — đi đường tắt
    assert len(ghi) == 1
    nas_sync._dong_bo("ngocht", "MkMoi999", nas_sync.NHOM_CHI_THEM)  # mật khẩu đổi → gọi lại
    assert len(ghi) == 2
    nas_sync._dong_bo("ngocht", "Mk12345", nas_sync.NHOM_TOAN_QUYEN)  # nhóm đổi → gọi lại
    assert len(ghi) == 3


def test_mk_yeu_bi_windows_tu_choi(monkeypatch):
    monkeypatch.setenv("NAS_DONG_BO", "true")
    monkeypatch.setattr(nas_sync.subprocess, "run", _fake_run(
        [], returncode=1,
        stderr="Set-LocalUser : The password does not meet the password policy requirements."))
    nas_sync._dong_bo("ngocht", "yeu123", nas_sync.NHOM_CHI_THEM)
    assert nas_sync.trang_thai("ngocht") == "mk_yeu"


def test_mk_yeu_dang_invalidpasswordexception(monkeypatch):
    """PS 5.1 chỉ ném 'InvalidPasswordException' (không có câu 'password does not
    meet') — phải nhận diện là mk_yeu, không phải lỗi chung."""
    monkeypatch.setenv("NAS_DONG_BO", "true")
    monkeypatch.setattr(nas_sync.subprocess, "run", _fake_run(
        [], returncode=1,
        stderr="New-LocalUser : Exception of type "
               "'Microsoft.PowerShell.Commands.InvalidPasswordException' was thrown."))
    nas_sync._dong_bo("thanhtho", "yeu123", nas_sync.NHOM_CHI_THEM)
    assert nas_sync.trang_thai("thanhtho") == "mk_yeu"


def test_loi_he_thong_ghi_chi_tiet_khong_lo_mat_khau(monkeypatch):
    monkeypatch.setenv("NAS_DONG_BO", "true")
    monkeypatch.setattr(nas_sync.subprocess, "run", _fake_run(
        [], returncode=1, stderr="Access is denied."))
    nas_sync._dong_bo("ngocht", "MatKhauBiMat1", nas_sync.NHOM_CHI_THEM)
    assert nas_sync.trang_thai("ngocht") == "loi"
    so = nas_sync._doc_so()
    assert "MatKhauBiMat1" not in so["ngocht"]["chi_tiet"]


def test_timeout_ghi_loi_khong_vo(monkeypatch):
    monkeypatch.setenv("NAS_DONG_BO", "true")

    def no(*a, **k):
        raise subprocess.TimeoutExpired(cmd="powershell", timeout=120)
    monkeypatch.setattr(nas_sync.subprocess, "run", no)
    nas_sync._dong_bo("ngocht", "Mk12345", nas_sync.NHOM_CHI_THEM)
    assert nas_sync.trang_thai("ngocht") == "loi"


# ---- chuẩn mật khẩu ----

def test_chuan_mat_khau():
    assert not nas_sync.mat_khau_dat_chuan("matkhaurieng123")   # thiếu chữ HOA
    assert not nas_sync.mat_khau_dat_chuan("Abc123")            # ngắn
    assert nas_sync.mat_khau_dat_chuan("Abc12345")
    # Luật ngầm Windows: chứa tên đăng nhập là bị chối dù đủ mạnh
    assert not nas_sync.mat_khau_dat_chuan("Thanh12345", ten="thanh")
    assert nas_sync.mat_khau_dat_chuan("Abc12345", ten="thanh")


# ---- gọi nền không chặn ----

def test_dong_bo_nen_ban_thread_khong_cho(monkeypatch):
    monkeypatch.setenv("NAS_DONG_BO", "true")
    ghi = []
    monkeypatch.setattr(nas_sync.subprocess, "run", _fake_run(ghi))
    nas_sync.dong_bo_nen("ngocht", "Mk12345", nas_sync.NHOM_CHI_THEM)
    # Thread nền — đợi ngắn cho nó chạy xong trong test (không có I/O ngoài thật)
    import time
    for _ in range(50):
        if ghi:
            break
        time.sleep(0.02)
    assert len(ghi) == 1
