"""Auth Phase 4: mật khẩu scrypt (stdlib) + session cookie (token ngẫu nhiên trong DB).

Session 30 ngày, cookie httponly + samesite=lax. Server hiện chạy sau localhost/
Docker LAN; khi lên VPS có HTTPS thì bật secure cookie (RADARY_SECURE_COOKIE=1).
Đăng ký với email đã có mật khẩu → 409; email tồn tại CHƯA có mật khẩu (tài khoản
migrate từ Phase 1) → lần đăng ký đầu chính là đặt mật khẩu (bootstrap).
"""
import hashlib, hmac, os, secrets, time
from fastapi import HTTPException, Request, Response

SESSION_DAYS = 30
COOKIE = 'radary_session'

def hash_password(pw):
    salt = secrets.token_bytes(16)
    h = hashlib.scrypt(pw.encode(), salt=salt, n=2**14, r=8, p=1)
    return salt.hex() + '$' + h.hex()

def verify_password(pw, stored):
    if not stored or '$' not in stored: return False
    salt_hex, h_hex = stored.split('$', 1)
    h = hashlib.scrypt(pw.encode(), salt=bytes.fromhex(salt_hex), n=2**14, r=8, p=1)
    return hmac.compare_digest(h.hex(), h_hex)

def create_session(conn, user_id):
    token = secrets.token_urlsafe(32)
    now = time.time()
    with conn:
        conn.execute('DELETE FROM sessions WHERE expires_ts < ?', (now,))
        conn.execute('INSERT INTO sessions(token, user_id, created_ts, expires_ts) VALUES(?,?,?,?)',
                     (token, user_id, now, now + SESSION_DAYS*86400))
    return token

def set_cookie(resp: Response, token):
    resp.set_cookie(COOKIE, token, max_age=SESSION_DAYS*86400, httponly=True, samesite='lax',
                    secure=os.environ.get('RADARY_SECURE_COOKIE') == '1')

def clear_session(conn, request: Request, resp: Response):
    token = request.cookies.get(COOKIE)
    if token:
        with conn: conn.execute('DELETE FROM sessions WHERE token=?', (token,))
    resp.delete_cookie(COOKIE)

# ===== SSO: nhận danh tính từ OUTLIERY (một cổng đăng nhập duy nhất) =====
# Bật bằng RADARY_TRUST_PROXY=1. Khi tắt (mặc định) mọi thứ chạy y như cũ.
#
# HAI VAN AN TOÀN — đừng gỡ cái nào:
#   1. Chỉ tin header khi client là LOOPBACK (127.0.0.1/::1). Radary bind 127.0.0.1 nên chỉ
#      OUTLIERY trên cùng máy tới được; nếu sau này ai mở radary ra LAN thì header giả từ ngoài
#      vẫn bị chặn ở đây, không phải chỉ dựa vào "app đang bind localhost".
#   2. Người dùng SSO được tạo KHÔNG có mật khẩu → không thể đăng nhập đường thường bằng tài
#      khoản đó; chỉ vào được qua OUTLIERY (nơi đã có đăng nhập + phân quyền bộ phận × level).
#
# V3 (Permissions v2 — DE.md mục 14): vai NỘI BỘ dịch từ X-Remote-Actions, KHÔNG
# còn RADARY_SSO_MAP (bài học map-theo-tên-đăng-nhập chết lặng lẽ khi hệ tài khoản
# thay máu — luật ghim #3: nối bằng mã, cấm map tên). Tài khoản SSO luôn là
# `<ten>@outliery.local`, OUTLIERY là nguồn sự thật duy nhất của vai.
# 04/08/2026 thêm 'manager' (luật OUTLIERY: Manager KHÔNG BAO GIỜ ngang Owner):
# manager = toàn quyền VẬN HÀNH (xóa video/kênh/pool, xóa cả workspace) nhưng KHÔNG
# đụng quản trị org (API key toàn org, thành viên, lời mời, cấu hình LLM — owner giữ).
_VAI_HOP_LE = ('viewer', 'leader', 'manager', 'owner')


def _la_loopback(request: Request) -> bool:
    return bool(request.client) and request.client.host in ('127.0.0.1', '::1', 'localhost')


