"""GUI web-local: Python http.server + board.html tĩnh + /api.

Chạy:  python3 -m seo.server [--port 8760] [--host 0.0.0.0]

MẶC ĐỊNH bind 127.0.0.1 (chỉ máy này). Không asset CDN — trang tự chứa, offline.
Mỗi lần sinh là một job riêng (`jobs.py`), poll qua `/api/status?run=<id>`.

**CHIA SẺ TRONG MẠNG:** đổi `--host 0.0.0.0` (hoặc `BIND_HOST` trong .env) thì phải có
`BOARD_PASSWORD` — `run()` TỪ CHỐI khởi động nếu thiếu. Xem `access.py` để biết vì sao:
`.env` giữ 1 khoá z.ai + 19 khoá YouTube và có 6 endpoint phá huỷ không xác thực.
Khuyến nghị dùng Tailscale/VPN nội bộ, **đừng phơi thẳng ra internet công cộng**.
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import threading
import time
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import (access, admin_keys, audit, common, episodes, jobs, library, llm, markets, niche_format,
               niches, roles, users)

HTML = Path(__file__).parent / "board.html"

# Ghi dữ liệu người dùng (profiles/formats/episodes/niches/markets) là chuỗi ĐỌC → SỬA → GHI.
# Một process nhưng `ThreadingHTTPServer` chạy mỗi request một thread, nên hai người bấm Lưu
# cùng lúc là bản sau đè bản trước IM LẶNG. RLock vì handler có thể gọi lồng nhau; giữ khoá
# chỉ trong lúc ghi file (micro giây), TUYỆT ĐỐI không giữ qua một lần chạy pipeline.
DATA_LOCK = threading.RLock()

# Endpoint chỉ ĐỌC — không cần khoá, và không được khoá kẻo poll 1 giây/lần chặn mất người đang ghi.
_READONLY = {"/api/login", "/api/logout"}

# ── MỖI ENDPOINT ĐÚNG MỘT QUYỀN ─────────────────────────────────────────────────────────────
# Bảng LỘ THIÊN, một chỗ. Chôn quyền vào if/else rải khắp handler là mỗi lần đổi phải đi dò,
# và chỗ quên thì không ai thấy. Self-test dưới cùng file BẮT BUỘC mọi endpoint có mặt ở đây —
# thêm endpoint mà quên khai là bộ kiểm kêu ngay, không lọt thành cửa không khoá.
PERM_OF = {
    # xem
    "/api/profiles": "view", "/api/formats": "view", "/api/episodes": "view",
    "/api/markets": "view", "/api/niche-bank": "view", "/api/runs": "view",
    "/api/result": "view", "/api/status": "view", "/api/title-index": "view",
    "/api/trash": "view", "/api/version": "view", "/api/roles": "view",
    "/api/overview": "view",
    # Bang thong ke kenh doi thu da nap — chi DOC lai formats/*.json, khong YouTube/LLM.
    "/api/format-channels": "view",
    # Tự đổi mật khẩu CỦA CHÍNH MÌNH — ai đăng nhập được cũng phải làm được, nên chỉ đòi
    # `view`. Khác hẳn `/api/user-passwd` (Owner đặt lại cho NGƯỜI KHÁC, không cần mật khẩu cũ).
    "/api/change-password": "view",
    # nhật ký: tách riêng vì nó lộ việc của NGƯỜI KHÁC, không phải dữ liệu công việc
    "/api/audit": "audit",
    # sinh / xuất — tốn token LLM
    "/api/generate": "generate", "/api/export": "generate", "/api/gen-cta": "generate",
    # extract — tốn quota YouTube
    # THÊM KÊNH CỦA MÌNH: ai cũng làm được, kể cả Seo (user chốt 2026-08-02). Người bấm sẽ
    # thành CHỦ kênh (`created_by` gán ngay dưới, ở handler) nên họ sửa được kênh mình vừa
    # dựng — không phải đi xin bàn giao từng cái.
    "/api/extract-profile": "extract_chan",
    # Dựng FORMAT từ kênh ĐỐI THỦ thì vẫn từ Leader trở lên: tốn gấp đôi call LLM và là dữ
    # liệu DÙNG CHUNG cho cả niche, một người bấm nhầm là cả nhóm chịu.
    "/api/extract-format": "extract",
    # sửa
    # Đổi CHỦ kênh: từ LEADER trở lên (user chốt 2026-08-02: *"việc phân kênh này tôi sẽ thêm
    # cả leader họ sẽ phân công cũng được"*). Cố ý KHÔNG dùng chung mức `edit` — `edit` là sửa
    # nội dung kênh, còn đây là đổi xem AI ĐƯỢC sửa nó, tức một hành động phân quyền.
    # Và cố ý KHÔNG dính vào `delete`: phân công là việc hằng ngày của Leader, còn xoá kênh
    # vẫn phải qua Manager/Owner — *"leader và SEO sẽ không được xoá kênh"*.
    "/api/set-channel-owner": "chan_owner",
    # Cấp lại mật khẩu là việc của quyền `users` — tức CHỈ Owner (user chốt 2026-08-02:
    # *"Owner sẽ là người cho phép cấp lại mk mới"*).
    "/api/resets": "users", "/api/reset-approve": "users", "/api/reset-drop": "users",
    "/api/update-profile": "edit", "/api/update-format": "edit", "/api/save-episode": "edit",
    "/api/set-langs": "edit",
    # thị trường: TẠO/SỬA từ Leader trở lên; XOÁ thì phải `delete` (Manager+) — user chốt
    # "Leader không được xoá thị trường, chỉ có từ cấp quản lý trở lên".
    "/api/save-market": "market",
    # KHO NICHE tách đôi: Seo THÊM được (làm giàu kho) nhưng KHÔNG xoá. Gộp cả hai vào `edit`
    # thì không cách nào diễn tả được, mà nới `edit` cho Seo là cho luôn quyền xoá kho.
    "/api/niche-add-title": "bank", "/api/niche-add-many": "bank",
    "/api/niche-remove": "bank_del",
    # xoá — kể cả `restore`: khôi phục ghi đè lên thư mục thật, cùng mức nguy hiểm
    "/api/delete-profile": "delete",
    # XOA FORMAT: tu LEADER tro len (user chot 2026-08-02) — khac han xoa KENH. Kenh giu
    # thu user go tay (link/CTA, sub_url) mat la khong dung lai duoc; Format chi la so lieu
    # harvest tu YouTube, nap lai mot luot la co. `server.selftest` co ngoai le tuong minh
    # cho endpoint nay, giong `/api/niche-remove`.
    "/api/delete-format": "fmt_del",
    "/api/delete-episode": "delete", "/api/delete-market": "delete",
    "/api/format-del-competitor": "delete",
    # DỌN HẲN thùng rác vẫn ở mức `delete` — đây là thao tác DUY NHẤT không lấy lại được.
    "/api/purge": "delete",
    # KHÔI PHỤC tách hẳn khỏi XOÁ (user chốt 2026-08-02): Leader cứu được đồ xoá nhầm mà vẫn
    # không xoá được gì. Gộp chung `delete` là muốn cứu một kênh cũng phải đi tìm Manager.
    "/api/restore": "restore",
    # QUẢN TÀI KHOẢN — chỉ Owner. Trước đây CỐ Ý không có endpoint (xem `users.py`); user chốt
    # 2026-08-02 cần tạo tài khoản từ giao diện. Rủi ro đã nêu vẫn còn nguyên, nên bù lại:
    # mọi endpoint ở đây đòi quyền `users` (chỉ Owner), ghi nhật ký từng thao tác, KHÔNG BAO
    # GIỜ trả hash ra ngoài, và **dòng lệnh vẫn là đường cứu hộ** khi tự khoá mình khỏi UI.
    "/api/users": "users", "/api/user-save": "users", "/api/user-passwd": "users",
    "/api/user-disable": "users", "/api/user-remove": "users",
    # API KEY (tab QUẢN TRỊ, 03/08/2026) — cùng mâm Owner với quản tài khoản: key là thứ
    # đắt nhất trong hệ. GET chỉ trả số lượng + đuôi key (admin_keys.summary), POST ghi
    # .env nguyên tử + đồng bộ os.environ, không cần restart.
    "/api/admin-keys": "users",
}
# Không cần đăng nhập (phải trả lời được thì board mới biết mình cần đăng nhập)
# `/api/forgot` BẮT BUỘC mở: người bấm nó đúng là người KHÔNG đăng nhập được. Đổi lại nó
# phải tự phòng thân — xem `_forgot_ok` (chặn theo IP) và `users.request_reset` (không bao
# giờ tiết lộ tên có tồn tại hay không).
_OPEN = {"/api/whoami", "/api/login", "/api/logout", "/api/forgot", "/api/health"}


# ── SSO V3 (19/08/2026 — đưa app vào OUTLIERY v2, APPS.md app 4/6) ──────────────────────────
def _sso_bat() -> bool:
    return os.environ.get("SEO_TRUST_PROXY") == "1"


THONG_DIEP_QT = ("Quản trị đã chuyển về OUTLIERY — khóa API nhập ở General › API Keys, "
                 "tài khoản/quyền cấp ở General › Accounts / Permissions")

# Cửa QUẢN TRỊ nội bộ (tài khoản + mật khẩu + API key): SSO bật → 404 vô điều kiện,
# KỂ CẢ vai owner nội bộ (luật Owner 16/08 "khóa + quản trị về MỘT CỬA V3"; lệnh user
# 19/08 "mọi truy xuất tài khoản đều thực hiện từ khối nền, không được tự tạo trong app").
# `/api/logout` CỐ Ý không nằm đây (chỉ xóa cookie cục bộ, vô hại); `/api/whoami` phải
# sống để board biết mình là ai.
_CUA_QUAN_TRI = {"/api/login", "/api/forgot", "/api/resets", "/api/reset-approve",
                 "/api/reset-drop", "/api/change-password", "/api/users",
                 "/api/user-save", "/api/user-passwd", "/api/user-disable",
                 "/api/user-remove", "/api/admin-keys"}


def vai_tu_claims(raw_actions: str | None, raw_role: str) -> str:
    """Dịch claims gateway V3 → vai nội bộ app. ACTIONS-FIRST (khuôn niche/radary):
    header `X-Remote-Actions` CÓ MẶT (kể cả chuỗi RỖNG) là nguồn sự thật —
    quan_tri→owner · toan_quyen→manager · sua→leader · van_hanh→seo · còn lại
    viewer (fail-closed: Manager bộ phận khác chỉ-đọc, không tốn token/quota).
    THIẾU hẳn header Actions (gateway đời cũ 8000) mới rơi về `X-Remote-Role`:
    nhận danh pháp mới ('admin' = vai cao nhất app) lẫn tên vai cũ; vai lạ →
    viewer (roles.DEFAULT, fail-closed)."""
    if raw_actions is not None:
        hd = {s.strip() for s in raw_actions.split(",") if s.strip()}
        if "quan_tri" in hd:
            return "owner"
        if "toan_quyen" in hd:
            return "manager"
        if "sua" in hd:
            return "leader"
        if "van_hanh" in hd:
            return "seo"
        return "viewer"
    r = (raw_role or "").strip().lower()
    return "owner" if r == "admin" else roles.norm(r)


def _profiles(errors: list | None = None) -> list[dict]:
    """FULL profile (kèm guide: blocks/hashtag/example + field user khai: niche/lang/links)."""
    return library.all_profiles(errors)


# ── PHẠM VI THỊ TRƯỜNG ──────────────────────────────────────────────────────────────────────
# Vai `leader`/`seo` chỉ thấy thị trường được giao. Lọc Ở SERVER, không lọc ở board: board đã
# có `inLang()` nhưng đó là tiện nghi hiển thị, ai mở DevTools gọi thẳng `/api/profiles` là
# thấy hết. Hai chỗ lọc cùng tồn tại là đúng — board lọc cho gọn mắt, server lọc cho thật.
def _scope_langs(me: dict) -> set[str] | None:
    """Tập NGÔN NGỮ người này được thấy. `None` = không giới hạn.

    Thị trường → ngôn ngữ vì dữ liệu (`profile.lang`, `format.lang`) gắn theo NGÔN NGỮ, còn
    thị trường chỉ là cách user gom nhóm. Thị trường chưa gán ngôn ngữ thì không đóng góp gì.
    """
    ms = roles.scope_markets(me)
    if ms is None:
        return None
    want = {m.strip().lower() for m in ms}
    out = set()
    for m in markets.all_markets():
        if (m.get("name") or "").strip().lower() in want:
            lg = niche_format.norm_lang(m.get("lang") or "")
            if lg:
                out.add(lg)
    return out


def _scope_deny(path: str, body: dict, me: dict) -> str:
    """Lý do TỪ CHỐI vì mục tiêu nằm ngoài phạm vi; rỗng = cho qua.

    **Lọc danh sách thôi thì chưa đủ.** Không thấy một kênh không có nghĩa là không sửa được
    nó — slug nằm trong URL YouTube, đoán ra là gọi thẳng `/api/delete-profile` được. Chốt
    phải đặt ở đường GHI, và đặt Ở ĐÂY (một chỗ) chứ không rải vào từng handler.

    Chỉ chặn khi **xác định được** mục tiêu nằm ngoài phạm vi. Không tra ra mục tiêu thì để
    handler tự trả 404 — đoán bừa rồi chặn là báo "không có quyền" cho một thứ không tồn tại,
    user đi xin quyền vô ích.
    """
    langs = _scope_langs(me)
    # GHI LÊN KÊNH nay hỏi CHỦ KÊNH (`profile.created_by`), không hỏi `users.channels` nữa.
    creator_only = roles.norm(me.get("role", "")) in roles.CREATOR_ONLY
    if langs is None and not creator_only:
        return ""
    b = body or {}

    def not_mine(sl):
        """Lý do từ chối GHI lên một kênh; rỗng = cho qua. Nói rõ CHỦ là ai để user biết hỏi ai."""
        p = library.load(sl)
        if not p or roles.can_write_profile(me, p):
            return ""
        ow = (p.get("created_by") or "").strip()
        nm = p.get("channel") or sl
        return (f"Kênh '{nm}' do {ow} tạo — bạn chỉ sửa được kênh do chính mình tạo." if ow
                else f"Kênh '{nm}' chưa có tài khoản nào đứng tên chủ (kênh tạo trước "
                     f"02/08/2026). Nhờ Leader / Manager / Owner gán chủ cho kênh này.")

    def bad(obj, what):
        return "" if _keep(obj or {}, langs) else f"{what} này nằm ngoài thị trường bạn phụ trách"

    if path in ("/api/update-profile", "/api/delete-profile", "/api/gen-cta"):
        sl = common.slug(str(b.get("slug") or ""))
        p = library.load(sl)
        if not p:
            return ""
        m = not_mine(sl)
        if m:
            return m
        return bad(p, "Kênh")
    if path == "/api/set-channel-owner":
        # CHỈ soi THỊ TRƯỜNG, **không** soi "kênh của mình": cả điểm của `chan_owner` là giao
        # kênh cho NGƯỜI KHÁC, nên đòi phải là chủ thì quyền này vô nghĩa.
        # Cần từ 2026-08-02, khi Leader được cấp `chan_owner`: hai vai cũ (Owner/Manager)
        # không bị giới hạn thị trường nên chỗ này chưa bao giờ lộ ra. Đo mới thấy: leader US
        # đổi được chủ kênh Tây Ban Nha.
        p = library.load(common.slug(str(b.get("slug") or "")))
        return bad(p, "Kênh") if p else ""
    if path == "/api/restore":
        # Leader khôi phục được, mà Leader bị giới hạn theo THỊ TRƯỜNG ⇒ phải soi mục trong
        # thùng rác TRƯỚC. Không soi thì họ lách hàng rào phạm vi bằng đường vòng: xoá không
        # được nhưng khôi phục được một kênh của thị trường khác.
        it = common.trash_peek(str(b.get("token") or ""))
        if not it:
            return ""                                      # không tra ra thì để handler trả 404
        # TẬP không mang `lang` (ngôn ngữ suy từ kênh của nó) ⇒ không soi được, cho qua —
        # cùng luật với `epInLang`: rỗng nghĩa là "không quy được về đâu", không phải "cấm".
        if it.get("kind") == "episodes":
            return ""
        return bad(it.get("data") or {}, "Mục")
    if path in ("/api/update-format", "/api/delete-format", "/api/format-del-competitor"):
        f = niche_format.load(str(b.get("slug") or ""))
        return bad(f, "Format") if f else ""
    if path in ("/api/save-market", "/api/delete-market"):
        nm = str(b.get("old") or b.get("name") or "").strip()
        return "" if roles.in_scope(me, nm) else f"Thị trường '{nm}' không thuộc phạm vi của bạn"
    if path in ("/api/generate", "/api/save-episode", "/api/delete-episode"):
        chans = [c for c in (b.get("channels") or []) if c]
        if not chans and b.get("slug"):                   # sửa/xoá tập cũ: lấy kênh đã lưu
            chans = [c for c in ((episodes.load(str(b["slug"])) or {}).get("channels") or []) if c]
        mine = [c for c in chans if not_mine(common.slug(c))]
        if mine:
            # Chỉ đường phải khớp LUẬT ĐANG CHẠY: nói "chưa được giao" là đẩy user đi xin
            # giao kênh — thao tác nay KHÔNG còn mở được quyền sửa, xin xong vẫn hỏng.
            return ("Trong danh sách có kênh bạn KHÔNG phải chủ (chỉ sinh được cho kênh do "
                    "chính mình tạo; nhờ Leader / Manager / Owner đổi chủ kênh): "
                    + ", ".join(mine[:4]) + ("…" if len(mine) > 4 else ""))
        out = [c for c in chans if not _keep(library.load(common.slug(c)) or {}, langs)]
        if out:
            return ("Trong danh sách có kênh ngoài thị trường bạn phụ trách: "
                    + ", ".join(out[:4]) + ("…" if len(out) > 4 else ""))
        return ""
    if path in ("/api/extract-profile", "/api/extract-format"):
        # `langs is None` = KHÔNG giới hạn thị trường (cùng nghĩa với `_keep`) — thiếu vế này
        # thì `lg not in None` ném TypeError → 500. Bug tiềm ẩn từ đầu, chỉ lộ 03/08/2026 khi
        # SSO đưa vai seo KHÔNG gán thị trường vào (tài khoản cũ ai cũng được gán nên vào
        # nhánh creator_only với langs=None là chuyện chưa từng xảy ra).
        lg = niche_format.norm_lang(str(b.get("lang") or ""))
        if lg and langs is not None and lg not in langs:
            return "Không tạo được mục cho ngôn ngữ ngoài thị trường bạn phụ trách"
    # Kho niche (`/api/niche-*`) CỐ Ý không soi phạm vi: một niche trải trên nhiều thị trường
    # (Life In có kênh Anh lẫn Tây Ban Nha), nên "kho niche này thuộc thị trường nào" là câu
    # hỏi sai hình dạng. Nó dừng ở quyền `edit`.
    return ""


# ── NICHE / NGÔN NGỮ MỚI: chỉ Leader+ được tạo, và không bao giờ tạo BẢN TRÙNG ──────────────
# (user chốt 2026-08-04: "Seo không được khai mới, tránh đặt sai tên và lặp; đã tạo rồi trùng
# ký tự thì không cho tạo nữa"). Niche/ngôn ngữ không có store riêng — chúng "ra đời" ngầm mỗi
# khi một profile/format/tập được ghi, nên chốt phải nằm ở ĐƯỜNG GHI, một chỗ, như _scope_deny.
_NL_PATHS = ("/api/update-profile", "/api/save-episode", "/api/extract-profile",
             "/api/extract-format", "/api/update-format", "/api/set-langs")


def _chuan_hoa_ten(s) -> str:
    """Khoá so 'trùng ký tự': gộp khoảng trắng + casefold + BỎ DẤU (NFD).

    Bỏ dấu là chủ đích: 'Đời Sống' vs 'Doi Song' là cùng một niche gõ vội — để cả hai tồn tại
    thì bộ lọc/kho niche chẻ đôi im lặng, đúng thứ luật này sinh ra để chặn.
    """
    import unicodedata
    s = " ".join(str(s or "").split()).casefold()
    # 'đ' (U+0111) KHÔNG phân rã qua NFD (nó là chữ riêng, không phải d+dấu) — thiếu dòng này
    # thì 'Đời Sống' vs 'Doi Song' vẫn coi là khác nhau, đúng ca selftest bắt được.
    s = s.replace("đ", "d")
    s = unicodedata.normalize("NFD", s)
    return "".join(ch for ch in s if not unicodedata.combining(ch))


def _ten_hien_co() -> tuple[dict, dict]:
    """(niches, langs) — map khoá-chuẩn-hoá → CHÍNH TẢ ĐANG DÙNG (gặp đầu tiên thắng).

    Đọc từ mọi nơi tên đang sống thật: profile + format (niche, lang), tập (niche),
    thị trường (lang). Không cache — dữ liệu nhỏ (chục file JSON), đọc mỗi lần ghi là rẻ
    hơn nhiều so với một cache phải nhớ xoá.
    """
    niches: dict = {}
    langs: dict = {}
    def _got(d, v):
        v = str(v or "").strip()
        if v:
            d.setdefault(_chuan_hoa_ten(v), v)
    for p in library.all_profiles():
        _got(niches, p.get("niche")); _got(langs, p.get("lang"))
    for f in niche_format.all_formats():
        _got(niches, f.get("niche")); _got(langs, f.get("lang"))
    for e in episodes.all_episodes():
        _got(niches, e.get("niche"))
    for m in markets.all_markets():
        _got(langs, m.get("lang"))
    return niches, langs


def _niche_lang_deny(path: str, b: dict, me: dict) -> str:
    """Lý do TỪ CHỐI vì tạo niche/ngôn ngữ mới sai luật; rỗng = cho qua.

    TÁC DỤNG PHỤ CÓ CHỦ ĐÍCH: giá trị trùng-ký-tự với tên đã có được VIẾT LẠI trong body
    thành đúng chính tả đang dùng (b là `_bcache` — handler đọc lại vẫn thấy bản đã sửa).
    'Không cho tạo bản trùng' nghĩa là DÙNG LẠI bản cũ, không phải bắt user gõ lại cho khớp
    từng dấu — chặn thẳng là phạt người gõ 'life in' thay vì 'Life In' vô cớ.
    """
    if path not in _NL_PATHS or not isinstance(b, dict):
        return ""
    niches, langs = _ten_hien_co()
    role = (me or {}).get("role", "")

    def _mot(kind: str, d: dict, v):
        v = str(v or "").strip()
        if not v:
            return "", v
        canon = d.get(_chuan_hoa_ten(v))
        if canon is not None:
            return "", canon                       # đã có → dùng lại đúng chính tả cũ
        if role == "seo":
            return (f"Vai Seo không tạo được {kind} MỚI ('{v}') — chọn trong danh sách có sẵn; "
                    f"cần {kind} mới thì nhờ Leader / Manager / Owner tạo trước.", v)
        return "", v                               # Leader+ tạo mới được

    for k, kind, d in (("niche", "niche", niches), ("lang", "ngôn ngữ", langs)):
        if k in b:
            err, canon = _mot(kind, d, b.get(k))
            if err:
                return err
            if str(b.get(k) or "").strip():
                b[k] = canon
    if path == "/api/set-langs":                   # khai hàng loạt: từng dòng items[]
        for it in (b.get("items") or []):
            if not isinstance(it, dict):
                continue
            err, canon = _mot("ngôn ngữ", langs, it.get("lang"))
            if err:
                return err
            if str(it.get("lang") or "").strip():
                it["lang"] = canon
    return ""


def _keep(obj: dict, langs: set[str] | None) -> bool:
    """Người bị giới hạn có được thấy mục này không (theo NGÔN NGỮ / thị trường).

    **Mục CHƯA khai ngôn ngữ thì AI CŨNG THẤY** — giấu đi thì kênh vừa extract xong (chưa kịp
    gán ngôn ngữ) biến mất khỏi mọi màn hình, user tưởng hỏng rồi extract lại, tốn quota. Đúng
    bài học đã ghi: thà hiện thừa còn hơn để dữ liệu thật biến mất im lặng.
    """
    if langs is None:
        return True
    lg = niche_format.norm_lang((obj or {}).get("lang") or "")
    return (not lg) or lg in langs


# ĐÃ GỠ `_keep_chan` (2026-08-02) — đừng viết lại. Nó lọc DANH SÁCH theo kênh được giao, tức
# ẩn kênh của người khác. User đảo quyết định sau khi đo: ẩn không kín (3 đường vòng vẫn lộ
# title/description) và làm thẻ TẬP nói dối "kênh đã bị xoá" cho kênh còn nguyên. Kênh được
# giao nay CHỈ chặn GHI (`roles.write_channels` + `_scope_deny`).




# Ô "quên mật khẩu" là endpoint DUY NHẤT ghi được dữ liệu mà không cần đăng nhập, nên nó
# phải tự có hàng rào. Không chặn thì một trang lạ (hoặc một người rảnh) bơm hàng nghìn tên
# vào và danh sách của Owner thành vô dụng — mà đó chính là lúc có người thật cần cấp lại.
_FORGOT: dict[str, list[float]] = {}
_FORGOT_LOCK = threading.Lock()
FORGOT_MAX, FORGOT_WIN = 5, 600.0                          # 5 lần / 10 phút / một IP


def _forgot_ok(ip: str) -> bool:
    now = time.time()
    with _FORGOT_LOCK:
        t = [x for x in _FORGOT.get(ip or "?", []) if now - x < FORGOT_WIN]
        if len(t) >= FORGOT_MAX:
            _FORGOT[ip or "?"] = t
            return False
        t.append(now)
        _FORGOT[ip or "?"] = t
        if len(_FORGOT) > 500:                             # đừng để dict phình vô hạn
            for k in [k for k, v in _FORGOT.items() if not any(now - x < FORGOT_WIN for x in v)]:
                _FORGOT.pop(k, None)
        return True


def _overview(me: dict) -> dict:
    """Bức tranh AI ĐANG CẦM GÌ, cắt theo đúng phạm vi của người đang xem.

    · Owner/Manager — mọi thị trường, mọi niche
    · Leader        — thị trường được giao ∩ **niche được giao** (Owner/Manager cấp)
    · Seo           — chỉ kênh được giao cho mình

    Hai con số về mỗi người, ĐỪNG GỘP:
      · `created`  = số kênh người đó ĐÃ TẠO (`profile.created_by`) — việc đã làm, không đổi
      · `holding`  = số kênh người đó ĐANG CẦM (`users.channels`) — trạng thái lúc này
    Một người có thể tạo 5 kênh mà đang cầm 2 (đã bàn giao), hoặc cầm 3 mà chưa tạo cái nào.
    Gộp thành "số kênh của X" là xoá mất chính thông tin user hỏi.

    `created_by` chỉ có từ 2026-08-02 nên kênh cũ hiện `""` — trả nguyên vậy để board ghi
    "không rõ", **đừng đoán** ai tạo.
    """
    profs = _profiles()
    langs = _scope_langs(me)
    nsc = roles.scope_niches(me)
    # TRỤC ĐỌC, không phải trục ghi — xem `roles.overview_channels`. Dùng `write_channels`
    # ở đây là Leader mất sạch màn này ngay khi luật ghi đổi sang CHỦ KÊNH.
    mine = roles.overview_channels(me)
    try:
        us = users.all_users()
    except Exception:                                      # noqa: BLE001 — users.json hỏng
        us = []
    hold: dict[str, list[str]] = {}                        # slug kênh → [tên người đang cầm]
    for u in us:
        for c in (u.get("channels") or []):
            hold.setdefault(c, []).append(u["name"])
    by_mkt: dict[str, dict] = {}
    for m in markets.all_markets():
        by_mkt[niche_format.norm_lang(m.get("lang") or "") or ""] = m
    out: dict[str, dict] = {}
    loose: list[dict] = []                                 # kênh chưa thuộc thị trường nào
    for p in profs:
        if not _keep(p, langs):
            continue
        nic = (p.get("niche") or "").strip()
        if nsc is not None and nic not in nsc:
            continue
        if mine is not None and p.get("slug") not in mine:
            continue
        row = {"slug": p.get("slug"), "name": p.get("channel"), "code": p.get("code"),
               "niche": nic or "(chưa phân loại)", "lang": p.get("lang", ""),
               "created_by": (p.get("created_by") or ""),
               "holders": sorted(hold.get(p.get("slug"), []))}
        mk = by_mkt.get(niche_format.norm_lang(p.get("lang") or ""))
        if not mk:
            loose.append(row)
            continue
        b = out.setdefault(mk["name"], {"market": mk["name"], "lang": mk.get("lang", ""),
                                        "niches": {}})
        b["niches"].setdefault(row["niche"], []).append(row)

    def _people(rows):
        acc: dict[str, dict] = {}
        for r in rows:
            for h in r["holders"]:
                acc.setdefault(h, {"user": h, "holding": 0, "created": 0})["holding"] += 1
            cb = r["created_by"]
            if cb:
                acc.setdefault(cb, {"user": cb, "holding": 0, "created": 0})["created"] += 1
        for a in acc.values():
            a["role"] = roles.norm((users.find(a["user"]) or {}).get("role", ""))
        return sorted(acc.values(), key=lambda x: (-x["holding"], x["user"]))

    mkts = []
    for b in out.values():
        nl = [{"niche": n, "channels": rows, "n_channels": len(rows), "people": _people(rows)}
              for n, rows in sorted(b["niches"].items())]
        allrows = [r for x in nl for r in x["channels"]]
        mkts.append({**{k: b[k] for k in ("market", "lang")}, "niches": nl,
                     "n_channels": len(allrows), "n_niches": len(nl),
                     "people": _people(allrows)})
    mkts.sort(key=lambda x: x["market"])
    return {"markets": mkts, "loose": loose,
            "scope": {"role": me["role"], "markets": roles.scope_markets(me),
                      "niches": nsc, "channels": mine, "me": me["name"]},
            "n_channels": sum(m["n_channels"] for m in mkts) + len(loose)}


def _done(who: str, ip: str, what: str, run: str, err: str | None = None, **extra) -> None:
    """Ghi dòng KẾT THÚC của một job chạy ngầm.

    Dòng lúc BẮT ĐẦU (`_post` ghi) chỉ nói *"đã nhận job"* — nó trả về sau vài mili giây
    trong khi việc thật chạy 20 giây. Job hỏng giữa chừng mà chỉ có dòng đó thì nhật ký ghi
    `ok=True` cho một lần sinh THẤT BẠI: đúng lỗi "ghi ý định, trình bày như kết quả" đã sửa
    ở đường đồng bộ, chỉ là nấp ở đường bất đồng bộ.
    """
    audit.log(who, ip, what + "-xong", ok=err is None, run=run,
              error=(err or None) and str(err)[:200], **extra)


def _run_generate(run: str, body: dict, job: dict, who: str = "", ip: str = "") -> None:
    """Module 2 (1 kênh) hoặc Module 4 (1 tập → N kênh) tuỳ body.channels. Import lazily.

    `job` là dict RIÊNG của lần sinh này (từ `jobs.start`). `pipeline.generate`/`episode.generate`
    nhận dict rồi tự `update()` vào đó, nên đưa dict của job vào là hai module ấy không phải sửa.
    """
    try:
        # Định tuyến theo số kênh CÒN TỒN TẠI, không theo số kênh đã tick: kênh bị xoá vẫn nằm
        # trong `episodes/*.json`, tick 2 mà 1 đã xoá thì rơi vào chế độ nhiều kênh cho đúng
        # 1 kênh — mất luôn màn chọn Title×3, mà vẫn tốn từng ấy token.
        picked = [s for s in (body.get("channels") or []) if s]
        alive = [s for s in picked if library.load(common.slug(s))]
        gone = [s for s in picked if s not in alive]
        job.update(step="harvest…", gone=gone)
        if len(alive) == 1 and not body.get("profile"):
            body = {**body, "profile": alive[0]}            # 1 kênh sống → luồng cổ điển cần profile
        if len(alive) > 1:
            from . import episode                     # noqa: PLC0415
            episode.generate(run, body, job)
        else:
            from . import pipeline                    # noqa: PLC0415 — lazy, xây dần
            pipeline.generate(run, body, job)
        # gắn run vào Tập để thẻ tập biết kênh nào đã có metadata (im lặng nếu không đi từ Tập).
        # PHẢI khoá: đây là đọc-sửa-ghi `episodes/<slug>.json` từ THREAD CỦA JOB, chạy song song
        # với người đang bấm Lưu tập ở tab khác — không khoá là một trong hai bản biến mất.
        with DATA_LOCK:
            episodes.attach_run(body.get("episode", ""), run)
        jobs.finish(run)
        _done(who, ip, "generate", run, episode=body.get("episode", ""))
    except Exception as e:                             # noqa: BLE001
        jobs.finish(run, error=str(e))
        _done(who, ip, "generate", run, err=str(e))


def _gated(fn, name, run, b, job, who, ip):
    """Đợi tới lượt trong hàng rồi mới chạy — MỘT chỗ cho cả ba loại job.

    Thread được spawn NGAY lúc bấm (để board có cái mà poll), nhưng việc thật chỉ bắt đầu khi
    `jobs.acquire` cấp chỗ. Bỏ cuộc (chờ quá lâu) thì vẫn phải ghi một dòng nhật ký `-xong`
    ok=False: im lặng ở đây là job biến mất trong khi nhật ký ghi như chưa từng có ai bấm.
    """
    if not jobs.acquire(run):
        _done(who, ip, name, run, err=(jobs.get(run) or {}).get("error") or "bỏ hàng đợi")
        return
    fn(run, b, job, who, ip)


def make_handler():
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, body, ctype="application/json", cookie=""):
            self._st = code            # nhớ lại để nhật ký ghi KẾT QUẢ THẬT, không phải ý định
            data = body if isinstance(body, bytes) else body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            if cookie:
                self.send_header("Set-Cookie", cookie)
            self.end_headers()
            self.wfile.write(data)

        def _json(self, code, obj, cookie=""):
            self._send(code, json.dumps(obj, ensure_ascii=False), cookie=cookie)

        # ── XÁC THỰC ────────────────────────────────────────────────────────────────
        def _tok(self) -> str:
            return access.token_from_cookie(self.headers.get("Cookie", ""))

        def _ip(self) -> str:
            return (self.client_address or ("?",))[0]

        def _sso(self) -> dict | None:
            """Danh tính từ proxy OUTLIERY (SSO một cửa :8000, user chốt 03/08/2026).

            CHỈ tin header khi đủ CẢ HAI: bật SEO_TRUST_PROXY=1 (nằm trong Arguments
            tác vụ nền, không phải .env — cùng lệ 4 app kia) VÀ client là loopback
            (app bind 127.0.0.1 nên đường từ xa duy nhất là proxy ĐÃ xác thực; thiếu
            điều kiện IP thì ai trong LAN cũng giả được header nếu cổng lỡ mở).

            Vai OUTLIERY → vai app qua `roles.norm`. Header có mặt thì THẮNG cookie —
            ngược bài học PlannerY là cố ý: đường proxy phải một nguồn sự thật.

            V3 19/08/2026 (lệnh user *"mọi truy xuất tài khoản đều thực hiện từ khối
            nền, không được tự tạo trong app"*): vai dịch từ `X-Remote-Actions` mỗi
            request (`vai_tu_claims`), KHÔNG còn `users.sync_sso` — app không ghi/tạo
            bản ghi tài khoản nào nữa (khác V2 05/08: upsert mỗi request). users.json
            chỉ còn được ĐỌC như dữ liệu DI SẢN V2 để giữ giới hạn thị trường/kênh đã
            gán; người không có bản ghi → không giới hạn (đúng hành vi V2 với người
            mới). Quản tài khoản/giới hạn giờ ở khối nền (General › Permissions)."""
            if not _sso_bat():
                return None
            if self._ip() not in ("127.0.0.1", "::1"):
                return None
            ten = (self.headers.get("X-Remote-User") or "").strip()
            if not ten:
                return None
            role = vai_tu_claims(self.headers.get("X-Remote-Actions"),
                                 self.headers.get("X-Remote-Role") or "")
            u = users.find(ten) or {}                    # CHỈ ĐỌC — không upsert
            return {"name": ten, "role": role,
                    "markets": u.get("markets") or [], "channels": u.get("channels") or [],
                    "niches": u.get("niches") or [], "auth": True}

        def _authed(self) -> bool:
            if self._sso():
                return True
            if _sso_bat():
                # SSO bật: CHẾ-ĐỘ-MỞ của access (chưa có users.json → ai cũng owner)
                # KHÔNG được áp — không danh tính từ gateway là CHƯA xác thực.
                return False
            return access.valid(self._tok())

        def _me(self) -> dict:
            me = self._sso()
            if me:
                return me
            if _sso_bat():                    # nhất quán với _authed: không rơi chế-độ-mở
                return {"name": "", "role": "", "markets": [], "channels": [],
                        "niches": [], "auth": False}
            return access.current(self._tok())

        def _quan_tri_dong(self, path: str) -> bool:
            """SSO bật → cửa quản trị nội bộ đáp 404 vô điều kiện (kể cả vai owner) —
            khuôn niche/radary/content: quản trị về MỘT CỬA V3."""
            if _sso_bat() and path in _CUA_QUAN_TRI:
                self._json(404, {"error": THONG_DIEP_QT})
                return True
            return False

        def _need_perm(self, path: str) -> bool:
            """Đáp 403 và trả True nếu vai hiện tại KHÔNG được gọi endpoint này.

            **Endpoint lạ (chưa khai trong `PERM_OF`) → đòi quyền CAO NHẤT (`users`)**, tức chỉ
            Owner gọi được. Fail-closed: quên khai một endpoint thì nó bị khoá chặt lại chứ
            không mở toang. Self-test cuối file bắt buộc mọi endpoint phải có mặt, nên nhánh
            này chỉ là lưới an toàn.
            """
            need = PERM_OF.get(path, "users")
            me = self._me()
            if roles.can(me["role"], need):
                return False
            audit.log(me["name"], self._ip(), path.replace("/api/", ""), ok=False,
                      error=f"thiếu quyền {need}")
            self._json(403, {"error": f"Vai {me['role'] or '?'} không có quyền "
                                      f"'{need}' ({roles.PERM_VN.get(need, need)})",
                             "need_perm": need, "role": me["role"]})
            return True

        # Mật khẩu TẠM chỉ đủ để vào ĐỔI MẬT KHẨU, không đủ để làm việc. Chặn ở SERVER chứ
        # không chỉ ẩn màn hình: ẩn nút thì mở DevTools gõ một dòng `fetch` là qua, mà người
        # đang dùng mật khẩu tạm là người mà ít nhất hai người khác biết mật khẩu của họ.
        _MC_OK = {"/api/whoami", "/api/login", "/api/logout", "/api/change-password",
                  "/api/forgot", "/api/roles", "/api/version"}

        def _must_change_deny(self, path: str) -> bool:
            # SSO không có mật khẩu ở app này — nếu tên SSO TRÙNG một tài khoản cũ đang
            # cắm cờ must_change thì không được khóa oan người ta (họ đổi mật khẩu ở
            # OUTLIERY, không phải ở đây).
            if self._sso():
                return False
            me = self._me()
            if not me["name"] or path in self._MC_OK:
                return False
            if not (users.find(me["name"]) or {}).get("must_change"):
                return False
            self._json(403, {"error": "Bạn đang dùng MẬT KHẨU TẠM do Owner cấp — phải đổi "
                                      "sang mật khẩu của riêng bạn trước khi làm gì khác.",
                             "must_change": True})
            return True

        def _need_login(self) -> bool:
            """Đáp 401 và trả True nếu request này phải đăng nhập trước.

            Trang `/` vẫn phục vụ khi CHƯA đăng nhập — nó chỉ là vỏ HTML tĩnh, và phải tải được
            thì mới có chỗ hiện ô nhập mật khẩu. Mọi `/api/*` (trừ login/whoami) thì chặn.
            """
            if self._authed():
                return False
            self._json(401, {"error": "Cần đăng nhập", "need_login": True})
            return True

        def _body(self) -> dict:
            # NHỚ LẠI kết quả: `self.rfile` là luồng, đọc lần hai ra rỗng. Từ khi `_post` phải
            # xem body để ghi nhật ký thì handler bên dưới sẽ là người đọc THỨ HAI — không nhớ
            # thì mọi endpoint POST nhận `{}` và im lặng làm sai.
            if getattr(self, "_bcache", None) is None:
                n = int(self.headers.get("Content-Length", 0))
                self._bcache = json.loads(self.rfile.read(n).decode("utf-8")) if n else {}
            return self._bcache

        def _query(self, key: str) -> str:
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            return (q.get(key) or [""])[0]

        def _get(self):
            path = self.path.split("?", 1)[0]
            if path in ("/", "/index.html"):
                self._send(200, HTML.read_bytes(), "text/html; charset=utf-8")
                return
            if path == "/api/health":
                # Health cho gateway /suc-khoe (V3) — không cần đăng nhập, không lộ gì.
                self._json(200, {"ok": True, "app": "seo-optimize"})
                return
            if self._quan_tri_dong(path):
                return
            if path == "/api/resets":
                # Metadata mật khẩu của MỌI người, cho Owner soi. **KHÔNG có mật khẩu trần ở
                # đây và sẽ không bao giờ có** — hash một chiều, xem ghi chú đầu `users.py`.
                # 03/08/2026: DỜI THÂN HANDLER xuống SAU cổng đăng nhập/quyền — trước đây
                # nhánh này đứng trước cổng nên AI GỌI CŨNG ĐỌC ĐƯỢC danh sách tên tài
                # khoản + metadata mật khẩu (lỗ lộ thông tin thật, tìm ra khi rà 03/08).
                # Giữ nhánh ở đây chỉ để path không rơi xuống 404 sớm; `pass` cho chảy
                # tiếp qua cổng rồi xử lý ở dưới.
                pass
            if path == "/api/whoami":
                # Board hỏi cái này TRƯỚC mọi thứ khác để biết có phải hiện ô mật khẩu không.
                # KHÔNG chặn — chặn thì board không biết vì sao mình bị chặn.
                me = self._me()
                sso = bool(self._sso())
                # SSO: gỡ 'users' khỏi danh sách quyền TRẢ CHO BOARD — pane Tài khoản/
                # API key tự ẩn (board gate bằng may('users')); chốt thật vẫn ở server
                # (_CUA_QUAN_TRI đáp 404). Vai/quyền server-side không đổi.
                ps = roles.perms(me["role"]) if me["role"] else set()
                if sso:
                    ps -= {"users"}
                self._json(200, {"need": access.enabled() or _sso_bat(), "auth": self._authed(),
                                 "per_user": access.per_user(),
                                 "user": me["name"], "role": me["role"],
                                 "perms": sorted(ps), "sso": sso,
                                 "markets": me["markets"],
                                 # Còn mật khẩu TẠM thì board phải ép đổi ngay — nhưng chốt
                                 # thật nằm ở `_must_change_deny`, không ở board.
                                 "must_change": bool((users.find(me["name"]) or {})
                                                     .get("must_change")) if me["name"] else False,
                                 "min_len": users.MIN_LEN,
                                 "n_running": jobs.n_running()})
                return
            # SSO bật cũng BẮT đăng nhập kể cả khi users.json trống — chế-độ-mở V2 chỉ
            # hợp khi app đứng một mình; sau gateway thì mọi request phải có danh tính.
            if (access.enabled() or _sso_bat()) and path.startswith("/api/") and self._need_login():
                return
            if path.startswith("/api/") and path not in _OPEN and self._must_change_deny(path):
                return
            if path.startswith("/api/") and path not in _OPEN and self._need_perm(path):
                return
            if path == "/api/resets":
                # Thân thật của /api/resets — nằm SAU cổng (quyền `users`, chỉ Owner).
                # **KHÔNG có mật khẩu trần ở đây và sẽ không bao giờ có** — hash một chiều.
                self._json(200, {"resets": users.resets(),
                                 "users": [{"name": u["name"], "pw_at": u.get("pw_at", ""),
                                            "pw_by": u.get("pw_by", ""),
                                            "must_change": bool(u.get("must_change")),
                                            "disabled": bool(u.get("disabled"))}
                                           for u in users.all_users()]})
                return
            if path == "/api/admin-keys":
                # Tab QUẢN TRỊ: trạng thái key — CHỈ số lượng + đuôi, không key trần.
                self._json(200, admin_keys.summary())
                return
            if path == "/api/version":
                # Vân tay của board.html để board tự biết mình đã cũ. ĐO TRƯỚC KHI SỬA
                # (2026-08-01): `_send` vốn đã gửi `Cache-Control: no-store` và F5 thường
                # ĐÃ ăn bản mới — cache HTTP không phải thủ phạm. Thủ phạm là cái tab mở
                # sẵn không bao giờ tải lại. Nên chốt nằm ở đây, không phải ở header.
                # `stat()` chứ không đọc file: poll vài giây/lần mà đọc 227 KB là phí.
                st = HTML.stat()
                # `d` = VÂN TAY DỮ LIỆU, đi ghép luôn vào lượt poll đang có (không thêm
                # request nào). Trước đây endpoint này chỉ soi `board.html` — tức soi CODE,
                # không soi DỮ LIỆU ⇒ người A thêm kênh thì tab của người B không có đường
                # nào biết, đo thật: sau 15 giây vẫn 1 kênh trong khi server đã có 2.
                self._json(200, {"v": f"{int(st.st_mtime)}-{st.st_size}", "d": data_version()})
            elif path == "/api/format-channels":
                # Loc theo THI TRUONG nhu moi danh sach khac: bang nay bay ra kenh doi
                # thu cua ca he thong, ma leader/seo chi duoc thay vung minh phu trach.
                langs = _scope_langs(self._me())
                rows = [r for r in niche_format.channel_table()
                        if _keep({"lang": r.get("lang", "")}, langs)]
                # `can_del` gửi kèm để board khỏi tự chép lại bảng quyền — chép là có ngày
                # màn hình nói một đằng, server chặn một nẻo. Đây CHỈ để đỡ vướng mắt; chốt
                # thật vẫn ở `PERM_OF["/api/delete-format"]`.
                self._json(200, {"rows": rows,
                                 "can_del": roles.can(self._me()["role"], "fmt_del")})
            elif path == "/api/profiles":
                # `load_errors`: file JSON hỏng bị bỏ qua nhưng KHÔNG được im lặng — biến mất
                # khỏi board là user tưởng đã bị xoá. Board hiện khối đỏ kèm tên file.
                errs: list = []
                me = self._me()
                lg = _scope_langs(me)
                # ĐỌC lọc theo THỊ TRƯỜNG, KHÔNG lọc theo kênh được giao. Bản trước ẩn luôn
                # kênh người khác — đo lại thấy ẩn không kín (title lộ qua title-index/runs/
                # result) và thẻ TẬP nói dối "kênh đã bị xoá". Quan trọng hơn: tool sinh ra để
                # né trùng metadata, mà không thấy kênh anh em thì không tra được.
                ps = [p for p in _profiles(errs) if _keep(p, lg)]
                # `can_write` để board mờ nút Sửa trên kênh không phải của mình — nói TRƯỚC,
                # thay vì để user gõ xong bấm Lưu rồi mới ăn 403. Nay hỏi CHỦ KÊNH
                # (`created_by`), không hỏi `users.channels`.
                lim = roles.norm(me.get("role", "")) in roles.CREATOR_ONLY
                if lim:
                    for x in ps:
                        x["can_write"] = roles.can_write_profile(me, x)
                # `n_assigned` nay là "số kênh SỬA ĐƯỢC" (= số kênh mình tạo), không còn là
                # "số kênh được giao" — board dùng nó để nói đúng một câu về QUYỀN SỬA.
                self._json(200, {"profiles": ps,
                                 "scope_langs": sorted(lg) if lg is not None else None,
                                 "write_only": lim,
                                 "n_assigned": sum(1 for x in ps if x.get("can_write")) if lim
                                               else None,
                                 "load_errors": errs})
            elif path == "/api/runs":
                # MÃ TẬP gắn ở đây chứ không trong library: `episodes` đã import `library` nên
                # library import ngược lại là vòng. Server biết cả hai nên nối ở đây là chỗ đúng.
                rs = library.runs(self._query("profile"), limit=library.RUNS_SCAN)
                by_run = {}
                for e in episodes.all_episodes():
                    for rid in (e.get("runs") or []):
                        by_run[rid] = {"code": e.get("code", ""), "episode": e.get("slug", ""),
                                       "episode_name": e.get("name", "")}
                for r in rs:
                    r.update(by_run.get(r.get("run"), {"code": "", "episode": "", "episode_name": ""}))
                folded = library.fold_runs(rs)
                # Cắt danh sách thì phải NÓI. Im lặng cắt là user mở thẻ kênh, không thấy tập cũ
                # đâu và tưởng lịch sử mất — trong khi file vẫn nằm nguyên trong runs/.
                self._json(200, {"runs": folded[:library.RUNS_KEEP],
                                 "more": max(len(folded) - library.RUNS_KEEP, 0),
                                 "scan_full": len(rs) >= library.RUNS_SCAN})
            elif path == "/api/markets":
                # THỊ TRƯỜNG = khối cấp cao nhất user tự khai. Kèm `orphan`: ngôn ngữ đang có
                # trên kênh/format mà CHƯA thị trường nào nhận — không nói ra thì những kênh
                # đó biến mất khỏi mọi khối ở main tab, im lặng.
                langs = ([p.get("lang", "") for p in _profiles()]
                         + [f.get("lang", "") for f in niche_format.all_formats()])
                me = self._me()
                ms = roles.scope_markets(me)
                mk = markets.all_markets()
                if ms is not None:                         # người bị giới hạn: chỉ thấy thị trường của mình
                    want = {x.strip().lower() for x in ms}
                    mk = [m for m in mk if (m.get("name") or "").strip().lower() in want]
                self._json(200, {"markets": mk,
                                 # `orphan` là việc CẤP HỆ THỐNG (ngôn ngữ chưa thị trường nào nhận).
                                 # Người bị giới hạn không sửa được nó, hiện ra chỉ tổ nhiễu.
                                 "orphan": markets.orphan_langs(langs) if ms is None else [],
                                 "scoped": ms is not None})
            elif path == "/api/title-index":
                # Nguyên liệu cho thanh tìm kiếm. Kênh/format/tập board đã có sẵn trong bộ nhớ;
                # riêng title đã sinh thì nằm rải trong runs/ nên phải hỏi server. Board gọi
                # MỘT lần lúc nạp + sau mỗi lần generate, không gọi theo từng phím gõ.
                self._json(200, {"titles": library.title_index()})
            elif path == "/api/formats":
                errs = []
                fs = niche_format.all_formats(errs)
                # ĐỀ XUẤT ngôn ngữ cho format CHƯA khai — đo từ chữ thật của đối thủ, 0 LLM,
                # 0 quota. Gắn vào field RIÊNG `lang_guess`, TUYỆT ĐỐI không ghi đè `lang`:
                # `lang_mismatch` dựa vào `lang` để phán 0-title, nên một phỏng đoán trôi vào
                # đó là đóng dấu "đã đối chiếu" cho thứ chưa ai duyệt.
                lg = _scope_langs(self._me())
                fs = [f for f in fs if _keep(f, lg)]
                for f in fs:
                    if not (f.get("lang") or "").strip():
                        f["lang_guess"] = niche_format.guess_lang(f)
                self._json(200, {"formats": fs, "load_errors": errs})
            elif path == "/api/trash":
                self._json(200, {"trash": common.trash_list(), "ttl_h": common.TRASH_TTL_H})
            elif path == "/api/episodes":
                errs = []
                eps = episodes.all_episodes(errs)
                # TẬP không mang `lang` — nó mang danh sách kênh. Suy ngôn ngữ từ kênh của nó,
                # đúng như `epInLang` bên board. Tập CHƯA tick kênh nào thì ai cũng thấy.
                lg = _scope_langs(self._me())
                if lg is not None:
                    by = {p.get("slug"): p for p in _profiles()}
                    eps = [e for e in eps
                           if not (e.get("channels") or [])
                           or any(_keep(by.get(c) or {}, lg) for c in (e.get("channels") or []))]
                for e in eps:                              # tiến độ đọc từ result.json thật
                    e["status"] = episodes.status(e)
                    # LỊCH SỬ TỪNG LẦN SINH của tập — để mở lại một lần cũ, không chỉ lần mới nhất.
                    e["history"] = episodes.run_history(e)
                self._json(200, {"episodes": eps, "load_errors": errs})
            elif path == "/api/niche-bank":
                # ?niche=<tên> → kho của đúng niche đó; không truyền → bảng đếm mọi niche
                n = self._query("niche")
                errs: list = []
                self._json(200, {**niches.load(n), "all": niches.all_banks(errs),
                                 "load_errors": errs} if n
                           else {"all": niches.all_banks(errs), "load_errors": errs})
            elif path == "/api/overview":
                self._json(200, _overview(self._me()))
            elif path == "/api/users":
                # `users.all_users()` đã lọc bỏ `hash`. Vẫn khẳng định lại ở đây: rò hash ra
                # board là dò offline được, không hàng rào tốc độ nào cản.
                us = [{k: v for k, v in u.items() if k != "hash"} for u in users.all_users()]
                for u in us:
                    u["role"] = roles.norm(u.get("role", ""))
                    u["perms"] = sorted(roles.perms(u["role"]))
                    u["chan_scoped"] = u["role"] in roles.CHAN_SCOPED
                self._json(200, {"users": us, "roles": list(roles.ROLES), "labels": roles.VN,
                                 "matrix": roles.matrix(),
                                 # Vai nào BỊ giới hạn theo gì — board đọc từ đây, KHÔNG chép
                                 # lại luật. Chép là có ngày form mở ô cho một vai mà server
                                 # bỏ qua giá trị đó (đúng thứ user vừa hỏi: "ô này để làm gì").
                                 "scoped_roles": sorted(roles.SCOPED),
                                 "chan_scoped_roles": sorted(roles.CHAN_SCOPED),
                                 "niche_scoped_roles": sorted(roles.NICHE_SCOPED),
                                 "markets": [m.get("name") for m in markets.all_markets()],
                                 # NICHE lấy từ chính profile đang có — không có store riêng
                                 # (niche là 1 field trên profile, xem đầu library.py).
                                 "niches": sorted({(p.get("niche") or "").strip()
                                                   for p in _profiles()} - {""}),
                                 "channels": [{"slug": p.get("slug"), "name": p.get("channel"),
                                               "lang": p.get("lang", "")} for p in _profiles()],
                                 "min_len": users.MIN_LEN, "me": self._me()["name"]})
            elif path == "/api/roles":
                # BẢNG "vai nào được làm gì" — dựng từ `roles._GRANT`, không chép tay. Board
                # hiện y nguyên bảng này, nên không có chuyện màn hình nói một đằng server
                # chặn một nẻo.
                me = self._me()
                self._json(200, {"matrix": roles.matrix(), "roles": list(roles.ROLES),
                                 "labels": roles.VN, "me": roles.describe(me["role"]),
                                 "scoped_roles": sorted(roles.SCOPED),
                                 "chan_scoped_roles": sorted(roles.CHAN_SCOPED),
                                 "my_markets": me["markets"],
                                 "my_channels": roles.scope_channels(me)})
            elif path == "/api/audit":
                # AI LÀM GÌ. Chỉ có nghĩa khi mỗi người một tài khoản — chưa bật thì nói thẳng
                # là mọi dòng đều mang tên "(chung)", đừng để user tưởng mình tra được ai.
                try:
                    n = max(1, min(int(self._query("n") or 200), 1000))
                except ValueError:
                    n = 200
                self._json(200, {"rows": audit.tail(n), "per_user": access.per_user()})
            elif path == "/api/status":
                # `?run=` BẮT BUỘC khi có nhiều người: thiếu nó thì server không có cách nào biết
                # hỏi job nào, và đoán bừa một job đang chạy chính là bug cũ (board người B hiện
                # tiến trình của người A). `snapshot('')` trả rỗng + `no_run` để board nói cho đúng.
                self._json(200, jobs.snapshot(self._query("run")))
            elif path == "/api/result":
                run = self.path.split("run=", 1)[-1] if "run=" in self.path else ""
                rd = common.run_dir(run)
                f = rd / "result.json"
                self._json(200, common.read_json(f) if f.exists() else {})
            else:
                self._json(404, {})

        def _cross_site(self) -> bool:
            """Chặn trang web LẠ gọi vào tool.

            Tool bind 127.0.0.1 nhưng `webbrowser.open` luôn mở sẵn browser, mà TRANG NÀO cũng
            fetch được `http://127.0.0.1:8760/api/*` — không có cookie/token gì để chặn. Phản biện
            2026-07-30 tái hiện bằng Edge thật: một trang lạ xoá VĨNH VIỄN mục trong `.trash/` qua
            `/api/purge`, và xoá được kênh/format qua `/api/delete-*`, user không bấm gì cả.

            `Sec-Fetch-Site` do CHÍNH browser gắn, JS không sửa được: `same-origin` là từ board của
            mình, `cross-site`/`same-site` là từ chỗ khác. Client không phải browser (curl, self-test)
            không gửi header này → cho qua, nếu chặn thì tự khoá luôn đường kiểm thử.
            """
            sfs = self.headers.get("Sec-Fetch-Site")
            if sfs and sfs != "same-origin":
                return True
            org = self.headers.get("Origin")
            if not org:
                return False
            # So với HOST mà client thật sự gõ, KHÔNG so với hằng số 127.0.0.1. Khi chia sẻ trong
            # mạng thì đồng nghiệp mở `http://100.x.y.z:8760` nên Origin là địa chỉ đó — so với
            # hằng số cũ là chặn oan MỌI request của họ, mà triệu chứng lại là "403 bí ẩn".
            host = (self.headers.get("Host") or "").strip()
            # Qua proxy OUTLIERY (một cửa :8000, 03/08/2026): httpx của proxy buộc đặt
            # Host=127.0.0.1:8760, host GỐC người dùng gõ nằm ở X-Forwarded-Host → chỉ so
            # với Host là 403 oan MỌI POST đi qua proxy. So với cả hai. An toàn không đổi:
            # app chỉ bind loopback nên đường duy nhất từ xa tới đây là proxy đã xác thực;
            # kẻ đứng được ở loopback thì tự giả Host được từ đầu.
            xfh = (self.headers.get("X-Forwarded-Host") or "").strip()
            try:
                p = urllib.parse.urlparse(org.rstrip("/"))
            except ValueError:
                return True
            return p.netloc not in {h for h in (host, xfh) if h}

        def do_POST(self):
            # Bọc CẢ hàm: exception xuyên ra ngoài là client mất kết nối KHÔNG có response —
            # board chỉ hiện "Failed to fetch" (không phân biệt được "chưa làm" với "làm rồi") và
            # cửa sổ server phun traceback, nhìn y như server sắp sập. Đúng lớp bẫy CLAUDE.md đã ghi.
            try:
                self._post()
            except Exception as e:                         # noqa: BLE001
                try:
                    self._json(500, {"error": f"{type(e).__name__}: {e}"})
                except Exception:                          # noqa: BLE001 — client đã ngắt
                    pass

        def do_GET(self):
            try:
                self._get()
            except Exception as e:                         # noqa: BLE001 — vd result.json hỏng
                try:
                    self._json(500, {"error": f"{type(e).__name__}: {e}"})
                except Exception:                          # noqa: BLE001
                    pass

        def _post(self):
            if self._cross_site():
                self._json(403, {"error": "Yêu cầu từ trang khác — bị chặn"})
                return
            if self._quan_tri_dong(self.path.split("?", 1)[0]):
                return
            if self.path == "/api/login":
                b = self._body()
                nm = str(b.get("name") or "")
                r = access.login(str(b.get("password") or ""), ip=self._ip(), name=nm)
                # Ghi CẢ lần sai — chuỗi thất bại liên tiếp là thứ duy nhất cho thấy có người
                # đang dò. Không ghi mật khẩu (audit.log chỉ nhận field đã chọn lọc).
                audit.log(r.get("user") or nm or "?", self._ip(), "login", ok=r["ok"],
                          error=None if r["ok"] else r.get("error"))
                if not r["ok"]:
                    self._json(401, r)               # 401 = sai mật khẩu, không phải lỗi server
                    return
                me = access.current(r.get("token", ""))
                self._json(200, {"ok": True, "need": access.enabled(), "user": r.get("user", ""),
                                 "role": me["role"],
                                 "perms": sorted(roles.perms(me["role"])) if me["role"] else [],
                                 "markets": me["markets"]},
                           cookie=access.set_cookie(r.get("token", "")) if r.get("token") else "")
                return
            if self.path == "/api/logout":
                audit.log(self._me()["name"], self._ip(), "logout")
                access.logout(self._tok())
                self._json(200, {"ok": True}, cookie=access.clear_cookie())
                return
            _p = self.path.split("?", 1)[0]
            # `/api/forgot` phải qua được KHI CHƯA ĐĂNG NHẬP — đúng người cần nó là người
            # không vào được. Nó tự phòng thân bằng `_forgot_ok` (chặn theo IP) và bằng việc
            # trả lời giống hệt nhau dù tên có thật hay không.
            if _p not in _OPEN and (access.enabled() or _sso_bat()) and self._need_login():
                return
            # MẬT KHẨU TẠM: chặn ở CẢ đường ghi, không chỉ đường đọc. Thiếu nhánh này thì người
            # dùng mật khẩu tạm bị chặn xem nhưng vẫn SỬA và SINH được — tức chốt chỉ có trên
            # giấy. (Đo được đúng vậy: sửa kênh trả 200.)
            if _p not in _OPEN and self._must_change_deny(_p):
                return
            # `_OPEN` cũng phải bỏ qua phần kiểm QUYỀN: `_need_perm` rơi về `users` cho mọi
            # path chưa khai (đúng, an toàn) ⇒ `/api/forgot` ăn 403 dù đã nằm trong `_OPEN`.
            if _p not in _OPEN and self._need_perm(_p):
                return
            deny = _scope_deny(self.path, self._body(), self._me())
            if not deny:
                # Niche/ngôn ngữ: canonical hoá tên trùng-ký-tự (sửa thẳng _bcache) + chặn
                # vai Seo tạo tên MỚI (user chốt 04/08). Phải chạy TRƯỚC handler vì handler
                # là người ghi tên đó xuống đĩa.
                deny = _niche_lang_deny(self.path, self._body(), self._me())
            if deny:
                audit.log(self._me()["name"], self._ip(),
                          self.path.replace("/api/", ""), ok=False, error=deny)
                self._json(403, {"error": deny, "out_of_scope": True})
                return
            # KHOÁ GHI: mọi endpoint POST còn lại đều đọc-sửa-ghi file dữ liệu. Không khoá thì hai
            # người bấm Lưu cùng lúc là bản sau đè bản trước, im lặng, không ai biết. Khoá ở ĐÂY
            # (một chỗ) thay vì rải vào từng module: thêm endpoint mới là tự động được bảo vệ.
            # Job dài KHÔNG chạy trong khoá này — nó chỉ spawn thread rồi trả về ngay.
            # NHẬT KÝ: ghi mọi thao tác GHI, kèm tên người. Chỉ vài field định danh đã chọn lọc
            # (`audit.fields`) — body của /api/generate mang cả kịch bản, không được lọt vào.
            #
            # GHI **SAU** KHI LÀM, kèm mã trạng thái. Bản đầu ghi TRƯỚC nên mọi dòng đều
            # `ok=True` kể cả khi thao tác thất bại — nhìn nhật ký thật của user thấy HAI dòng
            # `user-save` liền nhau cùng `ok=True` trong khi chỉ một cái thành công. Nhật ký
            # ghi Ý ĐỊNH mà trình bày như KẾT QUẢ thì đúng là nói dối, mà đây lại là chỗ
            # người ta tra khi có chuyện.
            # `self._me()` chứ KHÔNG `access.who(cookie)`: người vào bằng SSO không có cookie —
            # đọc thẳng cookie là audit ghi "(chưa đăng nhập)" cho người đã xác thực (dính thật
            # 03/08/2026, dòng user-save của Huonggiangsss).
            who, ip = self._me()["name"], self._ip()
            try:
                fields = audit.fields(self._body(), self.path)
            except Exception:                            # noqa: BLE001 — body hỏng: để handler báo
                fields = {}
            self._st = 200
            try:
                with DATA_LOCK:
                    self._post_locked()
            finally:
                st = getattr(self, "_st", 200)
                audit.log(who, ip, self.path.replace("/api/", ""), ok=st < 400,
                          status=None if st < 400 else st, **fields)

        def _post_locked(self):
            if self.path in ("/api/generate", "/api/extract-profile", "/api/extract-format"):
                b = self._body()
                # ID RUN PHẢI DUY NHẤT. Mặc định cũ là chuỗi cố định "gen" ⇒ mọi lần sinh
                # không kèm id đều ghi đè `runs/gen/`, và `attach_run` gắn đúng cái id dùng
                # chung đó vào MỌI tập. Hậu quả user gặp thật: bấm "Mở kết quả mới nhất" ở
                # tập Space lại ra kết quả của tập Life In — vì `runs[0]` của cả hai đều là
                # "gen", trỏ về một thư mục mà tập chạy sau đã ghi đè.
                # Nhận "gen" trần cũng coi như KHÔNG có id: client cũ gửi vậy thì vẫn phải an toàn.
                _raw = (b.get("run") or "").strip()
                run = common.slug(_raw) if _raw and _raw != "gen" else                     "gen-" + format(int(time.time() * 1000), "x")
                # Mở job ĐỒNG BỘ trước khi start thread → poll đầu tiên không bắt nhầm trạng thái
                # của lần trước. Quá trần đồng thời thì `start` raise, đáp 409 kèm NGUYÊN VĂN lý do
                # (nói rõ đang chạy mấy cái, tên gì) — "đang chạy" trống trơn là user đoán mò.
                try:
                    job = jobs.start(run)
                except RuntimeError as e:
                    self._json(409, {"error": str(e), "n_running": jobs.n_running()})
                    return
                if self.path == "/api/extract-profile":
                    # AI TẠO KÊNH — server gán, KHÔNG nhận từ body: body do client gửi nên
                    # khai gì cũng được, mà đây là dữ liệu dùng để quy trách nhiệm.
                    # `_me` (tên + vai) đi kèm để `profile.extract` chặn được việc extract ĐÈ
                    # lên kênh của người khác — nó chỉ biết kênh đích là cái nào SAU khi đã
                    # gọi YouTube, nên `_scope_deny` ở đây không làm thay được.
                    # `self._me()` để nhận CẢ danh tính SSO — access.current(cookie) trả rỗng
                    # cho người SSO ⇒ kênh extract xong KHÔNG CÓ CHỦ, chính người tạo hết sửa
                    # được kênh mình (luật created_by).
                    _who = self._me()
                    b = {**b, "created_by": _who["name"],
                         "_me": {"name": _who["name"], "role": _who.get("role", "")}}
                target = {"/api/generate": _run_generate, "/api/extract-profile": _run_extract,
                          "/api/extract-format": _run_extract_format}[self.path]
                nm = self.path.replace("/api/", "")
                threading.Thread(target=_gated,
                                 args=(target, nm, run, b, job, self._me()["name"],
                                       self._ip()), daemon=True).start()
                # `queued` để board nói ĐÚNG: người thứ 4 trở đi không "đang chạy", họ đang
                # XẾP HÀNG — hai chuyện khác nhau, và chỉ có ở đây mới biết được cái nào.
                self._json(200, {"started": True, "run": run,
                                 "queued": bool(job.get("queued")),
                                 "ahead": job.get("ahead", 0),
                                 "n_running": jobs.n_running(), "n_queued": jobs.n_queued()})
            elif self.path == "/api/forgot":
                # KHÔNG cần đăng nhập (đúng người cần nó là người không vào được). Ba hàng rào:
                #  · chặn theo IP (`_forgot_ok`)
                #  · **trả LỜI GIỐNG HỆT NHAU** dù tên có thật hay không — khác đi là biến ô
                #    này thành máy dò tên tài khoản, cùng luật với thông báo đăng nhập sai
                #  · `users.request_reset` gộp theo tên nên bấm 10 lần vẫn một dòng
                b = self._body()
                if not _forgot_ok(self._ip()):
                    self._json(429, {"error": "Bạn đã gửi quá nhiều yêu cầu — đợi ít phút, "
                                              "hoặc nhắn thẳng cho Owner."})
                else:
                    try:
                        users.request_reset(str(b.get("name") or ""), self._ip())
                    except Exception:                      # noqa: BLE001 — users.json hỏng
                        pass                               # vẫn trả câu giống hệt, không lộ gì
                    self._json(200, {"ok": True, "msg":
                        "Đã ghi nhận. Owner sẽ cấp cho bạn một mật khẩu tạm — nhắn cho họ "
                        "để nhận. (Nếu tên bạn gõ không có trong hệ thống thì cũng hiện "
                        "đúng câu này, nên hãy kiểm tra lại tên đăng nhập.)"})
            elif self.path == "/api/reset-approve":
                # Owner DUYỆT → server sinh mật khẩu tạm, trả về ĐÚNG MỘT LẦN cho Owner đọc
                # lại cho người kia. Không lưu bản trần ở đâu cả; Owner đóng cửa sổ là mất,
                # lúc đó chỉ còn cách cấp lại cái mới.
                b = self._body()
                nm = str(b.get("name") or "").strip()
                if not users.find(nm):
                    self._json(404, {"error": f"Không có người tên '{nm}'"})
                else:
                    pw = users.gen_password()
                    users.set_password(nm, pw, by=self._me()["name"], must_change=True)
                    access.revoke_user(nm)                 # mọi phiên cũ của họ tắt ngay
                    self._json(200, {"ok": True, "name": nm, "password": pw})
            elif self.path == "/api/reset-drop":
                b = self._body()
                nm = str(b.get("name") or "").strip()
                self._json(200, {"ok": users.drop_reset(nm), "name": nm})
            elif self.path == "/api/change-password":
                # ĐỔI MẬT KHẨU CỦA CHÍNH MÌNH. **Bắt buộc gõ mật khẩu CŨ**: không thì ai mượn
                # được cái tab đang mở là chiếm luôn tài khoản. `/api/user-passwd` (Owner đặt
                # lại cho người khác) cố ý KHÔNG đòi cũ — đó là hai việc khác nhau.
                b = self._body()
                me = self._me()
                if not access.per_user() or not me["name"]:
                    self._json(400, {"error": "Chưa bật tài khoản riêng — không có mật khẩu "
                                              "cá nhân để đổi"})
                elif not users.check(me["name"], str(b.get("old") or "")):
                    self._json(401, {"error": "Mật khẩu hiện tại không đúng"})
                else:
                    try:
                        users.set_password(me["name"], str(b.get("new") or ""))
                        # KHÔNG đá phiên của chính mình ra: người vừa đổi mật khẩu đang ngồi
                        # đây, bắt đăng nhập lại chỉ tổ phiền. Phiên KHÁC của họ thì huỷ.
                        keep = self._tok()
                        access.revoke_user(me["name"])
                        access.keep_alive(keep, me["name"])
                        self._json(200, {"ok": True})
                    except RuntimeError as e:
                        self._json(400, {"error": str(e)})
            elif self.path in ("/api/user-save", "/api/user-passwd",
                               "/api/user-disable", "/api/user-remove"):
                b = self._body()
                nm = str(b.get("name") or "").strip()
                try:
                    if self.path == "/api/user-save":
                        pw = str(b.get("password") or "")
                        if users.find(nm):
                            u = users.set_role(nm, str(b.get("role") or ""))
                            u = users.set_markets(nm, b.get("markets") or [])
                            u = users.set_channels(nm, b.get("channels") or [])
                            u = users.set_niches(nm, b.get("niches") or [])
                            if pw:
                                u = users.set_password(nm, pw)
                                # Đổi mật khẩu thì MỌI PHIÊN CŨ phải chết — không thì người bị
                                # đổi mật khẩu vẫn dùng tiếp tab đang mở suốt 30 ngày.
                                access.revoke_user(nm)
                        else:
                            u = users.add(nm, pw, str(b.get("note") or ""),
                                          role=str(b.get("role") or ""),
                                          markets=b.get("markets") or [],
                                          channels=b.get("channels") or [],
                                          niches=b.get("niches") or [])
                        # Hạ vai / thu hẹp phạm vi có hiệu lực ngay vì `access.current()` đọc
                        # lại từ đĩa mỗi request — không cần đá phiên ra.
                        self._json(200, {"ok": True, "user": u})
                    elif self.path == "/api/user-passwd":
                        # Owner đặt hộ ⇒ Owner BIẾT mật khẩu đó ⇒ bắt buộc `must_change`.
                        # Không ép thì nó nằm lại vĩnh viễn trong khi hai người cùng biết.
                        u = users.set_password(nm, str(b.get("password") or ""),
                                               by=self._me()["name"], must_change=True)
                        access.revoke_user(nm)
                        self._json(200, {"ok": True, "user": u})
                    elif self.path == "/api/user-disable":
                        off = bool(b.get("disabled"))
                        u = users.set_disabled(nm, off)
                        if off:
                            access.revoke_user(nm)      # khoá mà phiên cũ còn chạy thì khoá vô nghĩa
                        self._json(200, {"ok": True, "user": u})
                    else:
                        ok = users.remove(nm)
                        access.revoke_user(nm)
                        self._json(200 if ok else 404, {"ok": ok} if ok
                                   else {"error": f"Không có người tên '{nm}'"})
                except RuntimeError as e:
                    # 400 = lỗi ĐẦU VÀO (trùng tên, mật khẩu ngắn, hạ Owner cuối cùng…),
                    # board hiện nguyên văn. Không phải lỗi server.
                    self._json(400, {"error": str(e)})
            elif self.path == "/api/export":
                b = self._body()
                run = b.get("run") or "gen"
                rd = common.run_dir(run, create=True)
                txt = b.get("text", "")
                # `text` rỗng thì TỪ CHỐI: ghi đè metadata.txt thành 0 byte rồi vẫn đánh dấu
                # "đã xuất" là mất bản đã xuất trước đó mà lịch sử vẫn báo xanh — im lặng và sai.
                if not txt.strip():
                    self._json(400, {"error": "Không có nội dung để xuất (field `text` rỗng) — "
                                              "chưa ghi đè metadata.txt, chưa đánh dấu đã xuất"})
                else:
                    (rd / "metadata.txt").write_text(txt, encoding="utf-8")
                    library.mark_export(run, b.get("picked_title", ""))   # lịch sử: title NÀO đã dùng thật
                    self._json(200, {"ok": True, "path": str(rd / "metadata.txt")})
            elif self.path == "/api/set-channel-owner":
                # ĐỔI CHỦ KÊNH — từ LEADER trở lên. Cần có vì hai lý do THẬT, không phải cho đủ bộ:
                #  (1) kênh tạo trước 02/08/2026 không ai đứng tên ⇒ dưới luật mới thì Leader
                #      lẫn Seo đều không sửa được, mà không có đường nào gán chủ;
                #  (2) bàn giao kênh khi người phụ trách đổi (nghỉ việc, chuyển niche).
                # Lý do (2) trước đây là *"Seo không có quyền extract nên không bao giờ tự tạo
                # được kênh"* — KHÔNG CÒN ĐÚNG từ 2026-08-02: Seo có `extract_chan`, tự thêm
                # kênh là tự làm chủ. Đổi chủ nay là việc BÀN GIAO, không phải đường sống duy
                # nhất để Seo có kênh mà sửa.
                # Nhận tên RỖNG = gỡ chủ (trả kênh về diện chỉ Manager/Owner sửa).
                b = self._body()
                sl = common.slug(str(b.get("slug") or ""))
                nm = str(b.get("owner") or "").strip()
                p = library.load(sl)
                if not p:
                    self._json(404, {"error": "Không thấy kênh này"})
                elif nm and not users.find(nm):
                    # Gán cho một cái tên KHÔNG TỒN TẠI thì kênh thành không ai sửa được, mà
                    # màn hình vẫn ghi tên đó — đúng kiểu hỏng câm. Chặn ngay.
                    self._json(400, {"error": f"Không có tài khoản tên '{nm}'"})
                else:
                    old = (p.get("created_by") or "").strip()
                    library.set_owner(sl, nm)
                    self._json(200, {"ok": True, "slug": sl, "owner": nm, "old_owner": old})
            elif self.path == "/api/update-profile":
                b = self._body()
                try:
                    # MÃ KÊNH đi ĐƯỜNG RIÊNG có luật vai (user chốt 2026-08-04): Seo sửa được
                    # đúng 1 lần/kênh, Leader+ tự do — `library.set_code` giữ luật + cờ đếm.
                    # Chạy TRƯỚC update: mã bị chặn (hết lượt/trùng) thì trả lỗi ngay, KHÔNG
                    # lưu nửa form rồi báo lỗi nửa kia — user tưởng lưu hỏng cả.
                    if str(b.get("code") or "").strip():
                        library.set_code(b.get("slug", ""), b["code"],
                                         (self._me() or {}).get("role", ""))
                    self._json(200, {"ok": True, "profile": library.update(b.get("slug", ""), b)})
                except RuntimeError as e:              # luật mã kênh / không thấy profile
                    self._json(400, {"error": str(e)})
                except Exception as e:                 # noqa: BLE001 — profile không tồn tại
                    self._json(404, {"error": str(e)})
            elif self.path == "/api/save-market":
                b = self._body()
                try:
                    self._json(200, {"ok": True, "market": markets.save(
                        b.get("name", ""), b.get("lang", ""), b.get("note", ""),
                        old=b.get("old", ""))})
                except Exception as e:                     # noqa: BLE001 — trùng tên / tên rỗng
                    self._json(400, {"error": str(e)})     # 400 vì đây là lỗi ĐẦU VÀO, board hiện nguyên văn
            elif self.path == "/api/delete-market":
                b = self._body()
                # Xoá NHÓM, không đụng `lang` của kênh/format — chúng là dữ liệu thật đã khai.
                self._json(200, {"ok": markets.remove(b.get("name", ""))})
            elif self.path == "/api/set-langs":
                # Khai ngôn ngữ HÀNG LOẠT cho format (và kênh) — nếu không có đường này thì
                # tính năng "trang chủ theo ngôn ngữ" không dùng được: 0/10 format của user
                # đang chưa khai, tức mọi ngôn ngữ đều có tab FORMAT rỗng.
                # BÁO TỪNG MỤC, kể cả mục bỏ qua: khai 10 mà chỉ vào 8 rồi im lặng là đúng thứ
                # user đã phàn nàn ở `add_many`.
                b = self._body()
                done, skip = [], []
                for it in (b.get("items") or []):
                    slug, lang = str(it.get("slug", "")), str(it.get("lang", "")).strip()
                    kind = it.get("kind", "format")
                    if not slug or not lang:
                        skip.append({"slug": slug, "why": "thiếu slug hoặc ngôn ngữ"})
                        continue
                    try:
                        if kind == "profile":
                            library.update(slug, {"lang": lang})
                        else:
                            niche_format.update(slug, {"lang": lang})
                        done.append({"slug": slug, "lang": lang, "kind": kind})
                    except Exception as e:                 # noqa: BLE001
                        skip.append({"slug": slug, "why": str(e)})
                self._json(200, {"ok": True, "done": done, "skipped": skip})
            elif self.path == "/api/update-format":
                b = self._body()
                try:
                    self._json(200, {"ok": True, "format": niche_format.update(b.get("slug", ""), b)})
                except Exception as e:                 # noqa: BLE001
                    self._json(404, {"error": str(e)})
            elif self.path == "/api/save-episode":
                b = self._body()
                try:
                    self._json(200, {"ok": True, "episode": episodes.save(b)})
                except Exception as e:                     # noqa: BLE001 — thiếu tên tập
                    self._json(400, {"error": str(e)})
            elif self.path == "/api/niche-add-many":
                b = self._body()
                try:
                    self._json(200, niches.add_many(b.get("niche", ""), b.get("raw", ""),
                                                    kind=b.get("kind", "titles")))
                except Exception as e:                     # noqa: BLE001
                    self._json(400, {"error": str(e)})
            elif self.path == "/api/niche-remove":
                b = self._body()
                try:
                    self._json(200, niches.remove(b.get("niche", ""), b.get("items") or [],
                                                  kind=b.get("kind", "titles")))
                except Exception as e:                     # noqa: BLE001
                    self._json(400, {"error": str(e)})
            elif self.path == "/api/niche-add-title":
                # Thêm ĐÚNG 1 title, có check trùng. Trả 200 cả khi TỪ CHỐI: đây không phải lỗi
                # server, mà là kết quả kiểm — board đọc `kind` để hiện đúng thông báo/hỏi lại.
                b = self._body()
                try:
                    self._json(200, niches.add_title(b.get("niche", ""), b.get("title", ""),
                                                     force=bool(b.get("force"))))
                except Exception as e:                     # noqa: BLE001
                    self._json(400, {"error": str(e)})
            elif self.path == "/api/delete-episode":
                tok = episodes.delete(self._body().get("slug", ""))
                self._json(200 if tok else 404,
                           {"ok": True, "undo": tok} if tok else {"error": "không thấy tập"})
            elif self.path == "/api/restore":
                r = common.restore(self._body().get("token", ""))
                if r is None:
                    self._json(404, {"error": "Mục này đã hết hạn 24h hoặc đã khôi phục rồi"})
                elif r.get("outside"):
                    self._json(409, {"error": "Bản trong thùng rác trỏ ra NGOÀI dự án "
                                              f"({r.get('orig', '')}) — có thể .trash/ mang từ máy "
                                              "khác sang. KHÔNG khôi phục để không ghi bừa ra ngoài; "
                                              "mục vẫn còn trong thùng rác."})
                elif r.get("conflict"):
                    # Thông báo cũ bảo "đổi tên mục hiện tại" — mà UI KHÔNG có chỗ đổi tên file,
                    # nên user bị dồn vào việc xoá bản đang có để trả lại tên = tự phá dữ liệu.
                    self._json(409, {"error": "Đã có mục cùng tên trong dự án (có thể bạn vừa "
                                              "Extract lại). KHÔNG khôi phục để tránh đè mất bản "
                                              "đang dùng. Muốn lấy bản trong thùng rác thì đổi tên "
                                              f"file {r.get('orig', '')} bằng Explorer rồi bấm lại."})
                else:
                    self._json(200, {"ok": True, **r})
            elif self.path == "/api/purge":
                # XOÁ HẲN khỏi thùng rác. Board đã confirm; ở đây chỉ chạm file trong .trash/.
                # `at` = deleted_at mà panel thấy lúc liệt kê → chặn ca panel cũ xoá mất bản MỚI.
                b = self._body()
                try:
                    r = common.purge_one(b.get("token", ""), at=b.get("at"))
                except Exception as e:                     # noqa: BLE001 — file bị giữ/chỉ-đọc
                    # Không bọc thì exception xuyên do_POST ⇒ client mất kết nối, KHÔNG có response:
                    # board chỉ hiện "Lỗi xoá: Failed to fetch" và cửa sổ server phun traceback.
                    self._json(500, {"error": str(e)})
                else:
                    if r is None:
                        self._json(404, {"error": "Không còn mục này trong thùng rác"})
                    elif r.get("changed"):
                        self._json(409, {"error": "Mục này đã thay đổi từ lúc bạn mở danh sách "
                                                  "(có thể bạn vừa xoá lại kênh đó) — đóng rồi mở "
                                                  "lại thùng rác để xem bản hiện tại"})
                    else:
                        self._json(200, {"ok": True, **r})
            elif self.path == "/api/gen-cta":
                # 1 call LLM ngắn, KHÔNG tốn quota YouTube → chạy đồng bộ, không chiếm chỗ job nào.
                # cta.generate đo token bằng delta nên job khác đang chạy cũng không bị xoá sổ usage.
                b = self._body()
                try:
                    from . import cta                   # noqa: PLC0415 — lazy như các module khác
                    self._json(200, {"ok": True, **cta.build(b.get("slug", ""))})
                except Exception as e:                 # noqa: BLE001
                    self._json(400, {"error": str(e)})
            elif self.path == "/api/format-del-competitor":
                b = self._body()
                try:
                    self._json(200, {"ok": True, "format": niche_format.remove_competitor(
                        b.get("slug", ""), b.get("channel_id", ""))})
                except Exception as e:                 # noqa: BLE001
                    self._json(404, {"error": str(e)})
            elif self.path == "/api/delete-format":
                sl = common.slug(self._body().get("slug", ""))
                tok = common.trash(niche_format.formats_dir() / f"{sl}.json", "formats") if sl else None
                self._json(200 if tok else 404,
                           {"ok": True, "undo": tok} if tok else {"error": "không thấy format"})
            elif self.path == "/api/delete-profile":
                sl = common.slug(self._body().get("slug", ""))
                tok = common.trash(common.profiles_dir() / f"{sl}.json", "profiles") if sl else None
                self._json(200 if tok else 404,
                           {"ok": True, "undo": tok} if tok else {"error": "không thấy profile"})
            elif self.path == "/api/admin-keys":
                # Ghi key (tab QUẢN TRỊ) — .env nguyên tử + đồng bộ os.environ, ăn ngay
                # không restart. Đang trong DATA_LOCK nên hai người bấm Lưu không đè nhau.
                try:
                    self._json(200, {"ok": True, **admin_keys.save(self._body())})
                except ValueError as e:
                    self._json(400, {"error": str(e)})
            else:
                self._json(404, {})

    return H


def _run_extract(run: str, body: dict, job: dict, who: str = "", ip: str = "") -> None:
    try:
        job.update(step="extract profile…")
        from . import profile                         # noqa: PLC0415
        prof = profile.extract(body, job)
        jobs.finish(run, result={"slug": prof.get("slug", ""), "channel": prof.get("channel", ""),
                                 "code": prof.get("code", "")})
        _done(who, ip, "extract-profile", run, slug=prof.get("slug", ""))
    except Exception as e:                             # noqa: BLE001
        jobs.finish(run, error=str(e))
        _done(who, ip, "extract-profile", run, err=str(e))


def _run_extract_format(run: str, body: dict, job: dict, who: str = "", ip: str = "") -> None:
    """Module 3 — dán URL đối thủ trong niche → Format Profile (quota ~3-4 unit/kênh)."""
    try:
        job.update(step="đọc URL…")
        out = niche_format.extract(body, job)
        # chỉ giữ phần board cần báo lại (URL dán nhầm vào ô tên đã bị bỏ) — không nhồi cả
        # format vào status, poll 1 giây/lần mà kèm cả package thì phí băng thông vô ích
        # `dup_skipped` PHẢI đi kèm: dán 5 URL mà 2 cái đã có sẵn thì user chỉ thấy 3
        # Format mới và tự hỏi 2 cái kia đi đâu. Bỏ dòng nào thì phải nói dòng nào.
        jobs.finish(run, result={"name_ignored": out.get("name_ignored", ""),
                                 "dup_skipped": out.get("dup_skipped", [])})
        _done(who, ip, "extract-format", run)
    except Exception as e:                             # noqa: BLE001
        jobs.finish(run, error=str(e))
        _done(who, ip, "extract-format", run, err=str(e))


LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}


def lan_ip() -> str:
    """IP của máy này trong mạng, để IN RA cho user biết chia sẻ địa chỉ nào.

    Không gửi gói nào cả — `connect` trên UDP chỉ chọn route. Hỏng thì trả rỗng, đừng đoán.
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
        finally:
            s.close()
    except Exception:                                  # noqa: BLE001 — máy không có mạng
        return ""


# ── VÂN TAY DỮ LIỆU — để board của người khác biết mà tự cập nhật ───────────────────────
# Quét `stat()` chứ KHÔNG đếm bằng một biến trong bộ nhớ: biến đếm chỉ biết những thay đổi
# đi qua chính tiến trình này, nên `git pull` hay sửa file tay là nó nói dối rằng "không có
# gì mới". Quét đĩa thì thay đổi kiểu nào cũng thấy.
# Đo thật trên dữ liệu của user: 0,769 ms/lần ⇒ 7 người poll 1,5 giây/lần tốn 0,36% CPU.
# `runs/` CỐ Ý không nằm trong này: nó đổi liên tục suốt lúc sinh, đưa vào là board mọi người
# nhấp nháy cập nhật trong khi chẳng có gì họ cần thấy đổi. Việc "tập này đã sinh xong chưa"
# đi qua `episodes/*.json` (attach_run) nên vẫn bắt được.
# `logs/` cũng không: nó đổi theo từng thao tác, kể cả thao tác chỉ đọc.
_DATA_DIRS = ("profiles", "formats", "episodes", "niches")
_DATA_FILES = ("markets.json", "users.json")


def data_version() -> str:
    """Chuỗi đổi khi BẤT KỲ file dữ liệu nào thêm/sửa/xoá. Không đọc nội dung file."""
    n = mx = tong = 0
    for d in _DATA_DIRS:
        p = common.ROOT / d
        if not p.is_dir():
            continue
        try:
            with os.scandir(p) as it:
                for e in it:
                    if not e.name.endswith(".json"):
                        continue
                    st = e.stat()
                    n += 1; tong += st.st_size; mx = max(mx, st.st_mtime_ns)
        except OSError:                                # thư mục bị xoá giữa chừng — bỏ qua
            continue
    for f in _DATA_FILES:
        p = common.ROOT / f
        try:
            st = p.stat()
        except OSError:
            continue
        n += 1; tong += st.st_size; mx = max(mx, st.st_mtime_ns)
    # Cả BA con số, đừng bớt: chỉ `mx` thì sửa file rồi trả mtime cũ là không thấy; chỉ `n`
    # thì xoá 1 thêm 1 trong cùng một giây là hoà; chỉ `tong` thì đổi chữ mà giữ độ dài là lọt.
    return f"{n}-{mx}-{tong}"


def run(port: int, host: str = "127.0.0.1") -> None:
    shared = host not in LOCAL_HOSTS
    # ── HÀNG RÀO: mở ra mạng mà không có mật khẩu thì TỪ CHỐI CHẠY ──────────────────
    # Không phải cảnh báo rồi vẫn chạy: `.env` có 1 khoá z.ai + 19 khoá YouTube, và 6 endpoint
    # xoá dữ liệu không xác thực. Chạy tiếp là để user tưởng mình đã chia sẻ an toàn.
    if shared and not access.enabled():
        raise SystemExit(
            f"TỪ CHỐI CHẠY: đang bind {host} (mở ra mạng) mà chưa đặt BOARD_PASSWORD.\n"
            "  Ai vào được mạng này cũng xoá được kênh/format/tập của bạn và tiêu hết\n"
            "  quota YouTube + tiền LLM — không cần mật khẩu gì cả.\n\n"
            "  Cách sửa: thêm vào .env một dòng   BOARD_PASSWORD=<mật khẩu bạn chọn>\n"
            "  (.env đọc bằng utf-8-sig; ĐỪNG sửa bằng PowerShell Set-Content, nó thêm BOM)\n\n"
            "  Chỉ dùng một mình thì bỏ --host đi, mặc định 127.0.0.1 là an toàn sẵn.")
    # Trần call LLM toàn server — chỉnh được vì mỗi nhà cung cấp một mức chịu đựng khác nhau,
    # và người dùng mới là người biết gói mình mua tới đâu. Không có cách nào đoán hộ.
    try:
        _mp = int(os.environ.get("LLM_MAX_PARALLEL") or 0)
    except ValueError:
        _mp = 0
    if _mp:
        llm.set_global_parallel(_mp)

    srv = ThreadingHTTPServer((host, port), make_handler())
    url = f"http://127.0.0.1:{port}/"
    print(f"SEO Optimize board: {url}  (Ctrl+C để dừng)", flush=True)
    if shared:
        ip = lan_ip()
        print(f"  chia sẻ trong mạng: http://{ip or '<ip-máy-này>'}:{port}/", flush=True)
        print("  mật khẩu: ĐÃ BẬT", flush=True)
        print("  KHUYẾN CÁO: chỉ dùng trong VPN nội bộ (Tailscale/LAN). Mật khẩu đi qua HTTP\n"
              "  thường nên phơi thẳng ra internet công cộng là nghe trộm được.", flush=True)
    elif access.enabled():
        print("  mật khẩu: ĐÃ BẬT (đang chạy nội bộ nên vẫn phải đăng nhập)", flush=True)
    print(f"  sinh cùng lúc: {jobs.MAX_RUNNING} · hàng đợi tối đa {jobs.QUEUE_MAX} · "
          f"call LLM cùng lúc tối đa {llm.GLOBAL_PARALLEL}", flush=True)
    try:
        keys = common.load_keys()
        print(f"YouTube key: {len(keys)} · profiles: {len(_profiles())}", flush=True)
    except RuntimeError as e:
        # V3: khóa lấy từ KÉT mỗi lượt extract — gateway chưa lên / việc chưa cấp phát
        # thì app VẪN PHẢI SỐNG (dòng này chỉ là đếm key lúc boot); thông điệp rõ sẽ
        # hiện đúng lúc user bấm extract. Chết ở đây là khóa-chưa-cấp giết cả board.
        print(f"  YouTube key: CHƯA lấy được — {e}", flush=True)
    if not shared and not _sso_bat():
        # chạy nền sau gateway (SSO) thì tuyệt đối không bật trình duyệt trên máy chủ
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nĐã dừng server.")


def main(argv: list[str] | None = None) -> None:
    common.load_env()
    ap = argparse.ArgumentParser(description="SEO Optimize board GUI")
    ap.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8760)))
    ap.add_argument("--host", default=os.environ.get("BIND_HOST", "127.0.0.1"),
                    help="0.0.0.0 để chia sẻ trong mạng (BẮT BUỘC có BOARD_PASSWORD)")
    a = ap.parse_args(argv)
    run(a.port, a.host)


