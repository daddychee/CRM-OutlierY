"""VAULT — kho tài khoản số mã hóa, chỉ Owner (31/07/2026).

NGUYÊN TẮC (chốt với user):
- Trên đĩa KHÔNG BAO GIỜ tồn tại bản rõ: mọi mục nằm trong vault.enc mã hóa
  AES-256-GCM; khóa dữ liệu (DEK) ngẫu nhiên 32 byte, được BỌC bởi khóa sinh từ
  MẬT KHẨU CHỦ qua scrypt (chống dò) — trộm file/backup/ổ cứng = vô dụng.
- 10 SAFEKEY sinh lúc tạo vault, hiện ĐÚNG MỘT LẦN trên màn hình (không log, không
  lưu bản rõ). Mỗi safekey: (a) bọc thêm một bản DEK → quên mật khẩu chủ vẫn cứu
  được vault; (b) hash lưu ở safekey_login.json → dùng đặt lại mật khẩu đăng nhập
  OWNER khi quên. DÙNG MỘT LẦN: đã dùng là vô hiệu cả hai đường.
- Mất mật khẩu chủ VÀ hết safekey = mất trắng — không cửa hậu, đúng thiết kế.
- Mở vault = phiên Owner + mật khẩu chủ (CỬA THỨ HAI); DEK chỉ ở RAM, tự khóa
  sau VAULT_TU_KHOA giây không dùng.
- Sổ kiểm toán audit.csv CHỈ-GHI-THÊM: ai mở/xem/sửa/xóa mục nào, lúc nào.
"""

import base64
import csv
import hashlib
import hmac
import json
import os
import secrets
import threading
import uuid
from datetime import datetime
from pathlib import Path
from time import monotonic

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# scrypt: N=2^15 (~150ms/lần) — đủ đau cho kẻ dò, không phiền người dùng thật
SCRYPT_N, SCRYPT_R, SCRYPT_P = 2 ** 15, 8, 1
SO_SAFEKEY = 10
# Bảng chữ kiểu Crockford — bỏ 0/O/1/I/L tránh chép nhầm từ giấy; 20 ký tự ≈ 97 bit
BANG_CHU = "23456789ABCDEFGHJKMNPQRSTVWXYZ"
TU_KHOA_GIAY = int(os.getenv("VAULT_TU_KHOA", "600"))  # 10 phút không dùng → tự khóa

AUDIT_HEADER = ["Thời gian", "Ai", "Hành động", "Mục"]
NHOM_HOP_LE = ["google", "adsense", "proxy", "email", "the", "khac"]


def _thu_muc() -> Path:
    return Path(os.getenv("VAULT_DIR", "vault"))


def _file_vault() -> Path:
    return _thu_muc() / "vault.enc"


def _file_safekey() -> Path:
    return _thu_muc() / "safekey_login.json"


def _file_audit() -> Path:
    return _thu_muc() / "audit.csv"


def _b64(b: bytes) -> str:
    return base64.b64encode(b).decode()


def _un64(s: str) -> bytes:
    return base64.b64decode(s)


def _kdf(bi_mat: str, salt: bytes) -> bytes:
    return hashlib.scrypt(bi_mat.encode(), salt=salt, n=SCRYPT_N, r=SCRYPT_R,
                          p=SCRYPT_P, dklen=32, maxmem=128 * 1024 * 1024)


def _boc(khoa: bytes, du_lieu: bytes) -> dict:
    nonce = secrets.token_bytes(12)
    return {"nonce": _b64(nonce), "ct": _b64(AESGCM(khoa).encrypt(nonce, du_lieu, None))}


def _mo_boc(khoa: bytes, goi: dict) -> bytes:
    return AESGCM(khoa).decrypt(_un64(goi["nonce"]), _un64(goi["ct"]), None)