def vai_tu_headers(headers) -> str:
    """Dịch claims V3 → vai NỘI BỘ radary (viewer < leader < manager < owner-nội-bộ).

    ƯU TIÊN X-Remote-Actions (Permissions v2 — gateway tính từ luật + tick lẻ +
    acting, chảy sang TỪNG request): quan_tri → owner (tab Quản trị đầy đủ) ·
    toan_quyen → manager (xóa vận hành, không đụng quản trị org) ·
    them_video/tao_pool → leader · còn lại viewer.
    THIẾU hẳn header Actions (gateway đời cũ) → fallback X-Remote-Role danh pháp
    chuẩn: admin → owner nội bộ; manager/leader/viewer giữ nguyên.
    DEFAULT viewer — fail-closed (luật ghim #9); user 'trắng' không nổ (#4)."""
    raw = headers.get('X-Remote-Actions')
    if raw is not None:
        hd = {s.strip() for s in raw.split(',') if s.strip()}
        if 'quan_tri' in hd:
            return 'owner'
        if 'toan_quyen' in hd:
            return 'manager'
        if hd & {'them_video', 'tao_pool'}:
            return 'leader'
        return 'viewer'
    vai = (headers.get('X-Remote-Role') or 'viewer').strip().lower()
    if vai == 'admin':
        return 'owner'
    return vai if vai in ('manager', 'leader', 'viewer') else 'viewer'


def _org_sso(conn) -> int | None:
    """Org để gắn người dùng SSO. RADARY_SSO_ORG thắng; mặc định org id nhỏ nhất (công ty chỉ
    có một org 'Outliery'). Không có org nào → None (không tạo bừa)."""
    tuy_chinh = os.environ.get('RADARY_SSO_ORG', '').strip()
    if tuy_chinh.isdigit():
        return int(tuy_chinh)
    r = conn.execute('SELECT MIN(id) AS id FROM orgs').fetchone()
    return r['id'] if r and r['id'] else None


def user_from_proxy(conn, request: Request):
    """Danh tính do OUTLIERY truyền sang, hoặc None nếu không dùng được đường này."""
    if os.environ.get('RADARY_TRUST_PROXY') != '1' or not _la_loopback(request):
        return None
    ten = (request.headers.get('X-Remote-User') or '').strip().lower()
    if not ten:
        return None
    # Đánh dấu request này vào bằng SSO — /auth/me trả cờ này để giao diện GIẤU chip tài khoản
    # + nút Thoát của radary (danh tính đã hiện ở topbar OUTLIERY, một hệ tài khoản duy nhất).
    request.state.sso = True

    email = f'{ten}@outliery.local'
    u = conn.execute('SELECT * FROM users WHERE lower(email)=?', (email,)).fetchone()
    if not u:
        with conn:      # password_hash NULL → không đăng nhập được đường thường (van 2)
            conn.execute('INSERT INTO users(email, name, created_ts) VALUES(?,?,?)',
                          (email, ten, time.time()))
        u = conn.execute('SELECT * FROM users WHERE lower(email)=?', (email,)).fetchone()

    # ĐỒNG BỘ VAI MỖI REQUEST — MỌI NHÁNH (bài học 04/08 hệ cũ: nhánh nào "tôn
    # trọng vai đã cấu hình" là tick ở bảng phân quyền OUTLIERY không chảy sang).
    # V3: vai dịch từ X-Remote-Actions (fallback X-Remote-Role) — OUTLIERY là
    # nguồn sự thật DUY NHẤT. Chỉ đồng bộ CỘT role; workspace_id (giới hạn 1 niche
    # cấu hình trong radary) giữ nguyên — UPDATE không đụng cột đó.
    vai = vai_tu_headers(request.headers)
    if vai not in _VAI_HOP_LE:
        vai = 'viewer'
    org = _org_sso(conn)
    if org:
        cu = conn.execute('SELECT role FROM members WHERE org_id=? AND user_id=?',
                          (org, u['id'])).fetchone()
        # Cập nhật MỖI request: OUTLIERY hạ/nâng quyền một người thì radary theo ngay lượt sau.
        if not cu:
            with conn:
                conn.execute('INSERT INTO members(org_id, user_id, role, workspace_id) '
                             'VALUES(?,?,?,NULL)', (org, u['id'], vai))
        elif cu['role'] != vai:
            with conn:
                conn.execute('UPDATE members SET role=? WHERE org_id=? AND user_id=?',
                             (vai, org, u['id']))
    return u