def selftest() -> int:
    """`python -m seo.server --selftest` — soi BẢNG QUYỀN, không dựng server.

    Chốt quan trọng nhất: **mọi endpoint có trong file đều phải khai quyền**. Quên khai thì
    `_need_perm` rơi về `users` (chỉ Owner) — an toàn nhưng câm: người khác bấm nút thì nhận
    403 khó hiểu. Bộ kiểm này bắt lúc viết code, không đợi tới lúc user gặp.
    """
    import re                                            # noqa: PLC0415
    src = Path(__file__).read_text(encoding="utf-8")
    # Chỉ lấy phần THÂN handler, bỏ chính bảng PERM_OF (nếu không thì nó tự khớp với mình).
    body = src.split("def make_handler(", 1)[1]
    # BỎ CHÚ THÍCH TRƯỚC KHI SOI. Bẫy đã cắn ngay lần chạy đầu: chính câu chú thích mô tả mẫu
    # `self.path in ("/api/x", …)` bị đếm thành một endpoint tên `/api/x`. File này ghi rất
    # nhiều bài học dạng "đường này gọi thế", nên mọi phép dò đều phải chạy trên bản đã dọn.
    body = re.sub(r"(?m)^\s*#.*$", "", body)
    # Hai kiểu định tuyến, phải bắt CẢ HAI: `path == "/api/x"` và `self.path in ("/api/x", …)`.
    # Bản đầu chỉ bắt kiểu thứ nhất nên báo 3 endpoint (generate, extract-*) là "đã gỡ" trong
    # khi chúng đang chạy — bộ kiểm chỉ đúng bằng độ đầy đủ của phép dò.
    found = set(re.findall(r'path == "(/api/[a-z-]+)"', body))
    for grp in re.findall(r'self\.path in \(([^)]*)\)', body):
        found |= set(re.findall(r'"(/api/[a-z-]+)"', grp))
    declared = set(PERM_OF) | _OPEN
    missing = sorted(found - declared)
    stale = sorted(declared - found - {"/api/version"})
    bad = 0
    if missing:
        bad += 1
        print("  THIẾU KHAI QUYỀN (sẽ chỉ Owner gọi được, và không ai hiểu vì sao):")
        for p in missing:
            print("    ", p)
    else:
        print(f"  [ok]   {len(found)} endpoint đều đã khai quyền")
    if stale:
        print("  [chú ý] khai trong PERM_OF mà không thấy trong handler (endpoint đã gỡ?):")
        for p in stale:
            print("    ", p)
    for p, perm in PERM_OF.items():
        if perm not in roles.PERMS:
            bad += 1
            print(f"  QUYỀN LẠ: {p} -> '{perm}' không có trong roles.PERMS")
    # Không endpoint XOÁ nào được rơi xuống mức thấp hơn `delete` — TRỪ `niche-remove`, cố ý
    # ở `bank_del` để Leader xoá được kho mà vẫn không xoá được kênh/format/tập/thị trường.
    for p in PERM_OF:
        # HAI ngoai le tuong minh, deu do user chot: `niche-remove` o `bank_del` va
        # `delete-format` o `fmt_del` (Leader tro len). Liet ke tay chu khong noi long
        # dieu kien — noi long la lan sau them mot endpoint xoa hoi hot cung lot.
        if p in ("/api/niche-remove", "/api/delete-format"):
            continue
        # `/api/restore` CỐ Ý không nằm ở đây nữa: nó KHÔI PHỤC chứ không xoá.
        if ("delete" in p or p == "/api/purge") and PERM_OF[p] != "delete":
            bad += 1
            print(f"  NGUY HIỂM: {p} là thao tác xoá mà chỉ đòi '{PERM_OF[p]}'")
    # Seo/Leader tuyệt đối không được chạm tới endpoint `delete`
    for r in ("seo", "leader"):
        for p, perm in PERM_OF.items():
            if perm == "delete" and roles.can(r, perm):
                bad += 1
                print(f"  NGUY HIỂM: vai {r} gọi được {p}")
    # ĐÚNG NHỮNG GÌ USER CHỐT — chốt thẳng trên bảng endpoint, không chỉ trên bảng vai
    must = [("leader", "/api/restore", True,  "Leader phải KHÔI PHỤC được đồ xoá nhầm"),
            ("leader", "/api/purge",   False, "Leader vẫn KHÔNG được dọn hẳn thùng rác"),
            ("leader", "/api/delete-profile", False, "Leader vẫn KHÔNG được xoá kênh"),
            ("leader", "/api/set-channel-owner", True, "Leader phải đổi được chủ kênh"),
            ("seo",    "/api/restore", False, "Seo không khôi phục"),
            ("seo",    "/api/set-channel-owner", False, "Seo không đụng phân quyền kênh"),
            ("seo", "/api/niche-add-many", True,  "Seo phải THÊM được vào kho"),
            ("seo", "/api/niche-remove",   False, "Seo KHÔNG được xoá kho"),
            ("leader", "/api/niche-remove", True, "Leader phải xoá được kho"),
            ("leader", "/api/delete-market", False, "Leader KHÔNG được xoá thị trường"),
            ("manager", "/api/delete-market", True, "Manager phải xoá được thị trường"),
            ("seo", "/api/delete-profile", False, "Seo KHÔNG được xoá kênh"),
            # User chốt 2026-08-02: Seo TỰ THÊM kênh của mình và LÀ CHỦ kênh đó. Hai dòng này
            # phải đi cùng nhau — tự thêm được, nhưng không dựng Format đối thủ.
            ("seo", "/api/extract-profile", True, "Seo phải TỰ THÊM được kênh của mình"),
            # User chốt lại 2026-08-02: Seo NẠP được Format (hàng rào chuyển sang chống
            # trùng link), nhưng KHÔNG xoá Format — hai vế phải đi cùng nhau.
            ("seo", "/api/extract-format", True, "Seo phải NẠP được Format đối thủ"),
            ("seo", "/api/delete-format", False, "Seo KHÔNG xoá được Format"),
            ("leader", "/api/delete-format", True, "Leader phải xoá được Format"),
            ("leader", "/api/delete-profile", False, "...nhưng vẫn KHÔNG xoá được KÊNH")]
    for r, p, want, why in must:
        if roles.can(r, PERM_OF[p]) != want:
            bad += 1
            print(f"  SAI YÊU CẦU: {why} (vai {r} → {p})")

    # ── LÀM CHỦ KÊNH KHÔNG BAO GIỜ MỞ RA QUYỀN XOÁ (user chốt 2026-08-02) ──────────────
    # Nguyên văn: *"kể cả chủ kênh nếu mà ở vị trí SEO thì cũng không thể xoá kênh, phải
    # thông qua manager hoặc owner"*. Hai trục ĐỘC LẬP: `chan_owner`/`created_by` trả lời
    # *"ai được SỬA kênh này"*, còn `delete` là một quyền RIÊNG ở cấp vai.
    # Vì sao phải chốt lại dù bảng trên đã nói: thứ tự gác mới là thứ giữ luật này. `_need_perm`
    # xét `PERM_OF` **TRƯỚC**, `_scope_deny` (chỗ duy nhất đọc `created_by`) chạy **SAU** ⇒
    # quyền sở hữu không có đường nào chen lên trước để mở cửa. Đảo hai bước đó — dù chỉ để
    # "gộp cho gọn" — là chủ kênh cấp Seo xoá được kênh mình, và không ai nhận ra cho tới lúc
    # mất một kênh thật. Đo LIVE bằng tài khoản thật: seoB làm chủ kênh vẫn ăn 403.
    _own = {"role": "seo", "name": "an"}
    _prof = {"slug": "k", "created_by": "an"}
    if not roles.can_write_profile(_own, _prof):
        bad += 1
        print("  SAI YÊU CẦU: chủ kênh cấp Seo phải SỬA được kênh của mình")
    if roles.can("seo", PERM_OF["/api/delete-profile"]):
        bad += 1
        print("  NGUY HIỂM: chủ kênh cấp Seo lại XOÁ được kênh — phải qua Manager/Owner")
    # Cùng luật với Leader: làm chủ kênh cũng không mở ra quyền xoá.
    if roles.can("leader", PERM_OF["/api/delete-profile"]):
        bad += 1
        print("  NGUY HIỂM: Leader xoá được kênh")
    # ── NICHE/NGÔN NGỮ MỚI: Seo không tạo, trùng-ký-tự dùng lại bản cũ (user chốt 04/08) ──
    # Test trên thư mục TẠM — _ten_hien_co đọc profiles/formats/episodes/markets thật, không
    # cách ly là selftest phụ thuộc dữ liệu vận hành (và bẩn theo nó).
    import tempfile as _tf
    from pathlib import Path as _Path
    _old_root, _old_profiles, _old_runs = common.ROOT, common.PROFILES, common.RUNS
    try:
        with _tf.TemporaryDirectory() as _tmp:
            common.ROOT = _Path(_tmp)
            common.PROFILES = _Path(_tmp) / "profiles"
            common.RUNS = _Path(_tmp) / "runs"
            common.write_json(common.profiles_dir(create=True) / "k1.json",
                              {"channel": "K1", "code": "K-01", "niche": "Life In", "lang": "English"})
            assert _chuan_hoa_ten("  ĐỜI  Sống ") == _chuan_hoa_ten("doi song")
            _seo, _ld = {"role": "seo"}, {"role": "leader"}
            b = {"slug": "k1", "niche": "life   in", "lang": "ENGLISH"}
            assert _niche_lang_deny("/api/update-profile", b, _seo) == ""
            if not (b["niche"] == "Life In" and b["lang"] == "English"):
                bad += 1
                print("  SAI: trùng ký tự phải DÙNG LẠI đúng chính tả cũ", b)
            if "Seo" not in _niche_lang_deny("/api/update-profile", {"niche": "Niche La Hoac"}, _seo):
                bad += 1
                print("  SAI: Seo tạo niche MỚI phải bị chặn")
            if _niche_lang_deny("/api/update-profile", {"niche": "Niche La Hoac"}, _ld):
                bad += 1
                print("  SAI: Leader phải tạo được niche mới")
            if "Seo" not in _niche_lang_deny("/api/extract-format", {"lang": "Klingon"}, _seo):
                bad += 1
                print("  SAI: Seo tạo ngôn ngữ MỚI phải bị chặn")
            b2 = {"items": [{"kind": "format", "slug": "x", "lang": "english"}]}
            assert _niche_lang_deny("/api/set-langs", b2, _seo) == ""
            if b2["items"][0]["lang"] != "English":
                bad += 1
                print("  SAI: set-langs phải canonical hoá từng dòng", b2)
            if _niche_lang_deny("/api/generate", {"niche": "Tuy Y"}, _seo):
                bad += 1
                print("  SAI: path ngoài _NL_PATHS không được chặn")
    finally:
        common.ROOT, common.PROFILES, common.RUNS = _old_root, _old_profiles, _old_runs
    print("server.py selftest " + ("OK" if not bad else f"{bad} LOI"))
    return 1 if bad else 0


if __name__ == "__main__":
    import sys
    if sys.argv[1:2] == ["--selftest"]:
        raise SystemExit(selftest())
    main()
