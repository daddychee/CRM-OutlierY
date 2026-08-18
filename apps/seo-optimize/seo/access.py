"""Mật khẩu chung cho board khi chia sẻ trong mạng nội bộ (Tailscale/LAN).

**Vì sao cần, nói thẳng:** `.env` giữ 1 khoá z.ai + 19 khoá YouTube, và có 6 endpoint phá huỷ
(`delete-profile/format/episode/market`, `niche-remove`, `purge`) hoàn toàn không xác thực. Chừng
nào còn bind `127.0.0.1` thì không sao — không ai ngoài máy này gọi tới được. Vừa mở ra mạng là
mọi thứ đó thành công khai với mọi máy trong mạng.

**Đây KHÔNG phải hệ đăng nhập nhiều người dùng.** Một mật khẩu dùng chung, không phân quyền,
không biết ai làm gì. Nó chỉ trả lời đúng một câu: *"máy này có được phép gọi API không"*.
Muốn biết ai xoá cái gì thì phải có tài khoản riêng — việc khác hẳn, chưa làm.

**Lớp bảo vệ THẬT vẫn là mạng.** Mật khẩu đi qua HTTP thường; trong đường hầm Tailscale thì
đường truyền đã được mã hoá, còn phơi thẳng ra internet thì mật khẩu này bị nghe trộm được.
Vì thế `server.run` từ chối khởi động khi bind ra ngoài mà không có mật khẩu, nhưng **không**
tự cho rằng có mật khẩu là đủ để lên internet công cộng.

Không LLM, không quota, thuần stdlib.
"""
from __future__ import annotations

import hmac
import os
import secrets
import threading
import time

from . import roles, users

COOKIE = "seo_sid"
SESSION_H = 720                  # phiên sống 30 ngày — tool nội bộ, bắt gõ lại mỗi ngày là phiền vô ích
MAX_SESSIONS = 200               # trần chống phình bộ nhớ nếu có ai gọi /api/login liên tục
LOCK_FAILS = 20                  # sai quá số này trong LOCK_WINDOW giây thì khoá IP đó
LOCK_WINDOW = 600
LOCK_SECS = 300

_LOCK = threading.RLock()
_SESSIONS: dict[str, dict] = {}                  # token → {"exp": hạn, "user": tên}
_FAILS: dict[str, list] = {}                     # ip → [số lần sai, mốc thời gian đầu, hạn khoá]


def password() -> str:
    """Mật khẩu CHUNG đang cấu hình. Rỗng = không dùng đường này."""
    return (os.environ.get("BOARD_PASSWORD") or "").strip()


def per_user() -> bool:
    """Có tài khoản riêng từng người không (`users.json` có ít nhất 1 người còn hoạt động)."""
    return users.enabled()


def enabled() -> bool:
    """Có phải đăng nhập không.

    **Tài khoản riêng ĐÈ mật khẩu chung.** Đã khai từng người rồi mà `BOARD_PASSWORD` vẫn ăn
    thì có một cửa sau không tên, không khoá được, không hiện trong nhật ký — đúng thứ việc
    chuyển sang tài khoản riêng sinh ra để bỏ.
    """
    return per_user() or bool(password())


def _now() -> float:
    return time.time()


def _prune() -> None:
    now = _now()
    for t in [t for t, s in _SESSIONS.items() if s["exp"] <= now]:
        _SESSIONS.pop(t, None)


def locked_for(ip: str) -> int:
    """Còn bị khoá bao nhiêu giây vì gõ sai quá nhiều. 0 = không khoá."""
    with _LOCK:
        f = _FAILS.get(ip)
        if not f:
            return 0
        left = int(f[2] - _now())
        return left if left > 0 else 0


def _note_fail(ip: str) -> None:
    with _LOCK:
        now = _now()
        f = _FAILS.get(ip)
        if not f or now - f[1] > LOCK_WINDOW:        # cửa sổ cũ đã hết hạn → đếm lại từ đầu
            f = [0, now, 0.0]
        f[0] += 1
        if f[0] >= LOCK_FAILS:
            f[2] = now + LOCK_SECS
            f[0] = 0                                  # khoá rồi thì reset bộ đếm, đừng cộng dồn mãi
            f[1] = now
        _FAILS[ip] = f