def _ghi_nguyen_tu(p: Path, noi_dung: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tam = p.with_name(p.name + ".tmp")
    tam.write_text(noi_dung, encoding="utf-8")
    os.replace(tam, p)


def _doc_goi() -> dict:
    return json.loads(_file_vault().read_text(encoding="utf-8"))


def _ghi_goi(goi: dict) -> None:
    _ghi_nguyen_tu(_file_vault(), json.dumps(goi, ensure_ascii=False, indent=1))


def ghi_audit(ai: str, hanh_dong: str, muc: str = "") -> None:
    """Sổ kiểm toán CHỈ-GHI-THÊM — không bao giờ ghi nội dung bí mật, chỉ ghi tên mục."""
    p = _file_audit()
    p.parent.mkdir(parents=True, exist_ok=True)
    moi = not p.exists()
    with p.open("a", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        if moi:
            w.writerow(AUDIT_HEADER)
        w.writerow([datetime.now().isoformat(timespec="seconds"), ai, hanh_dong, muc])


def da_tao() -> bool:
    return _file_vault().is_file()


def _sinh_safekey() -> str:
    phan = ["".join(secrets.choice(BANG_CHU) for _ in range(5)) for _ in range(4)]
    return "-".join(phan)


def tao_vault(master: str, ai: str) -> list[str]:
    """Tạo vault + sinh 10 safekey. Trả danh sách safekey — NGƯỜI GỌI hiện một lần
    rồi quên; module KHÔNG lưu bản rõ ở bất cứ đâu."""
    if da_tao():
        raise ValueError("Vault đã tồn tại — không tạo đè (tránh xóa mất dữ liệu).")
    if len(master) < 12:
        raise ValueError("Mật khẩu chủ phải từ 12 ký tự — nó là cánh cửa duy nhất.")
    dek = secrets.token_bytes(32)
    salt_m = secrets.token_bytes(16)
    goi = {
        "phien_ban": 1,
        "salt_master": _b64(salt_m),
        "boc_master": _boc(_kdf(master, salt_m), dek),
        "boc_safekey": [],
        "du_lieu": _boc(dek, b"[]"),
    }
    safekeys, so_login = [], []
    for i in range(1, SO_SAFEKEY + 1):
        sk = _sinh_safekey()
        safekeys.append(sk)
        salt_boc = secrets.token_bytes(16)
        goi["boc_safekey"].append({"id": f"SK{i:02d}", "salt": _b64(salt_boc),
                                   **_boc(_kdf(sk, salt_boc), dek)})
        salt_hash = secrets.token_bytes(16)
        so_login.append({"id": f"SK{i:02d}", "salt": _b64(salt_hash),
                         "hash": _b64(_kdf(sk, salt_hash)), "da_dung": False})
    _ghi_goi(goi)
    _ghi_nguyen_tu(_file_safekey(), json.dumps(so_login, indent=1))
    ghi_audit(ai, "tao_vault", f"{SO_SAFEKEY} safekey")
    return safekeys


# ================= TRẠNG THÁI MỞ/KHÓA (DEK chỉ ở RAM, 1 tiến trình LAN) =================

_TT_KHOA = threading.Lock()
_DEK: bytes | None = None
_HET_HAN = 0.0


def _dek_dang_mo() -> bytes | None:
    """DEK nếu vault đang mở và chưa quá hạn; mỗi lần dùng GIA HẠN đồng hồ tự khóa."""
    global _DEK, _HET_HAN
    with _TT_KHOA:
        if _DEK is None or monotonic() > _HET_HAN:
            _DEK = None
            return None
        _HET_HAN = monotonic() + TU_KHOA_GIAY
        return _DEK


def dang_mo() -> bool:
    return _dek_dang_mo() is not None


def khoa(ai: str = "") -> None:
    global _DEK, _HET_HAN
    with _TT_KHOA:
        _DEK, _HET_HAN = None, 0.0
    if ai:
        ghi_audit(ai, "khoa_vault")


def mo_bang_master(master: str, ai: str) -> bool:
    global _DEK, _HET_HAN
    goi = _doc_goi()
    try:
        dek = _mo_boc(_kdf(master, _un64(goi["salt_master"])), goi["boc_master"])
    except InvalidTag:
        ghi_audit(ai, "mo_vault_SAI_mat_khau")
        return False
    with _TT_KHOA:
        _DEK, _HET_HAN = dek, monotonic() + TU_KHOA_GIAY
    ghi_audit(ai, "mo_vault")
    return True


# ================= MỤC TRONG VAULT =================

def doc_muc() -> list[dict] | None:
    """Danh sách mục khi vault ĐANG MỞ; khóa/quá hạn → None (route tự xử)."""
    dek = _dek_dang_mo()
    if dek is None:
        return None
    return json.loads(_mo_boc(dek, _doc_goi()["du_lieu"]))


def _ghi_muc(muc: list[dict], dek: bytes) -> None:
    goi = _doc_goi()
    goi["du_lieu"] = _boc(dek, json.dumps(muc, ensure_ascii=False).encode())
    _ghi_goi(goi)


def them_hoac_sua_muc(ai: str, id: str, nhom: str, ten: str, tai_khoan: str,
                      mat_khau: str, ghi_chu: str) -> str:
    dek = _dek_dang_mo()
    if dek is None:
        raise PermissionError("Vault đang khóa.")
    if nhom not in NHOM_HOP_LE:
        raise ValueError(f"Nhóm '{nhom}' không hợp lệ.")
    if not ten.strip():
        raise ValueError("Tên mục không được trống.")
    muc = json.loads(_mo_boc(dek, _doc_goi()["du_lieu"]))
    if id:
        cu = next((m for m in muc if m["id"] == id), None)
        if cu is None:
            raise ValueError("Không thấy mục cần sửa.")
        # sửa nhưng bỏ trống mật khẩu = GIỮ mật khẩu cũ (đỡ phải gõ lại khi chỉ đổi ghi chú)
        cu.update({"nhom": nhom, "ten": ten.strip(), "tai_khoan": tai_khoan,
                   "mat_khau": mat_khau or cu["mat_khau"], "ghi_chu": ghi_chu,
                   "sua_luc": datetime.now().isoformat(timespec="seconds")})
        ghi_audit(ai, "sua_muc", ten.strip())
    else:
        id = uuid.uuid4().hex[:8]
        muc.append({"id": id, "nhom": nhom, "ten": ten.strip(), "tai_khoan": tai_khoan,
                    "mat_khau": mat_khau, "ghi_chu": ghi_chu,
                    "sua_luc": datetime.now().isoformat(timespec="seconds")})
        ghi_audit(ai, "them_muc", ten.strip())
    _ghi_muc(muc, dek)
    return id


def xoa_muc(ai: str, id: str) -> None:
    dek = _dek_dang_mo()
    if dek is None:
        raise PermissionError("Vault đang khóa.")
    muc = json.loads(_mo_boc(dek, _doc_goi()["du_lieu"]))
    con = [m for m in muc if m["id"] != id]
    if len(con) == len(muc):
        raise ValueError("Không thấy mục cần xóa.")
    ten = next(m["ten"] for m in muc if m["id"] == id)
    _ghi_muc(con, dek)
    ghi_audit(ai, "xoa_muc", ten)


def xem_mat_khau(ai: str, id: str) -> str:
    """Lộ mật khẩu MỘT mục — mỗi lần lộ là MỘT dòng audit (đo được ai xem gì)."""
    dek = _dek_dang_mo()
    if dek is None:
        raise PermissionError("Vault đang khóa.")
    muc = json.loads(_mo_boc(dek, _doc_goi()["du_lieu"]))
    m = next((x for x in muc if x["id"] == id), None)
    if m is None:
        raise ValueError("Không thấy mục.")
    ghi_audit(ai, "xem_mat_khau", m["ten"])
    return m["mat_khau"]


# ================= SAFEKEY: khôi phục mật khẩu chủ + đặt lại đăng nhập Owner =================

def _doc_so_login() -> list[dict]:
    p = _file_safekey()
    if not p.is_file():
        return []
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except ValueError:
        return []


def _kiem_safekey(sk: str) -> str | None:
    """Safekey đúng + CHƯA DÙNG → id; sai/đã dùng → None. So bằng compare_digest."""
    sk = sk.strip().upper()
    for d in _doc_so_login():
        if d.get("da_dung"):
            continue
        if hmac.compare_digest(_kdf(sk, _un64(d["salt"])), _un64(d["hash"])):
            return d["id"]
    return None


def _vo_hieu_safekey(id: str) -> None:
    """DÙNG MỘT LẦN: đánh dấu đã dùng trong sổ login + gỡ bọc DEK khỏi vault.enc."""
    so = _doc_so_login()
    for d in so:
        if d["id"] == id:
            d["da_dung"] = True
    _ghi_nguyen_tu(_file_safekey(), json.dumps(so, indent=1))
    if da_tao():
        goi = _doc_goi()
        goi["boc_safekey"] = [b for b in goi["boc_safekey"] if b["id"] != id]
        _ghi_goi(goi)


def so_safekey_con_lai() -> int:
    return sum(1 for d in _doc_so_login() if not d.get("da_dung"))


def trang_thai_safekey() -> list[dict]:
    """Bảng theo dõi 10 safekey: id + còn/đã dùng (KHÔNG có cách nào lộ lại bản rõ —
    sổ chỉ giữ hash). Dùng cho bảng 'Safekey trong két' trên trang vault."""
    return [{"id": d["id"], "da_dung": bool(d.get("da_dung"))} for d in _doc_so_login()]


def khoi_phuc_master(sk: str, master_moi: str, ai: str) -> bool:
    """Quên mật khẩu chủ: 1 safekey mở được DEK → đặt mật khẩu chủ MỚI ngay.
    Safekey đó vô hiệu vĩnh viễn sau khi dùng."""
    if len(master_moi) < 12:
        raise ValueError("Mật khẩu chủ mới phải từ 12 ký tự.")
    sk = sk.strip().upper()
    id = _kiem_safekey(sk)
    if id is None:
        ghi_audit(ai, "khoi_phuc_master_SAI_safekey")
        return False
    goi = _doc_goi()
    boc = next((b for b in goi["boc_safekey"] if b["id"] == id), None)
    if boc is None:  # sổ login còn mà vault đã gỡ bọc (lệch tay) — coi như không dùng được
        ghi_audit(ai, "khoi_phuc_master_SAI_safekey")
        return False
    dek = _mo_boc(_kdf(sk, _un64(boc["salt"])), boc)
    salt_moi = secrets.token_bytes(16)
    goi["salt_master"] = _b64(salt_moi)
    goi["boc_master"] = _boc(_kdf(master_moi, salt_moi), dek)
    _ghi_goi(goi)
    _vo_hieu_safekey(id)
    ghi_audit(ai, "khoi_phuc_master", id)
    return True


def dat_lai_mat_khau_owner(ten: str, sk: str, mk_moi: str) -> bool:
    """Quên mật khẩu ĐĂNG NHẬP Owner: safekey = giấy thông hành từ két. Chỉ tài
    khoản level 5 mới đặt lại được bằng đường này (nhân viên quên → nhờ Owner reset
    như cũ). Safekey vô hiệu sau khi dùng."""
    from src.auth import doc_tat_ca_user, doi_mat_khau_xong  # import tại chỗ tránh vòng

    nguoi = next((u for u in doc_tat_ca_user() if u["ten"] == ten.strip()), None)
    if nguoi is None or nguoi["level"] != 5:
        ghi_audit(ten.strip() or "?", "dat_lai_login_TU_CHOI_khong_phai_owner")
        return False
    id = _kiem_safekey(sk)
    if id is None:
        ghi_audit(ten.strip(), "dat_lai_login_SAI_safekey")
        return False
    doi_mat_khau_xong(ten.strip(), mk_moi)
    _vo_hieu_safekey(id)
    ghi_audit(ten.strip(), "dat_lai_login_owner", id)
    return True
