# -*- coding: utf-8 -*-
"""KÉT CẤU HÌNH — API key + model LLM của CẢ HỆ ở MỘT chỗ (mảnh ③, Phase 3).

Hai ngăn tách bạch (chuẩn Vault/12-factor, hiến pháp mục 2.3):
- cau_hinh: không mật (provider, model, base_url, timeout) — đọc/ghi thẳng.
- bi_mat:   API key — mã hóa Fernet bằng khóa máy `data/nen/ket.key`, DB không
  bao giờ chứa plaintext, UI chỉ hiện ••••<4 cuối>.

ponytail: khóa Fernet nằm file cùng máy → trần bảo vệ = quyền NTFS thư mục data
(mọi tiến trình chạy cùng user đọc được). Đủ cho LAN 1 máy như đã chốt; nâng cấp:
DPAPI/TPM khi tách nhiều máy.

Quy ước khóa LLM theo VAI (writer/critic/extractor/router…):
  cau_hinh:  llm.<vai>.provider | llm.<vai>.model | llm.<vai>.base_url
  bi_mat:    llm.<vai>.api_key
  chung:     llm.timeout (mặc định 60) | llm.retry (mặc định 0)  ← bài học hệ cũ
             19/07 + 06/08 thành LUẬT NỀN: mọi lời gọi LLM có timeout, retry 0.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
from datetime import datetime
from pathlib import Path

from cryptography.fernet import Fernet

from nen.common import sqlite_migrate

ROOT = Path(__file__).resolve().parents[2]
DUONG_MIGRATIONS = Path(__file__).parent / "migrations"

TIMEOUT_MAC_DINH = 60
RETRY_MAC_DINH = 0


def _duong_db() -> Path:
    return Path(os.environ.get("KET_DB", ROOT / "data" / "nen" / "ket.db"))


def _duong_khoa() -> Path:
    return Path(os.environ.get("KET_KEY", ROOT / "data" / "nen" / "ket.key"))


def ket_noi(duong: Path | str | None = None) -> sqlite3.Connection:
    duong = Path(duong) if duong else _duong_db()
    duong.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(duong, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    sqlite_migrate.migrate(conn, DUONG_MIGRATIONS)
    return conn


def _fernet() -> Fernet:
    f = _duong_khoa()
    if not f.exists():
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(Fernet.generate_key())
    return Fernet(f.read_bytes())


def _gio() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ---------- cấu hình (không mật) ----------

def dat_cau_hinh(conn: sqlite3.Connection, khoa: str, gia_tri: str) -> None:
    with conn:
        conn.execute(
            "INSERT INTO cau_hinh (khoa, gia_tri, sua_luc) VALUES (?,?,?) "
            "ON CONFLICT(khoa) DO UPDATE SET gia_tri=excluded.gia_tri, "
            "sua_luc=excluded.sua_luc", (khoa, gia_tri, _gio()))


def lay_cau_hinh(conn: sqlite3.Connection, khoa: str, mac_dinh: str = "") -> str:
    r = conn.execute("SELECT gia_tri FROM cau_hinh WHERE khoa=?", (khoa,)).fetchone()
    return r["gia_tri"] if r else mac_dinh


# ---------- bí mật (mã hóa) ----------

def dat_bi_mat(conn: sqlite3.Connection, khoa: str, gia_tri: str) -> None:
    ma = _fernet().encrypt(gia_tri.encode("utf-8")).decode("ascii")
    with conn:
        conn.execute(
            "INSERT INTO bi_mat (khoa, gia_tri_ma, duoi, dau, sua_luc) VALUES (?,?,?,?,?) "
            "ON CONFLICT(khoa) DO UPDATE SET gia_tri_ma=excluded.gia_tri_ma, "
            "duoi=excluded.duoi, dau=excluded.dau, sua_luc=excluded.sua_luc",
            (khoa, ma, gia_tri[-4:], gia_tri[:3], _gio()))


def lay_bi_mat(conn: sqlite3.Connection, khoa: str) -> str | None:
    r = conn.execute("SELECT gia_tri_ma FROM bi_mat WHERE khoa=?", (khoa,)).fetchone()
    if not r:
        return None
    return _fernet().decrypt(r["gia_tri_ma"].encode("ascii")).decode("utf-8")


def liet_ke(conn: sqlite3.Connection) -> dict:
    """Cho UI: cau_hinh đầy đủ; bi_mat CHỈ khóa + đầu/đuôi (không bao giờ trả plaintext)."""
    return {
        "cau_hinh": [dict(r) for r in
                     conn.execute("SELECT * FROM cau_hinh ORDER BY khoa").fetchall()],
        "bi_mat": [{"khoa": r["khoa"], "dau": r["dau"], "duoi": r["duoi"],
                    "sua_luc": r["sua_luc"]}
                   for r in conn.execute("SELECT * FROM bi_mat ORDER BY khoa").fetchall()],
    }


def backfill_dau_khoa(conn: sqlite3.Connection) -> int:
    """Backfill MỘT LẦN cột 'dau' cho khóa nạp TRƯỚC migration 002 (dau rỗng).
    Idempotent: chỉ xử lý dòng dau='' → lần sau SELECT rỗng, không giải mã lại.
    Giải mã CHỈ để cắt 3 ký tự đầu — TUYỆT ĐỐI không log/in giá trị đầy đủ ở bất
    cứ đâu; KHÔNG đụng gia_tri_ma/sua_luc. Gọi mỗi lần mở trang API Keys (khuôn
    di_tru_llm_cu — rẻ vì hàng đã có dau bị SELECT loại ngay, không decrypt lại)."""
    rows = conn.execute("SELECT khoa, gia_tri_ma FROM bi_mat WHERE dau=''").fetchall()
    if not rows:
        return 0
    f = _fernet()
    so = 0
    with conn:
        for r in rows:
            try:
                plaintext = f.decrypt(r["gia_tri_ma"].encode("ascii")).decode("utf-8")
            except Exception:
                continue   # khóa hỏng/không giải mã được — bỏ qua, không chết cả đợt
            conn.execute("UPDATE bi_mat SET dau=? WHERE khoa=?",
                        (plaintext[:3], r["khoa"]))
            so += 1
    return so


# ---------- API KEYS theo LOẠI (trang /general/api-keys — DE.md mục 12.3, K1-K8) ----------
# Owner chốt qua 4 vòng mockup: hiển thị THEO API, LLM là MỘT loại trong đó,
# cấu hình theo app sinh từ viec_api của HỢP ĐỒNG, quota log JSON-lines chuẩn P4.

# transcript: dich vu transcriptapi.com (Content Ultimate S1b) — them loai khi
# app that can, dung tinh than DE.md 3b "dich_vu.<ten>" (khong de khoa ngoai ket).
# generate: Owner chot 17/08 — VEO + Seedream la HAI NHA cua CUNG MOT loai
# "generate" (sinh video/anh), dung khuon nha nhu llm — KHONG phai 2 loai rieng
# co dinh (bai hoc: tu an dinh loai la sai, phai de chon nha nhu llm).
LOAI_API = ("youtube", "llm", "generate", "transcript")
NHA_LLM = ("claude", "glm", "gemini", "chatgpt", "deepseek")
# provider/base_url suy từ NHÀ khi khóa không mang override riêng (migration giữ
# nguyên giá trị cũ per-khóa nên hệ đang chạy resolve ra ĐÚNG như trước).
NHA_LLM_INFO = {
    "claude": {"ten": "Claude (Anthropic)", "provider": "anthropic", "base_url": ""},
    "glm": {"ten": "GLM (Z.ai)", "provider": "openai_compatible",
            "base_url": "https://api.z.ai/api/paas/v4"},
    "gemini": {"ten": "Gemini (Google)", "provider": "openai_compatible",
               "base_url": "https://generativelanguage.googleapis.com/v1beta/openai"},
    "chatgpt": {"ten": "ChatGPT (OpenAI)", "provider": "openai_compatible",
                "base_url": "https://api.openai.com/v1"},
    "deepseek": {"ten": "Deepseek", "provider": "openai_compatible",
                 "base_url": "https://api.deepseek.com"},
}
NHA_GEN = ("veo", "seedream")
# generate KHÔNG đi qua factory LLM (không provider/base_url — chỉ nhãn hiển thị).
NHA_GEN_INFO = {"veo": {"ten": "VEO (Google Flow)"}, "seedream": {"ten": "Seedream"}}
TEN_LOAI_API = {"youtube": "YouTube Data API v3", "llm": "LLM",
                "generate": "Generate Video/Image API",
                "transcript": "YouTube Transcript"}
# Model gợi ý cho dropdown (mockup K2-K3) — gợi ý thôi, giá trị hiện hành luôn giữ.
MODEL_GOI_Y = {
    "claude": ["claude-fable-5", "claude-sonnet-5", "claude-haiku-4-5"],
    "glm": ["glm-4.5-air", "glm-5", "glm-5.2"],
    "gemini": ["gemini-2.5-pro", "gemini-2.5-flash"],
    "chatgpt": ["gpt-5", "gpt-5-mini"],
    "deepseek": ["deepseek-chat", "deepseek-reasoner"],
    "veo": ["veo-3.1", "veo-3"],
    "seedream": ["seedream-3.0"],
}
CHE_DO_CAP = ("mot_khoa", "xoay_vong", "du_phong")


def them_api_key(conn: sqlite3.Connection, loai: str, khoa: str,
                 nha: str = "", model: str = "") -> str:
    """Thêm một khóa API → id tự sinh api-NNN. Bí mật vào ngăn bi_mat (Fernet,
    write-only, UI chỉ thấy đuôi 4); metadata vào cau_hinh."""
    if loai not in LOAI_API:
        raise ValueError("Loại API phải là: " + " / ".join(LOAI_API))
    if loai == "llm" and nha not in NHA_LLM:
        raise ValueError("Nhà LLM phải là: " + " / ".join(NHA_LLM))
    if loai == "generate" and nha not in NHA_GEN:
        raise ValueError("Nhà Generate phải là: " + " / ".join(NHA_GEN))
    if loai not in ("llm", "generate"):
        nha = ""
    if not khoa.strip():
        raise ValueError("Thiếu khóa.")
    so = 0
    for r in conn.execute("SELECT khoa FROM cau_hinh WHERE khoa LIKE 'api.api-%.loai'"):
        m = re.fullmatch(r"api\.api-(\d+)\.loai", r["khoa"])
        if m:
            so = max(so, int(m.group(1)))
    kid = f"api-{so + 1:03d}"
    dat_bi_mat(conn, f"api.{kid}.key", khoa.strip())
    dat_cau_hinh(conn, f"api.{kid}.loai", loai)
    dat_cau_hinh(conn, f"api.{kid}.nha", nha)
    dat_cau_hinh(conn, f"api.{kid}.model", model.strip())
    dat_cau_hinh(conn, f"api.{kid}.ngay", datetime.now().strftime("%Y-%m-%d"))
    return kid


def liet_ke_api_keys(conn: sqlite3.Connection) -> list[dict]:
    """Cho UI: id + loại/nhà/model/ngày + ĐẦU 3/ĐUÔI 4 — không bao giờ trả plaintext."""
    ra = []
    for r in conn.execute("SELECT khoa, gia_tri FROM cau_hinh "
                          "WHERE khoa LIKE 'api.api-%.loai' ORDER BY khoa"):
        kid = r["khoa"].split(".")[1]
        b = conn.execute("SELECT dau, duoi FROM bi_mat WHERE khoa=?",
                         (f"api.{kid}.key",)).fetchone()
        ra.append({"id": kid, "loai": r["gia_tri"],
                   "nha": lay_cau_hinh(conn, f"api.{kid}.nha"),
                   "model": lay_cau_hinh(conn, f"api.{kid}.model"),
                   "ngay": lay_cau_hinh(conn, f"api.{kid}.ngay"),
                   "dau": b["dau"] if b else "", "duoi": b["duoi"] if b else ""})
    return ra


def thu_hoi_api_key(conn: sqlite3.Connection, kid: str) -> dict | None:
    """Thu hồi = xóa bí mật + metadata + GỠ khỏi mọi cấp phát. KHÔNG đụng lịch sử
    quota log (sử liệu). Trả {duoi} cho audit; không có khóa → None."""
    r = conn.execute("SELECT duoi FROM bi_mat WHERE khoa=?",
                     (f"api.{kid}.key",)).fetchone()
    if not r:
        return None
    with conn:
        conn.execute("DELETE FROM bi_mat WHERE khoa=?", (f"api.{kid}.key",))
        conn.execute("DELETE FROM cau_hinh WHERE khoa LIKE ?", (f"api.{kid}.%",))
    cp = doc_cap_phat(conn)
    doi = False
    for cac_viec in cp.values():
        for muc in cac_viec.values():
            if kid in muc.get("khoa", []):
                muc["khoa"] = [k for k in muc["khoa"] if k != kid]
                if len(muc["khoa"]) <= 1:
                    muc["che_do"] = "mot_khoa"
                doi = True
    if doi:
        _luu_cap_phat(conn, cp)
    return {"duoi": r["duoi"]}


# --- cấp phát khóa cho VIỆC-TRONG-APP (viec_api trong hợp đồng — K5-K7) ---

def doc_cap_phat(conn: sqlite3.Connection) -> dict:
    tho = lay_cau_hinh(conn, "api.cap_phat", "")
    if not tho:
        return {}
    try:
        return json.loads(tho)
    except ValueError:
        return {}


def _luu_cap_phat(conn: sqlite3.Connection, cp: dict) -> None:
    dat_cau_hinh(conn, "api.cap_phat", json.dumps(cp, ensure_ascii=False))


def luu_cap_phat_viec(conn: sqlite3.Connection, app_slug: str, viec: str,
                      khoa_ids: list[str], che_do: str = "",
                      model: str = "") -> dict:
    """Lưu cấp phát MỘT việc: nhiều khóa cùng loại (K5 vòng 4). Chế độ chuẩn hóa:
    ≤1 khóa = mot_khoa; >1 chọn xoay_vong/du_phong (mặc định xoay_vong).
    Chỉ giữ id khóa còn sống (khóa đã thu hồi tự rơi)."""
    khoa_ids = [k for k in khoa_ids
                if lay_cau_hinh(conn, f"api.{k}.loai")]
    cp = doc_cap_phat(conn)
    muc = cp.setdefault(app_slug, {}).setdefault(viec, {})
    muc["khoa"] = khoa_ids
    if len(khoa_ids) <= 1:
        muc["che_do"] = "mot_khoa"
    else:
        muc["che_do"] = che_do if che_do in ("xoay_vong", "du_phong") \
            else muc.get("che_do") if muc.get("che_do") in ("xoay_vong", "du_phong") \
            else "xoay_vong"
    muc["model"] = model.strip() if model else muc.get("model", "")
    muc["ngay"] = datetime.now().strftime("%Y-%m-%d")
    _luu_cap_phat(conn, cp)
    return muc


# --- migration một lần từ khuôn llm.<vai>.* cũ (idempotent) ---

def _suy_nha(provider: str, base_url: str) -> str:
    if provider == "anthropic":
        return "claude"
    u = (base_url or "").lower()
    if "z.ai" in u:
        return "glm"
    if "deepseek" in u:
        return "deepseek"
    if "google" in u or "gemini" in u:
        return "gemini"
    if "openai.com" in u:
        return "chatgpt"
    return "glm"   # không nhận diện: nhãn nhóm thôi — override per-khóa giữ giá trị thật


def di_tru_llm_cu(conn: sqlite3.Connection) -> list[dict]:
    """Mục llm.<vai>.* cũ trong két → khóa LLM mới + cấp phát ai-agent việc cùng
    tên. provider/base_url cũ GIỮ NGUYÊN làm override per-khóa → resolve ra đúng
    giá trị cũ kể cả base_url lạ. Mục cũ GIỮ làm fallback, không xóa. Đánh dấu
    api.di_tru.<vai> → chạy lại không nhân đôi (idempotent)."""
    ra = []
    for r in conn.execute(
            "SELECT khoa FROM bi_mat WHERE khoa LIKE 'llm.%.api_key'").fetchall():
        vai = r["khoa"].split(".")[1]
        if lay_cau_hinh(conn, f"api.di_tru.{vai}"):
            continue
        key = lay_bi_mat(conn, r["khoa"]) or ""
        if not key:
            continue
        provider = lay_cau_hinh(conn, f"llm.{vai}.provider")
        base_url = lay_cau_hinh(conn, f"llm.{vai}.base_url")
        model = lay_cau_hinh(conn, f"llm.{vai}.model")
        kid = them_api_key(conn, "llm", key, nha=_suy_nha(provider, base_url),
                           model=model)
        if provider:
            dat_cau_hinh(conn, f"api.{kid}.provider", provider)
        if base_url:
            dat_cau_hinh(conn, f"api.{kid}.base_url", base_url)
        luu_cap_phat_viec(conn, "ai-agent", vai, [kid], "mot_khoa", model)
        dat_cau_hinh(conn, f"api.di_tru.{vai}", kid)
        ra.append({"vai": vai, "id": kid, "duoi": key[-4:]})
    return ra


# ---------- LLM theo vai ----------

def cau_hinh_llm(conn: sqlite3.Connection, app_slug: str, vai: str) -> dict:
    """Trả cấu hình LLM đủ dùng cho MỘT VIỆC của MỘT APP. Việc chưa khai →
    provider rỗng (app tự quyết mock/báo thiếu — KHÔNG bịa mặc định gọi nhầm nhà).

    BUG ĐÃ SỬA 18/08 (Owner phê lần 3): bản cũ HARDCODE app 'ai-agent' — data-
    analytics xin vai 'writer' (trùng tên việc của ai-agent) bị trả nhầm khóa
    Writer của ai-agent, bỏ qua cấp phát data-analytics trên UI Per-app config.
    app_slug giờ BẮT BUỘC (không default ngầm — tránh lặp lại bug); tra
    cap_phat[app_slug][vai]. Ưu tiên CẤP PHÁT: khóa đầu được cấp + model của
    việc; provider/base_url ưu tiên override per-khóa (migration giữ nguyên giá
    trị cũ) rồi mới suy từ NHÀ. Việc CHƯA có trong cấp phát → fallback đọc
    llm.<vai>.* cũ Y NGUYÊN (hệ đang chạy không gãy — fallback này là sổ chung
    không theo app, đúng ngữ nghĩa di sản); việc CÓ nhưng 0 khóa → provider
    rỗng (tắt tường minh, không để fallback hồi sinh)."""
    chung = {
        "vai": vai,
        "timeout": int(lay_cau_hinh(conn, "llm.timeout", str(TIMEOUT_MAC_DINH))),
        "retry": int(lay_cau_hinh(conn, "llm.retry", str(RETRY_MAC_DINH))),
    }
    muc = doc_cap_phat(conn).get(app_slug, {}).get(vai)
    if muc is not None:
        ids = muc.get("khoa") or []
        if not ids:
            return {**chung, "provider": "", "model": "", "base_url": "",
                    "api_key": ""}
        kid = ids[0]
        info = NHA_LLM_INFO.get(lay_cau_hinh(conn, f"api.{kid}.nha"), {})
        return {
            **chung,
            "provider": lay_cau_hinh(conn, f"api.{kid}.provider")
                        or info.get("provider", ""),
            "model": muc.get("model") or lay_cau_hinh(conn, f"api.{kid}.model"),
            "base_url": lay_cau_hinh(conn, f"api.{kid}.base_url")
                        or info.get("base_url", ""),
            "api_key": lay_bi_mat(conn, f"api.{kid}.key") or "",
        }
    return {
        **chung,
        "provider": lay_cau_hinh(conn, f"llm.{vai}.provider"),
        "model": lay_cau_hinh(conn, f"llm.{vai}.model"),
        "base_url": lay_cau_hinh(conn, f"llm.{vai}.base_url"),
        "api_key": lay_bi_mat(conn, f"llm.{vai}.api_key") or "",
    }
