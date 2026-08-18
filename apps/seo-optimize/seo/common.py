"""Tiện ích dùng chung: paths, run/profile dir, JSON IO, .env, YouTube Data API.

Convention kế thừa Outline Extract. Key YouTube đọc từ api.txt (mỗi dòng 1 key,
gitignore) hoặc .env (YOUTUBE_API_KEY / YOUTUBE_API_KEYS). Xoay key khi hết quota.
"""
from __future__ import annotations

import json
import os
import re
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from . import khoa_v3

# Console Windows mặc định là cp1252/cp437 → MỌI print tiếng Việt ném UnicodeEncodeError.
# `server.run()` in "…(Ctrl+C để dừng)" ngay dòng đầu ⇒ double-click Start.bat là chết ngay
# lúc khởi động. Đặt ở common.py vì mọi entry point (server + self-test từng module) đều import.
# errors="replace": thà hiện dấu ? còn hơn làm sập tool vì một dòng log.
for _s in (sys.stdout, sys.stderr):
    if _s is not None and (getattr(_s, "encoding", "") or "").lower().replace("-", "") != "utf8":
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:                                  # noqa: BLE001 — stream bị thay thế/không hỗ trợ
            pass

# V3 (19/08/2026): DỮ LIỆU TÁCH KHỎI CODE (Luật 1 kien_truc_nen.md) — start-all đặt
# SEO_DATA_DIR=data/seo-optimize nên users.json/profiles/episodes/formats/niches/
# markets.json/runs/logs/.trash/.cache đều nằm ngoài folder code. Không đặt biến
# (chạy kiểu V2/dev lẻ) thì cạnh code như cũ. board.html/code neo theo __file__.
ROOT = Path(os.environ.get("SEO_DATA_DIR") or Path(__file__).resolve().parent.parent).resolve()
RUNS = ROOT / "runs"
PROFILES = ROOT / "profiles"

_ID_RE = re.compile(r"(?:v=|youtu\.be/|/shorts/|/embed/)([A-Za-z0-9_-]{11})")
_BARE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
_KEY_RE = re.compile(r"^AIza[A-Za-z0-9_-]{20,}$")
_YT_KEY_ENV_RE = re.compile(r"^YOUTUBE_API_KEYS?(?:_(\d+))?$")   # KEYS · KEY · KEY_1 … KEY_19


# ── config / keys ──
def load_env() -> None:
    """Nạp .env vào os.environ (không ghi đè biến đã có).

    Đọc bằng **utf-8-sig**, không phải utf-8: trên Windows, `Set-Content -Encoding utf8` (PowerShell
    5.1) và Notepad đều thêm BOM vào đầu file. Đọc utf-8 thường thì BOM dính vào tên biến ĐẦU TIÊN
    (`﻿LLM_PROVIDER`) ⇒ biến đó coi như KHÔNG TỒN TẠI, mà không có lỗi nào cả — tool âm thầm
    rơi về mặc định. Đã cắn 2026-07-30: user sửa .env bằng PowerShell, `LLM_PROVIDER` biến mất.
    """
    f = ROOT / ".env"
    if not f.exists():
        return
    for line in f.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        s = line.strip().lstrip("﻿")                  # phòng cả BOM đứng giữa file (nối file)
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _yt_key_order(name: str) -> tuple[int, int]:
    """YOUTUBE_API_KEYS / YOUTUBE_API_KEY trước, rồi _1 _2 … _10 theo SỐ (không theo mặt chữ)."""
    m = _YT_KEY_ENV_RE.match(name)
    n = m.group(1) if m else None
    return (1, int(n)) if n else (0, 0)


def load_keys() -> list[str]:
    """API key YouTube: ưu tiên api.txt (mỗi dòng 1 key), fallback .env.

    Nhận MỌI biến dạng `YOUTUBE_API_KEY*`: `YOUTUBE_API_KEYS` (nhiều key, phân tách bằng dấu
    phẩy/khoảng trắng), `YOUTUBE_API_KEY`, và cả loạt đánh số `YOUTUBE_API_KEY_1..N`.
    Gom hết rồi bỏ trùng — mỗi key là 10.000 quota/ngày, bỏ sót 1 biến là mất nguyên 1 trần quota.

    V3 (19/08/2026): sau gateway OUTLIERY thì nguồn khóa DUY NHẤT là KÉT (việc
    trich_kenh) — không fallback api.txt/.env kẻo hai nguồn khóa lệch nhau.
    """
    if khoa_v3.bat():
        return khoa_v3.khoa_youtube()
    keys: list[str] = []
    f = ROOT / "api.txt"
    if f.exists():
        for line in f.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if _KEY_RE.match(s) and s not in keys:
                keys.append(s)
    load_env()
    for name in sorted((n for n in os.environ if _YT_KEY_ENV_RE.match(n)), key=_yt_key_order):
        for s in re.split(r"[,\s]+", os.environ.get(name) or ""):
            s = s.strip()
            if _KEY_RE.match(s) and s not in keys:
                keys.append(s)
    return keys


# ── ids / slug / dirs ──
def extract_video_id(s: str) -> str | None:
    s = s.strip()
    if _BARE_ID_RE.match(s):
        return s
    m = _ID_RE.search(s)
    return m.group(1) if m else None


def parse_urls(text: str) -> list[str]:
    """Từ khối text nhiều dòng → danh sách video_id (giữ thứ tự, bỏ trùng)."""
    ids: list[str] = []
    for line in (text or "").splitlines():
        vid = extract_video_id(line)
        if vid and vid not in ids:
            ids.append(vid)
    return ids


def slug(s: str) -> str:
    s = re.sub(r"[^\w\s-]", "", s or "").strip().lower()
    return re.sub(r"[\s_-]+", "-", s) or "x"


def run_dir(name: str, *, create: bool = False) -> Path:
    d = RUNS / slug(name)
    if create:
        d.mkdir(parents=True, exist_ok=True)
    return d