def user_from_request(conn, request: Request):
    """Trả row user hoặc None. Không raise — caller quyết."""
    token = request.cookies.get(COOKIE)
    if not token:
        # Không có phiên riêng → thử danh tính từ OUTLIERY (một cổng đăng nhập duy nhất).
        return user_from_proxy(conn, request)
    u = conn.execute(
        'SELECT u.* FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token=? AND s.expires_ts>?',
        (token, time.time())).fetchone()
    return u or user_from_proxy(conn, request)   # phiên hết hạn vẫn vào được qua OUTLIERY

def require_user(conn, request: Request):
    u = user_from_request(conn, request)
    if not u: raise HTTPException(401, 'chưa đăng nhập')
    return u

def user_orgs(conn, user_id):
    return [dict(r) for r in conn.execute(
        'SELECT o.id, o.name, m.role FROM members m JOIN orgs o ON o.id=m.org_id WHERE m.user_id=?', (user_id,))]

def require_org_member(conn, user_id, org_id):
    r = conn.execute('SELECT role FROM members WHERE user_id=? AND org_id=?', (user_id, org_id)).fetchone()
    if not r: raise HTTPException(404, 'org không tồn tại hoặc bạn không phải thành viên')
    return r['role']

# Phase 5: bậc vai — chặn tại API (UI ẩn nút chỉ là phụ). Không thuộc org → 404 (không lộ tồn tại),
# thuộc org nhưng vai thấp hơn yêu cầu → 403.
# 23/07/2026: user đổi tên vai 'editor' → 'leader'; giữ alias 'editor' cùng bậc cho dữ liệu/phiên cũ.
# 04/08/2026: chèn 'manager' giữa leader và owner — mọi gate 'owner' sẵn có TỰ ĐỘNG vẫn chỉ
# owner qua (rank 3), gate 'leader' thì manager qua như trước; duy nhất XÓA WORKSPACE đổi
# gate sang 'manager' (delete_workspace — vận hành nặng, không phải quản trị org).
ROLE_RANK = {'viewer': 0, 'editor': 1, 'leader': 1, 'manager': 2, 'owner': 3}

def require_role(conn, user_id, org_id, minimum):
    role = require_org_member(conn, user_id, org_id)
    if ROLE_RANK.get(role, -1) < ROLE_RANK[minimum]:
        raise HTTPException(403, f'cần quyền {minimum} trở lên — vai của bạn là {role}')
    return role

def ws_for_user(conn, ws_id, user_id, min_role='viewer'):
    """Workspace nếu user thuộc org sở hữu nó VÀ trong phạm vi được cấp — 404 nếu không
    (không lộ sự tồn tại; thành viên bị giới hạn 1 niche coi các niche khác như không có),
    403 nếu là thành viên nhưng vai thấp hơn min_role."""
    row = conn.execute(
        'SELECT w.*, m.role AS member_role FROM workspaces w JOIN members m ON m.org_id=w.org_id '
        'WHERE w.id=? AND m.user_id=? AND (m.workspace_id IS NULL OR m.workspace_id=w.id)',
        (ws_id, user_id)).fetchone()
    if not row: raise HTTPException(404, f'workspace {ws_id} không tồn tại')
    if ROLE_RANK.get(row['member_role'], -1) < ROLE_RANK[min_role]:
        raise HTTPException(403, f'cần quyền {min_role} trở lên — vai của bạn là {row["member_role"]}')
    return row

def require_org_wide(conn, user_id, org_id):
    """403 nếu thành viên bị giới hạn 1 niche — dùng cho hành động cấp org (vd tạo niche mới)."""
    r = conn.execute('SELECT workspace_id FROM members WHERE org_id=? AND user_id=?',
                     (org_id, user_id)).fetchone()
    if r and r['workspace_id'] is not None:
        raise HTTPException(403, 'tài khoản bị giới hạn trong 1 niche — không làm được việc cấp org')
