# -*- coding: utf-8 -*-
"""Đồng bộ tài khoản NAS (Windows local user) theo tài khoản OUTLIERY — mảnh tầng
nền, DI TRÚ từ agent-app hệ cũ (src/nas_sync.py) theo Luật 1 (dữ liệu tách code)
+ Luật 4 (app chỉ import nen/common, không tự giữ mật khẩu/đường dữ liệu).

Triết lý GIỮ NGUYÊN hệ cũ: mỗi người một tài khoản Windows TRÙNG tên đăng nhập
OUTLIERY, mật khẩu CHÍNH LÀ mật khẩu OUTLIERY. SMB xác thực bằng tài khoản Windows
(không đọc được bcrypt của iam.db) nên đồng bộ chỉ làm được tại khoảnh khắc BIẾT
mật khẩu thật — GATEWAY gọi dong_bo_nen() ngay sau khi xác thực/đổi mật khẩu
thành công (xem nen/gateway/main.py), KHÔNG gọi từ app nghiệp vụ.

KHÁC hệ cũ MỘT ĐIỂM có chủ đích (đơn giản hóa nhờ IAM mới): `dong_bo_nen` nhận
`nhom` (tên nhóm Windows) làm THAM SỐ thay vì tự tính từ level — bên gọi (gateway)
đã có `iam.co_quyen(claims, "nas_cap_cao", "to-chuc", conn)` là MỘT CỬA quyết
định đúng/sai gồm cả ô tick lẻ + cấp truy cập (hieu_luc), nas_sync không cần biết
gì về bảng quyền của IAM — giữ module này thuần hạ tầng.

Nguyên tắc an toàn (giữ nguyên hệ cũ):
- Công tắc NAS_DONG_BO mặc định TẮT — máy dev/test không bao giờ đụng tài khoản
  Windows; chỉ máy server công ty bật.
- Mật khẩu sang PowerShell qua BIẾN MÔI TRƯỜNG của tiến trình con, không nằm
  trên command line, không ghi log.
- Chạy NỀN (thread daemon) — request không chờ PowerShell; mọi lời gọi ngoài có
  timeout.
- Tên hệ thống (Administrator, Guest, nhanvien…) CẤM đụng, tên phải đúng khuôn
  tài khoản Windows.
- Windows đang bật PasswordComplexity: mật khẩu yếu bị từ chối → ghi "mk_yeu"
  để trang /nas nói thẳng, không im lặng.

Sổ trạng thái data/nen/nas-dong-bo.json (ghi nguyên tử, Luật 6 — khai trong
nen/rules/apps.json mục du_lieu_nen):
  {ten: {"hash": bcrypt-của-mật-khẩu-đã-đồng-bộ, "trang_thai": "ok"|"mk_yeu"|"loi",
         "nhom": tên nhóm, "luc": ISO}}

VIỆC TREO (chưa mang sang — ghi rõ để không tưởng đã xong):
- doi_nhom_nen/vo_hieu_nen hệ cũ (đổi level qua trang quản trị / xóa tài khoản
  → đồng bộ lại nhóm / vô hiệu Windows) CHƯA nối vào iam.tao_tai_khoan/
  sua_tai_khoan/xoa_tai_khoan — người bị đổi cấp/khóa vẫn giữ quyền NAS cũ tới
  lần ĐĂNG NHẬP hoặc ĐỔI MẬT KHẨU kế tiếp. Nối đủ là việc riêng (đụng iam.py).
- Owner cấp/reset mật khẩu người khác (trang /nen/tai-khoan) CHƯA gọi dong_bo_nen
  — chỉ 2 đường TỰ đăng nhập/tự đổi mật khẩu đã nối (xem nen/gateway/main.py).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import threading
from datetime import datetime
from pathlib import Path

import bcrypt

ROOT = Path(__file__).resolve().parents[2]

NHOM_TOAN_QUYEN = "NAS-ToanQuyen"
NHOM_CHI_THEM = "NAS-ChiThem"

# Tài khoản Windows có sẵn của hệ — TUYỆT ĐỐI không đổi mật khẩu/nhóm qua đường này
TEN_CAM = {"administrator", "guest", "defaultaccount", "wdagutilityaccount", "nhanvien"}
# Khuôn tên SAM của Windows: chữ cái mở đầu, tối đa 20 ký tự, không dấu/cách
_TEN_HOP_LE = re.compile(r"^[A-Za-z][A-Za-z0-9._-]{0,19}$")

_khoa = threading.Lock()               # tuần tự hóa ghi sổ + gọi PowerShell
_da_dong_bo_phien: set[str] = set()    # tên đã đồng bộ THẬT trong đời tiến trình

# PowerShell 5.1: tạo nhóm nếu thiếu → tạo/cập nhật user → vào đúng nhóm, rời nhóm kia.
# Idempotent — chạy lại bao nhiêu lần cũng ra cùng trạng thái. Y HỆT hệ cũ.
_PS_DONG_BO = r"""
$ErrorActionPreference = "Stop"
$ten = $env:OUTLIERY_NAS_TEN
$nhom = $env:OUTLIERY_NAS_NHOM
$nhomKhac = $env:OUTLIERY_NAS_NHOM_KHAC
$mk = ConvertTo-SecureString $env:OUTLIERY_NAS_MK -AsPlainText -Force
foreach ($g in @($nhom, $nhomKhac)) {
  if (-not (Get-LocalGroup -Name $g -ErrorAction SilentlyContinue)) {
    New-LocalGroup -Name $g -Description "OUTLIERY NAS (dong bo tu dong)" | Out-Null
  }
}
$u = Get-LocalUser -Name $ten -ErrorAction SilentlyContinue
if ($u) {
  Set-LocalUser -Name $ten -Password $mk -PasswordNeverExpires $true
  Enable-LocalUser -Name $ten
} else {
  New-LocalUser -Name $ten -Password $mk -PasswordNeverExpires -AccountNeverExpires `
    -Description "NAS - dong bo tu OUTLIERY" | Out-Null
}
if (-not (Get-LocalGroupMember -Group $nhom -Member $ten -ErrorAction SilentlyContinue)) {
  Add-LocalGroupMember -Group $nhom -Member $ten
}
if (Get-LocalGroupMember -Group $nhomKhac -Member $ten -ErrorAction SilentlyContinue) {
  Remove-LocalGroupMember -Group $nhomKhac -Member $ten
}
"""


def bat() -> bool:
    """Đọc SỐNG mỗi lần — test/monkeypatch đổi được ngay."""
    return os.getenv("NAS_DONG_BO", "false").strip().lower() == "true"


def mat_khau_dat_chuan(mk: str, ten: str = "") -> bool:
    """Chuẩn mật khẩu KHI BẬT ĐỒNG BỘ NAS: Windows PasswordComplexity đòi 3/4 loại
    ký tự — ép đủ HOA + thường + số (3 loại chắc ăn nhất) và >= 8 ký tự. CỘNG luật
    ngầm của Windows: KHÔNG chứa tên đăng nhập (so không phân hoa thường). Yếu hơn
    chuẩn này là Windows từ chối lúc đồng bộ → tài khoản NAS không bao giờ sinh được."""
    ten = (ten or "").strip().lower()
    if ten and len(ten) >= 3 and ten in mk.lower():
        return False
    return (len(mk) >= 8 and re.search(r"[a-z]", mk) is not None
            and re.search(r"[A-Z]", mk) is not None
            and re.search(r"[0-9]", mk) is not None)


def _ten_dung(ten: str) -> bool:
    ten = (ten or "").strip()
    return bool(_TEN_HOP_LE.match(ten)) and ten.lower() not in TEN_CAM


def _duong_so() -> Path:
    return Path(os.environ.get("NAS_SO_DUONG", ROOT / "data" / "nen" / "nas-dong-bo.json"))


def _doc_so() -> dict:
    try:
        return json.loads(_duong_so().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _ghi_so(so: dict) -> None:
    """Ghi nguyên tử (file tạm + os.replace) — chuẩn chung mọi sổ của hệ."""
    duong = _duong_so()
    duong.parent.mkdir(parents=True, exist_ok=True)
    tam = duong.with_suffix(".json.tmp")
    tam.write_text(json.dumps(so, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tam, duong)


def _cap_nhat_so(ten: str, muc: dict | None) -> None:
    with _khoa:
        so = _doc_so()
        if muc is None:
            so.pop(ten, None)
        else:
            so[ten] = muc
        _ghi_so(so)


def _chay_ps(script: str, ten: str, nhom: str, mat_khau: str,
             timeout: int = 120) -> subprocess.CompletedProcess:
    """Mật khẩu qua ENV của tiến trình con — không bao giờ trên command line.
    Trần 120s: PowerShell khởi động nguội (máy vừa restart) có thể vượt xa mức thường."""
    moi_truong = {**os.environ,
                  "OUTLIERY_NAS_TEN": ten,
                  "OUTLIERY_NAS_NHOM": nhom,
                  "OUTLIERY_NAS_NHOM_KHAC": (NHOM_CHI_THEM if nhom == NHOM_TOAN_QUYEN
                                             else NHOM_TOAN_QUYEN),
                  "OUTLIERY_NAS_MK": mat_khau}
    return subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        env=moi_truong, capture_output=True, text=True, timeout=timeout)


def _dong_bo(ten: str, mat_khau: str, nhom: str) -> None:
    """Lõi đồng bộ (chạy trong thread nền). Nuốt mọi lỗi — NAS hỏng không được
    làm hỏng đăng nhập."""
    ten = ten.strip()
    if not (bat() and _ten_dung(ten) and mat_khau):
        return
    muc_cu = _doc_so().get(ten, {})
    # Mật khẩu + nhóm không đổi và đời tiến trình này đã đồng bộ thật → khỏi gọi lại
    if (ten in _da_dong_bo_phien and muc_cu.get("trang_thai") == "ok"
            and muc_cu.get("nhom") == nhom):
        try:
            if bcrypt.checkpw(mat_khau.encode(), muc_cu.get("hash", "").encode()):
                return
        except ValueError:
            pass  # hash hỏng trong sổ → đồng bộ lại cho chắc
    try:
        kq = _chay_ps(_PS_DONG_BO, ten, nhom, mat_khau)
    except (OSError, subprocess.TimeoutExpired) as e:
        # chi_tiet KHÔNG BAO GIỜ chứa mật khẩu (chỉ tên exception/stderr hệ thống)
        _cap_nhat_so(ten, {"trang_thai": "loi", "nhom": nhom,
                           "chi_tiet": f"{type(e).__name__}"[:300],
                           "luc": datetime.now().isoformat(timespec="seconds")})
        return
    if kq.returncode == 0:
        _da_dong_bo_phien.add(ten)
        _cap_nhat_so(ten, {
            "hash": bcrypt.hashpw(mat_khau.encode(), bcrypt.gensalt()).decode(),
            "trang_thai": "ok", "nhom": nhom,
            "luc": datetime.now().isoformat(timespec="seconds")})
        return
    # Windows bật PasswordComplexity — mật khẩu yếu bị từ chối là ca ĐOÁN TRƯỚC:
    # ghi "mk_yeu" để trang /nas chỉ đường đổi mật khẩu, không phải lỗi hệ.
    loi = (kq.stderr or "") + (kq.stdout or "")
    yeu = ("password does not meet" in loi.lower()
           or "0x800708c5" in loi.lower()
           or "invalidpasswordexception" in loi.lower())
    _cap_nhat_so(ten, {"trang_thai": "mk_yeu" if yeu else "loi", "nhom": nhom,
                       "chi_tiet": loi.strip()[:300],
                       "luc": datetime.now().isoformat(timespec="seconds")})


def dong_bo_nen(ten: str, mat_khau: str, nhom: str) -> None:
    """Đăng nhập đúng / tự đổi mật khẩu → đồng bộ NAS NỀN (không chờ). Gọi từ
    gateway — nơi duy nhất biết mật khẩu thật + đã tính xong `nhom` qua
    iam.co_quyen(claims, "nas_cap_cao", "to-chuc", conn)."""
    if not bat():
        return
    threading.Thread(target=_dong_bo, args=(ten, mat_khau, nhom), daemon=True).start()


def trang_thai(ten: str) -> str:
    """Cho trang /nas: 'ok' | 'mk_yeu' | 'loi' | 'chua' (chưa từng đồng bộ) |
    'tat' (công tắc tắt)."""
    if not bat():
        return "tat"
    return _doc_so().get(ten.strip(), {}).get("trang_thai", "chua")