def profiles_dir(*, create: bool = False) -> Path:
    if create:
        PROFILES.mkdir(parents=True, exist_ok=True)
    return PROFILES


# ── thùng rác: xoá được HOÀN TÁC 1 lần, tự dọn sau 24h ──
TRASH_TTL_H = 24                    # user chốt 2026-07-29: quá 24h thì dọn sạch


# Mọi thao tác thùng rác phải NỐI TIẾP nhau. ThreadingHTTPServer cho 2 request chạy song song:
# phản biện 2026-07-30 tái hiện được ca `restore` và `purge_one` chạy chồng → `purge` unlink xong
# trước khi `restore` kịp đọc file ⇒ hồ sơ MẤT TRẮNG khỏi cả `profiles/` lẫn `.trash/`.
_TRASH_LOCK = threading.Lock()


def _trash_dir(*, create: bool = False) -> Path:
    """Tính từ ROOT LÚC GỌI, không phải hằng số lúc import.

    Hằng số kiểu `TRASH = ROOT / ".trash"` bị đóng băng lúc import: self-test trỏ
    `common.ROOT` sang thư mục tạm thì thùng rác VẪN ghi vào dự án thật — đã cắn thật, self-test
    của episodes.py đổ 3 mục rác vào `.trash/` của user. Cùng lớp bẫy với `formats_dir`.
    """
    d = ROOT / ".trash"
    if create:
        d.mkdir(parents=True, exist_ok=True)
    return d


def purge_one(token: str, at: float | None = None) -> dict | None:
    """XOÁ HẲN 1 mục trong thùng rác. KHÔNG hoàn tác được — tầng UI phải hỏi lại trước khi gọi.

    An toàn đường dẫn nằm ở `_safe_token()`: whitelist mặt chữ nên token không thể chứa dấu gạch
    chéo (xuôi hay ngược), `..`, tên thiết bị Windows, hay ký tự điều khiển. Chỉ chạm đúng `<token>.json` TRONG
    `.trash/`, không bao giờ chạm `profiles/` `formats/` `episodes/` `runs/`.

    ĐỪNG viết hàng rào kiểu `f.parent.resolve() != _trash_dir().resolve()` rồi coi đó là bằng chứng
    chống thoát thư mục: `f` được ghép từ `_trash_dir() / name` nên parent LUÔN bằng, mệnh đề đó
    không bao giờ đúng — phản biện 2026-07-30 gọi thẳng nó là dead code gây ngộ nhận cho người sau.

    `at` = `deleted_at` mà UI thấy lúc liệt kê. Lệch > 1s nghĩa là file trong thùng đã là BẢN KHÁC
    → trả `{"changed": True}` để tầng trên hỏi lại, đừng xoá bản mới khi user tưởng đang dọn bản cũ.
    """
    name = _safe_token(token)
    if not name:
        return None
    with _TRASH_LOCK:                                      # cùng khoá với restore/trash: xem _TRASH_LOCK
        f = _trash_dir() / f"{name}.json"
        if not f.exists():
            return None
        try:
            b = read_json(f)
        except Exception:                                  # noqa: BLE001 — file rác vẫn phải xoá được
            b = {}
        if at is not None and abs(float(b.get("deleted_at") or 0) - float(at)) > 1.0:
            # Cùng token nhưng KHÁC bản: user xoá → extract lại → xoá lần nữa thì token y hệt.
            # Panel đang mở tả bản CŨ mà file trên đĩa là bản MỚI (đắt hơn) → không xoá mù.
            return {"changed": True, "deleted_at": b.get("deleted_at")}
        try:
            f.unlink()
        except FileNotFoundError:
            return None
        except OSError as e:
            raise RuntimeError(f"Không xoá được (file đang bị giữ hoặc chỉ-đọc): {e.strerror}") from e
    return {"kind": b.get("kind", ""), "stem": b.get("stem", name)}


def purge_trash(now: float | None = None) -> int:
    """Dọn mục quá hạn. Gọi kèm mỗi thao tác thùng rác — khỏi cần scheduler."""
    import time
    d = _trash_dir()
    if not d.exists():
        return 0
    cutoff = (now if now is not None else time.time()) - TRASH_TTL_H * 3600
    n = 0
    for f in d.glob("*.json"):
        try:
            if f.stat().st_mtime < cutoff:
                f.unlink()
                n += 1
        except OSError:                                    # file đang bị giữ → để lần sau
            pass
    return n


_TOKEN_OK = None                    # regex chốt token, khởi tạo lười


def _safe_token(token) -> str:
    """Token thùng rác hợp lệ, hoặc "" nếu đáng ngờ. Dùng CHUNG cho restore + purge_one.

    KHÔNG chỉ dựa vào `Path(...).name`: trên Windows, `.trash/CON.json` phân giải thành THIẾT BỊ
    console ở mọi thư mục → `exists()` trả True và `read_json` treo vĩnh viễn 1 thread của server;
    `NUL` thì ném WinError 87. Token không phải chuỗi (list/int) làm `Path()` ném TypeError, request
    chết không có response. Cả ba đều do phản biện 2026-07-30 tái hiện được.
    Whitelist mặt chữ chặn sạch cả ba, và khớp đúng dạng token do `trash()` sinh ra.
    """
    global _TOKEN_OK
    if _TOKEN_OK is None:
        # Token do `trash()` sinh LUÔN là `<kind>__<stem>` (+ `~n` nếu giữ bản cũ). Bắt buộc có `__`
        # là chặn luôn mọi tên thiết bị Windows (CON/NUL/CONIN$/COM1…) mà không cần danh sách đen.
        # `stem` đi qua slug()/ascii_slug() nên chỉ còn [a-z0-9-]; kind chỉ có chữ.
        _TOKEN_OK = re.compile(r"[a-z]{3,20}__[0-9a-z][0-9a-z-]{0,100}(?:~\d{1,2})?", re.I)
    name = Path(str(token or "")).name
    return name if _TOKEN_OK.fullmatch(name or "") else ""