def login(pw: str, ip: str = "", name: str = "") -> dict:
    """Đổi (tên +) mật khẩu lấy token phiên.

    Hai chế độ, `per_user()` quyết định:
      · có `users.json` → phải đúng CẢ tên lẫn mật khẩu, phiên nhớ tên đó (nhật ký tra được)
      · chưa có        → mật khẩu CHUNG như cũ, phiên mang tên `"(chung)"`

    Trả `{"ok": True, "token": …, "user": …}` hoặc `{"ok": False, "error": …, "wait": giây}`.
    **So sánh bằng `hmac.compare_digest`/pbkdf2**, không bằng `==`: `==` thoát ra ngay ở ký tự đầu
    khác nhau nên thời gian trả lời rò rỉ từng ký tự một.

    **Thông báo sai KHÔNG được nói rõ sai TÊN hay sai MẬT KHẨU** — nói ra là biếu không danh
    sách người dùng cho người đang dò.
    """
    if not enabled():
        return {"ok": True, "token": "", "user": "", "off": True}
    wait = locked_for(ip)
    if wait:
        return {"ok": False, "error": f"Sai quá nhiều lần — thử lại sau {wait} giây", "wait": wait}
    if per_user():
        u = users.check(name, pw)
        who = (u or {}).get("name", "")
        bad = "Tên hoặc mật khẩu không đúng"
    else:
        u = hmac.compare_digest((pw or "").encode(), password().encode()) or None
        who = "(chung)"
        bad = "Mật khẩu không đúng"
    if not u:
        _note_fail(ip)
        w = locked_for(ip)
        return {"ok": False, "error": bad + (f" — đã khoá {w} giây" if w else ""), "wait": w}
    with _LOCK:
        _prune()
        if len(_SESSIONS) >= MAX_SESSIONS:            # bỏ phiên gần hết hạn nhất, không xoá sạch
            for t, _ in sorted(_SESSIONS.items(), key=lambda kv: kv[1]["exp"])[:MAX_SESSIONS // 4]:
                _SESSIONS.pop(t, None)
        tok = secrets.token_urlsafe(32)
        _SESSIONS[tok] = {"exp": _now() + SESSION_H * 3600, "user": who}
        _FAILS.pop(ip, None)                          # đăng nhập được thì xoá lịch sử sai
    return {"ok": True, "token": tok, "user": who}


def session(token: str) -> dict | None:
    if not token:
        return None
    with _LOCK:
        s = _SESSIONS.get(token)
        if s is None:
            return None
        if s["exp"] <= _now():
            _SESSIONS.pop(token, None)
            return None
        return dict(s)


def who(token: str) -> str:
    """Tên người của phiên — để ghi nhật ký. Không xác thực thì trả rỗng."""
    if not enabled():
        return ""
    s = session(token)
    return (s or {}).get("user", "")


def current(token: str) -> dict:
    """Hồ sơ người đang đăng nhập, kèm VAI và PHẠM VI.

    **Đọc lại từ đĩa mỗi lần, không nhớ trong phiên**: đổi vai/thu hẹp thị trường phải có hiệu
    lực NGAY, không đợi người ta đăng xuất. Đọc một file JSON nhỏ, rẻ hơn nhiều so với việc
    một người bị hạ quyền vẫn xoá được dữ liệu suốt 30 ngày.

    Chưa bật xác thực → coi như `owner` không giới hạn (chạy một mình trên máy thì mọi hạn chế
    chỉ tổ vướng). Mật khẩu CHUNG → cũng `owner`: một mật khẩu thì không phân vai được, giả vờ
    có vai ở đó là nói dối.
    """
    if not enabled():
        return {"name": "", "role": "owner", "markets": [], "channels": [], "niches": [],
                "auth": False}
    s = session(token)
    if s is None:
        return {"name": "", "role": "", "markets": [], "channels": [], "niches": [],
                "auth": False}
    nm = s.get("user", "")
    if not per_user():
        return {"name": nm or "(chung)", "role": "owner", "markets": [], "channels": [],
                "niches": [], "auth": True}
    u = users.find(nm) or {}
    # `channels` PHẢI có mặt: `roles.scope_channels`/`sees_channel` đọc đúng khoá này. Thiếu nó
    # thì mọi Seo đọc ra "chưa được giao kênh nào" ⇒ thấy 0 kênh và bị 403 ngay trên kênh của
    # CHÍNH MÌNH — hỏng câm, vì nhìn bề ngoài giống hệt "phân quyền đang chạy đúng".
    # `channels` VÀ `niches` phải có mặt đủ: `roles.write_channels` / `roles.scope_niches` đọc
    # đúng hai khoá này. Thiếu một cái là phạm vi im lặng sai — đã cắn đúng vậy với `channels`
    # (mọi Seo đọc ra "chưa được giao kênh nào", ăn 403 ngay trên kênh của CHÍNH MÌNH).
    return {"name": nm, "role": roles.norm(u.get("role", "")),
            "markets": list(u.get("markets") or []),
            "channels": list(u.get("channels") or []),
            "niches": list(u.get("niches") or []), "auth": True}


def revoke_user(name: str) -> int:
    """Huỷ MỌI phiên của một người — khoá tài khoản mà phiên cũ vẫn chạy thì khoá vô nghĩa.

    Trả số phiên đã huỷ. Gọi sau `users.set_disabled(...)` / đổi mật khẩu.
    """
    n = (name or "").strip().lower()
    with _LOCK:
        gone = [t for t, s in _SESSIONS.items() if (s.get("user") or "").lower() == n]
        for t in gone:
            _SESSIONS.pop(t, None)
        return len(gone)


def keep_alive(token: str, name: str) -> None:
    """Dựng lại phiên vừa bị `revoke_user` quét trúng — dùng khi CHÍNH người đó tự đổi mật khẩu.

    Đổi mật khẩu phải giết mọi phiên KHÁC (máy khác, tab cũ), nhưng đá luôn người đang ngồi
    đổi thì chỉ tổ phiền mà không thêm an toàn gì: họ vừa chứng minh biết mật khẩu cũ.
    """
    if not token:
        return
    with _LOCK:
        _SESSIONS[token] = {"exp": _now() + SESSION_H * 3600, "user": name}


def valid(token: str) -> bool:
    if not enabled():
        return True
    s = session(token)
    if s is None:
        return False
    # Bị KHOÁ sau khi đã đăng nhập thì phiên phải chết ngay, không đợi hết hạn 30 ngày.
    if per_user() and s.get("user") not in ("", "(chung)"):
        u = users.find(s["user"])
        if u is None or u.get("disabled"):
            with _LOCK:
                _SESSIONS.pop(token, None)
            return False
    return True


def logout(token: str) -> None:
    with _LOCK:
        _SESSIONS.pop(token, None)


def token_from_cookie(header: str) -> str:
    """Moi token khỏi header `Cookie`. Tự tách, không dùng `http.cookies` cho một khoá."""
    for part in (header or "").split(";"):
        k, _, v = part.strip().partition("=")
        if k == COOKIE:
            return v.strip()
    return ""


def set_cookie(token: str, secure: bool = False) -> str:
    """Chuỗi cho header `Set-Cookie`.

    `HttpOnly` để JS không đọc được (một XSS trong board là mất luôn phiên).
    `SameSite=Strict` là hàng rào CSRF thứ hai, song song với `server._cross_site`.
    """
    bits = [f"{COOKIE}={token}", "Path=/", "HttpOnly", "SameSite=Strict",
            f"Max-Age={SESSION_H * 3600}"]
    if secure:
        bits.append("Secure")
    return "; ".join(bits)


def clear_cookie() -> str:
    return f"{COOKIE}=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0"


def n_sessions() -> int:
    with _LOCK:
        _prune()
        return len(_SESSIONS)


def _reset_for_test() -> None:
    with _LOCK:
        _SESSIONS.clear()
        _FAILS.clear()


if __name__ == "__main__":                            # self-test offline, không đụng gì bên ngoài
    import tempfile
    from pathlib import Path

    from . import common
    old = os.environ.get("BOARD_PASSWORD")
    _root = common.ROOT
    _td = tempfile.TemporaryDirectory()
    common.ROOT = Path(_td.name)                      # cô lập users.json — KHÔNG đụng bản thật
    try:
        # ── TẮT xác thực khi không đặt mật khẩu (giữ nguyên cách chạy một mình) ──
        os.environ.pop("BOARD_PASSWORD", None)
        _reset_for_test()
        assert not enabled()
        assert valid("") and valid("bat-ky-gi")        # tắt thì mọi thứ qua
        assert login("sai-be-bet")["ok"]

        # ── BẬT ──
        os.environ["BOARD_PASSWORD"] = "mat-khau-that"
        _reset_for_test()
        assert enabled()
        assert not valid("")                           # không token = không qua
        assert not valid("token-bia")
        r = login("sai", ip="1.1.1.1")
        assert not r["ok"] and "không đúng" in r["error"], r
        r = login("mat-khau-that", ip="1.1.1.1")
        assert r["ok"] and len(r["token"]) > 20, r
        tok = r["token"]
        assert valid(tok)
        logout(tok)
        assert not valid(tok), "logout phải huỷ phiên ngay"

        # Gần đúng vẫn là SAI — không có chuyện "gần giống thì cho qua" ở mật khẩu
        for pw in ("mat-khau-tha", "mat-khau-that ", "MAT-KHAU-THAT", ""):
            assert not login(pw, ip="2.2.2.2")["ok"], pw

        # ── Khoá IP sau khi sai quá nhiều ──
        _reset_for_test()
        for _ in range(LOCK_FAILS):
            login("sai", ip="3.3.3.3")
        assert locked_for("3.3.3.3") > 0, "phải khoá sau LOCK_FAILS lần sai"
        # ĐANG KHOÁ thì mật khẩu ĐÚNG cũng không vào được — nếu không thì khoá vô nghĩa
        assert not login("mat-khau-that", ip="3.3.3.3")["ok"]
        assert locked_for("4.4.4.4") == 0, "khoá phải theo TỪNG IP, không khoá cả server"

        # Đăng nhập được thì xoá lịch sử sai của IP đó
        _reset_for_test()
        login("sai", ip="5.5.5.5")
        assert login("mat-khau-that", ip="5.5.5.5")["ok"]
        assert not _FAILS.get("5.5.5.5")

        # ── Cookie ──
        assert token_from_cookie(f"a=1; {COOKIE}=xyz; b=2") == "xyz"
        assert token_from_cookie("khong-co-gi") == ""
        assert token_from_cookie("") == ""
        c = set_cookie("abc")
        assert "HttpOnly" in c and "SameSite=Strict" in c and "Secure" not in c
        assert "Secure" in set_cookie("abc", secure=True)
        assert "Max-Age=0" in clear_cookie()

        # ── Trần phiên: không phình vô hạn ──
        _reset_for_test()
        for _ in range(MAX_SESSIONS + 30):
            login("mat-khau-that", ip="6.6.6.6")
        assert n_sessions() <= MAX_SESSIONS, n_sessions()

        # ── Phiên HẾT HẠN thì không dùng được nữa ──
        _reset_for_test()
        tok = login("mat-khau-that")["token"]
        with _LOCK:
            _SESSIONS[tok]["exp"] = _now() - 1
        assert not valid(tok), "phiên quá hạn phải bị từ chối"

        # ── TÀI KHOẢN RIÊNG TỪNG NGƯỜI ─────────────────────────────────────────────
        _reset_for_test()
        users.add("thanh", "matkhau123")
        users.add("binh", "binhmatkhau1")
        assert per_user() and enabled()

        # Có users.json rồi thì BOARD_PASSWORD phải HẾT ăn — nếu không thì còn một cửa
        # sau không tên, không khoá được, không hiện trong nhật ký.
        assert not login("mat-khau-that", ip="9.9.9.9")["ok"], "mật khẩu chung phải hết hiệu lực"

        # Mọi khoá phạm vi phải CÓ MẶT trong `current()` — thiếu một cái là hỏng câm
        users.set_niches("thanh", ["Space"])
        _c = current(login("matkhau123", ip="0.0.0.0", name="thanh")["token"])
        assert set(_c) >= {"name", "role", "markets", "channels", "niches"}, _c
        assert _c["niches"] == ["Space"], _c
        users.set_niches("thanh", [])

        r = login("matkhau123", ip="7.7.7.7", name="thanh")
        assert r["ok"] and r["user"] == "thanh", r
        t_thanh = r["token"]
        assert valid(t_thanh) and who(t_thanh) == "thanh"
        assert not login("binhmatkhau1", ip="7.7.7.7", name="thanh")["ok"], "mật khẩu của người khác"
        # Thông báo KHÔNG được nói rõ sai TÊN hay sai MẬT KHẨU (biếu không danh sách người dùng)
        e1 = login("saibetnhe1", ip="8.8.8.8", name="thanh")["error"]
        e2 = login("saibetnhe1", ip="8.8.8.8", name="khong-he-co-nguoi-nay")["error"]
        assert e1 == e2, (e1, e2)

        # KHOÁ người → phiên đang chạy phải CHẾT NGAY, không đợi hết hạn 30 ngày
        r2 = login("binhmatkhau1", ip="6.6.6.6", name="binh")
        t_binh = r2["token"]
        assert valid(t_binh)
        users.set_disabled("binh", True)
        assert not valid(t_binh), "khoá tài khoản mà phiên cũ vẫn chạy thì khoá vô nghĩa"
        assert valid(t_thanh), "người khác KHÔNG được bị đá ra theo"

        # revoke_user: huỷ mọi phiên của đúng một người
        users.set_disabled("binh", False)
        t_b2 = login("binhmatkhau1", ip="6.6.6.6", name="binh")["token"]
        assert valid(t_b2)
        assert revoke_user("BINH") == 1, "tên không phân biệt hoa thường"
        assert not valid(t_b2) and valid(t_thanh)

        # Đổi mật khẩu: bản cũ chết, và phiên cũ nên bị thu hồi bằng revoke_user
        users.set_password("thanh", "matkhaumoi999")
        assert not login("matkhau123", ip="5.5.5.5", name="thanh")["ok"]
        assert login("matkhaumoi999", ip="5.5.5.5", name="thanh")["ok"]
        print("access.py self-test OK - tat khi khong dat mat khau, compare_digest, "
              "khoa theo TUNG IP, cookie HttpOnly+SameSite, tran phien, het han · "
              "tai khoan rieng DE mat khau chung, khoa nguoi la phien chet ngay, "
              "bao sai khong lo ten nao co that")
    finally:
        if old is None:
            os.environ.pop("BOARD_PASSWORD", None)
        else:
            os.environ["BOARD_PASSWORD"] = old
        common.ROOT = _root
        _td.cleanup()
