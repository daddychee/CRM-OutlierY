"""Content Ultimate — server hợp nhất: Outline board (oe) + Author Extract (voiceprofile).

Chạy:  python3 -m contentultimate.server [--port 8770] [--run <tên>] [--no-browser]
       (hoặc entry point:  .venv/bin/content-ultimate)

Một process, một port, kế thừa handler của voiceprofile.server (giữ nguyên /api/*):
  /                  → trang chủ 2 khối
  /outline           → board Outline (oe/board.html)
  /oe/api/*          → board / save / ingest / resume / status (tái dùng oe.s5_server)
  /author            → Author Extract 2 tab (voiceprofile/board.html, /api/* như cũ)
  /api/outlines      → liệt kê runs/*/outline.txt — hand-off outline → Writer
  /api/outline-load  → đọc nội dung 1 outline (chỉ file nằm trong danh sách trên)

CHỈ bind 127.0.0.1 — lên VPS phải đặt sau reverse proxy + HTTPS + auth (CLAUDE.md Phần C).
"""
from __future__ import annotations

import argparse
import os
import re
import secrets
import subprocess
import threading
import time
import webbrowser
from http.server import ThreadingHTTPServer
from pathlib import Path

from oe import common as oe_common
from oe import s5_server as oe_srv
from voiceprofile import server as vp_srv
from voiceprofile import usage as vp_usage
from voiceprofile.llm import load_env_file

OE_HTML = Path(oe_srv.__file__).parent / "board.html"
VP_HTML = Path(vp_srv.__file__).parent / "board.html"

# Board Outline THEO NGƯỜI DÙNG (2026-07-22): trước đây 1 run dir global — 2 người làm
# cùng lúc, người ingest sau ĐÈ board (và cả picks) của người trước. Giờ mỗi request tự
# mang run: ?run=/body.run (board gửi) → run user gắn gần nhất → run mặc định lúc khởi động.
RD = {"rd": None}                                       # fallback: run mới nhất có data
USER_RUNS: dict[str, str] = {}                          # user → run đang mở (persist qua restart)
USER_RUNS_PATH = oe_common.RUNS / ".user-runs.json"


def _load_user_runs() -> dict:
    try:
        d = oe_common.read_json(USER_RUNS_PATH)
        return d if isinstance(d, dict) else {}
    except Exception:                                   # noqa: BLE001 — thiếu/hỏng → bắt đầu rỗng
        return {}


def _set_user_run(user: str, run_name: str) -> None:
    if not user or USER_RUNS.get(user) == run_name:
        return
    USER_RUNS[user] = run_name
    try:
        oe_common.RUNS.mkdir(parents=True, exist_ok=True)
        oe_common.write_json(USER_RUNS_PATH, USER_RUNS)
    except Exception:                                   # noqa: BLE001 — persist là best-effort
        pass


def _rd_for(handler, run_param: str = "") -> Path:
    """Run dir cho request này. Run được nêu tường minh cũng GẮN user vào run đó
    (lần sau mở board không cần nói lại). run_dir tự làm sạch tên (_slug) — an toàn path."""
    user = (handler.headers.get("X-Remote-User") or "").strip()
    if run_param:
        rd = oe_common.run_dir(str(run_param))
        _set_user_run(user, rd.name)
        return rd
    if user and USER_RUNS.get(user):
        return oe_common.run_dir(USER_RUNS[user])
    return RD["rd"]

ENV_PATH = oe_common.ROOT / ".env"

# Tab Cài đặt (chỉ admin): catalog key được sửa qua app — không nhận key ngoài danh sách.
# ADMIN_USERS không phải secret (hiện rõ); các key còn lại chỉ hiện 4 ký tự cuối.
SETTING_KEYS = [
    ("ANTHROPIC_API_KEY", "Claude (Anthropic)", "mở 2 model: Claude Sonnet · Claude Opus"),
    ("GLM_API_KEY", "GLM (z.ai)", "mở 2 model: GLM 5.0 · GLM 5.2"),
    ("TRANSCRIPT_API_KEY", "transcriptapi.com", "S1b transcript — board Outline"),
    ("YOUTUBE_API_KEY", "YouTube Data API", "S1c comment — board Outline"),
    ("ADMIN_USERS", "Quản trị viên", "TÊN ĐĂNG NHẬP của admin (đúng tài khoản đăng nhập, "
                                     "vd: thanh — KHÔNG phải tên hiển thị), cách nhau dấu phẩy; "
                                     "để trống = ai cũng thấy tab này (chế độ máy cá nhân)"),
]


def merge_env(text: str, updates: dict[str, str]) -> str:
    """Cập nhật KEY=VALUE trong nội dung .env, giữ nguyên mọi dòng khác.

    - value rỗng → comment dòng đó (tắt key nhưng giữ dấu vết).
    - Dòng trùng key phía sau bị vô hiệu hoá nếu đang active (parser .env last-wins).
    """
    # Giá trị chỉ được một dòng: cắt ở ký tự xuống dòng để một API key/ADMIN_USERS
    # dán kèm "\nHTPASSWD_FILE=…" không chèn được biến .env khác (rà soát 2026-07-09).
    updates = {k: v.replace("\r", "").split("\n", 1)[0].strip() for k, v in updates.items()}
    seen: set[str] = set()
    out: list[str] = []
    for line in text.splitlines():
        m = re.match(r"\s*#?\s*([A-Za-z_][A-Za-z0-9_]*)\s*=", line)
        key = m.group(1) if m else None
        if key in updates:
            if key not in seen:
                seen.add(key)
                val = updates[key]
                out.append(f"{key}={val}" if val else f"# {key}=")
            elif not line.lstrip().startswith("#"):
                out.append("# " + line)
            else:
                out.append(line)
        else:
            out.append(line)
    for key, val in updates.items():
        if key not in seen:
            out.append(f"{key}={val}" if val else f"# {key}=")
    return "\n".join(out) + "\n"


def _env_dict() -> dict[str, str]:
    return load_env_file(ENV_PATH) if ENV_PATH.exists() else {}


def _is_admin(handler) -> bool:
    """ADMIN_USERS chưa cấu hình → mọi người là admin (chạy local một người).

    Đã cấu hình → chỉ user nginx xác thực và truyền qua header X-Remote-User
    (app bind 127.0.0.1 sau proxy nên header này không giả được từ ngoài).
    """
    vai = _vai_sso(handler)
    if vai is not None:              # SSO: vai OUTLIERY quyết, ADMIN_USERS không xét nữa
        return vai == "admin"
    admins = [u.strip() for u in _env_dict().get("ADMIN_USERS", "").split(",") if u.strip()]
    if not admins:
        return True
    return (handler.headers.get("X-Remote-User") or "").strip() in admins


def _esc(s: str) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def _me(handler) -> str:
    return (handler.headers.get("X-Remote-User") or "").strip()


# --- SSO từ OUTLIERY (30/07/2026): MỘT hệ tài khoản duy nhất -------------------------
# Bật bằng CU_TRUST_PROXY=1. OUTLIERY đã đăng nhập + phân quyền (bộ phận × level) rồi tiêm
# X-Remote-User + X-Remote-Role (viewer/leader/owner — tính từ bảng hanh_dong của
# apps_registry) vào mỗi request qua proxy. Khi cờ bật, VAI lấy từ header — ADMIN_USERS
# trong .env và roles.json KHÔNG còn là nguồn sự thật (hết cảnh mỗi app một bảng quyền).
# Van an toàn: chỉ tin khi client là LOOPBACK — app bind 127.0.0.1 nên chỉ proxy trên cùng
# máy tới được; lỡ sau này app mở ra LAN thì header giả từ ngoài vẫn bị chặn ở đây.
def _vai_sso(handler) -> str | None:
    """Vai đã dịch về thang của app ('admin'/'leader'/'creator'), None = SSO không hoạt động.

    V3 (Permissions v2 — DE.md mục 14): ƯU TIÊN X-Remote-Actions do gateway tính
    từ luật + tick lẻ + acting, chảy sang TỪNG request: quan_tri → admin (tab Cài
    đặt + API key) · sua → leader (tab Quản lý: nhật ký/token/bảo mật — trần vận
    hành, luật 04/08 'Manager không bao giờ ngang Owner') · còn lại creator.
    THIẾU hẳn header Actions (gateway đời cũ) → fallback X-Remote-Role DANH PHÁP
    MỚI: admin→admin · manager/leader→leader · viewer/lạ→creator.
    SSO đang bật là KHÔNG BAO GIỜ trả None ở giữa — DEFAULT creator fail-closed
    (bản cũ vai lạ trả None → rơi về ADMIN_USERS rỗng = ai cũng admin, bịt hẳn);
    None CHỈ khi cờ tắt hoặc client không phải loopback."""
    if os.environ.get("CU_TRUST_PROXY") != "1":
        return None
    if handler.client_address[0] not in ("127.0.0.1", "::1"):
        return None
    raw = handler.headers.get("X-Remote-Actions")
    if raw is not None:
        hd = {s.strip() for s in raw.split(",") if s.strip()}
        if "quan_tri" in hd:
            return "admin"
        if "sua" in hd:
            return "leader"
        return "creator"
    vai = (handler.headers.get("X-Remote-Role") or "").strip().lower()
    return {"admin": "admin", "manager": "leader", "leader": "leader"}.get(vai, "creator")


# --- "Tôi đang là ai" ----------------------------------------------------------------
#
# Basic auth KHÔNG có phiên ⇒ browser tự gửi lại mật khẩu đã nhớ, im lặng, mãi mãi.
# Hệ quả thật (user báo 2026-07-15): admin tạo tài khoản test rồi đăng nhập bằng nó,
# duyệt tool thấy chạy ngon → tưởng tool KHÔNG có bảo mật, và không hiểu vì sao /manage
# lại 403. Không hiện danh tính = user không có cách nào tự biết mình đang là ai.
# ⇒ Mọi trang admin phải nói rõ ĐANG LÀ AI + lối đổi tài khoản.

# z-index 60: phải nằm TRÊN mọi overlay/modal của 2 board (cao nhất đang là .ctaov z-index 58).
WHOAMI_CSS = """
  .whoami{position:fixed;top:0;right:0;z-index:60;display:flex;gap:9px;align-items:center;
    background:var(--panel);border:1px solid var(--border);border-top:none;border-right:none;
    border-radius:0 0 0 10px;padding:6px 12px;font:500 11.5px/1.5 system-ui,sans-serif;
    color:var(--muted);box-shadow:0 1px 8px rgba(0,0,0,.18)}
  .whoami b{color:var(--text)}
  .whoami .adm{color:var(--accent);font-weight:700}
  .whoami .out{border:1px solid var(--border);background:var(--raised);color:var(--muted);
    border-radius:6px;padding:3px 9px;text-decoration:none;font-weight:600;font-size:11px}
  .whoami .out:hover{border-color:var(--accent);color:var(--accent)}
"""


def _whoami_bar(handler) -> str:
    """Dải góc phải MỌI trang: đang đăng nhập là ai + nút thoát.

    Rỗng khi chạy local (không có nginx ⇒ không có danh tính thật để hiện — không bịa).
    Xem C2b: thiếu dải này user không có cách nào tự biết mình là ai (basic auth gửi lại
    mật khẩu im lặng) — đã gây hiểu lầm "tool không có bảo mật" 2026-07-15.
    """
    me = _me(handler)
    if not me:
        return ""
    if _vai_sso(handler) is not None:
        # SSO qua OUTLIERY: danh tính + vai đã hiện ở topbar OUTLIERY — không vẽ chip thứ
        # hai, không có nút Thoát riêng (đổi người = đăng xuất ở OUTLIERY).
        return ""
    admins = _admin_list()
    if not admins or me in admins:
        tag = ' <span class="adm">· quản trị viên</span>'
    elif _role_of(me) == ROLE_LEADER:
        tag = ' <span class="adm">· leader</span>'
    else:
        tag = ' <span>· creator</span>'
    return (f'<div class="whoami"><span>👤 <b>{_esc(me)}</b>{tag}</span>'
            f'<a class="out" href="/logout" title="Thoát để đăng nhập bằng tài khoản khác">'
            f'Thoát</a></div>')