def _free_token(token: str) -> str:
    """Chỗ trống cho bản mới, KHÔNG đè bản đang có trong thùng rác."""
    d = _trash_dir()
    if not (d / f"{token}.json").exists():
        return token
    for i in range(1, 100):
        if not (d / f"{token}~{i}.json").exists():
            return f"{token}~{i}"
    return f"{token}~99"


def trash(path: Path, kind: str = "") -> str | None:
    """XOÁ = chuyển vào thùng rác, KHÔNG unlink thật. Trả token để hoàn tác.

    **KHÔNG ĐÈ bản đang có trong thùng** (sửa 2026-07-30, phản biện bắt được ca mất dữ liệu THẬT):
    xoá kênh → extract lại (bản mới KHÔNG có link/CTA/sub_url/format vì hồ sơ cũ đã bị xoá nên
    `merge_user` chẳng có gì để gộp) → xoá lần nữa. Bản ghi thứ hai từng ĐÈ bản đầu, cuốn theo
    toàn bộ thứ user GÕ TAY — không harvest lại được bằng quota hay token. Giờ bản cũ được giữ
    thành `<token>~1.json`, hiện thành một dòng riêng trong thùng rác, vẫn tự dọn sau 24h.
    """
    import time
    p = Path(path)
    if not p.exists():
        return None
    with _TRASH_LOCK:
        purge_trash()
        token = _free_token(f"{kind or p.parent.name}__{p.stem}")
        body = {"kind": kind or p.parent.name, "orig": str(p), "stem": p.stem,
                "deleted_at": time.time(), "data": read_json(p)}
        _trash_dir(create=True)
        (_trash_dir() / f"{token}.json").write_text(json.dumps(body, ensure_ascii=False, indent=1),
                                                   encoding="utf-8")
        p.unlink()
    return token


def trash_list() -> list[dict]:
    purge_trash()
    out = []
    d = _trash_dir()
    for f in (d.glob("*.json") if d.exists() else []):
        try:
            b = read_json(f)
        except Exception:                                  # noqa: BLE001
            continue
        out.append({"token": f.stem, "kind": b.get("kind", ""), "stem": b.get("stem", ""),
                    "name": (b.get("data") or {}).get("name") or (b.get("data") or {}).get("channel")
                            or b.get("stem", ""),
                    "deleted_at": b.get("deleted_at", 0)})
    return sorted(out, key=lambda x: -x["deleted_at"])


def trash_peek(token: str) -> dict | None:
    """Bản ghi GỐC của một mục trong thùng rác, để soi phạm vi TRƯỚC khi cho khôi phục.

    Chỉ ĐỌC, không đụng gì. Cần vì từ 2026-08-02 Leader khôi phục được, mà Leader lại bị giới
    hạn theo THỊ TRƯỜNG — không xem trước thì họ khôi phục được cả kênh của thị trường khác,
    tức lách qua hàng rào phạm vi bằng đường vòng.
    """
    name = _safe_token(token)
    if not name:
        return None
    f = _trash_dir() / f"{name}.json"
    if not f.exists():
        return None
    try:
        b = read_json(f)
    except Exception:                                      # noqa: BLE001 — bản ghi hỏng
        return None
    return {"kind": b.get("kind", ""), "stem": b.get("stem", ""), "data": b.get("data") or {}}


_KINDS = ("profiles", "formats", "episodes")   # cả 3 đều là ROOT/<kind>, không có ngoại lệ


def restore(token: str) -> dict | None:
    """Đưa mục về chỗ cũ. Trả về thông tin đã khôi phục, hoặc None nếu hết hạn/không có.

    Đích được DỰNG LẠI từ `ROOT + kind + stem`, KHÔNG dùng `orig` (đường dẫn tuyệt đối lúc xoá):
    đổi tên/di chuyển thư mục dự án là `orig` trỏ vào chỗ cũ ⇒ file được ghi ra ngoài dự án, bản
    trong thùng bị xoá, mà UI vẫn báo "Đã khôi phục". Phản biện 2026-07-30 tái hiện được ca này.
    `orig` chỉ còn là dự phòng cho bản ghi cũ chưa có `kind`.
    """
    name = _safe_token(token)
    if not name:
        return None
    with _TRASH_LOCK:                                      # nối tiếp với purge_one/trash
        purge_trash()
        f = _trash_dir() / f"{name}.json"
        if not f.exists():
            return None
        b = read_json(f)
        kind = b.get("kind") or ""
        stem = b.get("stem") or ""
        dest = (ROOT / kind / f"{stem}.json") if (kind in _KINDS and stem) else Path(b.get("orig") or "")
        if not str(dest):
            return None
        # Chốt cuối: đích PHẢI nằm trong dự án. Nhánh dự phòng `orig` vẫn là đường ghi file duy nhất
        # có thể vượt ra ngoài ROOT — `.trash/` mang từ máy khác sang (orig kiểu POSIX
        # "/Users/…/profiles/x.json") thì trên Windows `Path()` coi là gốc ổ đĩa hiện tại và
        # `write_json` TẠO MỚI cả cây ở "C:\Users\…" — verify được 2026-07-30.
        try:
            outside = not dest.resolve().is_relative_to(ROOT.resolve())
        except (OSError, ValueError):
            outside = True
        if outside:
            return {"outside": True, "orig": str(dest)}    # KHÔNG ghi, KHÔNG unlink bản trong thùng
        if dest.exists():                                  # đã có file mới cùng tên → KHÔNG đè
            return {"conflict": True, "orig": str(dest)}
        write_json(dest, b.get("data") or {})              # ghi XONG mới unlink, không đảo thứ tự
        f.unlink()                                         # hoàn tác xong là hết, không lần 2
    return {"kind": kind, "stem": b.get("stem", ""), "orig": str(dest)}


