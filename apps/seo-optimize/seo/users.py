"""Tài khoản RIÊNG từng người — thay cho một mật khẩu chung (user chốt 2026-08-02).

**Mật khẩu chung được cái gì thì mất cái gì:** nó trả lời được *"máy này có được vào không"*
nhưng không bao giờ trả lời được *"AI vừa xoá kênh đó"*. Và muốn chặn một người thì phải đổi
mật khẩu của TẤT CẢ mọi người. Tài khoản riêng gỡ đúng hai chỗ đó.

**KHÔNG BAO GIỜ lưu mật khẩu trần.** Lưu `pbkdf2_sha256$<vòng>$<muối>$<hash>`:
  · **muối riêng từng người** — không có muối thì hai người đặt trùng mật khẩu ra cùng một hash,
    nhìn bảng là biết ngay, và một bảng tra sẵn phá được cả hai cùng lúc.
  · **200.000 vòng** — làm chậm việc dò offline. Chọn `pbkdf2_hmac` chứ không `scrypt` vì nó có
    ở mọi bản Python/OpenSSL; dự án này chạy trên máy Windows của user, không kiểm soát được
    OpenSSL bên dưới, mà một hàm băm "tốt hơn" nhưng thỉnh thoảng không tồn tại thì tệ hơn.
  · So bằng `hmac.compare_digest`, không bằng `==`.

**Thêm người CHỈ qua dòng lệnh, cố ý không có endpoint.** Một endpoint tạo tài khoản mà có lỗi
là kẻ ngoài tự cấp quyền cho mình. Ai sờ được vào máy/thư mục dự án thì mới thêm được người —
đúng mức tin cậy của một tool nội bộ.

`users.json` nằm trong `.gitignore`: hash lộ ra là dò offline được, không hàng rào tốc độ nào cản.

Không LLM, không quota, thuần stdlib.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
import threading
from datetime import datetime, timezone

from . import common, roles

ROUNDS = 200_000
MIN_LEN = 8              # ngắn hơn thì dò được trong tầm với, mà đây là tool có khoá API thật
MAX_USERS = 50
MAX_RESETS = 30          # trần yêu cầu cấp lại đang chờ — chặn người lạ làm ngập danh sách

# ── LUẬT ĐẶT MẬT KHẨU (user chốt 2026-08-02: *"Owner kiểm soát cả phần password mọi người
# đặt"*) ───────────────────────────────────────────────────────────────────────────────────
# **Owner KHÔNG XEM ĐƯỢC mật khẩu của ai** — hash pbkdf2 + muối riêng là một chiều, đó là
# chủ đích chứ không phải hạn chế. Nên "kiểm soát" ở đây = **áp luật lúc ĐẶT** + **thấy
# METADATA** (đặt lúc nào, ai đặt, còn là mật khẩu tạm không), chứ tuyệt đối không phải
# "xem được họ đặt gì". Đừng có ngày nào đó thêm một chỗ lưu bản trần cho tiện.
_WEAK = {"12345678", "123456789", "1234567890", "password", "matkhau", "qwertyui",
         "11111111", "00000000", "abcd1234", "admin123", "iloveyou", "letmein1"}


def weak_reason(pw: str, name: str = "") -> str:
    """Vì sao mật khẩu này quá yếu; rỗng = chấp nhận được.

    Cố ý chỉ chặn những kiểu **chắc chắn** tệ, không đòi "phải có hoa/số/ký tự đặc biệt":
    luật rườm rà đẩy người ta sang `Matkhau@1` và dán giấy nhớ lên màn hình, tệ hơn hẳn một
    mật khẩu dài mà họ nhớ được. Dài mới là thứ đáng đòi.
    """
    p = (pw or "").strip()
    if len(p) < MIN_LEN:
        return f"phải từ {MIN_LEN} ký tự trở lên (đang {len(p)})"
    low = p.lower()
    if low in _WEAK:
        return "nằm trong danh sách mật khẩu bị đoán ra đầu tiên"
    if name and low == (name or "").strip().lower():
        return "trùng đúng tên đăng nhập"
    # Chỉ chặn khi mật khẩu GẦN NHƯ CHỈ LÀ cái tên (`giang123`), KHÔNG chặn câu dài có chứa
    # tên (`giang-hoa-hong-2026`) — cái sau là mật khẩu tốt, chặn nó là đẩy người ta sang thứ
    # ngắn và khó nhớ hơn.
    nm = (name or "").strip().lower()
    if nm and len(nm) >= 4 and nm in low and len(p) < len(nm) + 6:
        return "gần như chỉ là tên đăng nhập"
    if len(set(p)) <= 2:
        return "chỉ gồm 1–2 ký tự lặp lại"
    d = "0123456789"
    if p in d or p in d[::-1] or low in "abcdefghijklmnopqrstuvwxyz":
        return "là một dãy liên tiếp trên bàn phím"
    return ""


def gen_password(n: int = 14) -> str:
    """Mật khẩu TẠM do máy sinh, để Owner cấp lại cho người quên.

    Bỏ các ký tự nhìn giống nhau (`0/O`, `1/l/I`) vì mật khẩu này được **đọc/chép tay** cho
    nhau — một chữ đọc nhầm là họ tưởng Owner cấp sai rồi xin lại lần nữa. Chia nhóm 4 bằng
    dấu `-` cho dễ đọc, độ dài vẫn thừa sức.
    """
    al = "abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    raw = "".join(secrets.choice(al) for _ in range(n))
    return "-".join(raw[i:i + 4] for i in range(0, len(raw), 4))


def _path():
    return common.ROOT / "users.json"


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def hash_pw(pw: str, salt: str = "") -> str:
    s = salt or secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", (pw or "").encode(), bytes.fromhex(s), ROUNDS).hex()
    return f"pbkdf2_sha256${ROUNDS}${s}${h}"


def verify(pw: str, stored: str) -> bool:
    """So mật khẩu với bản đã băm. Bản ghi hỏng/lạ → False, KHÔNG raise.

    Raise ở đây là một tài khoản hỏng làm sập cả đường đăng nhập của mọi người.
    """
    try:
        algo, rounds, salt, want = (stored or "").split("$", 3)
        if algo != "pbkdf2_sha256":
            return False
        got = hashlib.pbkdf2_hmac("sha256", (pw or "").encode(),
                                  bytes.fromhex(salt), int(rounds)).hex()
        return hmac.compare_digest(got, want)
    except Exception:                                    # noqa: BLE001 — bản ghi hỏng
        return False


def _load() -> dict:
    p = _path()
    if not p.exists():
        return {"users": []}
    try:
        d = common.read_json(p)
    except Exception:                                    # noqa: BLE001
        raise RuntimeError(f"users.json hỏng, không đọc được: {p}") from None
    if not isinstance(d, dict) or not isinstance(d.get("users"), list):
        raise RuntimeError("users.json sai định dạng (thiếu mảng `users`)")
    # NÂNG CẤP file cũ (tạo trước khi có vai): người ĐẦU TIÊN thành owner, còn lại vai thấp
    # nhất. Không làm thì mọi tài khoản cũ rơi về `seo` và KHÔNG AI quản được tài khoản nữa —
    # mà cửa duy nhất để sửa vai lại chính là quyền `users`.
    if d["users"] and any("role" not in u for u in d["users"]):
        for i, u in enumerate(d["users"]):
            u.setdefault("role", "owner" if i == 0 else roles.DEFAULT)
            u.setdefault("markets", [])
            u.setdefault("channels", [])
            u.setdefault("niches", [])
        common.write_json(_path(), d)
    d.setdefault("resets", [])
    # File tạo trước 02/08/2026 chưa có metadata mật khẩu. **KHÔNG bịa `pw_at`**: không biết
    # thì để rỗng và board ghi "không rõ", đừng lấy ngày tạo tài khoản làm ngày đặt mật khẩu.
    for u in d["users"]:
        u.setdefault("pw_at", "")
        u.setdefault("pw_by", "")
        u.setdefault("must_change", False)
    return d


def _save(d: dict) -> None:
    common.write_json(_path(), d)


def enabled() -> bool:
    """Có bật chế độ tài khoản riêng không = file tồn tại VÀ có ít nhất 1 người còn hoạt động.

    File rỗng/không có người nào bật thì coi như CHƯA bật — nếu không thì lỡ xoá hết người
    là khoá cứng cả tool, không ai vào được nữa mà cũng không có đường sửa từ giao diện.
    """
    try:
        return any(not u.get("disabled") for u in _load()["users"])
    except Exception:                                    # noqa: BLE001
        return False


def all_users() -> list[dict]:
    """Danh sách người dùng — KHÔNG kèm hash. Hash chỉ ở lại trong module này."""
    return [{k: v for k, v in u.items() if k != "hash"} for u in _load()["users"]]


_SSO_LOCK = threading.Lock()


def sync_sso(name: str, role: str) -> None:
    """Đồng bộ danh tính SSO từ cổng OUTLIERY vào sổ (user chốt 2026-08-05: *"tài khoản
    trong app chưa đồng bộ với tài khoản cổng"*).

    Đúng khuôn đã chốt với RadarY 04/08: **VAI đồng bộ MỖI REQUEST từ header** (cổng là
    nguồn sự thật duy nhất về vai — sổ ghi vai cũ sẽ chết lặng lẽ khi hệ tài khoản thay
    máu), sổ chỉ còn giữ **thiết lập + GIỚI HẠN** (markets/channels/niches — Owner tick
    trong tab Quản trị, `_sso` đọc lại từ đây nên tick là ĂN THẬT với người SSO).

    Bản ghi SSO KHÔNG có `hash` → không đăng nhập thẳng cổng 8760 được (`check()` băm so
    với chuỗi rỗng luôn False — fail-closed); cờ `sso=True` để pane khoá các nút vô nghĩa
    (đổi vai / đổi mật khẩu). CHỈ GHI khi có gì đổi — hàm này chạy trên mọi request, kể cả
    GET poll 1s/lần, ghi đĩa vô điều kiện là tự tạo bão I/O. Khoá riêng vì nó là đường ghi
    duy nhất chạy NGOÀI DATA_LOCK của server (GET cũng gọi).
    """
    n = (name or "").strip()
    r = roles.norm(role)
    if not n:
        return
    with _SSO_LOCK:
        d = _load()
        for u in d["users"]:
            if u.get("name", "").lower() == n.lower():
                if u.get("role") == r and u.get("sso"):
                    return                               # không đổi gì → không ghi
                u["role"], u["sso"] = r, True
                _save(d)
                return
        if len(d["users"]) >= MAX_USERS:
            return                                       # trần sổ — không để header lạ bơm đầy
        d["users"].append({"name": n, "role": r, "sso": True,
                           "note": "đồng bộ từ cổng OUTLIERY",
                           "markets": [], "channels": [], "niches": [],
                           "pw_at": "", "pw_by": "", "must_change": False,
                           "created": now_iso()})
        _save(d)


def find(name: str) -> dict | None:
    n = (name or "").strip().lower()
    for u in _load()["users"]:
        if u.get("name", "").lower() == n:
            return u
    return None


def check(name: str, pw: str) -> dict | None:
    """Trả bản ghi người dùng nếu đúng mật khẩu và chưa bị khoá; ngược lại None.

    **Vẫn băm một lần kể cả khi tên không tồn tại** — trả lời ngay lập tức cho tên không có
    thì thời gian phản hồi tự khai ra tên nào CÓ trong hệ thống.
    """
    u = find(name)
    if u is None:
        hash_pw(pw or "x")                               # tốn đúng bằng lúc có thật
        return None
    if u.get("disabled"):
        return None
    return u if verify(pw, u.get("hash", "")) else None


def _check_pw(pw: str, name: str = "") -> None:
    r = weak_reason(pw, name)
    if r:
        raise RuntimeError(f"Mật khẩu quá yếu: {r}")


def add(name: str, pw: str, note: str = "", role: str = "", markets: list | None = None,
        channels: list | None = None, niches: list | None = None) -> dict:
    n = (name or "").strip()
    if not n:
        raise RuntimeError("Thiếu tên người dùng")
    if find(n):
        raise RuntimeError(f"Đã có người tên '{n}' — dùng `passwd` để đổi mật khẩu")
    _check_pw(pw, n)
    d = _load()
    if len(d["users"]) >= MAX_USERS:
        raise RuntimeError(f"Quá {MAX_USERS} người — nhiều hơn thì tool này không phải chỗ đúng")
    # NGƯỜI ĐẦU TIÊN BẮT BUỘC là `owner` — ÉP, không phải mặc định (sửa 2026-08-02 sau khi
    # kiểm bằng trình duyệt). Form trên board gửi sẵn `role="seo"` nên bản cũ tạo ra một hệ
    # thống KHÔNG AI quản được: người duy nhất là `seo`, không có quyền `users`, mà cửa duy
    # nhất để sửa vai lại chính là quyền đó ⇒ tự khoá mình ngay ở bước đầu tiên.
    # Từ người thứ hai trở đi: khai gì dùng nấy, quên khai thì về vai THẤP NHẤT.
    r = ("owner" if not d["users"]
         else (roles.norm(role) if role else roles.DEFAULT))
    u = {"name": n, "hash": hash_pw(pw), "note": (note or "").strip(),
         "role": r, "markets": [str(m).strip() for m in (markets or []) if str(m).strip()],
         "channels": [str(c).strip() for c in (channels or []) if str(c).strip()],
         "niches": [str(x).strip() for x in (niches or []) if str(x).strip()],
         "created": now_iso(), "disabled": False,
         # METADATA mật khẩu — thứ DUY NHẤT Owner soi được. Không bao giờ có bản trần ở đây.
         "pw_at": now_iso(), "pw_by": n, "must_change": False}
    d["users"].append(u)
    _save(d)
    return {k: v for k, v in u.items() if k != "hash"}


def set_role(name: str, role: str) -> dict:
    r = roles.norm(role)
    d = _load()
    for u in d["users"]:
        if u.get("name", "").lower() == (name or "").strip().lower():
            # KHÔNG được hạ vai owner CUỐI CÙNG: hạ xong là không ai còn quyền `users`, tức
            # khoá cứng việc quản tài khoản mà giao diện không có đường sửa.
            if u.get("role") == "owner" and r != "owner" and _n_owners(d) <= 1:
                raise RuntimeError("Đây là Owner CUỐI CÙNG — hạ vai là không ai quản được "
                                   "tài khoản nữa. Cấp Owner cho người khác trước.")
            u["role"] = r
            u["updated"] = now_iso()
            _save(d)
            return {k: v for k, v in u.items() if k != "hash"}
    raise RuntimeError(f"Không có người tên '{name}'")


def set_markets(name: str, markets: list) -> dict:
    """Gán thị trường được vào. Rỗng = KHÔNG giới hạn (xem `roles.scope_markets`)."""
    d = _load()
    for u in d["users"]:
        if u.get("name", "").lower() == (name or "").strip().lower():
            u["markets"] = [str(m).strip() for m in (markets or []) if str(m).strip()]
            u["updated"] = now_iso()
            _save(d)
            return {k: v for k, v in u.items() if k != "hash"}
    raise RuntimeError(f"Không có người tên '{name}'")


def set_niches(name: str, ns: list) -> dict:
    """Giao NICHE cho một người (Leader). Rỗng = mọi niche — cùng luật với thị trường."""
    d = _load()
    for u in d["users"]:
        if u.get("name", "").lower() == (name or "").strip().lower():
            u["niches"] = [str(x).strip() for x in (ns or []) if str(x).strip()]
            u["updated"] = now_iso()
            _save(d)
            return {k: v for k, v in u.items() if k != "hash"}
    raise RuntimeError(f"Không có người tên '{name}'")


def set_channels(name: str, chans: list) -> dict:
    """Giao KÊNH cho một người. Vai không có `view_all` (tức Seo) thì CHỈ thấy những kênh này.

    Rỗng = **chưa được giao kênh nào** ⇒ thấy 0 kênh. Cố ý KHÁC `set_markets` (rỗng = mọi thị
    trường): "kênh của ai người đó thấy" thì chưa giao đúng nghĩa là chưa có gì. Xem
    `roles.scope_channels`.
    """
    d = _load()
    for u in d["users"]:
        if u.get("name", "").lower() == (name or "").strip().lower():
            u["channels"] = [str(c).strip() for c in (chans or []) if str(c).strip()]
            u["updated"] = now_iso()
            _save(d)
            return {k: v for k, v in u.items() if k != "hash"}
    raise RuntimeError(f"Không có người tên '{name}'")


def _n_owners(d: dict) -> int:
    return sum(1 for u in d["users"] if u.get("role") == "owner" and not u.get("disabled"))


def set_password(name: str, pw: str, by: str = "", must_change: bool = False) -> dict:
    """Đặt mật khẩu. `by` = ai đặt (chính họ, hay Owner cấp lại) — vào metadata cho Owner soi.

    `must_change=True` cho mật khẩu TẠM: người đó đăng nhập được nhưng **bị chặn ở mọi việc
    khác** cho tới khi tự đổi. Cấp mật khẩu tạm mà không ép đổi thì nó nằm lại vĩnh viễn,
    trong khi ít nhất hai người đã biết nó (Owner và người kia) — cộng thêm bất cứ ai nhìn
    qua vai lúc đọc cho nhau.
    """
    nm = (name or "").strip()
    _check_pw(pw, nm)
    d = _load()
    for u in d["users"]:
        if u.get("name", "").lower() == nm.lower():
            u["hash"] = hash_pw(pw)
            u["updated"] = u["pw_at"] = now_iso()
            u["pw_by"] = (by or u.get("name") or "").strip()
            u["must_change"] = bool(must_change)
            d["resets"] = [r for r in d.get("resets") or []
                           if str(r.get("name", "")).lower() != nm.lower()]
            _save(d)
            return {k: v for k, v in u.items() if k != "hash"}
    raise RuntimeError(f"Không có người tên '{name}'")


# ── QUÊN MẬT KHẨU ─────────────────────────────────────────────────────────────────────────
# Không gửi mail/SMS được (tool chạy local, không có kênh nào ra ngoài), nên luồng đúng là:
# người đó bấm "Quên mật khẩu" → tạo YÊU CẦU → **Owner duyệt và đọc mật khẩu tạm cho họ**.
# Việc xác minh danh tính do Owner làm ngoài đời (họ ngồi cùng nhóm) — tool không giả vờ
# làm được việc đó.

def request_reset(name: str, ip: str = "") -> None:
    """Ghi nhận một yêu cầu cấp lại. **KHÔNG BAO GIỜ báo cho người gọi biết tên có tồn tại hay
    không** — caller luôn trả cùng một câu. Tên không có thì lặng lẽ bỏ qua: ghi vào danh sách
    là biến ô "quên mật khẩu" thành máy dò tên tài khoản, và làm ngập danh sách của Owner.
    """
    nm = (name or "").strip()
    if not nm:
        return
    d = _load()
    u = next((x for x in d["users"] if x.get("name", "").lower() == nm.lower()), None)
    if u is None or u.get("disabled"):
        return                                           # khoá rồi thì xin cấp lại cũng vô nghĩa
    rs = d.get("resets") or []
    for r in rs:                                         # đã xin rồi thì chỉ dời giờ, đừng đẻ dòng mới
        if str(r.get("name", "")).lower() == nm.lower():
            r["at"] = now_iso(); r["ip"] = ip or r.get("ip", "")
            d["resets"] = rs; _save(d); return
    if len(rs) >= MAX_RESETS:
        return
    rs.append({"name": u["name"], "at": now_iso(), "ip": ip})
    d["resets"] = rs
    _save(d)


def resets() -> list[dict]:
    """Danh sách yêu cầu đang chờ, mới nhất trước. Bỏ yêu cầu của người đã bị xoá/khoá."""
    d = _load()
    live = {u.get("name", "").lower() for u in d["users"] if not u.get("disabled")}
    return sorted([r for r in (d.get("resets") or [])
                   if str(r.get("name", "")).lower() in live],
                  key=lambda r: r.get("at") or "", reverse=True)


def drop_reset(name: str) -> bool:
    """Bỏ một yêu cầu mà KHÔNG cấp mật khẩu mới (Owner thấy không hợp lệ)."""
    nm = (name or "").strip().lower()
    d = _load()
    rs = d.get("resets") or []
    keep = [r for r in rs if str(r.get("name", "")).lower() != nm]
    if len(keep) == len(rs):
        return False
    d["resets"] = keep
    _save(d)
    return True


def set_disabled(name: str, off: bool) -> dict:
    """Khoá/mở một người. **KHOÁ chứ không XOÁ** là mặc định đúng: xoá thì nhật ký còn tên
    mà tra không ra người, và tên đó lại được đăng ký lại bởi người khác."""
    d = _load()
    for u in d["users"]:
        if u.get("name", "").lower() == (name or "").strip().lower():
            if off and sum(1 for x in d["users"] if not x.get("disabled")) <= 1:
                raise RuntimeError("Đây là người CUỐI CÙNG còn hoạt động — khoá nốt là "
                                   "không ai vào được nữa. Thêm người khác trước.")
            if off and u.get("role") == "owner" and _n_owners(d) <= 1:
                raise RuntimeError("Đây là Owner CUỐI CÙNG — khoá nốt là không ai quản được "
                                   "tài khoản nữa. Cấp Owner cho người khác trước.")
            u["disabled"] = bool(off)
            u["updated"] = now_iso()
            _save(d)
            return {k: v for k, v in u.items() if k != "hash"}
    raise RuntimeError(f"Không có người tên '{name}'")


def remove(name: str) -> bool:
    d = _load()
    keep = [u for u in d["users"] if u.get("name", "").lower() != (name or "").strip().lower()]
    if len(keep) == len(d["users"]):
        return False
    if not any(not u.get("disabled") for u in keep) and d["users"]:
        raise RuntimeError("Xoá nốt là không còn ai đăng nhập được. Thêm người khác trước.")
    if not _n_owners({"users": keep}):
        raise RuntimeError("Xoá nốt là không còn Owner nào — không ai quản được tài khoản. "
                           "Cấp Owner cho người khác trước.")
    d["users"] = keep
    _save(d)
    return True


def _matrix_text() -> str:
    """Bảng "vai nào được làm gì" dạng chữ. Dựng TỪ `roles._GRANT` — chép tay là có ngày bảng
    in ra một đằng, server chặn một nẻo."""
    w = max(len(v) for v in roles.PERM_VN.values()) + 2
    out = ["VAI NÀO ĐƯỢC LÀM GÌ", " " * w + "".join(f"{r:>9}" for r in roles.ROLES)]
    for row in roles.matrix():
        out.append(roles.PERM_VN[row["perm"]].ljust(w)
                   + "".join(f"{('✓' if row['roles'][r] else '—'):>9}" for r in roles.ROLES))
    out += ["",
            "GHI LÊN KÊNH = CHỦ KÊNH: Leader/Seo chỉ sửa/sinh được kênh do CHÍNH MÌNH tạo;",
            "Manager/Owner sửa được mọi kênh. ĐỔI CHỦ kênh: từ Leader trở lên (phân công là",
            "việc hằng ngày) — nhưng XOÁ kênh thì vẫn phải Manager/Owner.",
            "Ai cũng XEM được mọi kênh trong thị trường của mình (tra title đã dùng chưa).",
            "Lệnh `channels` giờ CHỈ để theo dõi (số 'cầm' ở Tổng quan) — KHÔNG cấp quyền sửa.",
            "Leader/Seo còn bị giới hạn theo THỊ TRƯỜNG (lệnh `markets`)."]
    return chr(10).join(out)


def _cli(argv: list[str]) -> int:
    import getpass                                        # noqa: PLC0415
    cmd = (argv[0] if argv else "list").lower()
    # Mật khẩu KHÔNG BAO GIỜ nhận qua tham số dòng lệnh: nó nằm lại trong lịch sử shell và
    # hiện ra ở danh sách tiến trình cho mọi user khác trên máy. Luôn hỏi qua getpass.
    def ask() -> str:
        a = getpass.getpass("Mật khẩu mới: ")
        if a != getpass.getpass("Gõ lại: "):
            raise RuntimeError("Hai lần gõ không khớp")
        return a
    try:
        if cmd == "list":
            us = all_users()
            if not us:
                print("Chưa có tài khoản nào. Thêm:  python -m seo.users add <tên> [vai]")
                print("(chưa có ai thì tool dùng BOARD_PASSWORD như cũ)")
                print("Vai:", " · ".join(roles.ROLES), "— người ĐẦU TIÊN mặc định là owner")
                return 0
            print(f"{len(us)} tài khoản:")
            for u in us:
                ms = u.get("markets") or []
                scope = (", ".join(ms) if ms else
                         ("mọi thị trường" if not roles.is_scoped(u.get("role", "")) else
                          "mọi thị trường (chưa gán)"))
                ch = u.get("channels") or []
                kn = ("mọi kênh" if roles.can(u.get("role", ""), "view_all")
                      else (", ".join(ch) if ch
                            else "⚠ CHƯA giao kênh nào → người này thấy 0 kênh"))
                print(f"  {'✗ KHOÁ' if u.get('disabled') else '✓     '} {u['name']:<14}"
                      f" {roles.norm(u.get('role','')):<8} TT[{scope}]  KÊNH[{kn}]"
                      f"  {u.get('note','')}")
            print()
            print(_matrix_text())
        elif cmd == "add":
            # vai là tham số THỨ HAI, không phải cờ — gõ nhầm thì `roles.norm` rơi về vai
            # thấp nhất chứ không bao giờ cấp nhầm quyền cao.
            r = argv[2] if len(argv) > 2 else ""
            u = add(argv[1], ask(), " ".join(argv[3:]), role=r)
            print(f"{u['name']} — đã thêm, vai {u['role']}")
            if r and roles.norm(r) != (r or "").strip().lower():
                print(f"  ⚠ '{r}' không phải vai hợp lệ → đã đặt {u['role']} "
                      f"(vai hợp lệ: {' · '.join(roles.ROLES)})")
        elif cmd == "role":
            u = set_role(argv[1], argv[2])
            print(f"{u['name']} — vai {u['role']} · quyền: {' · '.join(sorted(roles.perms(u['role'])))}")
        elif cmd == "channels":
            u = set_channels(argv[1], argv[2:])
            ch = u.get("channels") or []
            if roles.can(u["role"], "view_all"):
                print(f"{u['name']} — vai {u['role']} vốn THẤY MỌI KÊNH; danh sách này được "
                      f"ghi lại nhưng không có tác dụng")
            else:
                print(f"{u['name']} — {len(ch)} kênh: "
                      + (", ".join(ch) if ch else "(chưa giao) → người này sẽ thấy 0 kênh"))
        elif cmd == "perms":
            print(_matrix_text())
        elif cmd == "markets":
            u = set_markets(argv[1], argv[2:])
            ms = u.get("markets") or []
            print(f"{u['name']} — {', '.join(ms) if ms else 'MỌI thị trường (bỏ giới hạn)'}")
            if ms and not roles.is_scoped(u["role"]):
                print(f"  ⚠ vai {u['role']} KHÔNG bị giới hạn theo thị trường — "
                      f"danh sách này được ghi lại nhưng không có tác dụng")
        elif cmd == "passwd":
            print(set_password(argv[1], ask())["name"], "— đã đổi mật khẩu")
        elif cmd in ("disable", "enable"):
            print(set_disabled(argv[1], cmd == "disable")["name"],
                  "— đã", "khoá" if cmd == "disable" else "mở")
        elif cmd in ("rm", "remove"):
            print("đã xoá" if remove(argv[1]) else "không có người tên đó")
        else:
            print("Dùng:  python -m seo.users <lệnh>")
            print("  list                          xem tài khoản + bảng quyền")
            print("  add <tên> [vai] [ghi chú]     thêm người (vai:", " ".join(roles.ROLES) + ")")
            print("  role <tên> <vai>              đổi vai")
            print("  markets <tên> [TT1 TT2 …]     giới hạn thị trường (bỏ trống = mọi thị trường)")
            print("  channels <tên> [slug1 slug2 …]  ghi nhận kênh ĐANG PHỤ TRÁCH — chỉ để")
            print("                                theo dõi, KHÔNG cấp quyền sửa (quyền sửa")
            print("                                đi theo CHỦ KÊNH)")
            print("  perms                         bảng vai nào được làm gì")
            print("  passwd <tên> · disable <tên> · enable <tên> · rm <tên>")
            return 2
    except IndexError:
        print("Thiếu tên người dùng"); return 2
    except RuntimeError as e:
        print("Lỗi:", e); return 1
    return 0


if __name__ == "__main__":
    import sys
    if sys.argv[1:2] == ["--selftest"]:
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as td:
            old = common.ROOT
            common.ROOT = Path(td)                        # cô lập: KHÔNG đụng users.json thật
            try:
                assert not enabled(), "chưa có file thì phải coi như CHƯA bật"
                assert all_users() == []

                # ── Băm ──
                h = hash_pw("mat-khau-dai")
                assert h.startswith("pbkdf2_sha256$") and "mat-khau-dai" not in h, h
                assert verify("mat-khau-dai", h) and not verify("mat-khau-dai ", h)
                assert not verify("", h) and not verify("sai", h)
                # MUỐI RIÊNG: cùng mật khẩu → hash KHÁC nhau
                assert hash_pw("giong-nhau-het") != hash_pw("giong-nhau-het")
                # bản ghi hỏng thì trả False chứ không nổ (một tài khoản hỏng không được
                # làm sập đường đăng nhập của cả nhóm)
                for bad in ("", "rac", "md5$1$aa$bb", "pbkdf2_sha256$x$y$z"):
                    assert verify("gi-cung-duoc", bad) is False, bad

                # ── Thêm / kiểm ──
                add("thanh", "matkhau123", "chủ kênh")
                assert enabled()
                assert check("thanh", "matkhau123")
                assert check("THANH", "matkhau123"), "tên không phân biệt hoa thường"
                assert check("thanh", "sai-roi") is None
                assert check("khong-co-nguoi-nay", "matkhau123") is None
                assert "hash" not in all_users()[0], "KHÔNG được lộ hash ra ngoài module"

                # trùng tên → từ chối; mật khẩu ngắn → từ chối
                for f, a in ((add, ("thanh", "matkhau123")), (add, ("moi", "ngan"))):
                    try:
                        f(*a); raise AssertionError(f"phải chặn: {a}")
                    except RuntimeError:
                        pass

                # ── Đổi mật khẩu: bản cũ phải chết ngay ──
                set_password("thanh", "matkhaumoi999")
                assert check("thanh", "matkhaumoi999") and check("thanh", "matkhau123") is None

                # ── Khoá: đăng nhập không được nữa, nhưng bản ghi còn (nhật ký tra được tên) ──
                add("binh", "binhmatkhau1")
                set_disabled("binh", True)
                assert check("binh", "binhmatkhau1") is None, "đã khoá thì mật khẩu đúng cũng không vào"
                assert any(u["name"] == "binh" for u in all_users()), "khoá KHÁC xoá"
                set_disabled("binh", False)
                assert check("binh", "binhmatkhau1")

                # ── KHÔNG được tự khoá/xoá hết người cuối cùng ──
                set_disabled("binh", True)
                for f, a in ((set_disabled, ("thanh", True)), (remove, ("thanh",))):
                    try:
                        f(*a); raise AssertionError("phải chặn khoá/xoá người cuối cùng")
                    except RuntimeError as e:
                        m = str(e).lower()               # thông báo viết CUỐI CÙNG in hoa
                        assert "cuối cùng" in m or "không còn ai" in m, e
                assert check("thanh", "matkhaumoi999"), "vẫn phải vào được"

                assert remove("binh") and not remove("binh")

                # ── VAI ────────────────────────────────────────────────────────────
                # người ĐẦU TIÊN phải là owner, không thì không ai quản được tài khoản
                assert find("thanh")["role"] == "owner", find("thanh")
                # ÉP owner cho người đầu tiên KỂ CẢ khi caller xin vai khác — form board gửi
                # sẵn role="seo", và nếu nghe theo thì hệ thống không còn ai quản tài khoản.
                _t2 = tempfile.TemporaryDirectory()
                _o2 = common.ROOT
                common.ROOT = Path(_t2.name)
                try:
                    assert add("aiđó", "matkhaudai123", role="seo")["role"] == "owner"
                finally:
                    common.ROOT = _o2
                    _t2.cleanup()
                u = add("seoer", "matkhauseo123")
                # 04/08 (7ece5d3): DEFAULT đổi "seo" → "viewer" (fail-closed) nhưng assertion
                # ghim chuỗi cũ ở đây bị bỏ sót → selftest tự vỡ (đúng bài học "ghim hằng số").
                # Ghim LUẬT chứ không ghim mặt chữ: mặc định = vai THẤP NHẤT của bảng.
                assert u["role"] == roles.DEFAULT == roles.ROLES[-1], \
                    f"người sau mặc định vai THẤP nhất, đang {u['role']!r} vs {roles.ROLES[-1]!r}"
                assert add("ld", "matkhauld1234", role="leader")["role"] == "leader"
                # vai gõ sai → rơi về THẤP nhất, KHÔNG bao giờ cấp nhầm quyền cao
                assert add("gonham", "matkhaunham12", role="admin")["role"] == roles.DEFAULT

                assert set_role("seoer", "manager")["role"] == "manager"
                assert set_role("seoer", "khong-co")["role"] == roles.DEFAULT, "vai lạ → thấp nhất"

                # KHÔNG hạ/khoá/xoá được Owner CUỐI CÙNG (mất luôn đường quản tài khoản)
                for f, a in ((set_role, ("thanh", "manager")),
                             (set_disabled, ("thanh", True)),
                             (remove, ("thanh",))):
                    try:
                        f(*a); raise AssertionError(f"phải chặn: {a}")
                    except RuntimeError as e:
                        assert "owner" in str(e).lower(), e
                # có owner thứ hai thì mới hạ được người cũ
                set_role("ld", "owner")
                assert set_role("thanh", "manager")["role"] == "manager"

                # ── PHẠM VI THỊ TRƯỜNG ─────────────────────────────────────────────
                set_role("seoer", "seo")
                assert set_markets("seoer", ["US", " SPAIN "])["markets"] == ["US", "SPAIN"]
                assert roles.scope_markets(find("seoer")) == ["US", "SPAIN"]
                assert not roles.in_scope(find("seoer"), "KOREA")
                assert set_markets("seoer", [])["markets"] == []
                assert roles.scope_markets(find("seoer")) is None, "bỏ trống = mọi thị trường"

                # ── GIAO KÊNH: nay CHỈ để theo dõi, KHÔNG cấp quyền sửa ────────────
                # Đổi luật 2026-08-02: quyền GHI đọc từ `profile.created_by` (CHỦ KÊNH),
                # không đọc danh sách này nữa. Giữ `set_channels` vì nó vẫn nuôi số
                # "cầm" ở Tổng quan — nhưng phải có ca chốt rằng nó KHÔNG mở quyền sửa,
                # kẻo về sau ai đó "sửa lại cho khớp tên hàm" rồi mở lại đúng cửa vừa đóng.
                assert set_channels("seoer", ["kenh-a", " kenh-b "])["channels"] == \
                    ["kenh-a", "kenh-b"]
                _P = [{"slug": "kenh-a", "created_by": "nguoi-khac"},
                      {"slug": "kenh-tu-tao", "created_by": "seoer"}]
                assert not roles.sees_channel(find("seoer"), "kenh-a", _P), \
                    "được GIAO kênh KHÔNG còn nghĩa là sửa được"
                assert roles.sees_channel(find("seoer"), "kenh-tu-tao", _P)
                # Leader NAY cũng bị giới hạn — chỉ Manager/Owner ghi được mọi kênh
                # `ld` đã bị nâng lên owner ở trên, nên phải lấy một Leader MỚI
                add("ld2", "matkhauld2222", role="leader")
                set_channels("ld2", ["kenh-a"])          # giao rồi vẫn không sửa được
                assert not roles.sees_channel(find("ld2"), "kenh-a", _P), \
                    "leader chỉ sửa được kênh do chính mình tạo"
                # `ld` giờ là owner (bị nâng vai ở trên) — dùng đúng nó làm ca đối chứng
                assert roles.scope_channels(find("ld"), _P) is None, "owner ghi mọi kênh"
                assert roles.sees_channel(find("ld"), "kenh-a", _P)

                # ── NÂNG CẤP file cũ (chưa có `role`) ──────────────────────────────
                raw = common.read_json(_path())
                for x in raw["users"]:
                    x.pop("role", None); x.pop("markets", None)
                common.write_json(_path(), raw)
                got = _load()["users"]
                assert got[0]["role"] == "owner", "người đầu tiên của file cũ phải thành owner"
                assert all(x.get("role") for x in got), "mọi bản ghi phải có vai sau khi nâng cấp"
                assert sum(1 for x in got if x["role"] == "owner") == 1
                # ── SSO SYNC (user chốt 05/08: sổ app phải khớp tài khoản cổng) ──────
                sync_sso("thanhmoi", "seo")
                u = find("thanhmoi")
                assert u and u.get("sso") is True and u["role"] == "seo", u
                assert "hash" not in u, "bản ghi SSO không có mật khẩu"
                assert check("thanhmoi", "bat-ky") is None, "SSO không đăng nhập local được"
                sync_sso("THANHMOI", "leader")           # vai đổi ở cổng → sổ ĐI THEO, không nhân đôi
                assert find("thanhmoi")["role"] == "leader"
                assert sum(1 for x in all_users() if x["name"].lower() == "thanhmoi") == 1
                set_markets("thanhmoi", ["US"])          # giới hạn Owner tick thì SỔ GIỮ
                sync_sso("thanhmoi", "leader")
                assert find("thanhmoi")["markets"] == ["US"], "sync không được xoá giới hạn"
                cu = find("ld2")                         # tài khoản LOCAL có sẵn: sync gắn cờ + vai
                sync_sso("ld2", "seo")
                assert find("ld2")["sso"] and find("ld2")["role"] == "seo"
                assert find("ld2").get("hash"), "sync không được đụng mật khẩu local"
                print("users.py self-test OK - bam co muoi rieng, khong luu mat khau tran, "
                      "ban ghi hong khong lam sap dang nhap, khoa != xoa, chan khoa/xoa nguoi cuoi, "
                      "vai (nguoi dau = owner, go sai roi ve THAP nhat, khong ha owner cuoi), "
                      "pham vi thi truong, nang cap file cu, sso sync (vai theo cong, giu gioi han)")
            finally:
                common.ROOT = old
        raise SystemExit(0)
    raise SystemExit(_cli(sys.argv[1:]))