def _forbidden_page(handler, need: str = "quản trị viên",
                    how: str = "") -> bytes:
    """403 nói RÕ bạn là ai, đang thiếu quyền gì, và xin quyền ở đâu — thay cho
    'Chỉ quản trị viên.' trống không (chính nó làm user tưởng tool hỏng/không có auth)."""
    me = _me(handler)
    admins = _admin_list()
    role = _role_of(me) if me else ""
    who = (f"Bạn đang đăng nhập bằng tài khoản <b>{_esc(me)}</b>"
           + (f" (vai: <b>{_esc(role)}</b>)" if role else "")
           + f" — trang này cần quyền <b>{_esc(need)}</b>.") if me else \
          f"Bạn chưa đăng nhập bằng tài khoản có quyền <b>{_esc(need)}</b>."
    if _vai_sso(handler) is not None:
        # SSO: quyền cấp ở OUTLIERY, không có chuyện "đăng nhập tài khoản khác" ở đây.
        loi_thoat = ("<p>Quyền được cấp trong <b>OUTLIERY</b> (bộ phận × level) — "
                     "nhờ Owner chỉnh trong trang Quản lý người dùng.</p>"
                     '<p><a href="/">← Về trang chủ</a> (các công cụ vẫn dùng bình thường)</p>')
    else:
        loi_thoat = ('<p><a href="/logout">→ Đăng nhập bằng tài khoản khác</a><br>'
                     '<a href="/">← Về trang chủ</a> (các công cụ vẫn dùng bình thường)</p>')
    lst = ", ".join(f"<b>{_esc(a)}</b>" for a in admins) or "(chưa đặt ADMIN_USERS)"
    how_html = f"<p>{how}</p>" if how else ""
    return (f"""<!doctype html><html lang="vi"><head><meta charset="utf-8"><link rel="stylesheet" href="/static/fonts/fonts.css"><script src="/static/theme.js"></script>
<title>403 — cần quyền {_esc(need)}</title><style>
 body{{margin:0;background:#090c12;color:#e8edf4;font:15px/1.6 'Inter',system-ui,sans-serif}}
 :root[data-theme="light"] body{{background:#F5F5F5;color:#16181C}}
 .w{{max-width:520px;margin:0 auto;padding:70px 24px}}
 h1{{font-size:26px;margin:0 0 10px}} p{{color:#8b96a8}} b{{color:#4c8fe0}}
 a{{color:#4c8fe0}} .box{{border-left:2px solid #243149;padding-left:14px;margin-top:18px;font-size:13px}}
</style></head><body><div class="w">
 <h1>403 — cần quyền {_esc(need)}</h1>
 <p>{who}</p>
 <div class="box">
   {how_html}
   <p>Quản trị viên hiện tại: {lst}</p>
   {loi_thoat}
 </div></div></body></html>""").encode("utf-8")


LOGOUT_HTML = """<!doctype html><html lang="vi"><head><meta charset="utf-8"><link rel="stylesheet" href="/static/fonts/fonts.css"><script src="/static/theme.js"></script>
<title>Đổi tài khoản</title><style>
 body{margin:0;background:#090c12;color:#e8edf4;font:15px/1.6 'Inter',system-ui,sans-serif}
 :root[data-theme="light"] body{background:#F5F5F5;color:#16181C}
 .w{max-width:520px;margin:0 auto;padding:70px 24px} h1{font-size:24px;margin:0 0 10px}
 p{color:#8b96a8} a{color:#4c8fe0}
</style></head><body><div class="w">
 <h1>Đã thoát</h1>
 <p>Trình duyệt sẽ hỏi lại tên đăng nhập ở lần vào sau.</p>
 <p><a href="/">← Vào lại</a></p>
 <p style="font-size:12.5px;margin-top:24px;border-left:2px solid #243149;padding-left:12px">
   Cách này dùng cơ chế basic auth nên tuỳ trình duyệt: nếu vào lại mà vẫn nhận tài khoản cũ,
   hãy đóng hẳn trình duyệt rồi mở lại, hoặc dùng cửa sổ ẩn danh.</p>
</div></body></html>"""


def _settings_payload() -> dict:
    env = _env_dict()
    items = []
    for key, label, hint in SETTING_KEYS:
        val = env.get(key, "")
        secret = key != "ADMIN_USERS"
        items.append({
            "key": key, "label": label, "hint": hint, "set": bool(val),
            "tail": (val[-4:] if len(val) >= 8 else "") if secret else "",
            "value": "" if secret else val,
        })
    return {"settings": items}


def _save_settings(b: dict) -> dict:
    allowed = {k for k, _, _ in SETTING_KEYS}
    updates = {k: str(v) for k, v in (b.get("updates") or {}).items() if k in allowed}
    if updates:
        text = ENV_PATH.read_text(encoding="utf-8") if ENV_PATH.exists() else ""
        ENV_PATH.write_text(merge_env(text, updates), encoding="utf-8")
    return {"ok": True, **_settings_payload()}


# --- Cookies YouTube (chống bot-check IP datacenter — heatmap.py tự dùng khi file có) ---

COOKIES_PATH = oe_common.ROOT / "cookies.txt"


def _cookies_status() -> dict:
    if not COOKIES_PATH.exists():
        return {"exists": False}
    st = COOKIES_PATH.stat()
    n = sum(1 for ln in COOKIES_PATH.read_text(encoding="utf-8").splitlines()
            if ln.strip() and not ln.startswith("#"))
    return {"exists": True, "mtime": st.st_mtime, "n_lines": n}


def _save_cookies(content: str) -> tuple[bool, str]:
    """Dán từ UI → ghi cookies.txt (600). Nội dung rỗng bị TỪ CHỐI — xóa phải qua
    action=delete (bug thật 2026-07-09: bấm Lưu với ô trống làm bay cookies cả team).
    """
    content = content.strip()
    if not content:
        return False, ("ô đang trống — dán nội dung cookies.txt rồi bấm Lưu "
                       "(muốn xóa hãy dùng nút Xóa cookies)")
    if "youtube.com" not in content or "\t" not in content:
        return False, ("nội dung không giống file cookies.txt (định dạng Netscape) — "
                       "xuất bằng extension 'Get cookies.txt LOCALLY' rồi dán NGUYÊN VĂN, "
                       "đừng copy từ DevTools")
    # Ghi ATOMIC (temp cùng thư mục → os.replace): chỉ cần quyền ghi THƯ MỤC, nên tự
    # lành cả khi cookies.txt cũ bị root sở hữu (bug thật 2026-07-10: file root-owned →
    # write_text PermissionError → mọi lần Lưu của cả team crash 500). replace cũng
    # tránh hỏng file khi 2 người lưu cùng lúc.
    try:
        tmp = COOKIES_PATH.with_suffix(".txt.tmp")
        tmp.write_text(content + "\n", encoding="utf-8")
        tmp.chmod(0o600)
        os.replace(tmp, COOKIES_PATH)
    except OSError as e:
        return False, (f"không ghi được cookies trên server ({e.strerror or e}) — "
                       "báo quản trị viên kiểm quyền file /opt/content-ultimate/cookies.txt")
    # Thiếu cookie đăng nhập = xuất từ phiên chưa login (đo thật 2026-07-09: 8 cookie
    # khách vãng lai vẫn bị bot-check; bản 26 cookie có login thì qua).
    login_markers = ("LOGIN_INFO", "SAPISID", "__Secure-1PSID")
    if not any(m in content for m in login_markers):
        return True, ("đã lưu, NHƯNG thiếu cookie đăng nhập (SID/LOGIN_INFO) — YouTube "
                      "nhiều khả năng vẫn chặn. Hãy ĐĂNG NHẬP YouTube trong cửa sổ đó "
                      "trước, rồi Export lại.")
    return True, "đã lưu"


# --- Khóa mời thành viên (mô hình mượn Radary: mã dùng-một-lần, có hạn, chặn brute-force) ---

INVITES_PATH = oe_common.ROOT / "invites.json"
INVITE_TTL = 7 * 24 * 3600            # khóa mời sống 7 ngày
_USER_RE = re.compile(r"^[A-Za-z0-9._-]{2,32}$")
_ACCEPT_FAILS: dict[str, tuple[int, float]] = {}   # ip -> (số lần thử hỏng, hạn reset)


def _htpasswd_file() -> Path | None:
    p = _env_dict().get("HTPASSWD_FILE", "").strip()
    return Path(p) if p else None


def _load_invites() -> list[dict]:
    return oe_common.read_json(INVITES_PATH) if INVITES_PATH.exists() else []


def _save_invites(lst: list[dict]) -> None:
    oe_common.write_json(INVITES_PATH, lst)


def _create_invite() -> dict:
    inv = {"token": secrets.token_urlsafe(9), "created": time.time(),
           "expires": time.time() + INVITE_TTL, "used_by": None, "used_at": None}
    lst = _load_invites()
    lst.append(inv)
    _save_invites(lst)
    return inv


def _existing_users(htfile: Path) -> set[str]:
    if not htfile.exists():
        return set()
    return {ln.split(":", 1)[0] for ln in htfile.read_text(encoding="utf-8").splitlines()
            if ":" in ln}


def _htpasswd_add(htfile: Path, user: str, pw: str) -> None:
    r = subprocess.run(["htpasswd", "-bB", str(htfile), user, pw],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or "htpasswd lỗi").strip()[:200])


def _accept_invite(token: str, user: str, pw: str, *,
                   htfile: Path | None = None, add_user=None) -> tuple[bool, str]:
    """Đổi khóa mời lấy tài khoản. htfile/add_user tiêm được để test offline."""
    htfile = htfile or _htpasswd_file()
    if not htfile:
        return False, "server chưa cấu hình HTPASSWD_FILE — báo quản trị viên"
    lst = _load_invites()
    inv = next((i for i in lst if i["token"] == token), None)
    if not inv or inv["used_by"] or inv["expires"] < time.time():
        return False, "khóa mời không hợp lệ, đã dùng hoặc hết hạn — xin khóa mới từ quản trị viên"
    user = user.strip()
    if not _USER_RE.match(user):
        return False, "tên đăng nhập 2-32 ký tự, chỉ chữ/số và . _ -"
    if len(pw) < 8:
        return False, "mật khẩu tối thiểu 8 ký tự"
    if user in _existing_users(htfile):
        return False, "tên đăng nhập này đã có người dùng — chọn tên khác"
    (add_user or _htpasswd_add)(htfile, user, pw)
    inv.update(used_by=user, used_at=time.time())
    _save_invites(lst)
    return True, "ok"


def _accept_guard(ip: str, limit: int = 20, window: int = 300) -> bool:
    """Chặn brute-force khóa mời theo IP (pattern _auth_guard của Radary). True = cho qua."""
    now = time.time()
    cnt, reset = _ACCEPT_FAILS.get(ip, (0, 0.0))
    if now > reset:
        cnt, reset = 0, now + window
    if cnt >= limit:
        return False
    _ACCEPT_FAILS[ip] = (cnt + 1, reset)
    return True


# --- Phân quyền 2 vai (user chốt 2026-07-16) -----------------------------------------
#
#   CREATOR (mặc định)  : dùng 3 công cụ — Outline Board · Author Extract · Writing.
#   LEADER              : Creator + trang Quản lý (nhật ký/token/bảo mật).
#   ADMIN (ADMIN_USERS) : đứng TRÊN vai trò — thêm Cài đặt (API key, thành viên, GÁN QUYỀN).
#
# Vai lưu ở roles.json (ngoài git — dữ liệu team, luật A2), thiếu tên = creator.
# Nhận diện vẫn CHỈ qua X-Remote-User do nginx ghi đè (luật C2). Local không cấu hình
# ADMIN_USERS → mọi người là admin (chế độ máy cá nhân) → mọi cổng đều mở như cũ.

ROLES_PATH = oe_common.ROOT / "roles.json"
ROLE_LEADER, ROLE_CREATOR = "leader", "creator"


def _load_roles() -> dict:
    try:
        d = oe_common.read_json(ROLES_PATH) if ROLES_PATH.exists() else {}
        return d if isinstance(d, dict) else {}
    except Exception:  # noqa: BLE001 — file rách không được khoá cả team ngoài cửa
        return {}


def _save_roles(d: dict) -> None:
    oe_common.write_json(ROLES_PATH, d)


def _role_of(user: str) -> str:
    return ROLE_LEADER if _load_roles().get(user) == ROLE_LEADER else ROLE_CREATOR


def _can_manage(handler) -> bool:
    """Quản lý (nhật ký/token/bảo mật): admin HOẶC leader."""
    vai = _vai_sso(handler)
    if vai is not None:              # SSO: vai OUTLIERY quyết, roles.json không xét nữa
        return vai in ("admin", "leader")
    if _is_admin(handler):
        return True
    return _role_of(_me(handler)) == ROLE_LEADER