def read_json(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path: Path, data) -> None:
    """Ghi NGUYÊN TỬ (file tạm + os.replace) — vá 03/08/2026 khi kiểm chống ghi đè.

    Đây là đường ghi CHUNG của mọi dữ liệu (users/profiles/episodes/niches/formats/
    markets). Ghi trần thì crash/mất điện GIỮA lúc ghi là file JSON cụt — users.json
    cụt là cả hệ đăng nhập chết. os.replace cùng ổ đĩa là rename nguyên tử của HĐH:
    bản cũ còn nguyên cho tới khi bản mới nằm trọn trên đĩa. Đuôi .json.tmp không
    lọt các glob("*.json") đang dùng. (DATA_LOCK đã tuần tự hóa ghi TRONG tiến trình
    — đo 03/08: 12/12 bản ghi sống khi bắn đồng thời; lớp này chống CRASH, không
    phải chống đua.)"""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tam = p.with_name(p.name + ".tmp")
    tam.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tam, p)


# ── YouTube Data API ──
_KEY_LOCK = threading.Lock()
_KEY_AT = 0            # key gần nhất còn dùng được — điểm BẮT ĐẦU của vòng xoay lần sau


def key_cursor() -> int:
    """Vị trí key đang dùng (cho self-test/chẩn đoán)."""
    with _KEY_LOCK:
        return _KEY_AT


def yt_get(endpoint: str, params: dict, keys: list[str]) -> dict:
    """GET YouTube Data API, xoay key khi quotaExceeded. Raise nếu hết key/lỗi khác.

    **Bắt đầu từ key gần nhất còn dùng được, KHÔNG dò lại từ `keys[0]`.** Bản cũ luôn khởi
    động ở key đầu danh sách: sang giữa ngày, khi 5 key đầu đã cạn quota, MỌI request phải
    ăn đủ 5 lượt round-trip hỏng (~200 ms/lượt, đo thật) rồi mới tới key sống — mà một lần
    extract format có ~5 request/kênh. Nhớ con trỏ thì mỗi lần một key cạn chỉ tốn ĐÚNG MỘT
    lượt hỏng, không phải mỗi request một lượt.
    Vẫn quay hết vòng nên không key nào bị bỏ sót, và con trỏ chỉ nhích khi có key trả 200.
    """
    if not keys:
        raise RuntimeError("Không có YouTube API key (api.txt / .env)")
    global _KEY_AT
    with _KEY_LOCK:
        start = _KEY_AT % len(keys)
    last = ""
    for off in range(len(keys)):
        i = (start + off) % len(keys)
        q = dict(params)
        q["key"] = keys[i]
        url = f"https://www.googleapis.com/youtube/v3/{endpoint}?" + urllib.parse.urlencode(q)
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                data = json.loads(r.read().decode("utf-8"))
            if i != start:                       # đổi key thành công → lần sau vào thẳng key này
                with _KEY_LOCK:
                    _KEY_AT = i
            return data
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")
            if e.code == 403 and "quota" in body.lower():
                last = body
                continue                         # hết quota key này → thử key kế
            raise RuntimeError(f"YouTube API {e.code}: {body[:200]}")
    raise RuntimeError("Hết quota tất cả key: " + last[:200])


def fetch_videos(ids: list[str], keys: list[str],
                 parts: str = "snippet,statistics,contentDetails") -> list[dict]:
    """videos.list batch 50 (1 unit/lô). Trả list item snippet (có tags thật của mọi video)."""
    out: list[dict] = []
    for i in range(0, len(ids), 50):
        chunk = ids[i:i + 50]
        d = yt_get("videos", {"part": parts, "id": ",".join(chunk), "maxResults": 50}, keys)
        out.extend(d.get("items", []))
    return out


_CHANNEL_RE = re.compile(r"/channel/(UC[\w-]{20,})")
_UC_RE = re.compile(r"^(UC[\w-]{20,})$")
_HANDLE_RE = re.compile(r"@([A-Za-z0-9._-]+)")
_USER_RE = re.compile(r"/user/([A-Za-z0-9_-]+)")
_C_RE = re.compile(r"/c/([^/?#]+)")


def resolve_channel_id(text: str, keys: list[str]) -> str | None:
    """URL/handle/ID kênh HOẶC 1 video của kênh → channelId. Dùng cho Module 1 (nhập URL kênh)."""
    text = (text or "").strip()
    m = _CHANNEL_RE.search(text) or _UC_RE.match(text)
    if m:
        return m.group(1)
    m = _HANDLE_RE.search(text)                                # @handle
    if m:
        d = yt_get("channels", {"part": "id", "forHandle": "@" + m.group(1)}, keys)
        if d.get("items"):
            return d["items"][0]["id"]
    m = _USER_RE.search(text)                                  # /user/name (cũ)
    if m:
        d = yt_get("channels", {"part": "id", "forUsername": m.group(1)}, keys)
        if d.get("items"):
            return d["items"][0]["id"]
    vid = extract_video_id(text)                               # 1 video của kênh → suy channel
    if vid:
        vids = fetch_videos([vid], keys, parts="snippet")
        if vids:
            return vids[0]["snippet"]["channelId"]
    m = _C_RE.search(text)                                     # /c/name hoặc tên trần → search
    q = m.group(1) if m else text
    if q:
        d = yt_get("search", {"part": "snippet", "type": "channel", "q": q, "maxResults": 1}, keys)
        if d.get("items"):
            return d["items"][0]["snippet"]["channelId"]
    return None


