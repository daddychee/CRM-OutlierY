# -*- coding: utf-8 -*-
"""Tầng dữ liệu Video Review — SQLite (migration có phiên bản) + LIÊN KẾT file NAS.

Từ 20/08/2026 app KHÔNG chép video vào kho nữa (user chốt): quy trình công ty là
anh em up bản dựng lên NAS rồi chọn file đó vào app, nên sổ chỉ giữ ĐƯỜNG TƯƠNG ĐỐI
trong VR_NAS_DIR (nguon='nas'). Bản ghi đời cũ nguon='kho' vẫn đọc được từ kho app.

- NAS là CHỈ ĐỌC tuyệt đối: app không ghi/xóa/đổi tên bất cứ thứ gì trong VR_NAS_DIR,
  kể cả khi người dùng xóa video (xóa vẫn là GỠ MỀM — bất biến hệ cũ).
- Vân tay (kich_thuoc + nas_mtime) chụp lúc liên kết → phát hiện file bị GHI ĐÈ bản
  mới cùng tên, vì bình luận gắn mốc giây của bản cũ sẽ lệch.
- Mọi hàm đọc env LÚC GỌI (không cache lúc import) để test đè đường bằng monkeypatch.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
import subprocess
from datetime import datetime
from pathlib import Path

_APP_DIR = Path(__file__).resolve().parents[1]           # apps/video-review
ROOT = _APP_DIR.parents[1]                                # D:\AI AGENT OUTLIERY

# BA bước duyệt (user chốt 20/08): Awaiting review → In review → Approved.
# 'Awaiting' suy từ 'chưa có bình luận nào', không phải giá trị lưu trong sổ.
# 'da_xoa' là GỠ MỀM, không phải một bước duyệt. 'can_sua' đã nghỉ hưu (mig 004).
TRANG_THAI_VIDEO = ("dang_duyet", "da_duyet", "da_xoa")
# CHỈ đúng một tên 'Feedback' (user chốt 24/08: giữ một quy ước, user sẽ nhắc
# anh em đặt đúng). Viết tắt kiểu 'FB' KHÔNG được nhận — thư mục tên lạ coi như
# không có khối feedback nên không bao giờ mở đường xóa cả thư mục tập.
TEN_THU_MUC_FEEDBACK = frozenset({"feedback"})
# .mov để được nhưng cảnh báo ở UI (tùy codec trình duyệt mới phát) — mp4/webm chắc ăn.
DUOI_CHO_PHEP = {".mp4": "video/mp4", ".m4v": "video/mp4",
                 ".webm": "video/webm", ".mov": "video/quicktime"}


def _db_path() -> Path:
    return Path(os.environ.get("VR_DB_PATH",
                               str(ROOT / "data" / "video-review" / "db" / "video_review.db")))


def kho_dir() -> Path:
    """Kho app — giờ chỉ còn giữ phụ đề gắn từ app + bản sao video đời cũ."""
    return Path(os.environ.get("VR_KHO_DIR", str(ROOT / "data" / "video-review" / "kho")))


def nas_dir() -> Path | None:
    """Gốc NAS được phép duyệt (env VR_NAS_DIR). CHƯA khai → None (tính năng ẩn)."""
    d = os.environ.get("VR_NAS_DIR", "").strip()
    if not d:
        return None
    p = Path(d)
    return p if p.is_dir() else None


def duong_nas_an_toan(goc: Path, tuong_doi: str) -> Path:
    """Đường client gửi → đường tuyệt đối TRONG gốc; ngoài gốc → PermissionError.
    Đường tuyệt đối/ổ đĩa client nhét vào cũng bị resolve rồi rơi ngoài gốc.
    Kiểm LẠI cả lúc phát video (không chỉ lúc liên kết) — sổ có thể bị sửa tay."""
    td = (tuong_doi or "").replace("\\", "/").strip("/")
    goc_rs = goc.resolve()
    if not td:
        return goc_rs
    con = (goc / td).resolve()
    if con != goc_rs and goc_rs not in con.parents:
        raise PermissionError("Đường ngoài gốc NAS")
    return con


def duong_video(video: dict) -> Path | None:
    """Đường file thật của một bản ghi — None khi không resolve nổi (NAS chưa khai
    / sổ trỏ ra ngoài gốc). Caller vẫn phải tự kiểm .is_file()."""
    if (video.get("nguon") or "kho") == "nas":
        goc = nas_dir()
        if goc is None:
            return None
        try:
            return duong_nas_an_toan(goc, video["duong"])
        except (PermissionError, OSError):
            return None
    return kho_dir() / video["duong"]


def tinh_trang_file(video: dict) -> dict:
    """Vân tay file lúc liên kết so với hiện tại — dữ liệu cho cảnh báo trên UI.
    'mat' = file không còn (bị xóa/đổi tên/di chuyển trên NAS, hoặc NAS chưa khai);
    'doi' = còn nhưng dung lượng/ngày sửa đã khác → bình luận gắn mốc giây có thể
    lệch (editor ghi đè bản mới cùng tên). CHỈ báo, không tự sửa sổ."""
    p = duong_video(video)
    if p is None or not p.is_file():
        return {"co": False, "doi": False, "duong_hien": str(p) if p else ""}
    st = p.stat()
    doi = False
    if (video.get("nguon") or "kho") == "nas":
        # CHỈ DUNG LƯỢNG mới là bằng chứng nội dung đổi. Ngày sửa nhích vì đủ thứ
        # lý do lành tính — sự cố 26/08: nhân sự bấm liên kết lúc Windows đang chép
        # dở lên NAS (Explorer đặt sẵn dung lượng đầy đủ nên byte khớp ngay, mtime
        # còn chạy tới lúc chép xong 3 phút sau) → app la "file bị ghi đè" oan.
        doi = bool(video.get("kich_thuoc")) and st.st_size != video["kich_thuoc"]
        cu_mt = video.get("nas_mtime")
        if not doi and cu_mt is not None and abs(st.st_mtime - float(cu_mt)) > 2:
            # nội dung y nguyên → tự cập nhật lại vân tay, khỏi so đi so lại mãi
            _ghi_mtime(video["ma"], st.st_mtime)
            video["nas_mtime"] = st.st_mtime
    return {"co": True, "doi": doi, "duong_hien": str(p),
            "kich_thuoc_hien": st.st_size}


def _ghi_mtime(ma: str, mtime: float) -> None:
    conn = ket_noi()
    try:
        conn.execute("UPDATE video SET nas_mtime=? WHERE ma=?", (mtime, ma))
        conn.commit()
    finally:
        conn.close()


def cap_nhat_van_tay(ma: str) -> dict:
    """Nhận file HIỆN TẠI trên NAS làm đúng bản đang review (nút trên banner cảnh
    báo). Ghi lại dung lượng + ngày sửa + codec — dùng khi bản dựng được xuất đè
    hợp lệ, hoặc khi cảnh báo đến từ một lần chép dở."""
    v = lay_video(ma)
    if v is None:
        raise KeyError(ma)
    p = duong_video(v)
    if p is None or not p.is_file():
        raise FileNotFoundError(ma)
    st = p.stat()
    conn = ket_noi()
    try:
        conn.execute("UPDATE video SET kich_thuoc=?, nas_mtime=?, codec=? WHERE ma=?",
                     (st.st_size, st.st_mtime, doc_codec(p), ma))
        conn.commit()
    finally:
        conn.close()
    return {"ma": ma, "kich_thuoc": st.st_size}


# Codec trình duyệt giải mã được trong thẻ <video>. HEVC/H.265 KHÔNG nằm đây:
# Chrome/Edge trên Windows thiếu HEVC Video Extension nên chỉ ra tiếng, hình đen,
# lại KHÔNG bắn sự kiện lỗi → im lặng là kiểu hỏng tệ nhất, phải tự dò mà báo.
CODEC_PHAT_DUOC = {"h264", "av1", "vp8", "vp9", "theora"}
TEN_CODEC = {"hevc": "H.265 (HEVC)", "prores": "ProRes", "mpeg4": "MPEG-4 Part 2",
             "vc1": "VC-1", "wmv3": "WMV", "dnxhd": "DNxHD"}


def ffprobe() -> str | None:
    """Đường ffprobe (env VR_FFPROBE, rồi PATH). Không có → bỏ dò, KHÔNG cảnh báo
    bừa (thà không biết còn hơn báo sai)."""
    d = os.environ.get("VR_FFPROBE", "").strip()
    if d and Path(d).is_file():
        return d
    return shutil.which("ffprobe")


def doc_codec(p: Path) -> str:
    """Codec luồng hình đầu tiên, '' nếu không dò được. Luôn có TIMEOUT — lệnh
    ngoài không được treo request (bài học LLM_TIMEOUT hệ cũ)."""
    exe = ffprobe()
    if exe is None or not p.is_file():
        return ""
    try:
        ra = subprocess.run(
            [exe, "-v", "error", "-select_streams", "v:0", "-show_entries",
             "stream=codec_name", "-of", "default=noprint_wrappers=1:nokey=1", str(p)],
            capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return ""
    return (ra.stdout or "").strip().splitlines()[0].strip() if ra.stdout.strip() else ""


def ffmpeg_exe() -> str | None:
    """ffmpeg đi kèm ffprobe (env VR_FFMPEG, rồi cạnh ffprobe, rồi PATH)."""
    d = os.environ.get("VR_FFMPEG", "").strip()
    if d and Path(d).is_file():
        return d
    pr = ffprobe()
    if pr:
        canh = Path(pr).with_name("ffmpeg.exe" if pr.lower().endswith(".exe") else "ffmpeg")
        if canh.is_file():
            return str(canh)
    return shutil.which("ffmpeg")


def quet_hong(p: Path, so_mau: int = 4, dai: int = 2, thoi_luong: float = 0.0) -> str:
    """Giải mã THỬ vài lát rải đều file, trả '' nếu sạch, hoặc câu tóm tắt chỗ hỏng.

    Vì sao phải làm: file chép dở/đứt giữa chừng lên NAS vẫn ĐỦ DUNG LƯỢNG và đọc
    được header (ffprobe báo h264 ngon lành) — chỉ giải mã tới vùng hỏng mới lộ.
    Quét cả file 1,4GB thì lâu, nên chỉ lấy mẫu: đủ để bắt lỗi diện rộng kiểu chép
    đứt (LI088.2 hỏng liên tục từ giây 110 tới hết), KHÔNG hứa bắt được một vệt
    xước nhỏ — đây là lưới cảnh báo, không phải giấy chứng nhận.
    """
    exe = ffmpeg_exe()
    if exe is None or not p.is_file():
        return ""
    if thoi_luong <= 0:
        thoi_luong = _thoi_luong(p)
    if thoi_luong <= 0:
        return ""
    hong = []
    for i in range(so_mau):
        moc = thoi_luong * (i + 1) / (so_mau + 1)
        try:
            ra = subprocess.run(
                [exe, "-v", "error", "-ss", f"{moc:.1f}", "-t", str(dai), "-i", str(p),
                 "-f", "null", "-"],
                capture_output=True, text=True, timeout=90)
        except (OSError, subprocess.SubprocessError):
            return ""
        if any(dau in (ra.stderr or "") for dau in
               ("Invalid NAL", "missing picture", "Error splitting", "corrupt", "Invalid data")):
            hong.append(int(moc))
    if not hong:
        return ""
    # Trả THUẦN các mốc giờ (giao diện app bằng tiếng Anh, câu chữ do template lo)
    return ", ".join(f"{m // 60:02d}:{m % 60:02d}" for m in hong)


def _thoi_luong(p: Path) -> float:
    exe = ffprobe()
    if exe is None:
        return 0.0
    try:
        ra = subprocess.run(
            [exe, "-v", "error", "-show_entries", "format=duration", "-of",
             "default=noprint_wrappers=1:nokey=1", str(p)],
            capture_output=True, text=True, timeout=30)
        return float((ra.stdout or "0").strip() or 0)
    except (OSError, ValueError, subprocess.SubprocessError):
        return 0.0


def ghi_hong(ma: str, hong: str) -> None:
    conn = ket_noi()
    try:
        conn.execute("UPDATE video SET hong=? WHERE ma=?", (hong, ma))
        conn.commit()
    finally:
        conn.close()


def dang_bi_ghi(p: Path) -> bool:
    """File còn bị tiến trình khác GIỮ để ghi (đang chép lên NAS) — mở đọc là dính
    PermissionError. Đo thật 26/08: LI088.3 đang chép cho đúng lỗi này."""
    try:
        with open(p, "rb") as f:
            f.read(1)
        return False
    except PermissionError:
        return True
    except OSError:
        return False


def ghi_codec(ma: str, codec: str) -> None:
    conn = ket_noi()
    try:
        conn.execute("UPDATE video SET codec=? WHERE ma=?", (codec, ma))
        conn.commit()
    finally:
        conn.close()


def bao_dam_codec(video: dict) -> str:
    """Codec của bản ghi, dò LƯỜI một lần rồi nhớ luôn (bản ghi đời cũ chưa có)."""
    if video.get("codec"):
        return video["codec"]
    p = duong_video(video)
    if p is None or not p.is_file():
        return ""
    c = doc_codec(p)
    if c:
        ghi_codec(video["ma"], c)
        video["codec"] = c
    return c


def canh_bao_codec(codec: str) -> str:
    """Câu cảnh báo cho người dùng, '' khi phát được hoặc chưa dò được."""
    if not codec or codec in CODEC_PHAT_DUOC:
        return ""
    return TEN_CODEC.get(codec, codec.upper())


def ket_noi() -> sqlite3.Connection:
    p = _db_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(p, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def khoi_tao() -> None:
    """Chạy migration còn thiếu (bảng schema_version = số file .sql đã áp)."""
    conn = ket_noi()
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS schema_version (v INTEGER NOT NULL)")
        hang = conn.execute("SELECT v FROM schema_version").fetchone()
        hien_tai = hang["v"] if hang else 0
        cac_file = sorted((_APP_DIR / "migrations").glob("*.sql"))
        for f in cac_file:
            so = int(f.name.split("_")[0])
            if so <= hien_tai:
                continue
            conn.executescript(f.read_text(encoding="utf-8"))
            hien_tai = so
        if hang:
            conn.execute("UPDATE schema_version SET v=?", (hien_tai,))
        else:
            conn.execute("INSERT INTO schema_version (v) VALUES (?)", (hien_tai,))
        conn.commit()
    finally:
        conn.close()


def them_video_nas(ten: str, duong_nas: str, nguoi_tao: str, bo_phan: str,
                   kich_thuoc: int, mtime: float, codec: str = "", hong: str = "",
                   luc: datetime | None = None) -> dict:
    """Ghi sổ 1 video LIÊN KẾT tới file có sẵn trên NAS — không chép byte nào.
    Mã VR-xxxx sinh từ rowid trong CÙNG transaction (không đua giữa 2 lượt thêm);
    ten_file = tên file thật trên NAS để hiện/tải về đúng tên anh em đặt."""
    duong_nas = (duong_nas or "").replace("\\", "/").strip("/")
    if not duong_nas:
        raise ValueError("Thiếu đường file trên NAS")
    ten_file = duong_nas.rsplit("/", 1)[-1]
    duoi = ("." + ten_file.rsplit(".", 1)[-1]).lower() if "." in ten_file else ""
    if duoi not in DUOI_CHO_PHEP:
        raise ValueError(f"Đuôi {duoi} không hỗ trợ (nhận: {', '.join(sorted(DUOI_CHO_PHEP))})")
    luc = luc or datetime.now()
    conn = ket_noi()
    try:
        cur = conn.execute(
            "INSERT INTO video (ma, ten, ten_file, duong, mime, kich_thuoc, nguoi_tao,"
            " bo_phan, tao_luc, nguon, nas_mtime, codec, hong)"
            " VALUES ('', ?, ?, ?, ?, ?, ?, ?, ?, 'nas', ?, ?, ?)",
            (ten or ten_file, ten_file, duong_nas, DUOI_CHO_PHEP[duoi], kich_thuoc,
             nguoi_tao, bo_phan, luc.strftime("%Y-%m-%d %H:%M:%S"), mtime, codec, hong))
        ma = f"VR-{cur.lastrowid:04d}"
        conn.execute("UPDATE video SET ma=? WHERE id=?", (ma, cur.lastrowid))
        conn.commit()
    finally:
        conn.close()
    return {"ma": ma, "ten": ten or ten_file, "ten_file": ten_file,
            "duong": duong_nas, "nguon": "nas", "codec": codec, "hong": hong}


def da_lien_ket(duong_nas: str) -> dict | None:
    """Bản ghi CÒN SỐNG đang trỏ đúng file NAS này (chống thêm trùng một bản dựng)."""
    duong_nas = (duong_nas or "").replace("\\", "/").strip("/")
    conn = ket_noi()
    try:
        hang = conn.execute(
            "SELECT * FROM video WHERE nguon='nas' AND duong=? AND trang_thai != 'da_xoa'"
            " ORDER BY id DESC", (duong_nas,)).fetchone()
        return dict(hang) if hang else None
    finally:
        conn.close()


def lay_video(ma: str) -> dict | None:
    conn = ket_noi()
    try:
        hang = conn.execute("SELECT * FROM video WHERE ma=?", (ma,)).fetchone()
        return dict(hang) if hang else None
    finally:
        conn.close()


def thu_muc_feedback(video: dict) -> str:
    """Đường TƯƠNG ĐỐI của khối Feedback chứa bản dựng này, '' nếu bản ghi không
    nằm trong khối Feedback nào (bản ghi đời cũ trỏ thẳng vào thư mục tập —
    KHÔNG được phép xóa cả thư mục đó, trong đó có bản master của team)."""
    phan = (video.get("duong") or "").split("/")[:-1]
    for i in range(len(phan) - 1, -1, -1):
        if phan[i].strip().lower() in TEN_THU_MUC_FEEDBACK:
            return "/".join(phan[:i + 1])
    return ""


def tap_da_duyet(ma_tap_can_tim: str) -> bool:
    """Tập ĐÃ NGHIỆM THU chưa — có ít nhất một bản Approved còn sống. Đây là điều
    kiện DUY NHẤT mở khóa việc dọn file trên NAS (user chốt 20/08)."""
    if not ma_tap_can_tim:
        return False
    return any(ma_tap(v) == ma_tap_can_tim and v["trang_thai"] == "da_duyet"
               for v in danh_sach_video())


LOAI_VIDEO = ("duyet", "full")


def gan_tap(ma: str, ma_tap: str, loai: str = "duyet") -> None:
    if loai not in LOAI_VIDEO:
        raise ValueError(f"Loại lạ: {loai}")
    conn = ket_noi()
    try:
        cur = conn.execute("UPDATE video SET ma_tap=?, loai=? WHERE ma=?",
                           (ma_tap.upper(), loai, ma))
        if cur.rowcount == 0:
            raise KeyError(ma)
        conn.commit()
    finally:
        conn.close()


def gan_youtube(ma: str, yt_id: str, dang_luc: str = "") -> None:
    conn = ket_noi()
    try:
        cur = conn.execute("UPDATE video SET yt_id=?, dang_luc=? WHERE ma=?",
                           (yt_id.strip(), dang_luc.strip(), ma))
        if cur.rowcount == 0:
            raise KeyError(ma)
        conn.commit()
    finally:
        conn.close()


def cac_tap() -> list[dict]:
    """Mọi tập có trong sổ, mỗi tập gom bản duyệt + bản full."""
    nhom: dict[str, dict] = {}
    for v in danh_sach_video():
        ma = v["ma_tap"] or ma_tap(v)
        g = nhom.setdefault(ma, {"ma": ma, "duyet": [], "full": None, "moi_id": 0})
        if v["loai"] == "full":
            g["full"] = v
        else:
            g["duyet"].append(v)
        g["moi_id"] = max(g["moi_id"], v["id"])
    ra = sorted(nhom.values(), key=lambda g: -g["moi_id"])
    for g in ra:
        g["so_duyet"] = len(g["duyet"])
        g["xong_duyet"] = bool(g["duyet"]) and all(
            v["trang_thai"] == "da_duyet" for v in g["duyet"])
    return ra


def mot_tap(ma_tap_can: str) -> dict | None:
    ma_tap_can = (ma_tap_can or "").upper()
    for g in cac_tap():
        if g["ma"] == ma_tap_can:
            return g
    return None


def cac_duong_nas_dang_dung() -> set[str]:
    """Đường NAS đã có bản ghi CÒN SỐNG — để danh sách NAS đánh dấu 'đã trong app'."""
    conn = ket_noi()
    try:
        return {h["duong"] for h in conn.execute(
            "SELECT duong FROM video WHERE nguon='nas' AND trang_thai != 'da_xoa'")}
    finally:
        conn.close()


_RE_TAP = re.compile(r"([A-Za-z]{2,4})[\s_-]?(\d{2,4})")


def ma_tap(video: dict) -> str:
    """Mã tập rút từ TÊN FILE, lùi về tên thư mục cha ('LI037 fix lần 2.mp4' →
    'LI037'; 'LI049_Round 3.mp4' → 'LI049'). Không nhận ra → '' (nhóm 'Khác').
    Quy ước đặt tên của team, không phải luật cứng — sai thì rơi vào Khác, không
    bao giờ gộp nhầm hai tập vào nhau vì mã phải khớp nguyên vẹn."""
    ten = video.get("ten_file") or ""
    # Cấu trúc kho của team: <tập>/Feedback/<bản dựng>.mp4 — lùi lên tìm mã tập thì
    # phải NHẢY QUA thư mục 'Feedback', nếu không cả kho gom vào một nhóm 'Feedback'.
    phan = [x for x in (video.get("duong") or "").split("/")[:-1]
            if x.strip().lower() not in TEN_THU_MUC_FEEDBACK]
    for nguon in [ten] + phan[::-1] + [video.get("ten") or ""]:
        for m in _RE_TAP.finditer(nguon):
            # bỏ qua chính MÃ CỦA APP (file đời cũ tên '2026-08-19_VR-0003_li083.mp4')
            # — mã tập phải là mã của team, không phải số thứ tự trong sổ
            if m.group(1).upper() == "VR":
                continue
            return (m.group(1) + m.group(2)).upper()
    return ""


def danh_sach_video() -> list[dict]:
    """Danh sách chưa-gỡ, mới nhất trước, kèm số bình luận còn mở, TỔNG bình luận,
    và so_khac = bình luận của NGƯỜI KHÁC người đăng.

    so_khac (KHÔNG phải so_tong) mới là dấu hiệu 'đã có người review' — sự cố
    24/08/2026: nhân sự up xong nhắn kèm 'anh dịch được không anh' thì mục tự nhảy
    sang In review sau 20 giây, cờ Awaiting tắt trước khi leader kịp nhìn."""
    conn = ket_noi()
    try:
        hang = conn.execute(
            "SELECT v.*, (SELECT COUNT(*) FROM binh_luan b WHERE b.video_ma = v.ma"
            "  AND b.trang_thai = 'mo') AS so_mo,"
            " (SELECT COUNT(*) FROM binh_luan b2 WHERE b2.video_ma = v.ma) AS so_tong,"
            " (SELECT COUNT(*) FROM binh_luan b3 WHERE b3.video_ma = v.ma"
            "  AND b3.nguoi <> v.nguoi_tao) AS so_khac"
            " FROM video v WHERE v.trang_thai != 'da_xoa' ORDER BY v.id DESC").fetchall()
        return [dict(h) for h in hang]
    finally:
        conn.close()


def doi_trang_thai(ma: str, trang_thai: str) -> None:
    if trang_thai not in TRANG_THAI_VIDEO:
        raise ValueError(f"Trạng thái lạ: {trang_thai}")
    conn = ket_noi()
    try:
        cur = conn.execute("UPDATE video SET trang_thai=? WHERE ma=?", (trang_thai, ma))
        if cur.rowcount == 0:
            raise KeyError(ma)
        conn.commit()
    finally:
        conn.close()


def xoa_cung_video(ma: str) -> dict:
    """XÓA CỨNG một bản ghi: bình luận + dòng video biến mất khỏi sổ, không khôi
    phục được (khác GỠ MỀM vốn chỉ ẩn khỏi danh sách). Chỉ dùng cho tập đã nghiệm
    thu xong — route lo phần quyền + xác nhận. Trả số bình luận đã xóa để ghi sổ."""
    conn = ket_noi()
    try:
        hang = conn.execute("SELECT ten FROM video WHERE ma=?", (ma,)).fetchone()
        if hang is None:
            raise KeyError(ma)
        so_bl = conn.execute("SELECT COUNT(*) FROM binh_luan WHERE video_ma=?",
                             (ma,)).fetchone()[0]
        conn.execute("DELETE FROM binh_luan WHERE video_ma=?", (ma,))
        conn.execute("DELETE FROM video WHERE ma=?", (ma,))
        conn.commit()
    finally:
        conn.close()
    return {"ma": ma, "ten": hang["ten"], "so_binh_luan": so_bl}


def cac_video_cua_tap(ma_tap_can_tim: str) -> list[dict]:
    """MỌI bản ghi của một tập, kể cả đã gỡ mềm — xóa cứng phải quét sạch, không
    để lại bản ghi ẩn của cùng tập đó trong sổ."""
    conn = ket_noi()
    try:
        hang = [dict(h) for h in conn.execute("SELECT * FROM video ORDER BY id").fetchall()]
    finally:
        conn.close()
    return [v for v in hang if ma_tap(v) == ma_tap_can_tim]


# ---------- bình luận ----------

def them_binh_luan(video_ma: str, nguoi: str, noi_dung: str,
                   ts_giay: float | None = None, ve_json: str | None = None) -> dict:
    noi_dung = (noi_dung or "").strip()
    if not noi_dung:
        raise ValueError("Bình luận rỗng")
    if ve_json:
        json.loads(ve_json)  # phải là JSON hợp lệ — hỏng thì ValueError nổ ngay tại cửa
    if lay_video(video_ma) is None:
        raise KeyError(video_ma)
    conn = ket_noi()
    try:
        cur = conn.execute(
            "INSERT INTO binh_luan (video_ma, nguoi, noi_dung, ts_giay, ve_json, tao_luc)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (video_ma, nguoi, noi_dung, ts_giay, ve_json,
             datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        hang = conn.execute("SELECT * FROM binh_luan WHERE id=?", (cur.lastrowid,)).fetchone()
        return dict(hang)
    finally:
        conn.close()


def ds_binh_luan(video_ma: str) -> list[dict]:
    """Bình luận theo mốc thời gian tăng dần; bình luận chung (không mốc) xuống cuối."""
    conn = ket_noi()
    try:
        hang = conn.execute(
            "SELECT * FROM binh_luan WHERE video_ma=?"
            " ORDER BY ts_giay IS NULL, ts_giay, id", (video_ma,)).fetchall()
        return [dict(h) for h in hang]
    finally:
        conn.close()


def _sua_binh_luan(bl_id: int, nguoi: str, la_duyet: bool, cau_sql: str) -> None:
    """Khuôn chung giải/xóa: chỉ CHÍNH CHỦ hoặc người có quyền duyệt (Leader+)."""
    conn = ket_noi()
    try:
        hang = conn.execute("SELECT nguoi FROM binh_luan WHERE id=?", (bl_id,)).fetchone()
        if hang is None:
            raise KeyError(bl_id)
        if hang["nguoi"] != nguoi and not la_duyet:
            raise PermissionError("Chỉ người viết hoặc Leader+ được thao tác")
        conn.execute(cau_sql, (bl_id,))
        conn.commit()
    finally:
        conn.close()


def giai_binh_luan(bl_id: int, nguoi: str, la_duyet: bool) -> None:
    _sua_binh_luan(bl_id, nguoi, la_duyet,
                   "UPDATE binh_luan SET trang_thai='da_giai' WHERE id=?")


def mo_lai_binh_luan(bl_id: int, nguoi: str, la_duyet: bool) -> None:
    _sua_binh_luan(bl_id, nguoi, la_duyet,
                   "UPDATE binh_luan SET trang_thai='mo' WHERE id=?")


def xoa_binh_luan(bl_id: int, nguoi: str, la_duyet: bool) -> None:
    _sua_binh_luan(bl_id, nguoi, la_duyet, "DELETE FROM binh_luan WHERE id=?")


# ---------- phụ đề (.srt/.vtt — mỗi video tối đa MỘT phụ đề) ----------
# Hai nguồn: (1) bản gắn TỪ APP nằm trong kho app (kho/phu-de/<ma>.srt) — app sở hữu,
# gỡ được; (2) file .srt anh em để CẠNH video trên NAS — app chỉ ĐỌC, không bao giờ
# ghi/xóa. Bản gắn từ app thắng (người dùng vừa gắn thì phải thấy bản mới).

DUOI_PHU_DE = (".srt", ".vtt")


def _phu_de_app(video: dict, duoi: str) -> Path:
    return kho_dir() / "phu-de" / f"{video['ma']}{duoi}"


def phu_de_tim(video: dict) -> tuple[Path | None, str]:
    """(đường, nguồn) với nguồn ∈ 'app' | 'nas' | 'kho' (sidecar đời cũ) | ''."""
    for d in DUOI_PHU_DE:
        p = _phu_de_app(video, d)
        if p.is_file():
            return p, "app"
    goc = duong_video(video)
    if goc is None:
        return None, ""
    canh = "nas" if (video.get("nguon") or "kho") == "nas" else "kho"
    for d in DUOI_PHU_DE:
        # hai lối đặt tên ngoài đời: "phim.mp4.srt" (kho app đời cũ) và "phim.srt"
        for ung in (goc.with_name(goc.name + d), goc.with_name(goc.stem + d)):
            if ung.is_file():
                return ung, canh
    return None, ""


def duong_phu_de(video: dict) -> Path | None:
    return phu_de_tim(video)[0]


def doc_phu_de_bytes(b: bytes) -> str:
    """SRT ngoài đời đủ kiểu encoding (CapCut/Premiere UTF-8, tool cũ UTF-16) —
    thử lần lượt, bí quá thay ký tự hỏng chứ không nổ."""
    for enc in ("utf-8-sig", "utf-16"):
        try:
            return b.decode(enc)
        except UnicodeDecodeError:
            pass
    return b.decode("utf-8", errors="replace")


def srt_sang_vtt(chu: str) -> str:
    """SRT → WebVTT (thứ DUY NHẤT <track> trình duyệt chịu đọc): thêm header +
    đổi dấu phẩy mili-giây thành chấm. Dòng số thứ tự SRT giữ nguyên — VTT coi
    là cue identifier hợp lệ. File đã là VTT → trả nguyên."""
    chu = chu.lstrip("﻿")
    if chu.lstrip().upper().startswith("WEBVTT"):
        return chu
    chu = re.sub(r"(\d{2}:\d{2}:\d{2}),(\d{3})", r"\1.\2", chu)
    return "WEBVTT\n\n" + chu


def ghi_phu_de(video: dict, chu: str, duoi: str) -> Path:
    """Ghi phụ đề vào KHO APP (nguyên tử) — TUYỆT ĐỐI không ghi lên NAS.
    Gắn bản mới thì gỡ bản app cũ khác đuôi."""
    dich = _phu_de_app(video, duoi)
    dich.parent.mkdir(parents=True, exist_ok=True)
    for d in DUOI_PHU_DE:
        cu = _phu_de_app(video, d)
        if d != duoi and cu.is_file():
            cu.unlink()
    tam = dich.with_name(dich.name + ".tam")
    tam.write_text(chu, encoding="utf-8", newline="")
    os.replace(tam, dich)
    return dich


def xoa_phu_de(video: dict) -> bool:
    """Gỡ phụ đề APP SỞ HỮU (kho app). Trả False khi phụ đề đang đọc từ file cạnh
    video trên NAS — app chỉ đọc, muốn bỏ thì gỡ file đó trên NAS."""
    p, nguon = phu_de_tim(video)
    if p is None or nguon == "nas":
        return False
    p.unlink()
    return True