# --- Tab Quản lý: thành viên · nhật ký làm việc · token · dấu hiệu bất thường -------
#
# GIỚI HẠN PHẢI BIẾT (đừng hứa quá với người dùng):
# Auth là nginx basic auth → KHÔNG có phiên đăng nhập. Mỗi request mang thẳng
# user/mật khẩu. Vì thế:
#   - không "đăng xuất thiết bị lạ" được, không thu hồi phiên được;
#   - lộ mật khẩu = kẻ lạ dùng được tới khi ĐỔI MẬT KHẨU (user thật cũng phải đổi theo);
#   - IP đổi liên tục là bình thường (4G/VPN/ISP) → mục cảnh báo là DẤU HIỆU để người
#     thật xem, không phải bằng chứng. Không tự khoá ai dựa trên nó.
# Muốn làm đúng (phiên, thu hồi, 2FA) phải đưa auth vào app — việc riêng, chưa làm.

def _remote_ip(handler) -> str:
    """IP client thật. nginx đặt X-Forwarded-For (deploy/nginx conf); lấy hop đầu."""
    return (handler.headers.get("X-Forwarded-For")
            or handler.client_address[0]).split(",")[0].strip()


# (user, ip, giờ) đã ghi — chặn access.jsonl phình to vì mỗi lần poll /api/status.
_SEEN: set[tuple[str, str, int]] = set()