def sub_url_from(text: str) -> str:
    """Link kênh (hoặc channelId / @handle) → link SUB_CONFIRMATION. Thuần chuỗi, 0 quota.

    User chỉ cần dán link kênh của mình, khỏi phải nhớ đuôi `?sub_confirmation=1`.
    Ưu tiên dạng `/channel/UC…` vì đó là dạng chuẩn, không chết khi kênh đổi handle.
    Không nhận ra được thì TRẢ NGUYÊN input — không đoán bừa, để tầng trên báo lỗi.
    """
    t = (text or "").strip()
    if not t:
        return ""
    if "sub_confirmation=1" in t:                          # đã đúng dạng rồi thì thôi
        return t
    base = t.split("?", 1)[0].split("#", 1)[0].rstrip("/")
    m = _CHANNEL_RE.search(base) or _UC_RE.match(base)
    if m:
        return f"https://www.youtube.com/channel/{m.group(1)}?sub_confirmation=1"
    m = _HANDLE_RE.search(base)
    if m:
        return f"https://www.youtube.com/@{m.group(1)}?sub_confirmation=1"
    m = _USER_RE.search(base)
    if m:
        return f"https://www.youtube.com/user/{m.group(1)}?sub_confirmation=1"
    return t


PROFILE_MIN_VIDEOS, PROFILE_MAX_VIDEOS = 5, 50


def channel_video_ids(channel_id: str, keys: list[str], limit: int = 30) -> list[str]:
    """channelId → `limit` video MỚI NHẤT (uploads playlist xếp mới→cũ, phân trang).

    Kênh nhiều video vẫn chỉ lấy N gần nhất: limit bị chốt trong [5, 50] để tránh
    tốn quota/thời gian (đủ pool để suy skeleton, không cần cả kênh).
    """
    limit = max(PROFILE_MIN_VIDEOS, min(int(limit), PROFILE_MAX_VIDEOS))
    d = yt_get("channels", {"part": "contentDetails", "id": channel_id}, keys)
    items = d.get("items", [])
    # Trả [] ở đây thì lời gọi bên trên báo "Kênh không có video công khai" — SAI nguyên nhân.
    # API không trả kênh nào nghĩa là id sai / kênh bị xoá / bị chặn, khác hẳn kênh rỗng.
    if not items:
        raise RuntimeError(f"API không trả về kênh nào cho id {channel_id} "
                           "— id sai, kênh đã xoá, hoặc bị chặn ở khu vực này")
    # Truy chuỗi thẳng items[0]["contentDetails"]["relatedPlaylists"]["uploads"] sẽ ném
    # KeyError hiện lên UI đúng một chữ 'uploads', không ai hiểu là lỗi gì.
    uploads = (((items[0].get("contentDetails") or {}).get("relatedPlaylists") or {}).get("uploads") or "")
    # Có `items` = kênh CÓ THẬT. Thiếu uploads playlist thì đó là kênh chưa đăng video nào
    # (kênh mới tinh) — trả [] để tầng trên xử lý như "chưa có video", KHÔNG phải lỗi.
    if not uploads:
        return []
    ids: list[str] = []
    token = None
    # Chặn cứng số trang: limit ≤ 50 và mỗi trang tối đa 50 nên 6 trang là quá dư. Không có
    # chặn này, một trang RỖNG mà vẫn kèm nextPageToken (video private/bị xoá lọt vào playlist)
    # sẽ làm vòng lặp không bao giờ tiến → quay vô hạn, đốt sạch quota của cả 19 key.
    for _ in range(6):
        if len(ids) >= limit:
            break
        params = {"part": "contentDetails", "playlistId": uploads, "maxResults": min(50, limit - len(ids))}
        if token:
            params["pageToken"] = token
        try:
            pl = yt_get("playlistItems", params, keys)
        except RuntimeError as e:
            # Kênh 0 video công khai: channels.list VẪN trả uploads id (UU… soi gương UC…,
            # luôn có mặt), nhưng playlistItems trên nó lại 404 playlistNotFound. Nhánh
            # `uploads` rỗng ở trên vì thế không bao giờ chạy ngoài đời — kênh mới tinh
            # phải nhận diện Ở ĐÂY, trả [] như kênh rỗng, KHÔNG phải lỗi.
            if "404" in str(e) and not ids:
                return []
            raise
        ids += [it["contentDetails"]["videoId"] for it in pl.get("items", [])
                if (it.get("contentDetails") or {}).get("videoId")]
        token = pl.get("nextPageToken")
        if not token:
            break
    return ids[:limit]


def channel_title(channel_id: str, keys: list[str]) -> str:
    d = yt_get("channels", {"part": "snippet", "id": channel_id}, keys)
    items = d.get("items", [])
    return items[0]["snippet"]["title"] if items else "channel"