def _touch(handler) -> None:
    """Ghi dấu (user, IP) — chỉ khi là cặp MỚI trong giờ đó. Không bao giờ ném lỗi."""
    try:
        user = (handler.headers.get("X-Remote-User") or "").strip()
        if not user:
            return                                   # chạy local không nginx → không theo dõi
        ip = _remote_ip(handler)
        key = (user, ip, int(time.time() // 3600))
        if key in _SEEN:
            return
        if len(_SEEN) > 5000:                        # chặn rò rỉ bộ nhớ khi chạy lâu ngày
            _SEEN.clear()
        _SEEN.add(key)
        vp_usage.record_access(user, ip, handler.path.split("?", 1)[0][:120])
    except Exception:  # noqa: BLE001 — theo dõi hỏng không được làm hỏng request
        pass


def _htpasswd_remove(htfile: Path, user: str) -> None:
    r = subprocess.run(["htpasswd", "-D", str(htfile), user],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or "htpasswd -D lỗi").strip()[:200])


def _admin_list() -> list[str]:
    return [u.strip() for u in _env_dict().get("ADMIN_USERS", "").split(",") if u.strip()]


def _users_payload() -> dict:
    """Danh sách thành viên + dấu vết hoạt động. Mọi con số ĐO từ sổ ghi, không đoán."""
    htfile = _htpasswd_file()
    if not htfile:
        return {"configured": False, "users": []}
    admins = _admin_list()
    roles = _load_roles()
    joined = {i["used_by"]: i["used_at"] for i in _load_invites() if i.get("used_by")}
    acc = vp_usage.read_rows(vp_usage.ACCESS)
    day_ago = time.time() - 86400
    users = []
    for name in sorted(_existing_users(htfile)):
        mine = [a for a in acc if a.get("user") == name]
        ips24 = sorted({a.get("ip") for a in mine if float(a.get("ts") or 0) >= day_ago})
        users.append({
            "user": name,
            "admin": name in admins,
            "role": ROLE_LEADER if roles.get(name) == ROLE_LEADER else ROLE_CREATOR,
            "joined": joined.get(name),
            "last_seen": max((float(a.get("ts") or 0) for a in mine), default=None),
            "ips_24h": ips24,
            "ips_all": sorted({a.get("ip") for a in mine})[:12],
        })
    return {"configured": True, "users": users, "admins": admins}


def _alerts(users: list[dict]) -> list[str]:
    """Dấu hiệu ĐÁNG XEM — không phải kết luận. Xem ghi chú giới hạn ở đầu khối."""
    out = []
    for u in users:
        n = len(u["ips_24h"])
        if n >= 3:
            out.append(f"{u['user']}: đăng nhập từ {n} IP khác nhau trong 24h "
                       f"({', '.join(u['ips_24h'][:4])}{'…' if n > 4 else ''}) — "
                       "có thể là 4G/VPN đổi IP, cũng có thể là tài khoản bị dùng chung.")
    return out


def _activity_payload(days: int = 14) -> dict:
    """Nhật ký job + token gộp theo user, trong `days` ngày gần nhất."""
    since = time.time() - days * 86400
    jobs = vp_usage.read_rows(vp_usage.HISTORY, since=since)
    use = vp_usage.read_rows(vp_usage.USAGE, since=since)

    tok_by_job: dict[str, dict] = {}
    for r in use:
        j = r.get("job") or ""
        d = tok_by_job.setdefault(j, {"in": 0, "out": 0, "calls": 0})
        d["in"] += int(r.get("in") or 0)
        d["out"] += int(r.get("out") or 0)
        d["calls"] += 1

    by_user: dict[str, dict] = {}
    for r in use:
        u = r.get("user") or vp_usage.ANON
        d = by_user.setdefault(u, {"user": u, "in": 0, "out": 0, "calls": 0, "jobs": 0})
        d["in"] += int(r.get("in") or 0)
        d["out"] += int(r.get("out") or 0)
        d["calls"] += 1
    for j in jobs:
        u = j.get("user") or vp_usage.ANON
        by_user.setdefault(u, {"user": u, "in": 0, "out": 0, "calls": 0, "jobs": 0})["jobs"] += 1

    rows = []
    for j in reversed(jobs):                          # mới nhất trước
        tok = tok_by_job.get(j.get("job") or "", {})
        rows.append({**j, "tok_in": tok.get("in", 0), "tok_out": tok.get("out", 0),
                     "tok_calls": tok.get("calls", 0)})
    return {"jobs": rows[:200], "by_user": sorted(by_user.values(), key=lambda x: -x["out"]),
            "days": days}


def _history_files() -> set[str]:
    """Whitelist: CHỈ các bản ký biến đã được ghi vào sổ mới cho xem (luật C2 — mọi
    endpoint đọc file phải whitelist, không nới theo đuôi file)."""
    out: set[str] = set()
    for j in vp_usage.read_rows(vp_usage.HISTORY):
        v = j.get("version")
        if v:
            out.add(v)
            out.add(str(Path(v).with_suffix("")) + ".outline.txt")
    return out


def _manage_users(b: dict, me: str) -> tuple[int, dict]:
    """Thêm/xoá/đổi mật khẩu. Không tự xoá/khoá chính mình (bài học ADMIN_USERS 2026-07-09)."""
    htfile = _htpasswd_file()
    if not htfile:
        return 422, {"error": "server chưa cấu hình HTPASSWD_FILE — chỉ chạy được trên VPS"}
    action = str(b.get("action") or "")
    user = str(b.get("user") or "").strip()
    if not _USER_RE.match(user):
        return 422, {"error": "tên đăng nhập 2-32 ký tự, chỉ chữ/số và . _ -"}
    existing = _existing_users(htfile)

    if action == "role":
        # Gán quyền (2026-07-16): chỉ admin gọi được (route POST /api/users đã gate).
        role = str(b.get("role") or "").strip().lower()
        if role not in (ROLE_CREATOR, ROLE_LEADER):
            return 422, {"error": "quyền chỉ có creator hoặc leader"}
        if user not in existing:
            return 422, {"error": "không có thành viên này"}
        if user in _admin_list():
            return 422, {"error": "quản trị viên đứng trên vai trò — không cần gán"}
        roles = _load_roles()
        if role == ROLE_LEADER:
            roles[user] = ROLE_LEADER
        else:
            roles.pop(user, None)            # creator = mặc định, không cần ghi
        _save_roles(roles)
        vi = "Leader (dùng tool + trang Quản lý)" if role == ROLE_LEADER else "Creator (chỉ dùng tool)"
        return 200, {"ok": True, "msg": f"{user} giờ là {vi}"}

    if action == "remove":
        if user == me:
            return 422, {"error": "không thể tự xoá tài khoản đang đăng nhập"}
        if user not in existing:
            return 422, {"error": "không có thành viên này"}
        if user in _admin_list():
            return 422, {"error": ("đây là quản trị viên — bỏ tên khỏi ADMIN_USERS "
                                   "trong tab Cài đặt trước, rồi mới xoá được")}
        _htpasswd_remove(htfile, user)
        roles = _load_roles()
        if user in roles:                     # dọn quyền của người đã xoá
            roles.pop(user)
            _save_roles(roles)
        return 200, {"ok": True, "msg": f"đã xoá {user} — mật khẩu cũ không vào được nữa"}

    pw = str(b.get("password") or "")
    if len(pw) < 8:
        return 422, {"error": "mật khẩu tối thiểu 8 ký tự"}
    if action == "add":
        if user in existing:
            return 422, {"error": "tên đăng nhập này đã có người dùng"}
        _htpasswd_add(htfile, user, pw)
        return 200, {"ok": True, "msg": f"đã tạo {user} — đưa mật khẩu cho họ qua kênh riêng"}
    if action == "reset":
        if user not in existing:
            return 422, {"error": "không có thành viên này"}
        _htpasswd_add(htfile, user, pw)          # htpasswd -bB ghi đè hash = đổi mật khẩu
        return 200, {"ok": True, "msg": (f"đã đổi mật khẩu {user}. Lưu ý: đây cũng là cách "
                                         "DUY NHẤT đá người lạ ra nếu tài khoản bị lộ.")}
    return 422, {"error": "action không hợp lệ"}

HOME = """<!doctype html>
<html lang="vi"><head><meta charset="utf-8"><link rel="stylesheet" href="/static/fonts/fonts.css"><script src="/static/theme.js"></script>
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Content Ultimate</title>
<style>
  :root{color-scheme:dark;--bg:#090c12;--panel:#121826;--raised:#182233;--border:#243149;--text:#e8edf4;
    --muted:#8b96a8;--accent:#4c8fe0;--accent-ink:#0b1220;
    --disp:'Inter',"Avenir Next","Segoe UI",system-ui,sans-serif}
    :root[data-theme="light"]{color-scheme:light;--bg:#F5F5F5;--panel:#FFFFFF;--raised:#FFFFFF;--border:#E0E0E0;
      --border-soft:#EAEAEA;--text:#16181C;--muted:#6C6C72;--faint:#9A9A9F;--accent:#2C6FC4;--accent-ink:#FFFFFF;
      --accent-soft:#E8F0FB;--link:#2C6FC4;--danger:#B14A3C;--danger-soft:rgba(177,74,60,.10);--ok:#4F7A3C;}
  *{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:15px/1.6 var(--disp)}
  .wrap{max-width:1100px;margin:0 auto;padding:60px 28px}
  .eyebrow{font-size:11px;letter-spacing:.16em;text-transform:uppercase;color:var(--muted)}
  h1{font-size:30px;margin:4px 0 6px}h1 em{color:var(--accent);font-style:normal}
  .flow{color:var(--muted);font-size:13px;margin-bottom:28px}
  .cards{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}
  @media (max-width:980px){.cards{grid-template-columns:1fr 1fr}}
  @media (max-width:640px){.cards{grid-template-columns:1fr}}
  a.card{display:block;background:var(--panel);border:1px solid var(--border);border-radius:12px;
    padding:20px 22px;color:inherit;text-decoration:none;transition:.12s}
  a.card:hover{border-color:var(--accent);background:var(--raised)}
  .card h2{margin:0 0 6px;font-size:17px}.card h2 span{color:var(--accent)}
  .card p{margin:0;font-size:12.5px;color:var(--muted)}
<!--WHOAMI_CSS-->
</style></head><body>
<!--WHOAMI-->
<div class="wrap">
  <div class="eyebrow">Bộ công cụ kịch bản YouTube</div>
  <h1>Content <em>Ultimate</em></h1>
  <p class="flow">① Outline Board (bằng chứng từ video → outline.txt) → ② Author Extract
    (bản thảo → hồ sơ giọng) → ③ Writing (outline × giọng → kịch bản).</p>
  <div class="cards">
    <a class="card" href="/outline"><h2><span>①</span> Outline Board</h2>
      <p>Dán URL các video cùng sóng → pipeline đo bằng chứng → tick chọn cluster → outline.txt tự xuất.</p></a>
    <a class="card" href="/author"><h2><span>②</span> Author Extract</h2>
      <p>Bản thảo tác giả → hồ sơ giọng văn (profile, clone-kit, dataset).</p></a>
    <a class="card" href="/write"><h2><span>③</span> Writing</h2>
      <p>Nạp outline từ board × tác giả từ library → kịch bản theo giọng, đo % giống.</p></a>
    <!--SETTINGS-->
  </div>
</div></body></html>"""

# Thẻ trang chủ theo VAI (phân quyền 2026-07-16): Quản lý cho leader+, Cài đặt chỉ admin.
MANAGE_CARD = """<a class="card" href="/manage"><h2><span>👥</span> Quản lý</h2>
      <p>Nhật ký làm việc từng người, token đã tiêu, dấu hiệu IP lạ — Leader trở lên.</p></a>"""
SETTINGS_CARD = """<a class="card" href="/settings"><h2><span>⚙</span> Cài đặt</h2>
      <p>API key · thành viên & phân quyền · cookies — chỉ quản trị viên.</p></a>"""

SETTINGS_HTML = """<!doctype html>
<html lang="vi"><head><meta charset="utf-8"><link rel="stylesheet" href="/static/fonts/fonts.css"><script src="/static/theme.js"></script>
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Content Ultimate — Cài đặt</title>
<style>
  :root{color-scheme:dark;--bg:#090c12;--panel:#121826;--raised:#182233;--border:#243149;--text:#e8edf4;
    --muted:#8b96a8;--faint:#6B7280;--accent:#4c8fe0;--accent-ink:#0b1220;--ok:#83A96F;
    --danger:#D97C6C;--mono:ui-monospace,"SF Mono",Menlo,Consolas,monospace;
    --disp:'Inter',"Avenir Next","Segoe UI",system-ui,sans-serif}
    :root[data-theme="light"]{color-scheme:light;--bg:#F5F5F5;--panel:#FFFFFF;--raised:#FFFFFF;--border:#E0E0E0;
      --border-soft:#EAEAEA;--text:#16181C;--muted:#6C6C72;--faint:#9A9A9F;--accent:#2C6FC4;--accent-ink:#FFFFFF;
      --accent-soft:#E8F0FB;--link:#2C6FC4;--danger:#B14A3C;--danger-soft:rgba(177,74,60,.10);--ok:#4F7A3C;}
  *{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:14px/1.55 var(--disp)}
  .wrap{max-width:1200px;margin:0 auto;padding:40px 28px 70px}
  /* 16:9 (2026-07-17): man rong xep 2 cot, man hep tu xep chong */
  .grid2{display:grid;grid-template-columns:1fr 1fr;gap:18px;align-items:start}
  @media (max-width:960px){.grid2{grid-template-columns:1fr}}
  .colh{margin:0 0 2px;font-size:20px}
  a.back{color:var(--muted);text-decoration:none;font-size:12.5px}
  h1{font-size:22px;margin:6px 0 2px}h1 em{color:var(--accent);font-style:normal}
  .sub{font-size:12.5px;color:var(--muted);margin:0 0 18px}
  .item{background:var(--panel);border:1px solid var(--border);border-radius:10px;padding:14px 16px;margin-bottom:10px}
  .item h3{margin:0;font-size:14px;display:flex;align-items:baseline;gap:10px}
  .st{font-family:var(--mono);font-size:11px;color:var(--ok)}
  .st.none{color:var(--faint)}
  .hint{font-size:11.5px;color:var(--faint);margin:2px 0 8px}
  .line{display:flex;gap:8px}
  input{flex:1;background:var(--raised);border:1px solid var(--border);border-radius:7px;
    color:var(--text);padding:8px 11px;font:12px var(--mono)}
  button{font:inherit;cursor:pointer;border:1px solid var(--border);background:var(--raised);
    color:var(--text);border-radius:7px;padding:8px 13px;font-size:12.5px;font-weight:600}
  button:hover{border-color:var(--faint)}
  button.off:hover{color:var(--danger);border-color:var(--danger)}
  .save{background:var(--accent);border-color:var(--accent);color:var(--accent-ink);
    font-weight:700;padding:10px 20px;margin-top:8px}
  .msg{font-size:12.5px;margin-top:10px;color:var(--ok)}
  .note{font-size:11.5px;color:var(--faint);margin-top:16px;line-height:1.6}
  .stabs{display:flex;gap:6px;margin:16px 0 0;border-bottom:1px solid var(--border)}
  .stab{padding:8px 14px;font-size:13px;font-weight:600;color:var(--muted);cursor:pointer;
    border:1px solid transparent;border-bottom:none;border-radius:8px 8px 0 0;margin-bottom:-1px}
  .stab.on{color:var(--text);background:var(--panel);border-color:var(--border)}
  a.stab{text-decoration:none;display:inline-block}
  .spane{display:none;padding-top:16px}.spane.on{display:block}
  /* Fallback THUAN CSS (2026-07-17): JS co chet thi bam tab van mo duoc pane qua
     anchor + :target — bai hoc "khong vao duoc tab thanh vien" khi JS hong phia client. */
  .spane:target{display:block}
  .spane:target~.spane.on:not(:target),body:has(.spane:target) .spane.on:not(:target){display:none}
  table{width:100%;border-collapse:collapse;font-size:12.5px}
  th{text-align:left;font-size:10.5px;letter-spacing:.09em;text-transform:uppercase;
    color:var(--faint);font-weight:600;padding:7px 9px;border-bottom:1px solid var(--border)}
  td{padding:8px 9px;border-bottom:1px solid var(--border);vertical-align:top}
  .mono2{font-family:var(--mono);font-size:11.5px}
  .tag{font-size:10px;font-weight:700;padding:1px 6px;border-radius:99px;
    border:1px solid var(--accent);color:var(--accent)}
  .row{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
  .card{background:var(--panel);border:1px solid var(--border);border-radius:10px;padding:14px 16px;margin-bottom:12px}
  .pri{background:var(--accent);border-color:var(--accent);color:var(--accent-ink);font-weight:700}
  select.role{background:var(--raised);border:1px solid var(--border);border-radius:6px;
    color:var(--text);padding:5px 7px;font:12px var(--disp)}
  .empty{color:var(--faint);font-size:12.5px;padding:14px 0}
<!--WHOAMI_CSS-->
</style></head><body>
<!--WHOAMI-->
<div class="wrap">
  <a class="back" href="/">← Trang chủ</a>
  <h1>⚙ <em>Cài đặt</em></h1>
  <div class="stabs">
    <a class="stab on" data-sp="keys" href="#sp_keys">API key &amp; Cookies</a>
    <a class="stab" data-sp="members" href="#sp_members">Thành viên &amp; quyền</a>
  </div>
  <div class="spane on" id="sp_keys">
  <div class="grid2">
  <div>
  <p class="sub">Key lưu vào kho <span style="font-family:var(--mono)">.env</span> trên server.
    Dropdown model của Writer/Extractor tự cập nhật theo key có sẵn.</p>
  <div id="list"></div>
  <button class="save" id="saveBtn">Lưu thay đổi</button>
  <div class="msg" id="msg"></div>
  </div>
  <div>
  <h1 class="colh">🍪 <em>Cookies</em> YouTube</h1>
  <p class="sub">Chống YouTube chặn IP server (bước S1 board Outline báo bot-check).
    Cài extension <b>"Get cookies.txt LOCALLY"</b> → mở youtube.com → Export →
    dán NGUYÊN VĂN vào đây. <b>Mẹo sống lâu:</b> đăng nhập YouTube trong cửa sổ
    ẩn danh → xuất cookies → đóng ngay cửa sổ ẩn danh (cookies không bị xoay vòng).
    Mục này MỌI thành viên đều dùng được (cả trên board Outline) — ai bị chặn tự dán,
    không phải chờ quản trị viên.</p>
  <div class="item">
    <h3>Trạng thái <span class="st none" id="ckSt">đang tải…</span></h3>
    <textarea id="ckTxt" placeholder="# Netscape HTTP Cookie File…  (dán nguyên văn file cookies.txt)"
      style="width:100%;min-height:110px;background:var(--raised);border:1px solid var(--border);
             border-radius:7px;color:var(--text);padding:9px 11px;font:11px var(--mono);resize:vertical"></textarea>
    <div class="line" style="margin-top:8px">
      <button id="ckSave">Lưu cookies</button>
      <button class="off" id="ckDel">Xóa cookies</button>
    </div>
  </div>

  </div>
  </div><!-- /grid2 -->
  </div><!-- /sp_keys -->

  <div class="spane" id="sp_members">
    <div class="grid2">
    <div class="card" style="margin-bottom:0">
      <div class="row" style="justify-content:space-between">
        <div>
          <b style="font-size:13.5px">Khóa mời</b>
          <div style="color:var(--faint);font-size:11.5px;margin-top:2px">
            Dùng 1 lần · hạn 7 ngày · họ tự đặt tên đăng nhập + mật khẩu. Người mới vào là <b>Creator</b>.</div>
        </div>
        <button class="pri" id="invBtn" style="width:auto">＋ Tạo khóa mời</button>
      </div>
      <div id="invList" style="margin-top:10px"></div>
    </div>
    <div class="card" style="margin-bottom:0">
      <div class="row">
        <div style="flex:1 0 100%;margin-bottom:2px">
          <b style="font-size:13.5px">Tạo thẳng tài khoản</b>
          <div style="color:var(--faint);font-size:11.5px;margin-top:2px">
            Khi cần vào ngay — anh đặt mật khẩu hộ rồi tự đưa qua kênh riêng.</div>
        </div>
        <input id="nu" placeholder="tên đăng nhập mới" style="flex:0 0 180px">
        <input id="np" type="password" placeholder="mật khẩu (≥ 8 ký tự)" style="flex:0 0 180px">
        <button id="addBtn" class="pri" style="width:auto">＋ Thêm</button>
      </div>
    </div>
    </div><!-- /grid2 -->
    <div style="height:16px"></div>
    <table><thead><tr><th>Thành viên</th><th>Quyền</th><th>Tham gia</th>
      <th>Hoạt động gần nhất</th><th style="text-align:right">Thao tác</th></tr></thead>
      <tbody id="utb"></tbody></table>
    <p class="note"><b>Creator</b> = dùng 3 công cụ (Outline Board · Author Extract · Writing).
      <b>Leader</b> = Creator + trang 👥 Quản lý (nhật ký, token, bảo mật).
      Quản trị viên (ADMIN_USERS) đứng trên vai trò — thêm trang Cài đặt này.
      Đổi quyền có hiệu lực NGAY (không cần đăng nhập lại). Xoá thành viên = gỡ khỏi
      <span class="mono2">.htpasswd</span>; quản trị viên phải gỡ khỏi ADMIN_USERS trước khi xoá.</p>
    <div class="msg" id="msg2"></div>
  </div><!-- /sp_members -->
</div>
<script>
window.onerror=function(m,src,l){try{var d=document.createElement('div');
d.style.cssText='background:#7a2018;color:#ffd7d0;padding:10px 14px;font:12px monospace;white-space:pre-wrap';
d.textContent='LỖI JS (chụp màn hình này gửi Claude): '+m+' @ dòng '+l;
document.body.prepend(d);}catch(e){}};
</script>
<script>
'use strict';
const $=s=>document.querySelector(s);
async function api(path, body){
  const r = await fetch(path,{method:body?'POST':'GET',headers:{'Content-Type':'application/json'},
                             body:body?JSON.stringify(body):undefined});
  if(r.status===403){document.body.innerHTML='<div class="wrap"><h1>403</h1><p>Chỉ quản trị viên.</p></div>';throw new Error('403');}
  return r.json();
}
function esc(s){return (s||'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));}
function render(items){
  $('#list').innerHTML = items.map(it=>`
    <div class="item">
      <h3>${esc(it.label)}
        <span class="st ${it.set?'':'none'}">${it.set?('đã có key'+(it.tail?' ····'+esc(it.tail):'')):'chưa có'}</span></h3>
      <div class="hint">${esc(it.hint)}</div>
      <div class="line">
        <input id="in_${it.key}" ${it.key==='ADMIN_USERS'?'':'type="password"'}
               value="${esc(it.value)}" placeholder="${it.key==='ADMIN_USERS'?'vd: thanh, editor2':'dán key mới — để trống là giữ nguyên'}">
        ${it.set&&it.key!=='ADMIN_USERS'?`<button class="off" data-k="${it.key}">Tắt</button>`:''}
      </div>
    </div>`).join('');
  document.querySelectorAll('.off').forEach(b=>b.addEventListener('click',async()=>{
    if(!confirm('Tắt key này? (dòng trong .env bị comment lại)'))return;
    const d = await api('/api/settings',{updates:{[b.dataset.k]:''}});
    render(d.settings); $('#msg').textContent='Đã tắt.';
  }));
}
$('#saveBtn').addEventListener('click',async()=>{
  const updates={};
  document.querySelectorAll('[id^=in_]').forEach(i=>{
    const k=i.id.slice(3), v=i.value.trim();
    if(k==='ADMIN_USERS'){ if(v!==(i.dataset.orig||'')) updates[k]=v; }
    else if(v) updates[k]=v;
  });
  if(!Object.keys(updates).length){$('#msg').textContent='Không có gì thay đổi.';return;}
  const d = await api('/api/settings',{updates});
  render(d.settings);
  $('#msg').textContent='Đã lưu vào .env — key mới dùng được ngay.';
});
(async()=>{
  const d = await api('/api/settings');
  render(d.settings);
  const au=d.settings.find(x=>x.key==='ADMIN_USERS');
  const el=$('#in_ADMIN_USERS'); if(el&&au){el.dataset.orig=au.value;}
})();

// Khóa mời đã chuyển sang tab Quản lý (/manage) — mọi việc về người ở chung một chỗ.
function fmtT(ts){return new Date(ts*1000).toLocaleString('vi-VN',{hour12:false});}

// ── Cookies YouTube ──
function renderCk(d){
  $('#ckSt').textContent = d.exists ? `đang có ${d.n_lines} cookie · cập nhật ${fmtT(d.mtime)}` : 'chưa có';
  $('#ckSt').className = 'st' + (d.exists ? '' : ' none');
}
$('#ckSave').addEventListener('click', async()=>{
  const v = $('#ckTxt').value.trim();
  if(!v){ $('#msg').textContent='Ô cookies đang trống — dán nội dung rồi bấm Lưu.'; return; }
  const r = await fetch('/api/cookies',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({content:v})});
  const d = await r.json();
  if(d.error){ $('#msg').textContent = d.error; return; }
  $('#ckTxt').value=''; renderCk(d);
  $('#msg').textContent = d.notice || 'Đã lưu cookies — mở lại run bị lỗi và bấm ↻ Tiếp tục.';
});
$('#ckDel').addEventListener('click', async()=>{
  if(!confirm('Xóa cookies trên server? (các run mới sẽ bị YouTube chặn cho tới khi dán lại)'))return;
  const r = await fetch('/api/cookies',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({action:'delete'})});
  renderCk(await r.json()); $('#msg').textContent='Đã xóa cookies.';
});
(async()=>{try{renderCk(await api('/api/cookies'));}catch(e){}})();

// ── Tab Cài đặt ── (JS chỉ là lớp phủ; không có JS thì anchor+:target vẫn chạy)
function openTab(sp){
  document.querySelectorAll('.stab').forEach(x=>x.classList.toggle('on',x.dataset.sp===sp));
  document.querySelectorAll('.spane').forEach(pn=>pn.classList.toggle('on',pn.id==='sp_'+sp));
}
function syncTabFromHash(){
  const h=location.hash;
  if(h==='#sp_members'||h==='#members') openTab('members');
  else if(h==='#sp_keys'||h==='') openTab('keys');
}
window.addEventListener('hashchange',syncTabFromHash);
syncTabFromHash();

// ── Thành viên & quyền (chuyển từ Quản lý sang 2026-07-16, thêm PHÂN QUYỀN) ──
function say2(s,err){const m=document.querySelector('#msg2');m.textContent=s;
  m.style.color=err?'var(--danger)':'var(--ok)';}
function ago2(ts){if(!ts)return '—';const s=(Date.now()/1000)-ts;
  if(s<3600)return Math.round(s/60)+' phút trước';
  if(s<86400)return Math.round(s/3600)+' giờ trước';
  return Math.round(s/86400)+' ngày trước';}
function renderUsers(d){
  const tb=document.querySelector('#utb');
  if(!d.configured){
    tb.innerHTML='<tr><td colspan="5" class="empty">Chưa cấu hình HTPASSWD_FILE — quản lý thành viên chỉ chạy trên VPS.</td></tr>';
    document.querySelector('#addBtn').disabled=true; return;
  }
  tb.innerHTML=(d.users||[]).map(u=>{
    // Quyền: admin đứng trên vai trò; người thường có dropdown creator/leader (đổi = lưu ngay)
    const roleCell=u.admin?'<span class="tag">quản trị</span>'
      :`<select class="role" data-ru="${esc(u.user)}">
          <option value="creator"${u.role!=='leader'?' selected':''}>Creator</option>
          <option value="leader"${u.role==='leader'?' selected':''}>Leader</option></select>`;
    return `<tr>
      <td><b>${esc(u.user)}</b></td>
      <td>${roleCell}</td>
      <td class="mono2">${u.joined?fmtT(u.joined):'—'}</td>
      <td>${ago2(u.last_seen)}</td>
      <td style="text-align:right"><div class="row" style="justify-content:flex-end">
        <button data-rs="${esc(u.user)}">Đổi mật khẩu</button>
        <button class="off" data-rm="${esc(u.user)}">Xoá</button>
      </div></td></tr>`;
  }).join('')||'<tr><td colspan="5" class="empty">Chưa có thành viên nào.</td></tr>';

  document.querySelectorAll('select.role').forEach(s=>s.addEventListener('change',async()=>{
    const d2=await api('/api/users',{action:'role',user:s.dataset.ru,role:s.value});
    if(d2.error){say2(d2.error,true);loadUsers();return;}
    say2(d2.msg); loadUsers();
  }));
  document.querySelectorAll('[data-rm]').forEach(b=>b.addEventListener('click',async()=>{
    const u=b.dataset.rm;
    if(!confirm('Xoá thành viên "'+u+'"?\\n\\nMật khẩu của họ hết vào được ngay. Kịch bản họ đã làm vẫn giữ nguyên.'))return;
    const d2=await api('/api/users',{action:'remove',user:u});
    if(d2.error){say2(d2.error,true);return;} say2(d2.msg); loadUsers();
  }));
  document.querySelectorAll('[data-rs]').forEach(b=>b.addEventListener('click',async()=>{
    const u=b.dataset.rs;
    const pw=prompt('Mật khẩu MỚI cho "'+u+'" (tối thiểu 8 ký tự).\\n\\nTự đưa cho họ qua kênh riêng — tool không gửi email.');
    if(!pw)return;
    const d2=await api('/api/users',{action:'reset',user:u,password:pw});
    if(d2.error){say2(d2.error,true);return;} say2(d2.msg); loadUsers();
  }));
}
document.querySelector('#addBtn').addEventListener('click',async()=>{
  const u=document.querySelector('#nu').value.trim(), pw=document.querySelector('#np').value;
  if(!u||!pw){say2('Điền tên đăng nhập và mật khẩu.',true);return;}
  const d2=await api('/api/users',{action:'add',user:u,password:pw});
  if(d2.error){say2(d2.error,true);return;}
  document.querySelector('#nu').value='';document.querySelector('#np').value='';
  say2(d2.msg); loadUsers();
});
async function loadUsers(){renderUsers(await api('/api/users'));}
function renderInv(d){
  const el=document.querySelector('#invList');
  if(!d.configured){
    el.innerHTML='<div class="empty">Chưa cấu hình HTPASSWD_FILE — mời thành viên chỉ chạy trên VPS.</div>';
    document.querySelector('#invBtn').disabled=true; return;
  }
  const rows=(d.invites||[]).slice().reverse().map(i=>{
    const link=location.origin+'/invite?k='+i.token;
    let st, act='';
    if(i.used_by) st=`<span class="st">đã dùng — ${esc(i.used_by)} · ${fmtT(i.used_at)}</span>`;
    else if(i.expires<Date.now()/1000){ st='<span class="st none">hết hạn</span>';
      act=`<button class="off inv-rv" data-t="${esc(i.token)}" style="width:auto">Xoá</button>`; }
    else { st=`<span class="st none">chờ dùng — hạn ${fmtT(i.expires)}</span>`;
      act=`<button class="inv-cp" data-l="${esc(link)}" style="width:auto">Copy link</button>
           <button class="off inv-rv" data-t="${esc(i.token)}" style="width:auto">Thu hồi</button>`; }
    return `<div style="border-top:1px solid var(--border);padding:9px 0">
      <div class="row" style="justify-content:space-between">
        <div><span class="mono2">${esc(i.token)}</span> ${st}
          ${i.used_by?'':`<div class="mono2" style="color:var(--faint);word-break:break-all;margin-top:3px">${esc(link)}</div>`}</div>
        <div class="row">${act}</div>
      </div></div>`;
  }).join('');
  el.innerHTML=rows||'<div class="empty">Chưa có khóa mời nào.</div>';
  document.querySelectorAll('.inv-cp').forEach(b=>b.addEventListener('click',async()=>{
    // navigator.clipboard chỉ có trên HTTPS/localhost — qua http://<IP LAN>:8000 phải
    // fallback execCommand (cùng bệnh nút Copy board Outline, 06/08/2026).
    try{
      if(navigator.clipboard&&navigator.clipboard.writeText)await navigator.clipboard.writeText(b.dataset.l);
      else{const ta=document.createElement('textarea');ta.value=b.dataset.l;
        ta.style.cssText='position:fixed;top:0;left:0;opacity:0';
        document.body.appendChild(ta);ta.focus();ta.select();
        const ok=document.execCommand('copy');ta.remove();if(!ok)throw new Error('copy');}
      say2('Đã copy link mời — gửi cho thành viên qua chat.');}
    catch{say2('Không copy tự động được — bôi đen link và copy tay.',true);}
  }));
  document.querySelectorAll('.inv-rv').forEach(b=>b.addEventListener('click',async()=>{
    renderInv(await api('/api/invites',{action:'revoke',token:b.dataset.t}));
  }));
}
document.querySelector('#invBtn').addEventListener('click',async()=>{
  renderInv(await api('/api/invites',{action:'create'}));
  say2('Đã tạo khóa mời — bấm Copy link rồi gửi cho thành viên.');
});
(async()=>{try{await loadUsers();renderInv(await api('/api/invites'));}catch(e){}})();
</script></body></html>"""


MANAGE_HTML = """<!doctype html>
<html lang="vi"><head><meta charset="utf-8"><link rel="stylesheet" href="/static/fonts/fonts.css"><script src="/static/theme.js"></script>
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Content Ultimate — Quản lý</title>
<style>
  :root{color-scheme:dark;--bg:#090c12;--panel:#121826;--raised:#182233;--border:#243149;--text:#e8edf4;
    --muted:#8b96a8;--faint:#6B7280;--accent:#4c8fe0;--accent-ink:#0b1220;--ok:#83A96F;
    --warn:#D9A441;--danger:#D97C6C;--mono:ui-monospace,"SF Mono",Menlo,Consolas,monospace;
    --disp:'Inter',"Avenir Next","Segoe UI",system-ui,sans-serif}
    :root[data-theme="light"]{color-scheme:light;--bg:#F5F5F5;--panel:#FFFFFF;--raised:#FFFFFF;--border:#E0E0E0;
      --border-soft:#EAEAEA;--text:#16181C;--muted:#6C6C72;--faint:#9A9A9F;--accent:#2C6FC4;--accent-ink:#FFFFFF;
      --accent-soft:#E8F0FB;--link:#2C6FC4;--danger:#B14A3C;--danger-soft:rgba(177,74,60,.10);--ok:#4F7A3C;}
  *{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:14px/1.55 var(--disp)}
  .wrap{max-width:1280px;margin:0 auto;padding:40px 28px 70px}
  a.back{color:var(--muted);text-decoration:none;font-size:12.5px}
  h1{font-size:22px;margin:6px 0 2px}h1 em{color:var(--accent);font-style:normal}
  h2{font-size:15px;margin:32px 0 4px}
  .sub{font-size:12.5px;color:var(--muted);margin:0 0 14px}
  .tabs{display:flex;gap:6px;margin:18px 0 4px;border-bottom:1px solid var(--border)}
  .tab{padding:8px 14px;font-size:13px;font-weight:600;color:var(--muted);cursor:pointer;
    border:1px solid transparent;border-bottom:none;border-radius:8px 8px 0 0;margin-bottom:-1px}
  .tab.on{color:var(--text);background:var(--panel);border-color:var(--border)}
  .pane{display:none;padding-top:18px}.pane.on{display:block}
  table{width:100%;border-collapse:collapse;font-size:12.5px}
  th{text-align:left;font-size:10.5px;letter-spacing:.09em;text-transform:uppercase;
    color:var(--faint);font-weight:600;padding:7px 9px;border-bottom:1px solid var(--border)}
  td{padding:8px 9px;border-bottom:1px solid var(--border);vertical-align:top}
  tr:hover td{background:var(--panel)}
  .mono{font-family:var(--mono);font-size:11.5px}
  .tag{font-size:10px;font-weight:700;padding:1px 6px;border-radius:99px;
    border:1px solid var(--border);color:var(--muted)}
  .tag.admin{color:var(--accent);border-color:var(--accent)}
  .tag.done{color:var(--ok);border-color:color-mix(in srgb,var(--ok) 45%,var(--border))}
  .tag.error{color:var(--danger);border-color:color-mix(in srgb,var(--danger) 45%,var(--border))}
  .tag.cancelled{color:var(--warn);border-color:color-mix(in srgb,var(--warn) 45%,var(--border))}
  button{font:inherit;cursor:pointer;border:1px solid var(--border);background:var(--raised);
    color:var(--text);border-radius:7px;padding:6px 11px;font-size:12px;font-weight:600}
  button:hover{border-color:var(--faint)}
  button.off:hover{color:var(--danger);border-color:var(--danger)}
  button.pri{background:var(--accent);border-color:var(--accent);color:var(--accent-ink);font-weight:700}
  input{background:var(--raised);border:1px solid var(--border);border-radius:7px;
    color:var(--text);padding:8px 11px;font:12px var(--disp)}
  .row{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
  .msg{font-size:12.5px;margin-top:12px;min-height:18px;color:var(--ok)}
  .msg.err{color:var(--danger)}
  .note{font-size:11.5px;color:var(--faint);line-height:1.6;margin-top:14px;
    border-left:2px solid var(--border);padding-left:12px}
  .alert{background:var(--panel);border:1px solid color-mix(in srgb,var(--warn) 40%,var(--border));
    border-left:3px solid var(--warn);border-radius:8px;padding:11px 13px;margin-bottom:8px;font-size:12.5px}
  .empty{color:var(--faint);font-size:12.5px;padding:18px 0}
  .card{background:var(--panel);border:1px solid var(--border);border-radius:10px;padding:14px 16px;margin-bottom:12px}
<!--WHOAMI_CSS-->
</style></head><body>
<!--WHOAMI-->
<div class="wrap">
  <a class="back" href="/">← Trang chủ</a>
  <h1>👥 <em>Quản lý</em></h1>
  <p class="sub">Nhật ký làm việc từng người · token đã tiêu · dấu hiệu bất thường.
    Thành viên &amp; phân quyền →
    <a href="/settings#sp_members" style="color:var(--accent)">Cài đặt · Thành viên &amp; quyền</a>
    (chỉ quản trị viên).</p>

  <div class="tabs">
    <div class="tab on" data-p="h">Nhật ký làm việc</div>
    <div class="tab" data-p="t">Token</div>
    <div class="tab" data-p="s">Bảo mật</div>
  </div>

  <div class="pane on" id="p_h">
    <p class="sub">Mỗi lần bấm Viết/Extract là một dòng. Bấm <b>Bản kịch bản</b> để đọc đúng
      bản người đó đã tạo lúc đó — <b>chỉ có từ 15/07/2026</b>, trước đó tool ghi đè nên không còn.</p>
    <table><thead><tr><th>Lúc</th><th>Ai</th><th>Việc</th><th>Nội dung</th>
      <th style="text-align:right">Ký tự</th><th style="text-align:right">Token</th>
      <th>Kết quả</th><th></th></tr></thead><tbody id="htb"></tbody></table>
  </div>

  <div class="pane" id="p_t">
    <p class="sub">Token đo từ chính response của provider (không ước lượng). Gộp 14 ngày gần nhất.</p>
    <table><thead><tr><th>Thành viên</th><th style="text-align:right">Job</th>
      <th style="text-align:right">Lượt gọi LLM</th><th style="text-align:right">Token vào</th>
      <th style="text-align:right">Token ra</th></tr></thead><tbody id="ttb"></tbody></table>
    <div class="note">Không quy ra tiền: giá mỗi model do provider đổi theo thời điểm, quy đổi ở
      đây sẽ là con số bịa. Token là thứ đo được thật — nhân với bảng giá hiện hành của z.ai/Anthropic
      khi cần đối soát hóa đơn.</div>
  </div>

  <div class="pane" id="p_s">
    <div id="alerts"></div>
    <div class="note" style="border-left-color:var(--warn)">
      <b>Đọc kỹ trước khi tin mục này.</b> Tool đang dùng nginx basic auth — <b>không có phiên
      đăng nhập</b>. Hệ quả thật:<br>
      • Không "đăng xuất thiết bị lạ" được. Nếu tài khoản bị lộ, cách <b>duy nhất</b> chặn là
      <b>đổi mật khẩu</b> (người thật cũng phải nhận mật khẩu mới).<br>
      • Nhiều IP <b>không chứng minh</b> bị lộ: 4G, VPN, đổi mạng đều làm IP nhảy. Đây là
      <b>dấu hiệu để người thật xem</b>, tool không tự khoá ai.<br>
      • Chỉ ghi được từ lúc bật tính năng này (15/07/2026), không có dữ liệu quá khứ.<br>
      Muốn chặt hơn (phiên, thu hồi, 2FA) phải đưa auth vào app — việc riêng, chưa làm.
    </div>
  </div>

  <div class="msg" id="msg"></div>
</div>
<script>
'use strict';
const $=s=>document.querySelector(s);
function esc(s){return String(s==null?'':s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));}
function fmtT(ts){return ts?new Date(ts*1000).toLocaleString('vi-VN',{hour12:false}):'—';}
function fmtN(n){return (n||0).toLocaleString('vi-VN');}
function ago(ts){
  if(!ts) return '—';
  const s=(Date.now()/1000)-ts;
  if(s<3600) return Math.round(s/60)+' phút trước';
  if(s<86400) return Math.round(s/3600)+' giờ trước';
  return Math.round(s/86400)+' ngày trước';
}
async function api(path, body){
  const r=await fetch(path,{method:body?'POST':'GET',headers:{'Content-Type':'application/json'},
                           body:body?JSON.stringify(body):undefined});
  if(r.status===403){document.body.innerHTML='<div class="wrap"><h1>403</h1><p>Chỉ quản trị viên.</p></div>';throw new Error('403');}
  return r.json();
}
function say(t,err){const m=$('#msg');m.textContent=t;m.className='msg'+(err?' err':'');}

document.querySelectorAll('.tab').forEach(t=>t.addEventListener('click',()=>{
  document.querySelectorAll('.tab').forEach(x=>x.classList.toggle('on',x===t));
  document.querySelectorAll('.pane').forEach(p=>p.classList.toggle('on',p.id==='p_'+t.dataset.p));
}));

// ── Bảo mật cần danh sách user (alerts) — chỉ ĐỌC; sửa thành viên ở Cài đặt ──
async function loadAlerts(){renderAlerts(await api('/api/users'));}

// ── Bảo mật ──
function renderAlerts(d){
  const a=d.alerts||[];
  $('#alerts').innerHTML=a.length
    ? a.map(x=>`<div class="alert">⚠ ${esc(x)}</div>`).join('')
    : '<div class="empty">Chưa thấy dấu hiệu nào đáng xem trong 24h qua.</div>';
}

// ── Nhật ký + Token ──
const KIND={writer:'Viết kịch bản',extractor:'Trích giọng văn'};
function renderAct(d){
  $('#htb').innerHTML=(d.jobs||[]).map(j=>{
    const what=j.kind==='writer'?(j.title||'—'):(j.author||'—');
    const tok=(j.tok_in||j.tok_out)?fmtN(j.tok_in+j.tok_out):'—';
    const btn=j.version?`<div class="row" style="justify-content:flex-end;gap:5px">
        <button data-v="${esc(j.version)}" title="Đọc ngay trong tab mới">Xem</button>
        <button data-dl="${esc(j.version)}" title="Tải file .md kịch bản về máy">⤓ Kịch bản</button>
        <button data-ol="${esc(j.version)}" title="Tải outline đã dùng để viết bản này">⤓ Outline</button>
      </div>`:'';
    return `<tr>
      <td class="mono">${fmtT(j.ts)}</td>
      <td><b>${esc(j.user)}</b></td>
      <td>${esc(KIND[j.kind]||j.kind)}</td>
      <td>${esc(what)}</td>
      <td style="text-align:right">${j.chars?fmtN(j.chars):'—'}</td>
      <td style="text-align:right" class="mono">${tok}</td>
      <td><span class="tag ${esc(j.status)}">${esc(j.status)}</span>
          ${j.secs?`<span style="color:var(--faint)"> ${j.secs}s</span>`:''}</td>
      <td style="text-align:right">${btn}</td></tr>`;
  }).join('')||'<tr><td colspan="8" class="empty">Chưa có job nào được ghi. Nhật ký bắt đầu từ lần chạy tiếp theo.</td></tr>';

  const hf=(p,dl)=>'/api/history-file?path='+encodeURIComponent(p)+(dl?'&dl=1':'');
  // outline cua mot ban nam canh no: <...>.md -> <...>.outline.txt (server whitelist ca hai)
  const outlineOf=p=>p.replace(/\\.md$/,'')+'.outline.txt';
  document.querySelectorAll('[data-v]').forEach(b=>b.addEventListener('click',()=>{
    window.open(hf(b.dataset.v),'_blank');
  }));
  document.querySelectorAll('[data-dl]').forEach(b=>b.addEventListener('click',()=>{
    location.href=hf(b.dataset.dl,true);
  }));
  document.querySelectorAll('[data-ol]').forEach(b=>b.addEventListener('click',()=>{
    location.href=hf(outlineOf(b.dataset.ol),true);
  }));

  $('#ttb').innerHTML=(d.by_user||[]).map(u=>`<tr>
      <td><b>${esc(u.user)}</b></td>
      <td style="text-align:right">${fmtN(u.jobs)}</td>
      <td style="text-align:right">${fmtN(u.calls)}</td>
      <td style="text-align:right" class="mono">${fmtN(u.in)}</td>
      <td style="text-align:right" class="mono"><b>${fmtN(u.out)}</b></td></tr>`
  ).join('')||'<tr><td colspan="5" class="empty">Chưa có token nào được ghi.</td></tr>';
}

(async()=>{
  try{ await loadAlerts(); renderAct(await api('/api/activity')); }
  catch(e){ if(e.message!=='403') say('Không tải được: '+e.message,true); }
})();
</script></body></html>"""


INVITE_HTML = """<!doctype html>
<html lang="vi"><head><meta charset="utf-8"><link rel="stylesheet" href="/static/fonts/fonts.css"><script src="/static/theme.js"></script>
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Content Ultimate — Nhận lời mời</title>
<style>
  :root{color-scheme:dark;--bg:#090c12;--panel:#121826;--raised:#182233;--border:#243149;--text:#e8edf4;
    --muted:#8b96a8;--faint:#6B7280;--accent:#4c8fe0;--accent-ink:#0b1220;--ok:#83A96F;
    --danger:#D97C6C;--disp:'Inter',"Avenir Next","Segoe UI",system-ui,sans-serif}
    :root[data-theme="light"]{color-scheme:light;--bg:#F5F5F5;--panel:#FFFFFF;--raised:#FFFFFF;--border:#E0E0E0;
      --border-soft:#EAEAEA;--text:#16181C;--muted:#6C6C72;--faint:#9A9A9F;--accent:#2C6FC4;--accent-ink:#FFFFFF;
      --accent-soft:#E8F0FB;--link:#2C6FC4;--danger:#B14A3C;--danger-soft:rgba(177,74,60,.10);--ok:#4F7A3C;}
  *{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:14px/1.55 var(--disp)}
  .wrap{max-width:420px;margin:0 auto;padding:60px 22px}
  .eyebrow{font-size:10.5px;letter-spacing:.15em;text-transform:uppercase;color:var(--muted)}
  h1{font-size:22px;margin:4px 0 4px}h1 em{color:var(--accent);font-style:normal}
  .sub{font-size:12.5px;color:var(--muted);margin:0 0 18px}
  .card{background:var(--panel);border:1px solid var(--border);border-radius:12px;padding:20px}
  label{display:block;font-size:10.5px;letter-spacing:.1em;text-transform:uppercase;color:var(--faint);margin:12px 0 4px}
  input{width:100%;background:var(--raised);border:1px solid var(--border);border-radius:7px;
    color:var(--text);padding:9px 11px;font:13px var(--disp)}
  button{width:100%;margin-top:16px;background:var(--accent);border:none;color:var(--accent-ink);
    font:inherit;font-weight:700;border-radius:8px;padding:11px;cursor:pointer}
  button:disabled{opacity:.5}
  .msg{font-size:12.5px;margin-top:12px}.msg.err{color:var(--danger)}.msg.ok{color:var(--ok)}
  a{color:var(--accent)}
</style></head><body><div class="wrap">
  <div class="eyebrow">Content Ultimate · Outliery</div>
  <h1>Nhận <em>lời mời</em></h1>
  <p class="sub">Bạn được mời vào bộ công cụ kịch bản của team. Tự chọn tên đăng nhập và mật khẩu.</p>
  <div class="card">
    <label for="u">Tên đăng nhập (chữ/số, không dấu)</label>
    <input id="u" autocomplete="username" placeholder="vd: lan, minh.editor">
    <label for="p1">Mật khẩu (tối thiểu 8 ký tự)</label>
    <input id="p1" type="password" autocomplete="new-password">
    <label for="p2">Nhập lại mật khẩu</label>
    <input id="p2" type="password" autocomplete="new-password">
    <button id="go">Tạo tài khoản</button>
    <div class="msg" id="msg"></div>
  </div>
</div>
<script>
'use strict';
const $=s=>document.querySelector(s);
const k = new URLSearchParams(location.search).get('k') || '';
if(!k){ $('#msg').textContent='Thiếu khóa mời trong đường link — dùng đúng link được gửi.'; $('#msg').className='msg err'; $('#go').disabled=true; }
$('#go').addEventListener('click', async ()=>{
  const u=$('#u').value.trim(), p1=$('#p1').value, p2=$('#p2').value, m=$('#msg');
  if(p1!==p2){ m.textContent='Hai lần nhập mật khẩu không khớp.'; m.className='msg err'; return; }
  $('#go').disabled=true;
  try{
    const r = await fetch('/invite/api/accept',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({k, user:u, password:p1})});
    const d = await r.json();
    if(d.ok){ m.innerHTML='✓ Tài khoản đã tạo. <a href="/">Bấm vào đây để đăng nhập</a> bằng tên + mật khẩu vừa đặt.'; m.className='msg ok'; }
    else { m.textContent=d.error||'Lỗi không rõ.'; m.className='msg err'; $('#go').disabled=false; }
  }catch(e){ m.textContent='Không gọi được server: '+e.message; m.className='msg err'; $('#go').disabled=false; }
});
</script></body></html>"""


def _suggest_outline(b: dict, rd: Path) -> tuple[int, dict]:
    """Nút ✨ Gợi ý outline (LLM). Đọc cluster+gaps của run trong request, gọi provider
    người dùng chọn, trả picks (gợi ý sửa được) — không tự lưu, không chấm điểm."""
    from oe import suggest
    from voiceprofile.llm import llm_text, provider_config

    if not rd or not (rd / "clusters.json").exists():
        return 400, {"error": "chưa có cluster — chạy pipeline outline trước"}
    clusters = oe_common.read_json(rd / "clusters.json")
    gaps = oe_common.read_json(rd / "gaps.json") if (rd / "gaps.json").exists() else []
    name, _, model = str(b.get("provider") or "").partition(":")
    try:
        cfg = provider_config(name or "glm")
        if model:
            cfg = {**cfg, "model": model}
        picks = suggest.suggest_outline(
            clusters, gaps, str(b.get("title") or ""),
            lambda s, u: llm_text(s, u, cfg, max_tokens=8000),
            n_chapters=int(b.get("chapters") or 7),
            # V3: ký tự + AVD (run_meta.json, nhập ở màn tạo run) → Python xếp vai
            total_chars=int(b.get("total_chars") or 0),
            avd_phut=_avd_cua_run(rd))
    except (RuntimeError, ValueError) as e:
        return 200, {"error": str(e)}
    return 200, {"picks": picks}


def _avd_cua_run(rd: Path) -> float | None:
    p = rd / "run_meta.json"
    if not p.exists():
        return None
    try:
        avd = oe_common.read_json(p).get("avd_phut")
        return float(avd) if avd else None
    except (ValueError, TypeError, OSError):
        return None


def _llm_cfg(b: dict) -> dict:
    from voiceprofile.llm import provider_config
    name, _, model = str(b.get("provider") or "").partition(":")
    cfg = provider_config(name or "glm")
    return {**cfg, "model": model} if model else cfg


def _sinh_titles(b: dict, rd: Path) -> tuple[int, dict]:
    """Nút 'Sinh title' (V3): title GỐC của sóng (0 LLM) + 5 title máy sinh, MỖI title
    kèm điểm vật liệu (Python đo, van chống bịa verbatim — oe/titles.py)."""
    from oe import titles as oe_titles
    from voiceprofile.llm import llm_text

    if not rd or not (rd / "clusters.json").exists():
        return 400, {"error": "chưa có cluster — chạy pipeline outline trước"}
    clusters = oe_common.read_json(rd / "clusters.json")
    gaps = oe_common.read_json(rd / "gaps.json") if (rd / "gaps.json").exists() else []
    videos = oe_common.read_json(rd / "videos.json") if (rd / "videos.json").exists() else {}
    try:
        cfg = _llm_cfg(b)
        ts = oe_titles.sinh_titles(clusters, gaps, videos,
                                   lambda s, u: llm_text(s, u, cfg, max_tokens=6000))
    except (RuntimeError, ValueError) as e:
        return 200, {"error": str(e)}
    return 200, {"titles": ts, "titles_goc": oe_titles.titles_goc_cua_song(videos)}


def _cham_title(b: dict, rd: Path) -> tuple[int, dict]:
    """Chấm title GÕ TAY qua đúng máy chấm của title máy sinh (một nguồn sự thật)."""
    from oe import titles as oe_titles
    from voiceprofile.llm import llm_text

    title = str(b.get("title") or "").strip()
    if not title:
        return 400, {"error": "chưa có title để chấm"}
    if not rd or not (rd / "clusters.json").exists():
        return 400, {"error": "chưa có cluster — chạy pipeline outline trước"}
    clusters = oe_common.read_json(rd / "clusters.json")
    try:
        cfg = _llm_cfg(b)
        kq = oe_titles.cham_title_tay(title, clusters,
                                      lambda s, u: llm_text(s, u, cfg, max_tokens=3000))
    except (RuntimeError, ValueError) as e:
        return 200, {"error": str(e)}
    return 200, {"title": kq}


def _py_split(b: dict, rd: Path) -> tuple[int, dict]:
    """Nút ⚡ Chia outline (PY): Python chia tất định từ số đo cluster (hook/ending
    mạnh nhất coverage→peak, N chương thứ tự theo pos) — 0 LLM, không tốn tiền."""
    from oe import suggest

    if not rd or not (rd / "clusters.json").exists():
        return 400, {"error": "chưa có cluster — chạy pipeline outline trước"}
    clusters = oe_common.read_json(rd / "clusters.json")
    try:
        picks = suggest.py_split(clusters, n_chapters=int(b.get("chapters") or 7),
                                 total_chars=int(b.get("total_chars") or 0))
    except ValueError as e:
        return 200, {"error": str(e)}
    return 200, {"picks": picks}


def _outlines() -> list[dict]:
    """Mọi runs/*/outline.txt, mới nhất trước — nguồn cho dropdown Writer.

    `total_chars`: độ dài user đặt trên board (hệ nguyên liệu 2026-07-16) — Writer lấy
    làm mặc định ô ký tự để hai nơi không lệch nhau. 0 = picks cũ chưa có.
    """
    out = []
    if oe_common.RUNS.exists():
        for p in oe_common.RUNS.glob("*/outline.txt"):
            try:
                txt = p.read_text(encoding="utf-8")
            except OSError:
                continue
            total = 0
            try:
                picks = oe_common.read_json(p.parent / "picks.json")
                total = int(picks.get("total_chars") or 0)
            except Exception:  # noqa: BLE001 — picks hong/thieu chi mat gia tri mac dinh
                pass
            title = next((ln.strip() for ln in txt.splitlines() if ln.strip()), "")
            out.append({"run": p.parent.name, "path": str(p),
                        "title": title[:120], "mtime": p.stat().st_mtime,
                        "total_chars": total})
    out.sort(key=lambda x: -x["mtime"])
    return out


def _default_run() -> str:
    """Run gần nhất có dữ liệu board; không có thì tên mặc định cho run đầu tiên."""
    if oe_common.RUNS.exists():
        dirs = [d for d in oe_common.RUNS.iterdir() if (d / "clusters.json").exists()]
        if dirs:
            return max(dirs, key=lambda d: d.stat().st_mtime).name
    return "video-outlier"


def make_handler(run_name: str):
    Base = vp_srv.make_handler()

    class Handler(Base):
        def _page(self, html: str) -> bytes:
            """Gắn dải 'đang đăng nhập là ai' vào trang HTML của lớp nối (có placeholder)."""
            return (html.replace("<!--WHOAMI_CSS-->", WHOAMI_CSS)
                        .replace("<!--WHOAMI-->", _whoami_bar(self))).encode("utf-8")

        def _board(self, path: Path) -> bytes:
            """Như _page nhưng cho 2 board.html của Khối 1/2 — chúng KHÔNG có placeholder.

            Tiêm từ đây thay vì sửa 2 file HTML kia (luật C1: không đụng Khối 1/2 khi không
            cần). Cả 2 file đều có đúng 1 `</style>` + `<body>` trơn và dùng chung bộ biến
            CSS (--panel/--border/--text/--accent) nên dải hiện đúng ở cả 2. Không khớp
            được thì trả nguyên trang: thiếu dải còn hơn gãy board.
            """
            html = path.read_text(encoding="utf-8")
            bar = _whoami_bar(self)
            if bar and "</style>" in html and "<body>" in html:
                html = html.replace("</style>", WHOAMI_CSS + "</style>", 1)
                html = html.replace("<body>", "<body>" + bar, 1)
            return html.encode("utf-8")

        def _vp_board(self, mode: str) -> bytes:
            """board.html của voiceprofile ở 2 route (user chốt 2026-07-16):
            /author = ① Extractor · /write = ② Writing — CÙNG một file, server tiêm
            CU_MODE để board ẩn tab kia (luật C1: không tách đôi file HTML). Chạy
            standalone (voiceprofile.server, không qua đây) → đủ 2 tab như cũ.
            Tiêm KHÔNG phụ thuộc whoami bar — local không nginx vẫn phải tách trang."""
            html = self._board(VP_HTML).decode("utf-8")
            return html.replace(
                "<body>", f'<body><script>window.CU_MODE="{mode}";</script>', 1
            ).encode("utf-8")

        def do_GET(self):
            path = self.path.split("?", 1)[0]
            if path == "/api/health":
                # Hợp đồng app V3 (apps.json health) — trả TRƯỚC _touch để probe
                # sức khỏe của gateway không rác sổ access.jsonl.
                self._json(200, {"ok": True, "app": "content-ultimate"})
                return
            _touch(self)
            if path in ("/", "/index.html"):
                card = ((MANAGE_CARD if _can_manage(self) else "")
                        + (SETTINGS_CARD if _is_admin(self) else ""))
                self._send(200, self._page(HOME.replace("<!--SETTINGS-->", card)),
                           "text/html; charset=utf-8")
            elif path == "/logout":
                if _vai_sso(self) is not None:
                    # SSO: 401 Basic sau proxy chỉ bật một hộp mật khẩu trình duyệt vô nghĩa
                    # (không gì trả lời nó). Đăng xuất nằm ở topbar OUTLIERY.
                    body = ("<p style='font-family:system-ui;padding:24px'>Tài khoản quản ở "
                            "<b>OUTLIERY</b> — dùng nút <b>Đăng xuất</b> trên thanh đầu trang. "
                            "<a href='/'>← Về trang chủ</a></p>").encode("utf-8")
                    self._send(200, body, "text/html; charset=utf-8")
                    return
                # Basic auth không có đăng xuất: trả 401 để browser hỏi lại mật khẩu.
                # Không phải cơ chế bảo mật — chỉ là lối đổi tài khoản (xem C2b).
                body = LOGOUT_HTML.encode("utf-8")
                self.send_response(401)
                self.send_header("WWW-Authenticate", 'Basic realm="Content Ultimate"')
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)
            elif path == "/manage":
                # Quản lý = admin HOẶC leader (phân quyền 2026-07-16)
                if not _can_manage(self):
                    self._send(403, _forbidden_page(
                        self, need="Leader",
                        how="Muốn theo dõi nhật ký/token của team? Nhờ quản trị viên nâng "
                            "bạn lên Leader trong Cài đặt → Thành viên."),
                        "text/html; charset=utf-8")
                    return
                self._send(200, self._page(MANAGE_HTML), "text/html; charset=utf-8")
            elif path == "/api/users":
                # GET (danh sách + cảnh báo IP) cho leader — tab Bảo mật cần;
                # THAY ĐỔI thành viên/quyền vẫn chỉ admin (nhánh POST).
                if not _can_manage(self):
                    self._json(403, {"error": "cần quyền Leader"})
                    return
                d = _users_payload()
                self._json(200, {**d, "alerts": _alerts(d.get("users", [])),
                                 "is_admin": _is_admin(self)})
            elif path == "/api/activity":
                if not _can_manage(self):
                    self._json(403, {"error": "cần quyền Leader"})
                    return
                self._json(200, _activity_payload())
            elif path == "/api/history-file":
                if not _can_manage(self):
                    self._json(403, {"error": "cần quyền Leader"})
                    return
                from urllib.parse import parse_qs, urlparse
                q = parse_qs(urlparse(self.path).query)
                raw = (q.get("path") or [""])[0]
                # Whitelist NGHIÊM: chỉ path đã nằm trong sổ nhật ký (luật C2 — không
                # bao giờ cho đọc theo đuôi file, credential nằm ở .txt).
                if raw not in _history_files() or not Path(raw).is_file():
                    self._json(404, {"error": "không có bản này trong nhật ký"})
                    return
                p = Path(raw)
                data = p.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                if (q.get("dl") or [""])[0]:
                    # Tên file đã là <ngày-giờ>-<user>.md nên tải về đọc là biết ai/lúc nào.
                    self.send_header("Content-Disposition",
                                     f'attachment; filename="{p.name}"')
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(data)
            elif path == "/settings":
                if not _is_admin(self):
                    self._send(403, _forbidden_page(self), "text/html; charset=utf-8")
                    return
                self._send(200, self._page(SETTINGS_HTML), "text/html; charset=utf-8")
            elif path == "/api/settings":
                if not _is_admin(self):
                    self._json(403, {"error": "chỉ quản trị viên"})
                    return
                self._json(200, _settings_payload())
            elif path == "/invite":
                if _vai_sso(self) is not None:
                    # SSO: tài khoản tạo/quản ở OUTLIERY — đường mời tạo tài khoản riêng ĐÓNG
                    # (mở cũng chỉ đẻ thêm một hệ tài khoản thứ hai lệch quyền).
                    self._send(404, "Tài khoản quản ở OUTLIERY (cổng 8000)".encode("utf-8"),
                               "text/plain; charset=utf-8")
                    return
                self._send(200, INVITE_HTML.encode("utf-8"), "text/html; charset=utf-8")
            elif path == "/api/invites":
                if not _is_admin(self):
                    self._json(403, {"error": "chỉ quản trị viên"})
                    return
                self._json(200, {"invites": _load_invites(),
                                 "configured": _htpasswd_file() is not None})
            elif path == "/api/cookies":
                # Mọi thành viên đã đăng nhập (nginx) đều dán được cookies — YouTube chặn
                # IP xảy ra thường xuyên, team tự sửa không phải chờ admin (2026-07-09).
                self._json(200, _cookies_status())
            elif path == "/outline":
                self._send(200, self._board(OE_HTML), "text/html; charset=utf-8")
            elif path == "/author":
                self._send(200, self._vp_board("extract"), "text/html; charset=utf-8")
            elif path == "/write":
                self._send(200, self._vp_board("write"), "text/html; charset=utf-8")
            elif path == "/oe/api/board":
                from urllib.parse import parse_qs, urlparse
                q = parse_qs(urlparse(self.path).query)
                self._json(200, oe_srv._board_data(
                    _rd_for(self, (q.get("run") or [""])[0].strip())))
            elif path == "/oe/api/m-mine":
                # Tab M (V2): Python quét beat+comment tìm ứng viên misconception —
                # tất định, 0 LLM (oe/m_mine.py, pattern là config). Cắt trần payload.
                from urllib.parse import parse_qs, urlparse

                from oe import m_mine
                q = parse_qs(urlparse(self.path).query)
                r = m_mine.mine(_rd_for(self, (q.get("run") or [""])[0].strip()))
                self._json(200, {"pure": r["pure"][:12], "soft": r["soft"][:12],
                                 "resonance": r["resonance"][:20],
                                 "top_comments": r["top_comments"][:12]})
            elif path == "/oe/api/status":
                from urllib.parse import parse_qs, urlparse
                q = parse_qs(urlparse(self.path).query)
                rn = (q.get("run") or [""])[0].strip()
                self._json(200, oe_srv.status_of(rn or _rd_for(self).name))
            elif path == "/api/outlines":
                self._json(200, {"outlines": _outlines()})
            else:
                super().do_GET()

        def do_POST(self):
            _touch(self)
            path = self.path.split("?", 1)[0]
            if path == "/api/users":
                if not _is_admin(self):
                    self._json(403, {"error": "chỉ quản trị viên"})
                    return
                me = (self.headers.get("X-Remote-User") or "").strip()
                try:
                    code, out = _manage_users(self._body(), me)
                except Exception as e:                   # noqa: BLE001 — htpasswd lỗi → báo tử tế
                    code, out = 500, {"error": str(e)[:200]}
                self._json(code, out)
            elif path == "/api/settings":
                if not _is_admin(self):
                    self._json(403, {"error": "chỉ quản trị viên"})
                    return
                b = self._body()
                # Chống tự khóa (bài học 2026-07-09: admin điền tên hiển thị vào ADMIN_USERS
                # và mất quyền): người đang sửa luôn được giữ lại trong danh sách admin.
                me = (self.headers.get("X-Remote-User") or "").strip()
                ups = b.get("updates") or {}
                if me and "ADMIN_USERS" in ups:
                    admins = [a.strip() for a in str(ups["ADMIN_USERS"]).split(",") if a.strip()]
                    if admins and me not in admins:
                        ups["ADMIN_USERS"] = ", ".join(admins + [me])
                self._json(200, _save_settings(b))
            elif path == "/invite/api/accept":
                if _vai_sso(self) is not None:
                    self._json(404, {"error": "Tài khoản quản ở OUTLIERY (cổng 8000)"})
                    return
                ip = (self.headers.get("X-Forwarded-For") or
                      self.client_address[0]).split(",")[0].strip()
                if not _accept_guard(ip):
                    self._json(429, {"error": "thử quá nhiều lần — chờ 5 phút rồi thử lại"})
                    return
                b = self._body()
                ok, msg = _accept_invite(str(b.get("k", "")), str(b.get("user", "")),
                                         str(b.get("password", "")))
                self._json(200 if ok else 422, {"ok": ok} if ok else {"error": msg})
            elif path == "/api/cookies":
                # Team tự phục vụ (xem ghi chú ở nhánh GET) — vẫn sau lớp đăng nhập nginx.
                b = self._body()
                if b.get("action") == "delete":
                    COOKIES_PATH.unlink(missing_ok=True)
                    self._json(200, _cookies_status())
                    return
                ok, msg = _save_cookies(str(b.get("content", "")))
                out = _cookies_status()
                if not ok:
                    out["error"] = msg
                elif msg != "đã lưu":
                    out["notice"] = msg
                self._json(200 if ok else 422, out)
            elif path == "/api/invites":
                if not _is_admin(self):
                    self._json(403, {"error": "chỉ quản trị viên"})
                    return
                b = self._body()
                if b.get("action") == "create":
                    _create_invite()
                elif b.get("action") == "revoke":
                    _save_invites([i for i in _load_invites()
                                   if i["token"] != b.get("token") or i["used_by"]])
                self._json(200, {"invites": _load_invites(),
                                 "configured": _htpasswd_file() is not None})
            elif path == "/oe/api/save":
                b = self._body()
                rd = _rd_for(self, str(b.pop("run", "") or ""))   # run không thuộc picks
                self._json(200, oe_srv._save(rd, b))
            elif path == "/oe/api/merge":
                try:
                    b = self._body()
                    rd = _rd_for(self, str(b.get("run") or ""))
                    result = oe_srv._merge(rd, b.get("names", []))
                except Exception as e:                   # noqa: BLE001 — trả lỗi cho GUI hiện
                    result = {"error": str(e)[:200]}
                self._json(200, result)
            elif path == "/oe/api/cta":
                b = self._body()
                try:
                    from oe.cta import generate_cta
                    from oe.llm import LLM as OeLLM
                    cta = generate_cta(OeLLM(oe_common.ROOT / ".env"),
                                       str(b.get("brief", "")), str(b.get("angle", "")),
                                       str(b.get("position", "giữa")))
                    result = {"cta": cta} if cta else {"error": "LLM trả rỗng"}
                except Exception as e:                   # noqa: BLE001
                    result = {"error": str(e)[:200]}
                self._json(200, result)
            elif path in ("/oe/api/ingest", "/oe/api/resume"):
                b = self._body()
                rn = (b.get("run") or "").strip() or "video-outlier"
                rd = oe_common.run_dir(rn, create=True)
                # V3: AVD kênh nhập cùng lượt với link (màn tạo run) → run_meta.json;
                # resume không gửi avd thì giữ nguyên giá trị cũ.
                try:
                    avd = float(b.get("avd") or 0)
                except (TypeError, ValueError):
                    avd = 0
                if avd > 0:
                    meta_p = rd / "run_meta.json"
                    meta = oe_common.read_json(meta_p) if meta_p.exists() else {}
                    meta["avd_phut"] = round(avd, 1)
                    oe_common.write_json(meta_p, meta)
                user = (self.headers.get("X-Remote-User") or "").strip()
                _set_user_run(user, rd.name)             # board của user này gắn vào run này
                ok, err = oe_srv.start_pipeline(rn, b.get("videos", ""),
                                                resume=path.endswith("resume"))
                if not ok:
                    self._json(409, {"error": err})
                    return
                self._json(200, {"started": True, "run": rd.name})
            elif path == "/api/outline-load":
                p = self._body().get("path", "")
                ok = any(o["path"] == p for o in _outlines())
                content = Path(p).read_text(encoding="utf-8") if ok else ""
                self._json(200, {"content": content})
            elif path == "/oe/api/suggest-outline":
                b = self._body()
                self._json(*_suggest_outline(b, _rd_for(self, str(b.get("run") or ""))))
            elif path == "/oe/api/py-split":
                b = self._body()
                self._json(*_py_split(b, _rd_for(self, str(b.get("run") or ""))))
            elif path == "/oe/api/titles":
                b = self._body()
                self._json(*_sinh_titles(b, _rd_for(self, str(b.get("run") or ""))))
            elif path == "/oe/api/cham-title":
                b = self._body()
                self._json(*_cham_title(b, _rd_for(self, str(b.get("run") or ""))))
            else:
                super().do_POST()

    return Handler


def run(port: int, run_name: str, open_browser: bool = True) -> None:
    RD["rd"] = oe_common.run_dir(run_name, create=True)
    USER_RUNS.update(_load_user_runs())                 # user → run gắn từ phiên trước
    # run dở dang (server bị dừng giữa chừng)? status_of đọc lại .pipeline.json khi board
    # hỏi — ở đây chỉ nhắc trên terminal.
    prev = oe_srv._load_status(run_name)
    if prev and not prev.get("done") and prev.get("completed"):
        print(f"  ↻ Run '{run_name}' dở dang ({len(prev['completed'])} bước xong) — mở board Outline rồi bấm 'Tiếp tục'.")
    srv = ThreadingHTTPServer(("127.0.0.1", port), make_handler(run_name))
    url = f"http://127.0.0.1:{port}/"
    print(f"Content Ultimate — {url}  (Ctrl+C để dừng)")
    print(f"  ① Outline board: {url}outline  (run: {run_name})")
    print(f"  ② Author Extract: {url}author")
    if open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nĐã dừng.")


def main() -> None:
    ap = argparse.ArgumentParser(description="Content Ultimate — server hợp nhất")
    # Fork V2 mặc định 8771 — bản gốc giữ 8770, hai bản chạy cạnh nhau trên cùng máy
    # (lỗi thật 2026-07-27: Start.command V2 đòi đúng port bản gốc đang giữ → Errno 48).
    ap.add_argument("--port", type=int, default=8771)
    ap.add_argument("--run", default=None, help="run của board Outline (mặc định: run mới nhất có data)")
    ap.add_argument("--no-browser", action="store_true", help="không tự mở browser (VPS/headless)")
    a = ap.parse_args()
    run(a.port, a.run or _default_run(), open_browser=not a.no_browser)


if __name__ == "__main__":
    main()