if __name__ == "__main__":                                 # self-test offline (không gọi mạng)

    # ── load_keys: gom mọi biến YOUTUBE_API_KEY*, bỏ trùng, xoay theo SỐ ──
    _real_load_env, load_env = load_env, lambda: None       # noqa: F811 — chặn đọc .env thật
    _saved = {k: v for k, v in os.environ.items() if k.startswith("YOUTUBE_API_KEY")}
    for k in _saved:
        del os.environ[k]
    K = lambda n: f"AIza{n}_" + "x" * 33                    # noqa: E731
    os.environ.update({"YOUTUBE_API_KEY_10": K(10), "YOUTUBE_API_KEY_2": K(2),
                       "YOUTUBE_API_KEY_1": K(1), "YOUTUBE_API_KEYS": f"{K(0)}, {K(1)}"})
    got = load_keys()
    assert [k[4:k.index("_")] for k in got] == ["0", "1", "2", "10"], got   # _2 trước _10, bỏ trùng K(1)
    for k in list(os.environ):
        if k.startswith("YOUTUBE_API_KEY"):
            del os.environ[k]
    os.environ.update(_saved)
    load_env = _real_load_env

    # ── channel_video_ids: lỗi phải NÓI ĐÚNG nguyên nhân, và không quay vô hạn ──
    _real_yt_get = yt_get
    calls = []

    def _fake(kind, params, keys, _plan=None):              # noqa: ANN001
        calls.append(kind)
        return _plan(kind, params) if _plan else {}

    yt_get = lambda k, p, ks: _fake(k, p, ks, PLAN)         # noqa: E731, F811

    PLAN = lambda k, p: {"items": []}                       # noqa: E731 — kênh không tồn tại
    try:
        channel_video_ids("UCxxx", ["k"])
        raise AssertionError("phải raise khi API không trả kênh nào")
    except RuntimeError as e:
        assert "id sai" in str(e), e

    # Kênh CÓ THẬT nhưng chưa có uploads playlist = kênh mới lập, chưa đăng video.
    # Phải trả [] để profile.extract tạo hồ sơ trống, KHÔNG được raise (raise là khoá cửa
    # vào của mọi kênh mới trong mạng lưới).
    PLAN = lambda k, p: {"items": [{"contentDetails": {}}]}  # noqa: E731
    assert channel_video_ids("UCxxx", ["k"]) == []

    # Kênh 0 video NGOÀI ĐỜI THẬT: uploads id vẫn được trả (UU… luôn có mặt) nhưng
    # playlistItems 404 playlistNotFound — sự cố thanhtho 06/08/2026, extract kênh mới
    # chết 5 lần liền. Phải trả [] như kênh rỗng; lỗi 404 GIỮA CHỪNG (đã có video) thì
    # vẫn phải nổ để không nuốt lỗi thật.
    def PLAN(k, p):                                         # noqa: F811
        if k == "channels":
            return {"items": [{"contentDetails": {"relatedPlaylists": {"uploads": "UU1"}}}]}
        raise RuntimeError('YouTube API 404: {"error": {"code": 404, "message": "The playlist '
                           'identified with the request\'s playlistId parameter cannot be found."}}')

    assert channel_video_ids("UCxxx", ["k"]) == [], "404 trang đầu phải thành kênh-rỗng"

    def PLAN(k, p):                                         # noqa: F811
        if k == "channels":
            return {"items": [{"contentDetails": {"relatedPlaylists": {"uploads": "UU1"}}}]}
        if p.get("pageToken"):
            raise RuntimeError("YouTube API 404: playlist biến mất giữa chừng")
        return {"items": [{"contentDetails": {"videoId": "v1"}}], "nextPageToken": "t2"}

    try:
        channel_video_ids("UCxxx", ["k"], limit=50)
        raise AssertionError("404 giữa chừng (đã gom được video) phải nổ, không nuốt")
    except RuntimeError as e:
        assert "404" in str(e), e

    # trang RỖNG mà vẫn kèm nextPageToken → trước đây quay vô hạn, đốt sạch quota
    def PLAN(k, p):                                         # noqa: F811
        if k == "channels":
            return {"items": [{"contentDetails": {"relatedPlaylists": {"uploads": "UU1"}}}]}
        return {"items": [], "nextPageToken": "luon-con-trang-sau"}

    calls.clear()
    assert channel_video_ids("UCxxx", ["k"], limit=50) == []
    assert calls.count("playlistItems") <= 6, f"phải chặn số trang, đang gọi {calls.count('playlistItems')}"

    # đường bình thường: gộp nhiều trang, cắt đúng limit, bỏ item thiếu videoId
    def PLAN(k, p):                                         # noqa: F811
        if k == "channels":
            return {"items": [{"contentDetails": {"relatedPlaylists": {"uploads": "UU1"}}}]}
        n = 0 if not p.get("pageToken") else 1
        return {"items": [{"contentDetails": {"videoId": f"v{n}{i}"}} for i in range(4)] + [{}],
                "nextPageToken": "t2" if n == 0 else None}

    assert channel_video_ids("UCxxx", ["k"], limit=6) == ["v00", "v01", "v02", "v03", "v10", "v11"]
    yt_get = _real_yt_get

    # ── slug / id ──
    assert extract_video_id("https://youtu.be/NTGYICp6c4s") == "NTGYICp6c4s"
    assert extract_video_id("khong-phai-url") is None
    assert slug("Cosmic Lens · CL-01") == "cosmic-lens-cl-01", slug("Cosmic Lens · CL-01")
    assert parse_urls("https://youtu.be/NTGYICp6c4s\nrác\nhttps://youtu.be/NTGYICp6c4s") == ["NTGYICp6c4s"]

    print("common.py self-test OK - gom key, loi noi dung nguyen nhan, chan lap vo han")

    # ── XOAY KEY: bắt đầu từ key còn sống, không dò lại từ đầu mỗi request ──
    import io as _io
    import urllib.error as _ue

    KEYS = ["k0", "k1", "k2", "k3"]
    DEAD: set = set()
    tried: list = []

    def _fake_open(url, timeout=30):                        # noqa: ANN001
        k = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["key"][0]
        tried.append(k)
        if k in DEAD:
            raise _ue.HTTPError(url, 403, "Forbidden", {},   # type: ignore[arg-type]
                                _io.BytesIO(b'{"error":{"message":"quotaExceeded"}}'))

        class _R:
            def read(self):
                return b'{"items":[]}'

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False
        return _R()

    _real_open = urllib.request.urlopen
    urllib.request.urlopen = _fake_open                     # noqa: F811
    _KEY_AT = 0
    try:
        yt_get("videos", {}, KEYS)
        assert tried == ["k0"], tried                       # key đầu còn sống → dùng luôn

        DEAD.add("k0")                                      # k0 cạn quota giữa ngày
        tried.clear()
        yt_get("videos", {}, KEYS)
        assert tried == ["k0", "k1"], tried                 # 1 lượt hỏng rồi nhảy sang k1
        assert key_cursor() == 1, key_cursor()

        tried.clear()                                       # ĐÂY là chỗ bản cũ phí: request kế tiếp
        yt_get("videos", {}, KEYS)                          # phải KHÔNG đụng lại k0 nữa
        yt_get("videos", {}, KEYS)
        assert tried == ["k1", "k1"], tried

        DEAD.update({"k1", "k2"})                           # cạn tiếp → vẫn quay hết vòng, không sót
        tried.clear()
        yt_get("videos", {}, KEYS)
        assert tried == ["k1", "k2", "k3"], tried
        assert key_cursor() == 3, key_cursor()

        tried.clear()                                       # con trỏ ở cuối → vòng lại từ đầu danh sách
        DEAD.add("k3")
        DEAD.discard("k0")
        yt_get("videos", {}, KEYS)
        assert tried == ["k3", "k0"], tried

        DEAD.update(KEYS)                                   # hết sạch → báo đúng, không im lặng
        try:
            yt_get("videos", {}, KEYS)
            raise AssertionError("phải raise khi hết quota mọi key")
        except RuntimeError as e:
            assert "Hết quota tất cả key" in str(e), e
    finally:
        urllib.request.urlopen = _real_open                 # noqa: F811
        _KEY_AT = 0

    print("common.py self-test OK - xoay key bat dau tu key con song, khong do lai tu dau")

    # ── THÙNG RÁC: xoá hoàn tác được ĐÚNG 1 lần, tự dọn sau 24h ──
    import tempfile
    import time as _time
    with tempfile.TemporaryDirectory() as _t:
        ROOT = Path(_t); PROFILES = ROOT / "profiles"        # _trash_dir() tự bám ROOT mới
        f = profiles_dir(create=True) / "kenh-a.json"
        write_json(f, {"channel": "Kênh A", "script": "DU-LIEU-QUY"})

        tok = trash(f, "profiles")
        assert tok == "profiles__kenh-a" and not f.exists(), tok
        assert [t["token"] for t in trash_list()] == [tok]
        assert trash_list()[0]["name"] == "Kênh A"          # hiện tên người đọc được, không phải slug

        r = restore(tok)                                    # hoàn tác lần 1: OK
        assert r and r["kind"] == "profiles" and f.exists(), r
        assert read_json(f)["script"] == "DU-LIEU-QUY", "khôi phục phải nguyên vẹn"
        assert restore(tok) is None, "hoàn tác lần 2 phải TỪ CHỐI"
        assert trash_list() == []

        # xoá lại rồi tạo file mới cùng tên → KHÔNG được đè bản mới
        tok = trash(f, "profiles")
        write_json(f, {"channel": "Kênh A mới"})
        assert restore(tok) == {"conflict": True, "orig": str(f)}
        assert read_json(f)["channel"] == "Kênh A mới", "bản mới bị ghi đè!"

        # Xoá 2 lần cùng 1 file → GIỮ CẢ HAI bản. Trước đây bản 2 đè bản 1, cuốn theo mọi field
        # user gõ tay (links/sub_url/format) vì extract lại không có gì để merge — mất thật.
        f2 = profiles_dir() / "kenh-b.json"
        write_json(f2, {"channel": "B", "v": 1}); t1 = trash(f2, "profiles")
        write_json(f2, {"channel": "B", "v": 2}); t2 = trash(f2, "profiles")
        assert t1 == "profiles__kenh-b" and t2 == "profiles__kenh-b~1", (t1, t2)
        assert len([t for t in trash_list() if t["stem"] == "kenh-b"]) == 2, trash_list()
        assert read_json(_trash_dir() / f"{t1}.json")["data"]["v"] == 1, "bản CŨ bị đè!"
        assert read_json(_trash_dir() / f"{t2}.json")["data"]["v"] == 2

        # quá 24h → tự dọn
        assert purge_trash(now=_time.time() + (TRASH_TTL_H + 1) * 3600) >= 1
        assert trash_list() == [] and restore(tok) is None

        assert trash(profiles_dir() / "khong-ton-tai.json") is None

        # ── XOÁ HẲN: đúng 1 mục trong thùng rác, và KHÔNG chạm được ra ngoài ──
        h = profiles_dir(create=True) / "kenh-purge.json"
        write_json(h, {"channel": "K", "code": "P1"})
        tk = trash(h, "profiles")
        assert purge_one(tk) == {"kind": "profiles", "stem": "kenh-purge"}
        assert trash_list() == [] and not h.exists(), "xoá hẳn: mất khỏi thùng, KHÔNG về chỗ cũ"
        assert purge_one(tk) is None, "xoá lần 2 phải vô hại"

        keep = profiles_dir() / "dung-xoa.json"
        write_json(keep, {"channel": "ĐỪNG XOÁ"})
        for bad in ("../profiles/dung-xoa", "..\\profiles\\dung-xoa", "/etc/passwd",
                    "", ".", "..", "../../.env", "dung-xoa"):
            assert purge_one(bad) is None, bad
        assert keep.exists(), "token độc thoát ra ngoài .trash/ — LỖ HỔNG"

        # Tên THIẾT BỊ Windows: `.trash/CON.json` phân giải thành console ở mọi thư mục →
        # read_json treo vĩnh viễn 1 thread server; NUL ném WinError 87. Whitelist phải chặn trước.
        for dev in ("CON", "con", "NUL", "CONIN$", "CONOUT$", "PRN", "AUX", "COM1", "LPT1"):
            assert _safe_token(dev) == "", f"tên thiết bị Windows lọt: {dev}"
        # token KHÔNG PHẢI CHUỖI: trước đây Path(list) ném TypeError → request chết không response
        for junk in ([1, 2], 123, {"a": 1}, None, b"x"):
            assert purge_one(junk) is None and restore(junk) is None, junk
        assert _safe_token("x" * 300) == "", "token 300 ký tự phải bị loại"
        assert _safe_token("profiles__kenh-b~1") == "profiles__kenh-b~1", "token ~n phải hợp lệ"

        # Chốt BẢN: cùng token nhưng deleted_at lệch → không xoá mù bản mới
        f3 = profiles_dir() / "kenh-c.json"
        write_json(f3, {"v": 1}); t3 = trash(f3, "profiles")
        at_real = read_json(_trash_dir() / f"{t3}.json")["deleted_at"]
        assert (purge_one(t3, at=at_real - 999) or {}).get("changed") is True, "xoá mù bản khác!"
        assert (_trash_dir() / f"{t3}.json").exists(), "đã trả changed thì KHÔNG được xoá"
        assert purge_one(t3, at=at_real) == {"kind": "profiles", "stem": "kenh-c"}

        # restore dựng đích từ ROOT+kind+stem, KHÔNG tin `orig` tuyệt đối
        f4 = profiles_dir() / "kenh-d.json"
        write_json(f4, {"v": 9}); t4 = trash(f4, "profiles")
        tf = _trash_dir() / f"{t4}.json"
        bad = read_json(tf); bad["orig"] = str(Path(_t) / "cho-khac" / "kenh-d.json")
        write_json(tf, bad)                                # giả lập dự án đã bị đổi tên thư mục
        r4 = restore(t4)
        assert f4.exists() and read_json(f4)["v"] == 9, (r4, f4.exists())
        assert not (Path(_t) / "cho-khac").exists(), "ghi ra NGOÀI dự án theo orig cũ"

        # `.trash/` mang từ máy khác sang: kind lạ + orig kiểu POSIX → phải TỪ CHỐI, không ghi bừa
        f5 = profiles_dir() / "kenh-e.json"
        write_json(f5, {"v": 5}); t5 = trash(f5, "profiles")
        tf5 = _trash_dir() / f"{t5}.json"
        b5 = read_json(tf5); b5["kind"] = "khong-biet"
        b5["orig"] = "/Users/ai-do/Documents/SEO Optimize/profiles/kenh-e.json"
        write_json(tf5, b5)
        r5 = restore(t5)
        assert (r5 or {}).get("outside") is True, r5
        assert tf5.exists(), "đã từ chối thì KHÔNG được tiêu bản trong thùng rác"
    print("common.py self-test OK - thung rac: hoan tac 1 lan, xoa han an toan, tu don sau 24h")

    # .env có BOM (PowerShell Set-Content -Encoding utf8 / Notepad trên Windows) → biến ĐẦU TIÊN
    # phải vẫn đọc được. Trước đây BOM dính vào tên biến, biến đó coi như không tồn tại mà không
    # báo lỗi gì, tool âm thầm rơi về mặc định.
    with tempfile.TemporaryDirectory() as _tb:
        ROOT = Path(_tb)
        body = chr(10).join(["FIRST_VAR=alpha", "SECOND_VAR=beta", ""])
        (ROOT / ".env").write_bytes(b"\xef\xbb\xbf" + body.encode("utf-8"))   # BOM y như Windows ghi
        for k in ("FIRST_VAR", "SECOND_VAR"):
            os.environ.pop(k, None)
        load_env()
        assert os.environ.get("FIRST_VAR") == "alpha", "BOM nuốt mất biến đầu tiên"
        assert os.environ.get("SECOND_VAR") == "beta"
        for k in ("FIRST_VAR", "SECOND_VAR"):
            os.environ.pop(k, None)
    print("common.py self-test OK - .env co BOM van doc duoc bien dau tien")

    # thùng rác phải bám ROOT lúc gọi — self-test KHÔNG được đụng .trash/ của dự án thật
    _real = _trash_dir()
    with tempfile.TemporaryDirectory() as _t2:
        ROOT = Path(_t2); PROFILES = ROOT / "profiles"
        assert _trash_dir() != _real, (_trash_dir(), _real)
        g = profiles_dir(create=True) / "x.json"
        write_json(g, {"a": 1})
        trash(g, "profiles")
        assert (_trash_dir() / "profiles__x.json").exists()
        assert not (_real / "profiles__x.json").exists(), "self-test ghi vào .trash/ dự án thật!"
    print("common.py self-test OK - thung rac bam ROOT luc goi, khong ro ri sang du an that")

    # ── sub_confirmation: dán link kênh là ra, khỏi nhớ đuôi query ──
    UC = "UC" + "x" * 22
    assert sub_url_from(f"https://www.youtube.com/channel/{UC}") == \
        f"https://www.youtube.com/channel/{UC}?sub_confirmation=1"
    assert sub_url_from(UC) == f"https://www.youtube.com/channel/{UC}?sub_confirmation=1"
    assert sub_url_from("https://www.youtube.com/@CosmicLens") == \
        "https://www.youtube.com/@CosmicLens?sub_confirmation=1"
    assert sub_url_from("@CosmicLens") == "https://www.youtube.com/@CosmicLens?sub_confirmation=1"
    assert sub_url_from("youtube.com/user/OldName/") == \
        "https://www.youtube.com/user/OldName?sub_confirmation=1"
    # link kênh có sẵn query/fragment/dấu / thừa → vẫn ra đúng, không nhân đôi query
    assert sub_url_from(f"https://www.youtube.com/channel/{UC}/videos?view=0#frag") == \
        f"https://www.youtube.com/channel/{UC}?sub_confirmation=1"
    # đã đúng dạng thì GIỮ NGUYÊN, không bọc thêm lần nữa
    done = f"https://www.youtube.com/channel/{UC}?sub_confirmation=1"
    assert sub_url_from(done) == done
    assert sub_url_from("https://youtube.com/@x?sub_confirmation=1") == "https://youtube.com/@x?sub_confirmation=1"
    # không nhận ra được thì trả nguyên input, KHÔNG bịa
    assert sub_url_from("linh tinh") == "linh tinh"
    assert sub_url_from("") == "" and sub_url_from(None) == ""
    print("common.py self-test OK - sub_url_from: dan link kenh la ra link dang ky")
