"""FastAPI backend — tầng đọc + điều khiển trên SQLite. Engine không import file này.

Phase 4: mọi route workspace/org đều yêu cầu đăng nhập và phân tách theo org
(user chỉ thấy workspace thuộc org mình là thành viên). API key lưu mã hóa Fernet.
Chạy: .venv/bin/python server.py → http://127.0.0.1:8000 (docs: /docs).
"""
import json, os, secrets, sqlite3, time, urllib.parse
from contextlib import contextmanager
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request, Response
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from . import __version__, alertsview, auth, channel_info, core, crypto, db, heatmap, khoa_v3, llm, niche_report, report, scan, scheduler, series
from .harvest import runner as harvest_runner

WEB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'web')
app = FastAPI(title='Radary', version=__version__)

@contextmanager
def get_conn():
    c = db.connect()
    try: yield c
    finally: c.close()

@app.on_event('startup')
def _startup():
    with get_conn() as c:
        n = crypto.encrypt_existing(c)
        if n: print(f'[crypto] đã mã hóa {n} API key plaintext trong DB', flush=True)
    if os.environ.get('RADARY_SCHEDULER', '1') != '0':
        scheduler.start()

@app.get('/api/health')
def health():
    return {'ok': True, 'version': __version__, 'ts': time.time()}

@app.middleware('http')
async def _no_stale_ui(request: Request, call_next):
    """Frontend không build-step nên không có hash tên file — bắt trình duyệt revalidate
    app.js/index.html mỗi lần mở (ETag → 304, gần như miễn phí) để deploy xong là thấy UI mới."""
    resp = await call_next(request)
    duong = request.url.path
    if not duong.startswith('/api'):
        # no-cache = "duoc luu nhung phai hoi lai". Qua cong 9000 app chay TRONG IFRAME
        # va di qua mot tang proxy nua, thuc te van dinh ban cu (user bao 21/08: va xong
        # van thay hanh vi cu). Frontend khong co build-hash nen khong co duong nao khac
        # de ep — dat no-store cho HTML/JS: luon tai moi. ~100KB trong LAN, chap nhan duoc.
        resp.headers['Cache-Control'] = ('no-store, must-revalidate'
                                         if duong.endswith(('.js', '.html', '/')) else 'no-cache')
        resp.headers['Pragma'] = 'no-cache'
    return resp

# ---------------- auth ----------------
# Gia cố khi lộ internet (Funnel/domain — deploy_vps.md §8):
#  - RADARY_INVITE_ONLY=1: đăng ký MỚI bắt buộc kèm mã mời (bootstrap tài khoản migrate vẫn được)
#  - rate-limit đăng nhập/đăng ký theo (IP, email): 20 lần thử / 5 phút — chống brute-force
INVITE_ONLY = os.environ.get('RADARY_INVITE_ONLY') == '1'

def _sso_quan_tri_dong():
    """LÀM GỌN (Owner 16/08): khi chạy sau cổng OUTLIERY, MỌI cửa quản trị org của
    radary — API key, thành viên, lời mời, cấu hình LLM — đóng 404 KỂ CẢ vai owner
    nội bộ: khóa nhập ở General › API Keys, quyền cấp ở General › Permissions.
    App tự đọc khóa để CHẠY vẫn được (khoa_v3) — chỉ đóng cửa nhập/xem/sửa."""
    if os.environ.get('RADARY_TRUST_PROXY') == '1':
        raise HTTPException(404, 'quản trị chuyển về OUTLIERY — General › API Keys / Permissions')


def _sso_dong_cua_local():
    """V3: khi chạy sau cổng OUTLIERY (RADARY_TRUST_PROXY=1) thì các cửa tài
    khoản CỤC BỘ đóng 404 như V2 đã làm — một hệ đăng nhập duy nhất, tài khoản
    SSO không mật khẩu không dùng được các đường này."""
    if os.environ.get('RADARY_TRUST_PROXY') == '1':
        raise HTTPException(404, 'đăng nhập cục bộ đã đóng — vào qua cổng OUTLIERY')
_auth_fails = {}          # (ip, email) -> (số lần thử, hạn reset) — in-memory, đủ cho 1 process

def _auth_guard(request: Request, email: str, limit=20, window=300):
    ip = (request.headers.get('x-forwarded-for') or
          (request.client.host if request.client else '?')).split(',')[0].strip()
    key = (ip, email)
    now = time.time()
    cnt, reset = _auth_fails.get(key, (0, 0))
    if now > reset: cnt, reset = 0, now + window
    if cnt >= limit:
        raise HTTPException(429, 'quá nhiều lần thử — chờ vài phút rồi thử lại')
    _auth_fails[key] = (cnt + 1, reset)
    return key

class RegisterIn(BaseModel):
    email: str
    password: str
    org_name: str = ''
    invite: str = ''         # Phase 5: có mã mời → vào org của người mời, không tạo org riêng

class LoginIn(BaseModel):
    email: str
    password: str

@app.post('/api/auth/register', status_code=201)
def register(body: RegisterIn, request: Request, resp: Response):
    _sso_dong_cua_local()
    email = body.email.strip().lower()
    if '@' not in email or len(body.password) < 8:
        raise HTTPException(422, 'email không hợp lệ hoặc mật khẩu <8 ký tự')
    guard_key = _auth_guard(request, email)
    with get_conn() as c:
        u = c.execute('SELECT * FROM users WHERE email=?', (email,)).fetchone()
        inv = None
        if body.invite.strip():
            inv = c.execute('SELECT * FROM invites WHERE code=?', (body.invite.strip(),)).fetchone()
            if not inv or inv['used_by'] or inv['expires_ts'] < time.time():
                raise HTTPException(422, 'mã mời không hợp lệ, đã dùng hoặc đã hết hạn — xin mã mới từ owner')
        if INVITE_ONLY and not inv and not u:
            raise HTTPException(403, 'server này chỉ nhận đăng ký kèm mã mời — xin mã từ owner')
        with c:
            if u and u['password_hash']:
                raise HTTPException(409, 'email đã có tài khoản — hãy đăng nhập')
            if u:      # tài khoản migrate (chưa có mật khẩu): lần đăng ký đầu = đặt mật khẩu
                c.execute('UPDATE users SET password_hash=? WHERE id=?', (auth.hash_password(body.password), u['id']))
                uid = u['id']
            else:
                uid = c.execute('INSERT INTO users(email, password_hash, created_ts) VALUES(?,?,?)',
                                (email, auth.hash_password(body.password), time.time())).lastrowid
                if not inv:      # không có mã mời → org riêng như cũ
                    org = c.execute('INSERT INTO orgs(name, created_ts) VALUES(?,?)',
                                    (body.org_name.strip() or f'Org của {email}', time.time())).lastrowid
                    c.execute('INSERT INTO members(org_id, user_id, role) VALUES(?,?,?)', (org, uid, 'owner'))
            if inv:              # vào org của người mời với đúng vai + phạm vi trên mã; mã cháy sau 1 lần dùng
                c.execute('INSERT OR IGNORE INTO members(org_id, user_id, role, workspace_id) VALUES(?,?,?,?)',
                          (inv['org_id'], uid, inv['role'], inv['workspace_id']))
                c.execute('UPDATE invites SET used_by=?, used_ts=? WHERE id=?', (uid, time.time(), inv['id']))
        auth.set_cookie(resp, auth.create_session(c, uid))
        _auth_fails.pop(guard_key, None)
        return {'email': email, 'orgs': auth.user_orgs(c, uid)}

@app.post('/api/auth/login')
def login(body: LoginIn, request: Request, resp: Response):
    _sso_dong_cua_local()
    guard_key = _auth_guard(request, body.email.strip().lower())
    with get_conn() as c:
        u = c.execute('SELECT * FROM users WHERE email=?', (body.email.strip().lower(),)).fetchone()
        if not u or not auth.verify_password(body.password, u['password_hash']):
            raise HTTPException(401, 'sai email hoặc mật khẩu')
        auth.set_cookie(resp, auth.create_session(c, u['id']))
        _auth_fails.pop(guard_key, None)
        return {'email': u['email'], 'orgs': auth.user_orgs(c, u['id'])}

class ResetIn(BaseModel):
    email: str
    code: str
    new_password: str

@app.post('/api/auth/reset')
def reset_password(body: ResetIn, request: Request, resp: Response):
    _sso_dong_cua_local()
    """Phase 5.2: đặt lại mật khẩu bằng mã reset do owner phát. Public + rate-limit như login.
    Thành công → hủy MỌI session cũ của tài khoản và đăng nhập lại luôn."""
    email = body.email.strip().lower()
    guard_key = _auth_guard(request, email)
    if len(body.new_password) < 8:
        raise HTTPException(422, 'mật khẩu mới phải ≥8 ký tự')
    with get_conn() as c:
        u = c.execute('SELECT * FROM users WHERE email=?', (email,)).fetchone()
        r = c.execute('SELECT * FROM pw_resets WHERE code=?', (body.code.strip(),)).fetchone()
        if not u or not r or r['user_id'] != u['id'] or r['used_ts'] or r['expires_ts'] < time.time():
            raise HTTPException(422, 'mã reset không hợp lệ, đã dùng hoặc hết hạn — xin owner phát mã mới')
        with c:
            c.execute('UPDATE users SET password_hash=? WHERE id=?',
                      (auth.hash_password(body.new_password), u['id']))
            c.execute('UPDATE pw_resets SET used_ts=? WHERE id=?', (time.time(), r['id']))
            c.execute('DELETE FROM sessions WHERE user_id=?', (u['id'],))   # đăng xuất mọi thiết bị cũ
        auth.set_cookie(resp, auth.create_session(c, u['id']))
        _auth_fails.pop(guard_key, None)
        return {'email': email, 'orgs': auth.user_orgs(c, u['id'])}

@app.post('/api/auth/logout')
def logout(request: Request, resp: Response):
    with get_conn() as c:
        auth.clear_session(c, request, resp)
    return {'ok': True}

@app.get('/api/auth/me')
def me(request: Request):
    with get_conn() as c:
        u = auth.require_user(c, request)
        # sso=True: danh tính đến từ OUTLIERY (auth.user_from_proxy) — giao diện dựa cờ này
        # để giấu chip tài khoản + nút Thoát (một cổng đăng nhập duy nhất).
        return {'email': u['email'], 'orgs': auth.user_orgs(c, u['id']),
                'sso': bool(getattr(request.state, 'sso', False))}

# ---------------- orgs & API keys (BYO key, mã hóa) ----------------
class KeyIn(BaseModel):
    key: str
    note: str = ''
    workspace_id: int = 0     # 0 = toàn org; số = chỉ dùng cho niche đó (Phase 5.1)
    backup: bool = False      # dự phòng: chỉ được dùng khi key chính hết quota/403

class KeyPatch(BaseModel):
    workspace_id: int = -1    # -1 = giữ nguyên; 0 = toàn org; số = gán niche
    backup: int = -1          # -1 = giữ nguyên; 0 = chính; 1 = dự phòng

def _ws_of_org_or_none(c, org, workspace_id):
    if not workspace_id: return None
    if not c.execute('SELECT id FROM workspaces WHERE id=? AND org_id=?', (workspace_id, org)).fetchone():
        raise HTTPException(404, 'workspace không thuộc org này')
    return workspace_id

@app.get('/api/orgs')
def orgs(request: Request):
    with get_conn() as c:
        u = auth.require_user(c, request)
        out = auth.user_orgs(c, u['id'])
        for o in out:
            o['key_count'] = c.execute('SELECT COUNT(*) n FROM api_keys WHERE org_id=?', (o['id'],)).fetchone()['n']
        return out

@app.get('/api/orgs/{org}/keys')
def org_keys(org: int, request: Request):
    _sso_quan_tri_dong()   # V3: quan tri org ve mot cua OUTLIERY (API Keys + Permissions)
    with get_conn() as c:
        u = auth.require_user(c, request)
        auth.require_role(c, u['id'], org, 'owner')     # key là tài sản nhạy cảm nhất của org
        out = []
        for r in c.execute('SELECT k.id, k.key, k.note, k.workspace_id, k.backup, k.harvest, '
                           'w.name AS workspace_name '
                           'FROM api_keys k LEFT JOIN workspaces w ON w.id=k.workspace_id '
                           'WHERE k.org_id=? ORDER BY k.harvest, k.backup, k.id', (org,)):
            plain = crypto.decrypt(r['key'])
            out.append({'id': r['id'], 'note': r['note'], 'masked': plain[:6] + '…' + plain[-4:],
                        'workspace_id': r['workspace_id'], 'workspace_name': r['workspace_name'],
                        'backup': r['backup'], 'harvest': r['harvest']})
        return out

@app.post('/api/orgs/{org}/keys', status_code=201)
def add_key(org: int, body: KeyIn, request: Request):
    _sso_quan_tri_dong()   # V3: quan tri org ve mot cua OUTLIERY (API Keys + Permissions)
    k = body.key.strip()
    if len(k) < 20: raise HTTPException(422, 'key quá ngắn')
    with get_conn() as c:
        u = auth.require_user(c, request)
        # 23/07: leader được gắn key cho MỘT niche trong phạm vi mình (mở khóa flow New Niche);
        # key toàn org (workspace_id trống) vẫn là quyền owner
        role = auth.require_role(c, u['id'], org, 'leader')
        if role != 'owner':
            if not body.workspace_id:
                raise HTTPException(403, 'leader chỉ gắn key cho một niche cụ thể — key toàn org do owner quản')
            auth.ws_for_user(c, body.workspace_id, u['id'], 'leader')
        ws_scope = _ws_of_org_or_none(c, org, body.workspace_id)
        # chặn dán TRÙNG key đã có (sự cố thật 11/07: tưởng key mới, hóa ra key cũ đã cạn quota)
        for r in c.execute('SELECT id, key, workspace_id FROM api_keys WHERE org_id=?', (org,)):
            if crypto.decrypt(r['key']) == k:
                raise HTTPException(409, f'key này ĐÃ TỒN TẠI trong org (key #{r["id"]}) — đây KHÔNG phải key mới. '
                                         'Muốn thêm quota phải tạo key mới từ một dự án Google Cloud KHÁC.')
        with c:
            kid = c.execute('INSERT INTO api_keys(org_id, key, note, workspace_id, backup) VALUES(?,?,?,?,?)',
                            (org, crypto.encrypt(k), body.note, ws_scope, 1 if body.backup else 0)).lastrowid
        return {'id': kid, 'masked': k[:6] + '…' + k[-4:], 'workspace_id': ws_scope,
                'backup': 1 if body.backup else 0}

@app.post('/api/orgs/{org}/keys/{kid}/test')
def test_key(org: int, kid: int, request: Request):
    _sso_quan_tri_dong()   # V3: quan tri org ve mot cua OUTLIERY (API Keys + Permissions)
    """Phase 5.1: kiểm key sống/chết ngay trong app (tốn 1 unit khi key còn quota)."""
    import urllib.error, urllib.request
    with get_conn() as c:
        u = auth.require_user(c, request)
        auth.require_role(c, u['id'], org, 'owner')
        r = c.execute('SELECT key FROM api_keys WHERE id=? AND org_id=?', (kid, org)).fetchone()
        if not r: raise HTTPException(404, 'key không tồn tại')
        k = crypto.decrypt(r['key'])
    url = 'https://www.googleapis.com/youtube/v3/videos?part=id&id=dQw4w9WgXcQ&key=' + k
    try:
        with urllib.request.urlopen(url, timeout=15):
            return {'ok': True, 'note': 'CÒN QUOTA — key dùng được'}
    except urllib.error.HTTPError as e:
        try:
            reason = json.load(e).get('error', {}).get('errors', [{}])[0].get('reason', str(e.code))
        except Exception:
            reason = str(e.code)
        hint = {'quotaExceeded': 'hết quota — key này (hoặc DỰ ÁN chứa nó) đã cạn 10K hôm nay',
                'keyInvalid': 'key sai/bị thu hồi',
                'accessNotConfigured': 'dự án chưa bật YouTube Data API v3'}.get(reason, '')
        return {'ok': False, 'reason': reason, 'note': hint}
    except Exception as e:
        raise HTTPException(502, f'không gọi được YouTube: {e}')

@app.patch('/api/orgs/{org}/keys/{kid}')
def patch_key(org: int, kid: int, body: KeyPatch, request: Request):
    """Phase 5.1: đổi phạm vi niche / loại chính-dự phòng của key TẠI CHỖ — không cần dán lại key."""
    with get_conn() as c:
        u = auth.require_user(c, request)
        auth.require_role(c, u['id'], org, 'owner')
        r = c.execute('SELECT workspace_id, backup FROM api_keys WHERE id=? AND org_id=?', (kid, org)).fetchone()
        if not r: raise HTTPException(404, 'key không tồn tại')
        ws_scope = r['workspace_id'] if body.workspace_id == -1 else _ws_of_org_or_none(c, org, body.workspace_id)
        backup = r['backup'] if body.backup == -1 else (1 if body.backup else 0)
        with c:
            c.execute('UPDATE api_keys SET workspace_id=?, backup=? WHERE id=? AND org_id=?',
                      (ws_scope, backup, kid, org))
        return {'id': kid, 'workspace_id': ws_scope, 'backup': backup}

@app.delete('/api/orgs/{org}/keys/{kid}')
def del_key(org: int, kid: int, request: Request):
    _sso_quan_tri_dong()   # V3: quan tri org ve mot cua OUTLIERY (API Keys + Permissions)
    with get_conn() as c:
        u = auth.require_user(c, request)
        auth.require_role(c, u['id'], org, 'owner')
        with c:
            n = c.execute('DELETE FROM api_keys WHERE id=? AND org_id=?', (kid, org)).rowcount
        if not n: raise HTTPException(404, 'key không tồn tại')
        return {'deleted': kid}

# ---------------- thành viên & mã mời (Phase 5 — owner quản) ----------------
class InviteIn(BaseModel):
    role: str = 'viewer'
    workspace_id: int = 0     # 0 = toàn org; số = giới hạn đúng 1 niche (Phase 5)

@app.get('/api/orgs/{org}/members')
def org_members(org: int, request: Request):
    _sso_quan_tri_dong()   # V3: quan tri org ve mot cua OUTLIERY (API Keys + Permissions)
    with get_conn() as c:
        u = auth.require_user(c, request)
        auth.require_role(c, u['id'], org, 'owner')
        return [dict(r) for r in c.execute(
            'SELECT u.id, u.email, m.role, m.workspace_id, w.name AS workspace_name '
            'FROM members m JOIN users u ON u.id=m.user_id '
            'LEFT JOIN workspaces w ON w.id=m.workspace_id '
            'WHERE m.org_id=? ORDER BY u.email', (org,))]

class MemberPatch(BaseModel):
    role: str = ''            # '' = giữ nguyên; viewer | leader
    workspace_id: int = -1    # -1 = giữ nguyên; 0 = toàn org; số = giới hạn đúng 1 niche

@app.patch('/api/orgs/{org}/members/{uid}')
def patch_member(org: int, uid: int, body: MemberPatch, request: Request):
    """Owner sửa thành viên TẠI CHỖ: nâng/hạ vai + gán phạm vi niche (lệnh user 08/07/2026)."""
    with get_conn() as c:
        u = auth.require_user(c, request)
        auth.require_role(c, u['id'], org, 'owner')
        if uid == u['id']: raise HTTPException(422, 'không tự sửa chính mình')
        t = c.execute('SELECT role, workspace_id FROM members WHERE org_id=? AND user_id=?',
                      (org, uid)).fetchone()
        if not t: raise HTTPException(404, 'user không phải thành viên org này')
        if t['role'] == 'owner': raise HTTPException(422, 'không sửa owner khác qua đường này')
        role = t['role']
        if body.role:
            if body.role not in ('viewer', 'leader'):
                raise HTTPException(422, 'vai chỉ đổi được giữa viewer|leader')
            role = body.role
        ws_scope = t['workspace_id']
        if body.workspace_id != -1:
            if body.workspace_id == 0:
                ws_scope = None
            else:
                if not c.execute('SELECT id FROM workspaces WHERE id=? AND org_id=?',
                                 (body.workspace_id, org)).fetchone():
                    raise HTTPException(404, 'workspace không thuộc org này')
                ws_scope = body.workspace_id
        with c:
            c.execute('UPDATE members SET role=?, workspace_id=? WHERE org_id=? AND user_id=?',
                      (role, ws_scope, org, uid))
        return {'user_id': uid, 'role': role, 'workspace_id': ws_scope}

@app.post('/api/orgs/{org}/members/{uid}/pwreset', status_code=201)
def create_pwreset(org: int, uid: int, request: Request):
    _sso_quan_tri_dong()   # V3: quan tri org ve mot cua OUTLIERY (API Keys + Permissions)
    """Phase 5.2: owner phát mã reset mật khẩu cho thành viên quên mật khẩu (1 lần, 24h)."""
    with get_conn() as c:
        u = auth.require_user(c, request)
        auth.require_role(c, u['id'], org, 'owner')
        t = c.execute('SELECT u.email FROM members m JOIN users u ON u.id=m.user_id '
                      'WHERE m.org_id=? AND m.user_id=?', (org, uid)).fetchone()
        if not t: raise HTTPException(404, 'user không phải thành viên org này')
        code, exp = 'rs-' + secrets.token_urlsafe(9), time.time() + 24*3600
        with c:
            c.execute('INSERT INTO pw_resets(user_id, code, created_by, created_ts, expires_ts) '
                      'VALUES(?,?,?,?,?)', (uid, code, u['id'], time.time(), exp))
        return {'code': code, 'email': t['email'], 'expires_ts': exp}

@app.delete('/api/orgs/{org}/members/{uid}')
def remove_member(org: int, uid: int, request: Request):
    _sso_quan_tri_dong()   # V3: quan tri org ve mot cua OUTLIERY (API Keys + Permissions)
    with get_conn() as c:
        u = auth.require_user(c, request)
        auth.require_role(c, u['id'], org, 'owner')
        if uid == u['id']: raise HTTPException(422, 'không thể tự gỡ chính mình khỏi org')
        with c:
            n = c.execute('DELETE FROM members WHERE org_id=? AND user_id=?', (org, uid)).rowcount
        if not n: raise HTTPException(404, 'user không phải thành viên org này')
        return {'removed': uid}

@app.post('/api/orgs/{org}/invites', status_code=201)
def create_invite(org: int, body: InviteIn, request: Request):
    _sso_quan_tri_dong()   # V3: quan tri org ve mot cua OUTLIERY (API Keys + Permissions)
    if body.role not in ('viewer', 'leader'):
        raise HTTPException(422, 'vai của mã mời phải là viewer|leader (không mời owner qua mã)')
    with get_conn() as c:
        u = auth.require_user(c, request)
        auth.require_role(c, u['id'], org, 'owner')
        ws_scope = None
        if body.workspace_id:
            wrow = c.execute('SELECT id FROM workspaces WHERE id=? AND org_id=?',
                             (body.workspace_id, org)).fetchone()
            if not wrow: raise HTTPException(404, 'workspace không thuộc org này')
            ws_scope = body.workspace_id
        code, exp = 'rdy-' + secrets.token_urlsafe(9), time.time() + 7*86400
        with c:
            iid = c.execute('INSERT INTO invites(org_id, code, role, created_by, created_ts, expires_ts, workspace_id) '
                            'VALUES(?,?,?,?,?,?,?)', (org, code, body.role, u['id'], time.time(), exp, ws_scope)).lastrowid
        return {'id': iid, 'code': code, 'role': body.role, 'expires_ts': exp, 'workspace_id': ws_scope}

@app.get('/api/orgs/{org}/invites')
def list_invites(org: int, request: Request):
    _sso_quan_tri_dong()   # V3: quan tri org ve mot cua OUTLIERY (API Keys + Permissions)
    with get_conn() as c:
        u = auth.require_user(c, request)
        auth.require_role(c, u['id'], org, 'owner')
        return [dict(r) for r in c.execute(
            'SELECT i.id, i.code, i.role, i.created_ts, i.expires_ts, i.workspace_id, w.name AS workspace_name '
            'FROM invites i LEFT JOIN workspaces w ON w.id=i.workspace_id '
            'WHERE i.org_id=? AND i.used_by IS NULL AND i.expires_ts>? ORDER BY i.id DESC', (org, time.time()))]

@app.delete('/api/orgs/{org}/invites/{iid}')
def revoke_invite(org: int, iid: int, request: Request):
    _sso_quan_tri_dong()   # V3: quan tri org ve mot cua OUTLIERY (API Keys + Permissions)
    with get_conn() as c:
        u = auth.require_user(c, request)
        auth.require_role(c, u['id'], org, 'owner')
        with c:
            n = c.execute('DELETE FROM invites WHERE id=? AND org_id=? AND used_by IS NULL', (iid, org)).rowcount
        if not n: raise HTTPException(404, 'mã không tồn tại hoặc đã dùng')
        return {'revoked': iid}

# ---------------- LLM diễn giải (Phase 7 — owner cấu hình, BYO key Claude/GLM) ----------------
class LlmIn(BaseModel):
    provider: str = 'claude'
    model: str = ''
    key: str = ''            # rỗng = giữ key cũ (chỉ đổi provider/model)

@app.get('/api/orgs/{org}/llm')
def get_llm(org: int, request: Request):
    _sso_quan_tri_dong()   # V3: quan tri org ve mot cua OUTLIERY (API Keys + Permissions)
    with get_conn() as c:
        u = auth.require_user(c, request)
        auth.require_role(c, u['id'], org, 'owner')
        r = c.execute('SELECT provider, model, key FROM llm_config WHERE org_id=?', (org,)).fetchone()
        if not r: return {'configured': False, 'provider': 'claude', 'model': '', 'masked': ''}
        plain = crypto.decrypt(r['key']) if r['key'] else ''
        return {'configured': bool(plain), 'provider': r['provider'], 'model': r['model'],
                'masked': (plain[:5] + '…' + plain[-4:]) if plain else ''}

@app.put('/api/orgs/{org}/llm')
def put_llm(org: int, body: LlmIn, request: Request):
    _sso_quan_tri_dong()   # V3: quan tri org ve mot cua OUTLIERY (API Keys + Permissions)
    if body.provider not in llm.PROVIDERS:
        raise HTTPException(422, f'provider phải là {"|".join(llm.PROVIDERS)}')
    with get_conn() as c:
        u = auth.require_user(c, request)
        auth.require_role(c, u['id'], org, 'owner')
        old = c.execute('SELECT key FROM llm_config WHERE org_id=?', (org,)).fetchone()
        key = crypto.encrypt(body.key.strip()) if body.key.strip() else (old['key'] if old else '')
        if not key: raise HTTPException(422, 'chưa có API key')
        model = body.model.strip() or llm.DEFAULT_MODEL[body.provider]
        with c:
            c.execute('INSERT OR REPLACE INTO llm_config(org_id, provider, model, key, updated_ts) '
                      'VALUES(?,?,?,?,?)', (org, body.provider, model, key, time.time()))
        return {'saved': True, 'provider': body.provider, 'model': model}

@app.post('/api/orgs/{org}/llm/test')
def test_llm(org: int, request: Request):
    _sso_quan_tri_dong()   # V3: quan tri org ve mot cua OUTLIERY (API Keys + Permissions)
    with get_conn() as c:
        u = auth.require_user(c, request)
        auth.require_role(c, u['id'], org, 'owner')
        cfg = llm.org_llm(c, org)
        if not cfg: raise HTTPException(400, 'chưa cấu hình LLM')
    try:
        reply = llm.complete(cfg, 'Trả lời đúng một từ.', 'Nói "OK" nếu bạn nhận được tin này.',
                             max_tokens=20, timeout=45)
    except RuntimeError as e:
        raise HTTPException(502, str(e))
    return {'ok': True, 'reply': reply[:100], 'model': cfg['model']}

# ---------------- Hỏi Radar (Phase 7 — leader+, LLM diễn giải chỉ số sống) ----------------
class AskIn(BaseModel):
    q: str

_ask_counts = {}             # (user_id, ngày) -> số lượt LLM đã dùng; trần 30/ngày/người (chung ask + đọc chart)

def _llm_quota(uid):
    day = time.strftime('%Y-%m-%d')
    n = _ask_counts.get((uid, day), 0)
    if n >= 30: raise HTTPException(429, 'đã hết 30 lượt AI hôm nay — mai dùng tiếp')
    _ask_counts[(uid, day)] = n + 1
    return 30 - n - 1

@app.post('/api/workspaces/{ws}/ask')
def ask_radar(ws: int, body: AskIn, request: Request):
    if not body.q.strip(): raise HTTPException(422, 'câu hỏi rỗng')
    with get_conn() as c:
        u = auth.require_user(c, request)
        w = auth.ws_for_user(c, ws, u['id'], 'leader')
        cfg = llm.org_llm(c, w['org_id'])
        if not cfg: raise HTTPException(400, 'org chưa cấu hình LLM — owner vào tab Quản trị thêm key')
        remaining = _llm_quota(u['id'])
        try:
            answer = llm.ask(c, ws, cfg, body.q)
        except RuntimeError as e:
            raise HTTPException(502, str(e))
        return {'answer': answer, 'provider': cfg['provider'], 'model': cfg['model'],
                'remaining_today': remaining}

# ---------------- workspaces ----------------
class WorkspaceIn(BaseModel):
    name: str
    tz: str = 'Asia/Ho_Chi_Minh'
    org_id: int = 0          # 0 = org đầu tiên của user
    market: str = ''         # mã thị trường TT-xx từ đế — BẮT BUỘC khi chạy trong V3 (18/08)
    ngach: str = ''          # mã ngách N-xxx từ đế — BẮT BUỘC khi V3; market phải THUỘC ngách

# ---- Pool theo THỊ TRƯỜNG của NGÁCH (18/08/2026 — docs/RADARY_THI_TRUONG.md) ----
def _v3() -> bool:
    return os.environ.get('RADARY_TRUST_PROXY') == '1'

def _kiem_de(ngach: str, market: str, cho_phep_goc: bool = False) -> tuple[str, str]:
    """Validation dropdown Ở SERVER khi V3: ngách tồn tại trong đế, thị trường
    THUỘC tập thị trường của ngách (user chọn ở General › Niches).
    cho_phep_goc: market RỖNG hợp lệ = POOL GỐC của ngách (kênh chưa phân loại
    thị trường — workspace hiện hữu nhận làm ngách). Standalone giữ hành vi cũ."""
    ngach, market = (ngach or '').strip(), (market or '').strip()
    if not _v3():
        return ngach, market
    from . import thi_truong_v3
    try:
        ng = next((n for n in thi_truong_v3.ds_ngach() if n.get('ma') == ngach), None)
        if not ngach or not ng:
            raise HTTPException(422, 'phải chọn NGÁCH từ danh mục OUTLIERY '
                                     '(thiếu thì Owner thêm ở General › Niches)')
        if cho_phep_goc and not market:
            return ngach, market
        if not ng.get('thi_truong'):
            raise HTTPException(422, f'ngách {ng.get("ten") or ngach} chưa khai thị trường nào '
                                     '— Owner gắn thị trường cho ngách ở General › Niches trước')
        if market not in ng['thi_truong']:
            raise HTTPException(422, 'phải chọn THỊ TRƯỜNG thuộc ngách này '
                                     '(danh sách khai ở General › Niches) — mỗi pool gắn đúng một thị trường')
    except RuntimeError as e:
        raise HTTPException(502, str(e))
    return ngach, market

@app.get('/api/ngach')
def ngach_list(request: Request):
    """Ngách + tập thị trường của từng ngách (kèm tên đẹp) cho dropdown/tab UI.
    Ngoài V3 → [] (UI tự ẩn, hành vi standalone không đổi)."""
    with get_conn() as c:
        auth.require_user(c, request)
    if not _v3():
        return []
    from . import thi_truong_v3
    try:
        ten_tt = {t['ma']: t for t in thi_truong_v3.danh_sach()}
        return [{'ma': n['ma'], 'ten': n.get('ten') or n['ma'],
                 'thi_truong': [ten_tt.get(m, {'ma': m, 'ten': m, 'ngon_ngu': ''})
                                for m in n.get('thi_truong', [])]}
                for n in thi_truong_v3.ds_ngach()]
    except RuntimeError as e:
        raise HTTPException(502, str(e))

@app.get('/api/ngach/{ma}/volume')
def ngach_volume(ma: str, request: Request, days: int = 30):
    """VOLUME CẢ NGÁCH (user 18/08: 'xem được cả volume của niche'): cộng nhịp
    views của MỌI pool thuộc ngách mà user thấy được (lọc phạm vi như
    list_workspaces) + bảng volume theo thị trường. Chỉ đọc pool_stats/
    channel_stats — số đo thật đã quét, không gọi YouTube, không bịa.
    Gộp theo NGÀY (giờ máy chủ = giờ VN — cùng quy ước bucket căn giờ VN)."""
    days = max(2, min(days, 400))
    with get_conn() as c:
        u = auth.require_user(c, request)
        pools = [dict(r) for r in c.execute(
            'SELECT DISTINCT w.id, w.name, w.market FROM workspaces w '
            'JOIN members m ON m.org_id=w.org_id WHERE m.user_id=? '
            'AND (m.workspace_id IS NULL OR m.workspace_id=w.id) AND w.ngach=? '
            'ORDER BY w.market', (u['id'], ma))]
        if not pools:
            raise HTTPException(404, 'ngách chưa có pool nào (hoặc ngoài phạm vi của bạn)')
        # thứ tự ưu tiên user 19/08: US → Tây Ban Nha → khác; "Chưa phân loại" cuối bảng
        pools.sort(key=lambda p: {'TT-US': 0, 'TT-SPAIN': 1}.get(p['market'], 2) if p['market'] else 9)
        ids = [p['id'] for p in pools]
        qm = ','.join('?' * len(ids))
        now = time.time()
        ngay: dict = {}
        for r in c.execute(f'SELECT bucket_ts, dviews, vph_avg, n_young FROM pool_stats '
                           f'WHERE workspace_id IN ({qm}) AND bucket_ts>=?',
                           (*ids, now - days * 86400)):
            d0 = time.strftime('%Y-%m-%d', time.localtime(r['bucket_ts']))
            g = ngay.setdefault(d0, {'dviews': 0, 'vs': 0.0, 'n': 0})
            g['dviews'] += r['dviews']
            g['vs'] += r['vph_avg'] * r['n_young']
            g['n'] += r['n_young']
        hom_nay = time.strftime('%Y-%m-%d', time.localtime(now))
        # dang_do: ngày CHƯA TRỌN (hôm nay) — UI không vẽ lên đường (điểm ngày-dở
        # cạnh ngày-trọn nhìn như "cắm đầu" — user bắt 19/08), chỉ hiện ghi chú
        pts = [{'ngay': k, 'dviews': v['dviews'], 'n': v['n'],
                'vph_avg': (v['vs'] / v['n']) if v['n'] else 0,
                'dang_do': k == hom_nay}
               for k, v in sorted(ngay.items())]
        ten_tt = {}
        if _v3():
            from . import thi_truong_v3
            try: ten_tt = {t['ma']: t.get('ten') or t['ma'] for t in thi_truong_v3.danh_sach()}
            except RuntimeError: pass          # gateway chết — hiện mã trần, volume vẫn sống
        bang = []
        for p in pools:
            v7 = c.execute('SELECT COALESCE(SUM(dviews),0) FROM channel_stats '
                           'WHERE workspace_id=? AND bucket_ts>=?', (p['id'], now - 7 * 86400)).fetchone()[0]
            v28 = c.execute('SELECT COALESCE(SUM(dviews),0) FROM channel_stats '
                            'WHERE workspace_id=? AND bucket_ts>=?', (p['id'], now - 28 * 86400)).fetchone()[0]
            bang.append({
                'id': p['id'],
                'nhan': (ten_tt.get(p['market'], p['market']) or 'Chưa phân loại'),
                'kenh': c.execute('SELECT COUNT(*) FROM channels WHERE workspace_id=? AND active=1',
                                  (p['id'],)).fetchone()[0],
                'video': c.execute('SELECT COUNT(*) FROM videos WHERE workspace_id=? AND dead=0',
                                   (p['id'],)).fetchone()[0],
                'views_7d': v7, 'views_28d': v28})
        tong = {k: sum(b[k] for b in bang) for k in ('kenh', 'video', 'views_7d', 'views_28d')}
        return {'ngach': ma, 'days': days, 'pools': bang, 'tong': tong, 'pts': pts}

@app.get('/api/workspaces')
def list_workspaces(request: Request):
    with get_conn() as c:
        u = auth.require_user(c, request)
        ten_tt, ten_ng = {}, {}
        if _v3():                        # nhãn thị trường/ngách — best-effort, gateway chết KHÔNG giết list
            from . import thi_truong_v3
            try:
                ten_tt = {t['ma']: t.get('ten') or t['ma'] for t in thi_truong_v3.danh_sach()}
                ten_ng = {n['ma']: n.get('ten') or n['ma'] for n in thi_truong_v3.ds_ngach()}
            except RuntimeError: pass
        out = []
        for w in c.execute('SELECT w.id, w.name, w.tz, w.org_id, w.market, w.ngach FROM workspaces w '
                           'JOIN members m ON m.org_id=w.org_id WHERE m.user_id=? '
                           'AND (m.workspace_id IS NULL OR m.workspace_id=w.id) ORDER BY w.id', (u['id'],)):
            tiers = {str(r['tier']): r['n'] for r in c.execute(
                'SELECT tier, COUNT(*) n FROM videos WHERE workspace_id=? AND dead=0 GROUP BY tier', (w['id'],))}
            so_kenh = c.execute('SELECT COUNT(*) FROM channels WHERE workspace_id=? AND active=1',
                                (w['id'],)).fetchone()[0]
            out.append({'id': w['id'], 'name': w['name'], 'tz': w['tz'], 'org_id': w['org_id'],
                        'market': w['market'], 'market_ten': ten_tt.get(w['market'], w['market']),
                        'ngach': w['ngach'], 'ngach_ten': ten_ng.get(w['ngach'], w['ngach']),
                        'videos': sum(tiers.values()), 'tiers': tiers,
                        'channels': so_kenh,     # Data Pool quản theo SỐ KÊNH (user 18/08)
                        'heartbeat_ts': db.kv_get(c, w['id'], 'heartbeat', 0)})
        return out

@app.post('/api/workspaces', status_code=201)
def create_workspace(body: WorkspaceIn, request: Request):
    # cho_phep_goc: ngach + market RỖNG = dựng POOL GỐC "Chưa phân loại" cho ngách
    # MỚI từ General (19/08 — user phát hiện ngách mới không hiện đâu trong RadarY)
    ngach, market = _kiem_de(body.ngach, body.market, cho_phep_goc=True)
    with get_conn() as c:
        u = auth.require_user(c, request)
        my_orgs = auth.user_orgs(c, u['id'])
        if not my_orgs: raise HTTPException(400, 'user chưa thuộc org nào')
        org = body.org_id or my_orgs[0]['id']
        auth.require_role(c, u['id'], org, 'leader')
        auth.require_org_wide(c, u['id'], org)      # bị giới hạn 1 niche → không tạo niche mới
        with c:
            ws = db.create_workspace(c, org, body.name.strip(), tz=body.tz,
                                     market=market, ngach=ngach)
            db.set_jobs(c, ws, {'discover': 0, 'hot': 0, 't1': 0, 'd01': 0, 'd26': 0, 'allages': 0,
                                'weekly': scan.next_sunday_8am(core.tzinfo(body.tz))})
        return {'id': ws, 'name': body.name.strip(), 'org_id': org,
                'market': market, 'ngach': ngach}

class MarketIn(BaseModel):
    market: str
    ngach: str = ''

@app.patch('/api/workspaces/{ws}/market')
def set_workspace_market(ws: int, body: MarketIn, request: Request):
    """Nối pool với đế (leader trở lên). market RỖNG = NHẬN LÀM POOL GỐC của
    ngách (kênh hiện có = 'chưa phân loại') — khi đó TÊN workspace ĐỒNG NHẤT
    theo tên ngách General (luật user 18/08: 'chỉ khi tạo niche trong General
    thì mới có tên pool trong Radary'). Ghi event config_change có vết."""
    ngach, market = _kiem_de(body.ngach, body.market, cho_phep_goc=True)
    with get_conn() as c:
        u = auth.require_user(c, request)
        auth.ws_for_user(c, ws, u['id'], 'leader')
        ten_moi = None
        if _v3() and ngach and not market:      # nhận gốc → tên theo General
            from . import thi_truong_v3
            try:
                ten_moi = next((n.get('ten') for n in thi_truong_v3.ds_ngach()
                                if n.get('ma') == ngach), None)
            except RuntimeError:
                ten_moi = None                  # danh mục vừa đọc được ở _kiem_de — hụt thì giữ tên cũ
        with c:
            if ten_moi:
                c.execute('UPDATE workspaces SET market=?, ngach=?, name=? WHERE id=?',
                          (market, ngach, ten_moi, ws))
            else:
                c.execute('UPDATE workspaces SET market=?, ngach=? WHERE id=?', (market, ngach, ws))
            db.append_events(c, ws, [{'ts': time.time(), 'kind': 'config_change',
                                      'payload': {'market': market, 'ngach': ngach,
                                                  'ten': ten_moi, 'by': u['email']}}])
        return {'id': ws, 'market': market, 'ngach': ngach, 'name': ten_moi}

@app.get('/api/workspaces/{ws}/status')
def ws_status(ws: int, request: Request):
    with get_conn() as c:
        u = auth.require_user(c, request)
        w = auth.ws_for_user(c, ws, u['id'])
        tiers = {str(r['tier']): r['n'] for r in c.execute(
            'SELECT tier, COUNT(*) n FROM videos WHERE workspace_id=? AND dead=0 GROUP BY tier', (ws,))}
        return {'id': ws, 'name': w['name'], 'tz': w['tz'], 'org_id': w['org_id'],
                'tiers': tiers, 'videos': sum(tiers.values()),
                'heartbeat_ts': db.kv_get(c, ws, 'heartbeat', 0), 'jobs': db.get_jobs(c, ws),
                'push_count': db.kv_get(c, ws, 'push_count', {'date': '', 't2': 0})}

# ---------------- nhật ký quét ----------------
@app.get('/api/workspaces/{ws}/cycles')
def cycles(ws: int, request: Request, limit: int = 20):
    with get_conn() as c:
        u = auth.require_user(c, request)
        auth.ws_for_user(c, ws, u['id'])
        return db.recent_cycles(c, ws, min(limit, 100))

# ---------------- board ----------------
@app.get('/api/workspaces/{ws}/board')
def board(ws: int, request: Request):
    with get_conn() as c:
        u = auth.require_user(c, request)
        auth.ws_for_user(c, ws, u['id'])
        data = db.kv_get(c, ws, 'board', None)
        if data is None: raise HTTPException(404, 'chưa có chu kỳ quét nào — gọi POST /run hoặc chờ scheduler')
        # Phase 3.10: gắn cờ ⭐ lúc đọc — bấm sao thấy ngay, không chờ chu kỳ quét
        favs = c.execute('SELECT yt_id, title FROM channels WHERE workspace_id=? AND favorite=1', (ws,)).fetchall()
        fav_ids = {r['yt_id'] for r in favs}
        fav_titles = {r['title'] for r in favs}      # fallback cho board cũ chưa có ch_id
        for co in data.get('cohorts', []):
            for v in co['videos']:
                v['fav'] = v.get('ch_id') in fav_ids or v.get('channel') in fav_titles
        for v in data.get('allages', []):
            v['fav'] = v.get('ch_id') in fav_ids or v.get('channel') in fav_titles
        return data

@app.get('/api/workspaces/{ws}/board.md', response_class=PlainTextResponse)
def board_md(ws: int, request: Request):
    with get_conn() as c:
        u = auth.require_user(c, request)
        auth.ws_for_user(c, ws, u['id'])
    path = os.path.join(report.report_dir(ws), 'radar_board.md')
    if not os.path.exists(path): raise HTTPException(404, 'chưa có board — chưa chu kỳ nào chạy')
    return open(path, encoding='utf-8').read()

# ---------------- alerts / events + vòng tự chấm ----------------
# ---------------- nhịp pool (Phase 3.13) ----------------
@app.get('/api/workspaces/{ws}/pulse')
def pulse(ws: int, request: Request, days: int = 7, start: str = '', end: str = ''):
    """Sóng views + VPH TB toàn pool từ pool_stats. ≤14 ngày trả điểm 6h, dài hơn gộp theo ngày.
    Range: days=7|30|90|365|1825 hoặc start/end=YYYY-MM-DD (custom). Viewer đọc được, 0 quota."""
    from datetime import datetime, timedelta
    with get_conn() as c:
        u = auth.require_user(c, request)
        w = auth.ws_for_user(c, ws, u['id'])
        tz = core.tzinfo(w['tz'])
        now = time.time()
        if start:
            try:
                t0 = datetime.strptime(start, '%Y-%m-%d').replace(tzinfo=tz).timestamp()
                t1 = (datetime.strptime(end or start, '%Y-%m-%d').replace(tzinfo=tz) + timedelta(days=1)).timestamp()
            except ValueError:
                raise HTTPException(400, 'ngày phải dạng YYYY-MM-DD')
            if t1 <= t0: raise HTTPException(400, 'ngày kết thúc phải sau ngày bắt đầu')
        else:
            t0, t1 = now - max(1, min(days, 5 * 366)) * 86400, now
        rows = c.execute('SELECT bucket_ts, dviews, vph_avg, n_young FROM pool_stats '
                         'WHERE workspace_id=? AND bucket_ts>=? AND bucket_ts<? ORDER BY bucket_ts',
                         (ws, t0, t1)).fetchall()
        w0 = c.execute('SELECT config FROM workspaces WHERE id=?', (ws,)).fetchone()
        since = c.execute('SELECT MIN(bucket_ts) FROM pool_stats WHERE workspace_id=?', (ws,)).fetchone()[0]
        if (t1 - t0) <= 14 * 86400 + 1:
            # Hai lý do KHÁC NHAU làm khung gần nhất trông như "pool đang tụt":
            #  dang_chay — khung 6 giờ hiện tại mới trôi được một phần, dviews tất nhiên
            #    thấp hơn; vẫn là số thật của phần thời gian đã qua nên đánh dấu chứ
            #    không xóa.
            #  chua_chot — video cũ chỉ được quét 1 lần/24h (cadence 'allages'), mà
            #    dviews = chênh lệch giữa HAI lần quét chia đều cho khoảng giữa. Phần
            #    views của nhóm video cũ vì thế CHỈ được phân bổ vào một khung SAU khi
            #    có lần quét kế tiếp — mọi khung chưa qua vòng quét toàn pool đều còn
            #    thiếu và sẽ tự đầy lên.
            # Mốc chốt lấy từ LỊCH JOB thật, không đoán "24 giờ qua": ngưỡng cứng loại
            # nhầm cả khung đã đầy. Đo thật ws20 (user báo 22/08): allages due 23/08
            # 00:59 → lần gần nhất 22/08 00:59; khung 21/08 18h (hết lúc 00:00) đã được
            # điền bù 122.852 trong khi khung 22/08 00h mới 53.831.
            B6 = 6 * 3600
            cfg_ws = json.loads(w0['config'] or '{}') if w0 else {}
            cad = ((cfg_ws.get('cadence') or {}).get('allages')
                   or db.DEFAULT_CFG['cadence']['allages'])
            due_all = (db.get_jobs(c, ws) or {}).get('allages') or 0
            moc_chot = (due_all - cad) if due_all else (now - cad)
            pts = []
            for r in rows:
                het = r['bucket_ts'] + B6
                pts.append({'ts': r['bucket_ts'], 'dviews': r['dviews'],
                            'vph_avg': r['vph_avg'], 'n': r['n_young'],
                            'dang_chay': het > now,
                            'chua_chot': het > moc_chot,
                            'phan_tram_da_troi': (round(100 * (now - r['bucket_ts']) / B6)
                                                  if het > now else 100)})
            res = '6h'
        else:                                          # gộp ngày: views cộng dồn, VPH TB trọng số theo n video trẻ
            byday = {}
            for r in rows:
                d = datetime.fromtimestamp(r['bucket_ts'], tz).strftime('%Y-%m-%d')
                a = byday.setdefault(d, {'ts': r['bucket_ts'], 'dviews': 0, 'wsum': 0.0, 'nsum': 0, 'n': 0})
                a['dviews'] += r['dviews']
                a['wsum'] += r['vph_avg'] * r['n_young']; a['nsum'] += r['n_young']
                a['n'] = max(a['n'], r['n_young'])
            hom_nay = datetime.fromtimestamp(now, tz).strftime('%Y-%m-%d')
            pts = []
            for ngay, a in sorted(byday.items()):
                pts.append({'ts': a['ts'], 'dviews': a['dviews'],
                            'vph_avg': round(a['wsum'] / a['nsum'], 1) if a['nsum'] else 0,
                            'n': a['n'], 'dang_chay': ngay == hom_nay,
                            'chua_chot': ngay == hom_nay,
                            'phan_tram_da_troi': (round(100 * (now - a['ts']) / 86400)
                                                  if ngay == hom_nay else 100)})
            res = 'day'
        return {'res': res, 'points': pts, 'since_ts': since}

# ---------------- heatmap giờ đăng (heatmap_build_brief — chỉ đọc, 0 quota) ----------------
@app.get('/api/workspaces/{ws}/heatmap')
def heatmap_api(ws: int, request: Request, days: int = 90, tz: str = 'vn', channel: str = ''):
    with get_conn() as c:
        u = auth.require_user(c, request)
        auth.ws_for_user(c, ws, u['id'])               # viewer xem được (Board)
        if days not in (0, 30, 90): raise HTTPException(400, 'days chỉ nhận 0 (tất cả) | 30 | 90')
        return heatmap.compute(c, ws, days=days, tz_off=0 if tz == 'utc' else 7, channel=channel)

# ---------------- Metrics (user duyệt mockup kiểu vidIQ 23/07/2026 — thay Top kênh/ngày) ----------------
def _metrics_data(c, ws, tz, channel='', now=None):
    """Tiles khối Metrics trên Board. Phạm vi = toàn pool hoặc 1 kênh (channel_title, khớp heatmap).
    Chỉ số đo thật (channel_stats/ticks/channel_snap) — % thiếu lịch sử trả None, UI hiện '—' (không bịa)."""
    from datetime import datetime, timedelta
    now = now or time.time()
    chf, arg = ('AND channel_title=?', [channel]) if channel else ('', [])
    ch_yt = None                         # yt_id của kênh đang xem → nút mở thẳng YouTube
    if channel:
        r0 = c.execute("SELECT channel_yt_id FROM videos WHERE workspace_id=? AND channel_title=? "
                       "AND channel_yt_id!='' LIMIT 1", (ws, channel)).fetchone()
        ch_yt = r0['channel_yt_id'] if r0 else None
    n_ch = c.execute('SELECT COUNT(*) FROM channels WHERE workspace_id=? AND active=1', (ws,)).fetchone()[0]
    n_vid = c.execute(f'SELECT COUNT(*) FROM videos WHERE workspace_id=? AND dead=0 {chf}', (ws, *arg)).fetchone()[0]
    durs = [r[0] for r in c.execute(f'SELECT duration_s FROM videos WHERE workspace_id=? AND duration_s>180 {chf} '
                                    'ORDER BY duration_s', (ws, *arg))]
    n30 = c.execute(f'SELECT COUNT(*) FROM videos WHERE workspace_id=? AND pub_ts>? '
                    f'AND (duration_s IS NULL OR duration_s>180) {chf}', (ws, now - 30 * 86400, *arg)).fetchone()[0]
    r = c.execute(f'SELECT AVG(last_vph), COUNT(*) FROM videos WHERE workspace_id=? AND dead=0 AND pub_ts>? {chf}',
                  (ws, now - 6 * 86400, *arg)).fetchone()
    avg_vph, n_young = (round(r[0], 1) if r[0] else 0), r[1]
    surging = c.execute(f'SELECT COUNT(*) FROM videos WHERE workspace_id=? AND dead=0 AND tier>=1 {chf}',
                        (ws, *arg)).fetchone()[0]
    # ---- nhịp 7 ngày (channel_stats — số đo thật, giữ vĩnh viễn) ----
    chf2, arg2 = ('AND ch=?', [channel]) if channel else ('', [])
    def q7(a, b):
        return c.execute(f'SELECT COALESCE(SUM(dviews),0) FROM channel_stats WHERE workspace_id=? '
                         f'AND bucket_ts>? AND bucket_ts<=? {chf2}', (ws, a, b, *arg2)).fetchone()[0]
    gain7, prev7 = q7(now - 7 * 86400, now), q7(now - 14 * 86400, now - 7 * 86400)
    oldest = c.execute('SELECT MIN(bucket_ts) FROM pool_stats WHERE workspace_id=?', (ws,)).fetchone()[0]
    gain7_pct = (round((gain7 - prev7) / prev7 * 100, 1)
                 if prev7 > 0 and oldest and oldest <= now - 13.5 * 86400 else None)
    # ---- snapshot ngày (channel_snap — Total views/Subscribers trọn đời kênh, % so ~7 ngày trước) ----
    snap_day = c.execute('SELECT MAX(day) FROM channel_snap WHERE workspace_id=?', (ws,)).fetchone()[0]
    total_views = subs = tv_pct = subs_pct = None
    if snap_day:
        yt = ch_yt or '∅'
        def snap(day):
            q, a = 'SELECT ch_yt_id, subs, total_views FROM channel_snap WHERE workspace_id=? AND day=?', [ws, day]
            if channel: q += ' AND ch_yt_id=?'; a.append(yt)
            return {r3['ch_yt_id']: r3 for r3 in c.execute(q, a)}
        cur = snap(snap_day)
        tv = [r3['total_views'] for r3 in cur.values() if r3['total_views'] is not None]
        sb = [r3['subs'] for r3 in cur.values() if r3['subs'] is not None]
        total_views, subs = (sum(tv) if tv else None), (sum(sb) if sb else None)
        target = (datetime.strptime(snap_day, '%Y-%m-%d') - timedelta(days=7)).strftime('%Y-%m-%d')
        old_day = c.execute('SELECT MAX(day) FROM channel_snap WHERE workspace_id=? AND day<=?',
                            (ws, target)).fetchone()[0]
        if old_day:
            old = snap(old_day)
            def dpct(f):                 # so trên GIAO 2 tập kênh — kênh thêm/gỡ giữa chừng không làm méo %
                ks = [k for k in cur.keys() & old.keys() if cur[k][f] is not None and old[k][f] is not None]
                a, b = sum(cur[k][f] for k in ks), sum(old[k][f] for k in ks)
                return round((a - b) / b * 100, 2) if b > 0 else None
            tv_pct, subs_pct = dpct('total_views'), dpct('subs')
    # ---- Top outlier 7 ngày: bậc cao nhất đạt được + VPH đỉnh so P50 sóng tiền lệ ----
    cands = []
    for r2 in c.execute("SELECT ts, video_yt_id, payload FROM events WHERE workspace_id=? AND kind='tier' "
                        "AND ts>? AND video_yt_id!=''", (ws, now - 7 * 86400)):
        try: cands.append((json.loads(r2['payload']).get('to', 0), r2['ts'], r2['video_yt_id']))
        except Exception: pass
    out = None
    for to, _, yt2 in sorted(cands, reverse=True):
        if to < 1: break
        v = c.execute(f'SELECT * FROM videos WHERE workspace_id=? AND yt_id=? {chf}', (ws, yt2, *arg)).fetchone()
        if not v: continue
        ticks = [[t['ts'], t['views']] for t in
                 c.execute('SELECT ts, views FROM ticks WHERE video_id=? ORDER BY ts', (v['id'],))]
        s2 = series.vph_series(ticks, v['pub_ts'])
        peak_age, peak_vph = max(((a, vp) for a, vp, _ in s2), key=lambda x: x[1], default=(0, 0))
        ref = series.reference_bands(c, ws, now, exclude_yt=yt2)
        band = next((b for b in ref['bands'] if int(b['age_h'] // series.BUCKET_H) == int(peak_age // series.BUCKET_H)), None)
        pct = round((peak_vph - band['p50']) / band['p50'] * 100) if band and band['p50'] > 0 else None
        out = {'yt_id': yt2, 'title': v['title'], 'ch': v['channel_title'], 'tier': to,
               'peak_vph': round(peak_vph), 'pct_p50': pct, 'n_waves': ref['n_waves']}
        break
    # ---- hạng trong pool theo views 7 ngày (chỉ phạm vi kênh) ----
    rank = None
    if channel:
        sums = c.execute('SELECT ch, SUM(dviews) s FROM channel_stats WHERE workspace_id=? AND bucket_ts>? '
                         'GROUP BY ch ORDER BY s DESC', (ws, now - 7 * 86400)).fetchall()
        pos = next((i + 1 for i, r2 in enumerate(sums) if r2['ch'] == channel), None)
        rank = {'pos': pos, 'of': n_ch} if pos else None
    return {'scope': channel or 'pool', 'n_channels': n_ch, 'snap_day': snap_day, 'channel_yt_id': ch_yt,
            'total_views': total_views, 'total_views_pct': tv_pct, 'subs': subs, 'subs_pct': subs_pct,
            'gain7': int(gain7), 'gain7_pct': gain7_pct,
            'videos_tracked': n_vid, 'avg_len_m': round(durs[len(durs) // 2] / 60) if durs else 0,
            'upload_wk': round(n30 / 4.3 / (1 if channel else max(n_ch, 1)), 1),
            'avg_vph': avg_vph, 'n_young': n_young, 'surging': surging, 'outlier': out, 'rank': rank}

@app.get('/api/workspaces/{ws}/metrics')
def metrics_api(ws: int, request: Request, channel: str = ''):
    with get_conn() as c:
        u = auth.require_user(c, request)
        w = auth.ws_for_user(c, ws, u['id'])           # viewer xem được (Board)
        return _metrics_data(c, ws, core.tzinfo(w['tz']), channel)

# ---------------- DISCOVERY + MAPPING (21/08/2026 — docs/discovery-mapping.md) ----
# CẦU (người ta gõ gì) ghép với CUNG (31.917 video đã có) → bản đồ 4 ô. Vế cung đọc
# SQLite thuần: 0 quota, 0 LLM. Vế cầu gọi autocomplete — CÙNG IP với harvest nên
# rate-limit bắt buộc (BoDem), trần mặc định thấp.
def _vung_cua_ws(w) -> tuple[dict, str | None]:
    """(tham số vùng cho API ngoài, tên ngôn ngữ) của thị trường pool — lấy từ ĐẾ.

    Không khai được thị trường (pool gốc) → trả rỗng: KHÔNG đoán 'US'. UI hiện cảnh
    báo để người chọn. Sự cố 21/08: pool gốc lẫn kênh Việt → seed tiếng Việt → đo cả
    thị trường Việt, trong khi công ty chỉ làm Mỹ.
    """
    from . import mapping, thi_truong_v3
    ma_tt = (w['market'] or '').strip()
    if not ma_tt:
        return {}, None
    try:
        tt = {x['ma']: x for x in thi_truong_v3.danh_sach()}.get(ma_tt) or {}
    except Exception:                                    # noqa: BLE001 — đế chết thì không ép vùng
        return {}, None
    ngon_ngu = tt.get('ngon_ngu')
    return mapping.vung_ngon_ngu(ma_tt, ngon_ngu), ngon_ngu


class QuetCauIn(BaseModel):
    seed: str
    chan: list[str] = []          # từ chặn của workspace (nhiễu game/kênh lạ)
    tu_hoi: bool = False          # thêm biến thể what/why/how — tốn thêm 9 lời gọi
    lay_hn: bool = False          # nguồn phụ Hacker News (lệch tệp, mặc định tắt)
    tran: int = 20                # trần lời gọi cho phiên này (mỗi lời gọi ~1s)
    do_luon: bool = True          # đo thị trường ngay cho cụm triển vọng (xem dưới)
    do_toi_da: int = 8            # trần cụm đo tự động (~102 units/cụm)


@app.post('/api/workspaces/{ws}/discovery/scan')
def discovery_scan(ws: int, body: QuetCauIn, request: Request):
    """Quét tín hiệu CẦU quanh một seed rồi ghi vào keywords/keyword_stats.

    Chạy ĐỒNG BỘ có chủ ý: trần 20 lời gọi × ~1s ≈ 20s, và route là `def` (FastAPI
    đẩy sang threadpool) nên không khoá event loop. Muốn quét rộng thì tăng `tran`,
    nhưng nhớ IP dùng chung với harvest.
    """
    from . import discovery
    if not body.seed.strip():
        raise HTTPException(422, 'thiếu seed')
    with get_conn() as c:
        u = auth.require_user(c, request)
        w = auth.ws_for_user(c, ws, u['id'], 'leader')  # quét = tiêu tài nguyên → leader+
        vung, _ = _vung_cua_ws(w)
        dem = discovery.BoDem(tran=max(1, min(int(body.tran), 120)))
        muc = discovery.quet(body.seed, chan=tuple(body.chan), lay_hn=body.lay_hn,
                             dem=dem, tu_hoi=body.tu_hoi, vung=vung)
        kq = db.kw_luu(c, ws, muc)

        # ĐO LUÔN cụm có triển vọng nhất (21/08 — sửa sau khi user báo bảng toàn "chưa
        # đo"): quét xong mà để 191 dòng thô rồi bắt bấm 19 lô là đẩy việc của máy sang
        # người. Chỉ đo cụm lọt ra từ >= 2 hướng gõ — tín hiệu cầu duy nhất ta có.
        do_kq = {}
        if body.do_luon:
            from . import thi_truong
            ung_vien = [m['cum'] for m in muc if m.get('do_phu', 0) >= 2][:body.do_toi_da]
            if ung_vien:
                try:
                    r = thi_truong.do_nhieu_cum(ung_vien, tran=body.do_toi_da, vung=vung)
                    db.kw_luu_thi_truong(c, ws, r['ket_qua'])
                    do_kq = {'da_do': r['da_do'], 'quota_da_tieu': r['quota_da_tieu']}
                except RuntimeError as e:
                    do_kq = {'loi_do': str(e)}      # quét vẫn giữ, chỉ mất phần đo
        return {**kq, 'loi_goi': dem.da_goi, 'cham_tran': dem.da_goi >= dem.tran,
                'do': do_kq, 'vung': vung, 'cum': muc[:50]}


@app.get('/api/workspaces/{ws}/discovery/goi-y-seed')
def goi_y_seed_api(ws: int, request: Request):
    """Seed ĐÚNG NGÁCH, rút từ chính title video pool đang theo dõi.

    Sự cố 21/08: ô seed để tự do → user gõ 'vietnam' → autocomplete trả 'vietnam
    airlines', 'vietnam khmer rouge war' — cả vũ trụ chủ đề, không cụm nào thuộc ngách.
    """
    from . import mapping
    with get_conn() as c:
        u = auth.require_user(c, request)
        w = auth.ws_for_user(c, ws, u['id'])
        _, ngon_ngu = _vung_cua_ws(w)
        return {'seed': mapping.goi_y_seed(mapping.tai_kho(c, ws), ngon_ngu=ngon_ngu),
                'ngon_ngu': ngon_ngu, 'market': w['market']}


@app.get('/api/workspaces/{ws}/mapping')
def mapping_api(ws: int, request: Request):
    """Bản đồ của POOL đang mở: tóm tắt pool + cầu + cung nội bộ + THỊ TRƯỜNG THẬT.

    Viewer xem được (giống Board) — đây là thứ để ĐỌC, không sửa.
    """
    from . import mapping
    with get_conn() as c:
        u = auth.require_user(c, request)
        w = auth.ws_for_user(c, ws, u['id'])
        pool = db.tom_tat_pool(c, ws)
        vung, ngon_ngu = _vung_cua_ws(w)
        pool.update({'ten': w['name'], 'ngach': w['ngach'], 'market': w['market'],
                     'ngon_ngu': ngon_ngu, 'vung': vung})
        # Cảnh báo pool trộn ngôn ngữ (pool gốc = hàng chờ, hay lẫn kênh thị trường khác)
        kho_ = mapping.tai_kho(c, ws)
        if kho_:
            lac = sum(1 for v in kho_ if not mapping.hop_ngon_ngu(v['title'], ngon_ngu))
            pool['ti_le_khac_ngon_ngu'] = round(100 * lac / len(kho_))
            pool['so_video_tieng_viet'] = sum(1 for v in kho_ if mapping.la_tieng_viet(v['title']))
        cums = db.kw_danh_sach(c, ws)
        if not cums:
            return {'muc': [], 'du_mau': False, 'chua_quet': True, 'pool': pool,
                    'ly_do_thieu_mau': 'Chưa quét cầu lần nào — bấm "Quét cầu" với một seed.',
                    'nhan_o': mapping.NHAN_O, 'nhan_qd': mapping.NHAN_QD}
        bd = mapping.ban_do(mapping.tai_kho(c, ws), cums)
        bd = mapping.gan_thi_truong(bd, db.kw_thi_truong(c, ws), pool.get("view_giua_moi"))
        bd['nhan_o'] = mapping.NHAN_O
        bd['pool'] = pool
        return bd


# Tab DANG NONG (22/08 — user: "qua nhieu tu khoa hot bi bo qua", chot "cho phep
# tieu quota"): danh sach 0 quota tu mapping.tu_khoa_nong; kem NGAN SACH tu soi
# thi truong ngoai cho cum nong chua co ban luu — toi da NGAN_SACH_NONG cum/ngay/
# pool, chay NEN sau khi tra response (khong bat user cho 102 units x N). Cum da
# soi thi ban B nam trong tra_cuu_log -> lan sau doc lai 0 quota, bam cum la mo
# ban day du. Dem ca ban B do tay trong ngay vao ngan sach: dem thua an toan hon
# dem thieu (quota la tien).
NGAN_SACH_NONG = 5


def _soi_nen_nong(ws: int, cums: list[str], vung: dict | None):
    for cum in cums:
        try:
            _soi_khoi_b(ws, cum, vung, trends=False)   # trends chay trinh duyet ~17s/cum
        except Exception:                               # noqa: BLE001 — nen: lo thi bo cum do
            pass


@app.get('/api/workspaces/{ws}/discovery/tu-khoa-nong')
def tu_khoa_nong_api(ws: int, request: Request, nhiem_vu_nen: BackgroundTasks,
                     ngon_ngu: str = ''):
    from . import mapping
    with get_conn() as c:
        u = auth.require_user(c, request)
        w = auth.ws_for_user(c, ws, u['id'])
        duoc_soi = auth.ROLE_RANK.get(w['member_role'], -1) >= auth.ROLE_RANK['leader']
        vung, tu_de = _vung_cua_ws(w)
        loc = ngon_ngu.strip() or tu_de
        ra = mapping.tu_khoa_nong(mapping.tai_kho(c, ws), ngon_ngu=loc)
        if not ra.get('co_du_lieu'):
            return ra
        # dinh ket qua ngoai da luu + dem ngan sach hom nay
        dau_ngay = time.time() - (time.time() % 86400)
        da_soi_hom_nay = 0
        for r in c.execute("SELECT b FROM tra_cuu_log WHERE workspace_id=? AND b!=''", (ws,)):
            try:
                if (json.loads(r['b']).get('ts') or 0) >= dau_ngay:
                    da_soi_hom_nay += 1
            except ValueError:
                pass
        chua_soi = []
        for m in ra['cum']:
            luu = db.tra_cuu_doc(c, ws, m['cum'])
            b = (luu or {}).get('b')
            if b:
                yt = (b.get('youtube') or {})
                m['ngoai'] = {'ts': b.get('ts'),
                              'tong_view_90n': yt.get('tong_view_90n'),
                              'so_ket_qua': yt.get('so_ket_qua')}
            else:
                chua_soi.append(m['cum'])
    con = max(0, NGAN_SACH_NONG - da_soi_hom_nay)
    soi_ngay = chua_soi[:con] if duoc_soi else []
    if soi_ngay:
        nhiem_vu_nen.add_task(_soi_nen_nong, ws, soi_ngay, vung)
        for m in ra['cum']:
            if m['cum'] in soi_ngay:
                m['dang_soi'] = True
    ra.update({'ngan_sach_ngay': NGAN_SACH_NONG, 'da_soi_hom_nay': da_soi_hom_nay,
               'dang_soi': soi_ngay, 'duoc_soi': duoc_soi})
    return ra


@app.get('/api/workspaces/{ws}/discovery/tu-khoa-noi')
def tu_khoa_noi(ws: int, request: Request, so_cum: int = 30, ngon_ngu: str = '',
                cua_so: int = 7):
    """Cụm nào trong pool ĐANG LÊN / ĐANG GIẢM — 0 quota, đọc dữ liệu sẵn có.

    Không phải chờ tích luỹ: `pub_ts` của video trong pool có từ 2009 nên mật độ cụm
    theo tháng dựng được ngay. Pool lại được scheduler quét liên tục nên số tự cập
    nhật mỗi vòng quét — "realtime" theo nhịp pool.
    """
    from . import mapping, tra_cuu
    with get_conn() as c:
        u = auth.require_user(c, request)
        w = auth.ws_for_user(c, ws, u['id'])
        _, tu_de = _vung_cua_ws(w)
        # Pool CHƯA gắn thị trường thì đế không cho biết ngôn ngữ -> trước đây không lọc
        # gì, nên cụm tiếng Việt lọt vào pool đang xem (user báo 21/08). Nay người chọn
        # được; pool có thị trường thì vẫn tự động theo đế.
        loc = ngon_ngu.strip() or tu_de
        kho = mapping.tai_kho(c, ws)
        if cua_so not in tra_cuu.CUA_SO_HOP_LE:
            cua_so = 7           # user chốt 22/08: mặc định NHÌN GẦN, nới ra khi cần
        # UNG VIEN trich tu VUNG DANG DO (ky nay + ky truoc), khong phai top tan suat
        # toan lich su (user 22/08: "khong co ly do gi ma khong tong hop duoc tu khoa
        # cua hang nghin video"). Top tich luy la tieu chi nguoc voi cum dang noi —
        # cung goc benh voi Hot Topic (98% sot): cua so 7 ngay ma ung vien lay tu
        # tron doi thi cum moi nhu tuan nay vo hinh. Toan-thoi-gian (0) giu tron kho.
        kho_uv = kho if cua_so == 0 else             [v for v in kho if (v.get('pub_ts') or 0) >= time.time() - 2 * cua_so * 86400]
        # HAI LOAI từ khoá, user 21/08 chỉ ra thiếu loại thứ hai:
        #   mẫu câu  — cụm 2-3 từ lặp lại ("life in", "travel documentary")
        #   ĐỐI TƯỢNG — nước/địa danh/chủ thể, thường MỘT từ nên n-gram bỏ sót
        mau = [g['seed'] for g in mapping.goi_y_seed(kho_uv, so_goi_y=max(1, min(so_cum, 60)),
                                                     ngon_ngu=loc, moi_vi_tri=True)]
        dt = [d['cum'] for d in mapping.doi_tuong(kho_uv, so_muc=max(1, min(so_cum, 40)),
                                                  ngon_ngu=loc)]
        cums = mau + [x for x in dt if x not in mau]
        # Nhan LOAI theo luat tu-loai (user chot 22/08): cum danh tu = doi tuong —
        # "solar system"/"james webb" tu goi_y_seed cung la doi tuong, khong chi
        # danh sach dt. Thieu nltk -> phieu None -> ve nhan theo nguon nhu cu.
        phieu = mapping.bang_pos(kho_uv, loc)
        if phieu is not None:
            loai = {c: mapping.loai_cum(c, phieu) for c in cums}
        else:
            loai = {**{m: 'mau_cau' for m in mau}, **{x: 'doi_tuong' for x in dt}}
        dem_nn = {}
        for v in kho:
            ma = mapping.nhan_dien_ngon_ngu(v['title'])
            if ma:
                dem_nn[ma] = dem_nn.get(ma, 0) + 1
        # xu huong + canh tranh do trong cua so; do tren TRON kho (tong_video can
        # tron doi), chi UNG VIEN la trich tu vung do.
        xh = tra_cuu.xu_huong_cum(kho, cums, cua_so=cua_so)
        for m in xh:
            m['loai'] = loai.get(m['cum'], 'mau_cau')
        return {'cum': xh,
                'cach_lay': ('Đếm trên tiêu đề video trong chính pool này. ĐỐI TƯỢNG = danh '
                             'từ hoặc tên riêng (nhận diện TỪ LOẠI — tag chữ thường + đối '
                             'chiếu từ điển 234k từ). MẪU CÂU = cụm lặp lại còn lại (tính '
                             'từ / động từ / trạng từ).'),
                'cua_so_ngay': cua_so or tra_cuu.CUA_SO_NGAY, 'so_video_pool': len(kho),
                'cua_so': cua_so,
                'ngon_ngu_loc': loc, 'tu_de': bool(tu_de),
                'ngon_ngu_trong_pool': sorted(dem_nn.items(), key=lambda x: -x[1])}


@app.get('/api/workspaces/{ws}/tra-cuu/lich-su')
def tra_cuu_lich_su(ws: int, request: Request, limit: int = 30):
    """Từ khoá đã tra ở pool này. Có route riêng để mở tab (hoặc F5) là thấy ngay —
    trước đó lịch sử chỉ về kèm kết quả tra cứu nên F5 xong là trắng bảng."""
    with get_conn() as c:
        u = auth.require_user(c, request)
        auth.ws_for_user(c, ws, u['id'])
        return {'lich_su': db.tra_cuu_danh_sach(c, ws, limit=max(1, min(limit, 100)))}


# ĐÃ GỠ route /tra-cuu/so-sanh (21/08). Nó xếp hạng mọi từ khoá đã tra ở pool theo
# tổng view 90 ngày — nhưng user chỉ ra đúng: MỖI TỪ KHOÁ LÀ MỘT PHIÊN, đo ở thời điểm
# khác nhau (cửa sổ 90 ngày trượt theo ngày đo) và phạm vi khác nhau (địa danh vs mẫu
# câu). Đặt cạnh nhau để so là so hai thứ không cùng hệ quy chiếu.
# Lịch sử tra cứu giữ nguyên, nhưng CHỈ để xem lại từng phiên — không tổng hợp.

@app.get('/api/workspaces/{ws}/tra-cuu')
def tra_cuu_pool(ws: int, request: Request, cum: str = '', xem_lai: int = 0):
    """KHỐI A — pool đang mở làm gì với từ khoá này + xu hướng theo lứa đăng.

    Đọc SQLite thuần: 0 quota, dưới 1 giây. Viewer xem được.
    """
    from . import mapping, tra_cuu
    if not cum.strip():
        raise HTTPException(422, 'thiếu từ khoá')
    with get_conn() as c:
        u = auth.require_user(c, request)
        w = auth.ws_for_user(c, ws, u['id'])
        vung, ngon_ngu = _vung_cua_ws(w)
        pool = db.tom_tat_pool(c, ws)
        pool.update({'ten': w['name'], 'ngach': w['ngach'], 'market': w['market'],
                     'ngon_ngu': ngon_ngu, 'vung': vung})
        q = cum.strip()
        cu = db.tra_cuu_doc(c, ws, q)
        # KHỐI A LUÔN TÍNH TƯƠI, không bao giờ đọc cache (22/08 — user báo "in pool
        # không có video nào về kyrgyzstan, không tin nổi"): bản do PROBE NỀN của
        # Hot Topic tạo chỉ có khối B, cột a rỗng '{}' → xem lại thấy khối A trắng
        # trong khi pool có 12 video thật. Khối A đọc SQLite dưới 1 giây và 0 quota
        # nên cache nó vừa vô ích vừa đẻ ra bản thiếu; cache CHỈ dành cho khối B
        # (nơi tốn units/tiền). Tính tươi còn được thêm: luật/pool đổi thì số đổi theo.
        if xem_lai and cu and not (cu.get('a') or {}).get('co_du_lieu'):
            kho_t = mapping.tai_kho(c, ws)
            a_tuoi = tra_cuu.xu_huong_pool(kho_t, q)
            gon_t = tra_cuu.cum_rut_gon(q)
            if gon_t and a_tuoi.get('co_du_lieu'):
                ag_t = tra_cuu.xu_huong_pool(kho_t, gon_t)
                if ag_t.get('co_du_lieu'):
                    a_tuoi['doi_chieu'] = {'cum': gon_t, 'so_video': ag_t['so_video'],
                                           'so_kenh': ag_t['so_kenh'],
                                           'ti_trong_view': ag_t['ti_trong_view'],
                                           'vph_giua': ag_t.get('vph_giua')}
            if a_tuoi.get('co_du_lieu'):
                db.tra_cuu_luu(c, ws, q, a=a_tuoi)      # vá luôn bản lưu thiếu
                cu = db.tra_cuu_doc(c, ws, q)
        if xem_lai:                           # xem lại: KHÔNG tính lại, KHÔNG gọi gì
            if not cu:
                # Không có bản lưu thì "xem lại" KHÔNG được biến thành tra mới: làm vậy
                # là từ khoá của pool khác tự chui vào lịch sử pool này (user báo 22/08 —
                # "từ khoá ở thị trường nào giữ nguyên thị trường đó"). Chốt ở SERVER nên
                # mọi đường vào đều chặn, không chỉ nút bấm.
                return {'cum': q, 'pool': pool, 'trong_pool': None,
                        'khong_co_ban_luu': True,
                        'lich_su': db.tra_cuu_danh_sach(c, ws)}
            return {'cum': q, 'pool': pool, 'trong_pool': cu['a'], 'ngoai': cu['b'],
                    'tu_lich_su': True, 'ts': cu['ts'],
                    'lich_su': db.tra_cuu_danh_sach(c, ws)}
        kho_q = mapping.tai_kho(c, ws)
        a = tra_cuu.xu_huong_pool(kho_q, q)
        # ĐỐI CHIẾU cụm rút gọn: cùng chủ đề nhưng bỏ từ khung ("life in X" → "X").
        # 0 quota — chỉ đọc pool. Cho biết mình đang nhìn CÔNG THỨC hay CHỦ ĐỀ.
        gon = tra_cuu.cum_rut_gon(q)
        if gon:
            ag = tra_cuu.xu_huong_pool(kho_q, gon)
            if ag.get('co_du_lieu'):
                a['doi_chieu'] = {'cum': gon, 'so_video': ag['so_video'],
                                  'so_kenh': ag['so_kenh'],
                                  'ti_trong_view': ag['ti_trong_view'],
                                  'vph_giua': ag.get('vph_giua')}
        db.tra_cuu_luu(c, ws, q, a=a)         # khối B giữ nguyên bản cũ nếu đã có
        return {'cum': q, 'pool': pool, 'trong_pool': a,
                'ngoai': (cu or {}).get('b'), 'ts': time.time(),
                'lich_su': db.tra_cuu_danh_sach(c, ws)}


def _ghi_bo_qua_khoa(ham, *a, **kw):
    """Ghi cache/lịch sử — HỎNG THÌ BỎ QUA, không được giết kết quả tra cứu.

    RadarY có scheduler quét trong cùng tiến trình; lúc nó giữ khoá ghi SQLite thì mọi
    lệnh ghi khác nhận "database is locked" (bệnh đã vá 2 tầng 31/07, vẫn còn cửa hẹp).
    Người dùng vừa chờ 20 giây và tiêu 102 units — mất kết quả chỉ vì không ghi nổi
    cache là đánh đổi sai. Mất cache thì lần sau hỏi lại, không mất gì khác.
    """
    try:
        return ham(*a, **kw)
    except sqlite3.OperationalError as e:
        print(f'[tra-cuu] bo qua ghi ({e}) — ket qua van tra ve', flush=True)
        return None


class TraCuuNgoaiIn(BaseModel):
    """Advance Mapping — người dùng tick từng phần (22/08).

    Mỗi phần một loại chi phí khác nhau nên phải tách được: ngoai_pool tiêu
    units YouTube, serp tiêu lượt SERP, Reddit tiêu tiền Apify (route riêng).
    Mặc định BẬT hết để bấm thẳng vẫn ra đầy đủ như trước.
    """
    cum: str
    ngoai_pool: bool = True    # YouTube market — 102 units
    trends: bool = True        # Google Trends + vùng quan tâm — 3 lượt SERP
    serp_google: bool = True   # Câu hỏi thật + liên quan + web — 1 lượt SERP


@app.post('/api/workspaces/{ws}/tra-cuu/ngoai')
def tra_cuu_ngoai(ws: int, body: TraCuuNgoaiIn, request: Request):
    """KHỐI B — thiên hạ đang thịnh hành gì quanh từ khoá này, THEO THỊ TRƯỜNG pool.

    YouTube: video nổi 90 ngày + kênh mới nổi (~102 units). Google Trends: interest
    12 tháng + truy vấn đang lên (0 quota nhưng ~17s vì thư viện chạy trình duyệt).
    Một nguồn chết không giết nguồn kia.
    """
    from . import thi_truong, tra_cuu
    cum = body.cum.strip()
    if not cum:
        raise HTTPException(422, 'thiếu từ khoá')
    with get_conn() as c:
        u = auth.require_user(c, request)
        w = auth.ws_for_user(c, ws, u['id'], 'leader')      # tiêu quota → leader+
        vung, _ = _vung_cua_ws(w)
    return _soi_khoi_b(ws, cum, vung, trends=body.trends,
                       ngoai_pool=body.ngoai_pool, serp_google=body.serp_google)


def _soi_khoi_b(ws: int, cum: str, vung: dict | None, trends: bool = True,
                ngoai_pool: bool = True, serp_google: bool = True) -> dict:
    """Thân khối B — tách khỏi route để tab Đang nóng soi NỀN dùng lại y nguyên
    (cùng dữ liệu, cùng chỗ lưu; bấm cụm là mở được bản đầy đủ)."""
    from . import thi_truong, tra_cuu
    yt = {'co_du_lieu': False, 'ly_do': 'chưa hỏi (bỏ tick Ngoài Pool)'}
    quota = 0
    if ngoai_pool:
        try:
            api_yt = scan.API(khoa_v3.lay_khoa(thi_truong.VIEC_KHOA))
            yt = tra_cuu.ngoai_youtube(api_yt, cum, vung)
            quota = api_yt.used
        except RuntimeError as e:
            yt = {'co_du_lieu': False, 'ly_do': str(e)}
    geo = (vung or {}).get('regionCode') or 'US'
    lang = (vung or {}).get('relevanceLanguage') or 'en'
    # SERP (Owner chốt 22/08): 2 lời gọi/cụm — Trends ổn định (thay trendspyg chạy
    # trình duyệt, đo thật chỉ 43% thành công) + MỘT lời gọi google gộp ba khối
    # (câu hỏi thật / tìm kiếm liên quan / kết quả web). Chưa cấp khóa → bỏ qua
    # êm, khối cũ chạy nguyên như trước.
    from . import serp as _serp
    bo_serp = _serp.BoKhoa(khoa_v3.lay_khoa_day_du('tra_cuu_ngoai'))
    sp = {'co_khoa': bo_serp.con_khoa(), 'da_tieu': 0, 'loi': ''}
    # Biến thể người ta GÕ quanh từ khoá — luôn có dữ liệu, kể cả khi Trends im lặng
    # (từ khoá hẹp như 'life in alaska' thì Trends trả related rỗng). 0 quota, ~9s.
    from . import discovery
    if not ngoai_pool:
        bt = {}
    else:
        bt = discovery.mo_rong(cum, discovery.BoDem(tran=9), vung=vung, tu_hoi=False)
    bien_the = sorted(({'cum': k, 'do_phu': v['do_phu'], 'hang': v['hang_tot_nhat'],
                        'nguon': 'youtube'}
                       for k, v in bt.items() if k != cum.lower()),
                      key=lambda m: (-m['do_phu'], m['hang']))[:10]
    # Nguồn gợi ý THỨ HAI (Bing): ra cụm mà YouTube autocomplete không gợi ý. Chỉ giữ
    # cụm MỚI so với danh sách trên — trùng thì không thêm dòng vô ích.
    da_co = {m['cum'] for m in bien_the} | {cum.lower()}
    bien_the += [{'cum': c, 'do_phu': None, 'hang': i + 1, 'nguon': 'bing'}
                 for i, c in enumerate(discovery.goi_y_bing(cum, vung=vung))
                 if c not in da_co][:8]
    # Trends: đọc cache trong NGÀY trước — Google chặn theo IP, hỏi lại cùng từ khoá
    # vừa vô ích vừa làm dính rate limit lâu hơn.
    # Hai đường dẫn tới đây: probe nền của Hot Topic (cố ý tắt để khỏi đốt quota)
    # và người bỏ tick Google Trends trong Advance Mapping. Cùng một cách chữa —
    # bấm nút "Lấy Google Trends" — nên nói chung một câu, khỏi phân biệt vô ích.
    tr = {'co_du_lieu': False, 'tu_nen': True,
          'ly_do': 'Chưa lấy Google Trends (bỏ tick, hoặc bản do quét nền tạo)'}
    if trends:
        with get_conn() as c2:
            try:
                tr = db.trends_doc(c2, cum, geo) or {}
            except sqlite3.OperationalError:
                tr = {}
            if tr:
                tr['tu_cache'] = True
            elif bo_serp.con_khoa():
                try:
                    tr = bo_serp.chay(_serp.trends, cum, geo=geo)
                    lq = bo_serp.chay(_serp.truy_van_lien_quan, cum, geo=geo)
                    tr.update(lq)
                    tr['vung'] = bo_serp.chay(_serp.theo_vung, cum, geo=geo)
                except Exception as e:                       # noqa: BLE001
                    sp['loi'] = str(e)
                    tr = {'co_du_lieu': False, 'ly_do': f'SERP: {e}'}
                if tr.get('co_du_lieu'):
                    _ghi_bo_qua_khoa(db.trends_ghi, c2, cum, geo, tr)
            else:
                tr = tra_cuu.google_trends(cum, geo=geo)
                if tr.get('co_du_lieu'):
                    _ghi_bo_qua_khoa(db.trends_ghi, c2, cum, geo, tr)
    # Hai nguồn 0 key, nhanh (~1-2s): tin báo đang nói gì + mức quan tâm trên Wikipedia.
    # Reddit đã thử cả .json lẫn .rss đều 403 từ IP này; X/Twitter cần bản trả phí.
    gg = {'co_du_lieu': False, 'ly_do': 'chưa cấp khóa SERP cho việc tra_cuu_ngoai'}
    if not serp_google:
        gg = {'co_du_lieu': False, 'ly_do': 'chưa hỏi (bỏ tick Google Trends/SERP)'}
    elif bo_serp.con_khoa():
        try:
            gg = bo_serp.chay(_serp.google, cum, geo=geo, lang=lang)
        except Exception as e:                               # noqa: BLE001
            sp['loi'] = str(e)
            gg = {'co_du_lieu': False, 'ly_do': f'SERP: {e}'}
    sp['da_tieu'] = bo_serp.da_tieu
    sp['khoa_het'] = bo_serp.het
    sp['con_khoa'] = bo_serp.con_khoa()
    ra = {'cum': cum, 'youtube': yt, 'trends': tr, 'google': gg, 'serp': sp,
          'bien_the': bien_the,
          'news': tra_cuu.google_news(cum, geo=geo, lang=lang),
          'wiki': tra_cuu.wikipedia(cum, lang=lang),
          'quota_da_tieu': quota, 'vung': vung, 'ts': time.time()}
    with get_conn() as c3:                     # lưu để xem lại không tốn quota lần hai
        _ghi_bo_qua_khoa(db.tra_cuu_luu, c3, ws, cum, b=ra)
        try:
            ra['lich_su'] = db.tra_cuu_danh_sach(c3, ws)
        except sqlite3.OperationalError:
            ra['lich_su'] = []
    return ra


@app.get('/api/workspaces/{ws}/tra-cuu/report')
def tra_cuu_report(ws: int, request: Request, cum: str = '', json: int = 0):
    """Xuất báo cáo MỘT từ khoá (khối A/B/C) ra Markdown — 0 quota.

    Dựng từ BẢN LƯU, không gọi nguồn nào; khối A tính tươi như mọi khi (đọc
    SQLite dưới 1 giây). Markdown vì Owner đưa cho AI đọc: rẻ token nhất mà vẫn
    giữ cấu trúc bảng, không như PDF hay vỡ bảng lúc trích xuất.
    """
    from . import mapping, report_cum, tra_cuu
    q = cum.strip()
    if not q:
        raise HTTPException(422, 'thiếu từ khoá')
    with get_conn() as c:
        u = auth.require_user(c, request)
        w = auth.ws_for_user(c, ws, u['id'])          # xem được thì xuất được
        vung, ngon_ngu = _vung_cua_ws(w)
        pool = db.tom_tat_pool(c, ws)
        pool.update({'ten': w['name'], 'ngach': w['ngach'], 'market': w['market'],
                     'ngon_ngu': ngon_ngu})
        kho = mapping.tai_kho(c, ws)
        a = tra_cuu.xu_huong_pool(kho, q)
        gon = tra_cuu.cum_rut_gon(q)
        if gon:
            ag = tra_cuu.xu_huong_pool(kho, gon)
            if ag.get('co_du_lieu'):
                a['doi_chieu'] = {'cum': gon, 'so_video': ag['so_video'],
                                  'so_kenh': ag['so_kenh'],
                                  'ti_trong_view': ag['ti_trong_view']}
        cu = db.tra_cuu_doc(c, ws, q) or {}
    md = report_cum.dung(q, pool, a, cu.get('b'), ts=cu.get('ts') or time.time(),
                         kem_json=bool(json))
    ten = ''.join(ch if ch.isalnum() or ch in ' -_' else '' for ch in q).strip() or 'tu-khoa'
    ten = f"radary-{ten.replace(' ', '-')}.md"
    return Response(md, media_type='text/markdown; charset=utf-8',
                    headers={'Content-Disposition':
                             f'attachment; filename="{urllib.parse.quote(ten)}"'})


class TrendsIn(BaseModel):
    cum: str = ""


@app.post('/api/workspaces/{ws}/tra-cuu/trends')
def tra_cuu_trends(ws: int, body: TrendsIn, request: Request):
    """BỔ SUNG Google Trends cho bản lưu thiếu.

    Bản lưu do probe nền của Hot Topic tạo thì Trends bị TẮT có chủ đích —
    nền chạy 5 cụm/ngày, nếu mỗi cụm nuốt 3 lượt SERP thì riêng đường nền đã
    ~450 lượt/tháng, vượt xa gói free 100. Giữ nguyên tắc "quota chỉ tiêu khi
    NGƯỜI quyết định": ai mở xem thật thì bấm, 3 lượt SERP.
    """
    from . import serp as _serp
    cum = body.cum.strip()
    if not cum:
        raise HTTPException(422, 'thiếu từ khoá')
    with get_conn() as c:
        u = auth.require_user(c, request)
        w = auth.ws_for_user(c, ws, u['id'], 'leader')       # tiêu quota → leader+
        vung, _ = _vung_cua_ws(w)
    geo = (vung or {}).get('regionCode') or 'US'
    bo = _serp.BoKhoa(khoa_v3.lay_khoa_day_du('tra_cuu_ngoai'))
    if not bo.con_khoa():
        return {'co_du_lieu': False,
                'ly_do': 'Chưa cấp khóa SERP cho việc tra_cuu_ngoai — General › API Keys'}
    try:
        tr = bo.chay(_serp.trends, cum, geo=geo)
        tr.update(bo.chay(_serp.truy_van_lien_quan, cum, geo=geo))
        tr['vung'] = bo.chay(_serp.theo_vung, cum, geo=geo)
    except Exception as e:                                   # noqa: BLE001
        return {'co_du_lieu': False, 'ly_do': f'SERP: {e}'}
    with get_conn() as c2:
        if tr.get('co_du_lieu'):
            _ghi_bo_qua_khoa(db.trends_ghi, c2, cum, geo, tr)
        cu = db.tra_cuu_doc(c2, ws, cum) or {}
        b = cu.get('b') if isinstance(cu.get('b'), dict) else {}
        b = b or {'cum': cum}
        b['trends'] = tr
        _ghi_bo_qua_khoa(db.tra_cuu_luu, c2, ws, cum, b=b)
    tr['da_tieu'] = bo.da_tieu
    return tr


class RedditIn(BaseModel):
    cum: str = ""
    ky: str = "year"                 # year | month | week | all


@app.post('/api/workspaces/{ws}/tra-cuu/reddit')
def tra_cuu_reddit(ws: int, body: RedditIn, request: Request):
    """Reddit ĐÚNG NGHĨA (upvote/bình luận/subreddit) qua Apify — TỐN TIỀN nên
    chỉ chạy khi người bấm, đúng khuôn nút "Hỏi lại (102 units)" của khối B.
    Kết quả ghi vào bản lưu để mở lại 0 đồng."""
    from . import reddit as _rd
    cum = body.cum.strip()
    if not cum:
        raise HTTPException(422, 'thiếu từ khoá')
    with get_conn() as c:
        u = auth.require_user(c, request)
        auth.ws_for_user(c, ws, u['id'], 'leader')          # tiêu tiền → leader+
    ks = khoa_v3.lay_khoa_day_du('reddit')
    if not ks:
        return {'co_du_lieu': False,
                'ly_do': 'Chưa cấp khóa Apify cho việc reddit — General › API Keys'}
    try:
        ra = _rd.tim(ks[0]['key'], cum, ky=(body.ky or 'year'))
    except _rd.HetCredit:
        ra = {'co_du_lieu': False,
              'ly_do': 'Apify hết credit tháng (gói FREE $5) — đợi sang tháng hoặc nâng gói'}
    except Exception as e:                                   # noqa: BLE001
        ra = {'co_du_lieu': False, 'ly_do': f'Apify: {e}'}
    ra['credit'] = _rd.du_credit(ks[0]['key'])
    # nhap vao ban luu khoi B de mo lai khong ton dong nao
    with get_conn() as c2:
        cu = db.tra_cuu_doc(c2, ws, cum) or {}
        b = (cu.get('b') or {}) if isinstance(cu.get('b'), dict) else {}
        b['reddit'] = ra
        b.setdefault('cum', cum)
        _ghi_bo_qua_khoa(db.tra_cuu_luu, c2, ws, cum, b=b)
    return ra


class DoThiTruongIn(BaseModel):
    cum: list[str] = []      # rỗng = tự lấy các cụm CHƯA đo, theo thứ tự cầu cao trước
    tran: int = 10           # trần cụm mỗi lần bấm (~102 units/cụm)


@app.post('/api/workspaces/{ws}/discovery/do-thi-truong')
def do_thi_truong(ws: int, body: DoThiTruongIn, request: Request):
    """Đo THỊ TRƯỜNG THẬT cho cụm: YouTube trả bao nhiêu view cho video mới, cụm còn
    sống không, KÊNH NHỎ CÓ LỌT TOP KHÔNG. Đây là tầng thiếu của bản Mapping đầu tiên
    (user chỉ ra 21/08: hai vế đều lấy từ thứ RadarY đã biết → không quyết định được gì).

    Khoá lấy từ KÉT OUTLIERY (General › API Keys) — mọi khoá đều ở General.
    """
    from . import mapping, thi_truong
    with get_conn() as c:
        u = auth.require_user(c, request)
        w = auth.ws_for_user(c, ws, u['id'], 'leader')   # tiêu quota → leader+
        vung, _ = _vung_cua_ws(w)
        cums = [x.strip().lower() for x in body.cum if x.strip()]
        if not cums:
            da_do = set(db.kw_thi_truong(c, ws))
            cums = [m['cum'] for m in db.kw_danh_sach(c, ws) if m['cum'] not in da_do]
        if not cums:
            return {'da_do': 0, 'ghi_chu': 'mọi cụm đã có số liệu thị trường hôm nay'}
        tran = max(1, min(int(body.tran), thi_truong.TRAN_CUM))
        try:
            kq = thi_truong.do_nhieu_cum(cums, tran=tran, vung=vung)
        except RuntimeError as e:                        # chưa cấp khoá / gateway chết
            raise HTTPException(400, str(e))
        ghi = db.kw_luu_thi_truong(c, ws, kq['ket_qua'])
        return {**{k: v for k, v in kq.items() if k != 'ket_qua'}, **ghi,
                'nhan_qd': mapping.NHAN_QD}


class BoQuaIn(BaseModel):
    cum: str
    bo: bool = True


@app.post('/api/workspaces/{ws}/keywords/bo-qua')
def keyword_bo_qua(ws: int, body: BoQuaIn, request: Request):
    """Gạt cụm nhiễu khỏi bản đồ — GỠ MỀM, bật lại được, lịch sử giữ nguyên."""
    with get_conn() as c:
        u = auth.require_user(c, request)
        auth.ws_for_user(c, ws, u['id'], 'leader')
        n = db.kw_bo_qua(c, ws, body.cum, body.bo)
        if not n:
            raise HTTPException(404, 'không có cụm này trong workspace')
        return {'ok': True, 'cum': body.cum.strip().lower(), 'bo_qua': body.bo}


@app.get('/api/workspaces/{ws}/keywords/lich-su')
def keyword_lich_su(ws: int, request: Request, cum: str = ''):
    """Chuỗi theo ngày của một cụm — thứ chỉ RadarY làm được (nó có scheduler)."""
    with get_conn() as c:
        u = auth.require_user(c, request)
        auth.ws_for_user(c, ws, u['id'])
        if not cum.strip():
            raise HTTPException(422, 'thiếu cụm')
        return {'cum': cum.strip().lower(), 'chuoi': db.kw_lich_su(c, ws, cum)}


@app.get('/api/workspaces/{ws}/alerts')
def alerts(ws: int, request: Request, limit: int = 100, offset: int = 0, kind: str = ''):
    """Tab Cảnh báo gom theo đơn vị (mockup user duyệt 24/07/2026). Trả object có 'mode':
    tier (mặc định)→waves (Đang sống/Đã lắng) · retitle|rethumb→channels · dead/purge/pool/config→flat."""
    with get_conn() as c:
        u = auth.require_user(c, request)
        auth.ws_for_user(c, ws, u['id'])
        return alertsview.view(c, ws, kind, limit, offset)

class VerdictIn(BaseModel):
    action: str          # acted | ignored

@app.post('/api/workspaces/{ws}/alerts/{event_id}/verdict')
def set_verdict(ws: int, event_id: int, body: VerdictIn, request: Request):
    if body.action not in ('acted', 'ignored'): raise HTTPException(422, 'action phải là acted|ignored')
    with get_conn() as c:
        u = auth.require_user(c, request)
        auth.ws_for_user(c, ws, u['id'], 'leader')      # verdict = thẩm định ghi vào DB, viewer chỉ xem
        ev = c.execute('SELECT id FROM events WHERE id=? AND workspace_id=?', (event_id, ws)).fetchone()
        if not ev: raise HTTPException(404, 'event không tồn tại trong workspace này')
        with c:
            c.execute('INSERT OR REPLACE INTO verdicts(event_id, action, ts) VALUES(?,?,?)',
                      (event_id, body.action, time.time()))
        return {'event_id': event_id, 'action': body.action}

# ---------------- tab Báo cáo (Phase 5 — viewer xem được, tổng quan sửa bởi leader+) ----------------
class OverviewIn(BaseModel):
    md: str

@app.get('/api/workspaces/{ws}/reports')
def reports_list(ws: int, request: Request):
    with get_conn() as c:
        u = auth.require_user(c, request)
        auth.ws_for_user(c, ws, u['id'])
        items = report.list_reports(c, ws)
        items[0]['meta'] = niche_report.status(c, ws)   # trạng thái sinh báo cáo ngách (mục ghim)
        return items

@app.get('/api/workspaces/{ws}/reports/{rid}')
def report_read(ws: int, rid: str, request: Request):
    with get_conn() as c:
        u = auth.require_user(c, request)
        auth.ws_for_user(c, ws, u['id'])
        r = report.read_report(c, ws, rid)
        if r is None: raise HTTPException(404, 'báo cáo không tồn tại')
        return r

@app.put('/api/workspaces/{ws}/overview')
def put_overview(ws: int, body: OverviewIn, request: Request):
    """Ghi đè tay nội dung tổng quan (markdown) — lối thoát qua API; đường chính là refresh tự sinh."""
    with get_conn() as c:
        u = auth.require_user(c, request)
        auth.ws_for_user(c, ws, u['id'], 'leader')
        with c:
            db.kv_set(c, ws, 'overview_doc', body.md)
        return {'saved': True, 'chars': len(body.md)}

@app.post('/api/workspaces/{ws}/overview/refresh', status_code=202)
def overview_refresh(ws: int, request: Request):
    """Sinh lại BÁO CÁO NGÁCH từ pool đối thủ (Phase 6) — chạy nền, leader trở lên.
    Quét full uploads (cap 300/kênh) → OX v3 + LIFT/FDR + bảng cược → ghi đè tổng quan."""
    with get_conn() as c:
        u = auth.require_user(c, request)
        auth.ws_for_user(c, ws, u['id'], 'leader')
        if not db.api_keys(c, ws):
            raise HTTPException(400, 'org chưa có API key — thêm trong tab Quản trị')
        n = c.execute('SELECT COUNT(*) FROM channels WHERE workspace_id=? AND active=1', (ws,)).fetchone()[0]
        if not n:
            raise HTTPException(400, 'pool chưa có kênh nào — thêm đối thủ trước')
    if not niche_report.start(ws):
        raise HTTPException(409, 'đang có lượt sinh báo cáo chạy — chờ nó xong')
    return {'started': True, 'channels': n,
            'note': 'quét chạy nền vài phút — trạng thái hiện ngay trên tab Báo cáo'}

# ---------------- hiệu chỉnh ngưỡng (căn cứ dữ liệu, không chỉnh theo cảm giác) ----------------
@app.get('/api/workspaces/{ws}/calibration')
def calibration(ws: int, request: Request):
    """Phân phối VPH quan sát được (board hiện tại + events 14 ngày) → đề xuất THÔ sàn T1-T4.
    Spec: sàn chỉnh theo phân phối thực sau ≥2 tuần dữ liệu — trước đó chỉ là tham khảo."""
    with get_conn() as c:
        u = auth.require_user(c, request)
        auth.ws_for_user(c, ws, u['id'])
        vphs = []
        board_d = db.kv_get(c, ws, 'board', None)
        if board_d:
            for co in board_d['cohorts']: vphs += [v['vph'] for v in co['videos'] if v['vph'] > 0]
        for r in c.execute("SELECT payload FROM events WHERE workspace_id=? AND kind='tier' AND ts>=?",
                           (ws, time.time() - 14*86400)):
            p = json.loads(r['payload'])
            if p.get('vph', 0) > 0: vphs.append(p['vph'])
        vphs.sort()
        def pct(p): return round(vphs[min(int(len(vphs)*p), len(vphs)-1)], 1) if vphs else 0
        cfg = db.get_config(c, ws)
        first_seen = c.execute('SELECT MIN(ts) FROM ticks WHERE video_id IN '
                               '(SELECT id FROM videos WHERE workspace_id=?)', (ws,)).fetchone()[0]
        days = round((time.time() - first_seen)/86400, 1) if first_seen else 0
        return {'n': len(vphs), 'days_of_data': days, 'reliable': days >= 14,
                'p50': pct(0.5), 'p80': pct(0.8), 'p90': pct(0.9), 'p95': pct(0.95), 'p99': pct(0.99),
                'max': vphs[-1] if vphs else 0,
                'current': {k: cfg[k] for k in ('T1_vph', 'T2_vph', 'T3_vph', 'T4_vph')},
                'suggested': {'T1_vph': pct(0.80), 'T2_vph': pct(0.95), 'T3_vph': pct(0.99),
                              'T4_vph': round(pct(0.99)*3, 1)}}

# ---------------- channels (pool) ----------------
class ChannelsIn(BaseModel):
    items: list          # URL /channel/UC…, @handle, /user/…, UC-id trần

@app.get('/api/workspaces/{ws}/channels')
def channels(ws: int, request: Request):
    with get_conn() as c:
        u = auth.require_user(c, request)
        auth.ws_for_user(c, ws, u['id'], 'leader')      # 23/07: Data Pool = leader trở lên
        return [dict(r) for r in c.execute(
            'SELECT yt_id, title, active, favorite FROM channels WHERE workspace_id=? ORDER BY title', (ws,))]

def _khoa_quet(c, ws):
    """V3: khóa từ KÉT theo việc quet_dinh_ky (khuôn run_cycle — KHÔNG fallback
    bảng nội bộ; trả nợ 19/08: add_channels từng đọc bảng nội bộ nên pool MỚI
    chỉ với được khóa org-wide cũ → 403 hết vòng). Standalone: bảng nội bộ như V2."""
    if _v3():
        from . import khoa_v3
        try:
            return khoa_v3.lay_khoa('quet_dinh_ky')
        except RuntimeError as e:
            raise HTTPException(503, str(e))
    keys = db.api_keys(c, ws)
    if not keys:
        raise HTTPException(400, 'niche này chưa có key YouTube — owner gắn KEY CHÍNH trong '
                                 'Cài đặt của niche (hoặc key toàn org trong tab Quản trị)')
    return keys

@app.post('/api/workspaces/{ws}/channels')
def add_channels(ws: int, body: ChannelsIn, request: Request):
    items = [str(x) for x in body.items if str(x).strip()]
    if not items: raise HTTPException(400, 'items rỗng')
    with get_conn() as c:
        u = auth.require_user(c, request)
        auth.ws_for_user(c, ws, u['id'], 'leader')
        keys = _khoa_quet(c, ws)
        try:
            found = scan.resolve_channels(scan.API(keys), items)
        except RuntimeError as e:      # YouTube từ chối mọi khóa — trả lỗi đọc được thay vì 500 trần
            raise HTTPException(503, f'YouTube API từ chối khi resolve kênh: {str(e)[:200]}')
        if not found: raise HTTPException(422, 'không resolve được kênh nào từ input')
        added, existing, reactivated = [], [], []
        with c:
            for cid, info in found.items():
                cur = c.execute('SELECT id, active FROM channels WHERE workspace_id=? AND yt_id=?', (ws, cid)).fetchone()
                if cur and cur['active']:
                    existing.append({'yt_id': cid, 'title': info['title']})      # trùng — không đụng gì
                elif cur:                                                        # từng gỡ mềm → khôi phục
                    c.execute('UPDATE channels SET active=1, title=?, uploads_playlist=? WHERE id=?',
                              (info['title'], info['uploads'], cur['id']))
                    reactivated.append({'yt_id': cid, 'title': info['title']})
                else:
                    c.execute('INSERT INTO channels(workspace_id, yt_id, title, uploads_playlist) VALUES(?,?,?,?)',
                              (ws, cid, info['title'], info['uploads']))
                    added.append({'yt_id': cid, 'title': info['title']})
            if added or reactivated:
                db.append_events(c, ws, [{'ts': time.time(), 'kind': 'pool_change',
                                          'added': [a['yt_id'] for a in added],
                                          'reactivated': [a['yt_id'] for a in reactivated], 'by': u['email']}])
                c.execute('UPDATE jobs SET due_ts=0 WHERE workspace_id=? AND name=?', (ws, 'discover'))
        return {'added': added, 'reactivated': reactivated, 'existing': existing,
                'resolved': len(found), 'input': len(items)}

class FavoriteIn(BaseModel):
    favorite: bool

@app.post('/api/workspaces/{ws}/channels/{yt_id}/favorite')
def set_favorite(ws: int, yt_id: str, body: FavoriteIn, request: Request):
    """Phase 3.10: bật/tắt ⭐ cho kênh — trạng thái chung cả workspace, leader trở lên."""
    with get_conn() as c:
        u = auth.require_user(c, request)
        auth.ws_for_user(c, ws, u['id'], 'leader')
        with c:
            n = c.execute('UPDATE channels SET favorite=? WHERE workspace_id=? AND yt_id=?',
                          (1 if body.favorite else 0, ws, yt_id)).rowcount
        if not n: raise HTTPException(404, 'kênh không có trong pool')
        return {'yt_id': yt_id, 'favorite': body.favorite}

@app.get('/api/workspaces/{ws}/channels/{yt_id}/info')
def channel_profile(ws: int, yt_id: str, request: Request):
    with get_conn() as c:
        u = auth.require_user(c, request)
        auth.ws_for_user(c, ws, u['id'], 'leader')      # hồ sơ kênh thuộc Data Pool — leader trở lên
        ch = c.execute('SELECT * FROM channels WHERE workspace_id=? AND yt_id=?', (ws, yt_id)).fetchone()
        if not ch: raise HTTPException(404, 'kênh không có trong pool')
        keys = _khoa_quet(c, ws)
        try:
            return channel_info.get_info(c, ch, scan.API(keys))
        except LookupError as e:
            raise HTTPException(404, str(e))

@app.delete('/api/workspaces/{ws}/channels/{yt_id}')
def remove_channel(ws: int, yt_id: str, request: Request):
    """Gỡ kênh = xóa luôn video/tick/lịch sử packaging của kênh (lệnh user 08/07/2026).
    events giữ nguyên (append-only); dòng kênh soft (active=0) để còn khôi phục được."""
    with get_conn() as c:
        u = auth.require_user(c, request)
        auth.ws_for_user(c, ws, u['id'], 'leader')
        with c:
            n = c.execute('UPDATE channels SET active=0 WHERE workspace_id=? AND yt_id=?', (ws, yt_id)).rowcount
            purged = 0
            if n:
                gone = {r['yt_id'] for r in c.execute(
                    'SELECT yt_id FROM videos WHERE workspace_id=? AND channel_yt_id=?', (ws, yt_id))}
                sub = 'SELECT id FROM videos WHERE workspace_id=? AND channel_yt_id=?'
                for t in ('ticks', 'title_hist', 'thumb_hist'):
                    c.execute(f'DELETE FROM {t} WHERE video_id IN ({sub})', (ws, yt_id))
                purged = c.execute('DELETE FROM videos WHERE workspace_id=? AND channel_yt_id=?',
                                   (ws, yt_id)).rowcount
                board = db.kv_get(c, ws, 'board', None)
                if board and gone:          # dọn board NGAY — không bắt user chờ chu kỳ quét kế
                    for co in board.get('cohorts', []):
                        co['videos'] = [v for v in co['videos'] if v['yt_id'] not in gone]
                        co['size'] = len(co['videos'])
                    board['allages'] = [v for v in board.get('allages', []) if v['yt_id'] not in gone]
                    db.kv_set(c, ws, 'board', board)
                db.append_events(c, ws, [{'ts': time.time(), 'kind': 'pool_change', 'removed': [yt_id],
                                          'purged_videos': purged, 'by': u['email']}])
        if not n: raise HTTPException(404, 'kênh không có trong pool')
        return {'removed': yt_id, 'purged_videos': purged, 'note': 'board đã được dọn ngay'}

class MoveIn(BaseModel):
    to_ws: int
    yt_ids: list[str]
    confirm: bool = False

@app.post('/api/workspaces/{ws}/channels/move')
def move_channels(ws: int, body: MoveIn, request: Request):
    """TÁCH POOL THEO THỊ TRƯỜNG (18/08 — docs/RADARY_THI_TRUONG.md): chuyển kênh
    sang pool khác cùng org, GIỮ LỊCH SỬ — channels/videos đổi workspace_id
    (ticks/title_hist/thumb_hist bám video_id nên nguyên vẹn), channel_stats cộng
    dồn sang đích theo tên kênh, channel_snap chuyển theo ch_yt_id. events ở lại
    (append-only, sử liệu) + ghi pool_change cả 2 bên. pool_stats KHÔNG tách —
    nhịp pool đích chỉ tích từ lúc chuyển (trung thực, không bịa quá khứ).
    manager trở lên (thao tác dữ liệu lớn, cùng nấc xóa workspace)."""
    ids = [s.strip() for s in body.yt_ids if s.strip()]
    if not ids: raise HTTPException(400, 'yt_ids rỗng')
    if body.to_ws == ws: raise HTTPException(422, 'pool đích trùng pool nguồn')
    if not body.confirm: raise HTTPException(422, 'cần confirm=true — chuyển kênh dời cả lịch sử theo dõi sang pool đích')
    with get_conn() as c:
        u = auth.require_user(c, request)
        w_from = auth.ws_for_user(c, ws, u['id'], 'manager')
        w_to = auth.ws_for_user(c, body.to_ws, u['id'], 'manager')
        if w_from['org_id'] != w_to['org_id']:
            raise HTTPException(422, 'hai pool không cùng org')
        rows = c.execute(f'SELECT id, yt_id, title FROM channels WHERE workspace_id=? '
                         f'AND yt_id IN ({",".join("?"*len(ids))})', (ws, *ids)).fetchall()
        thieu = set(ids) - {r['yt_id'] for r in rows}
        if thieu: raise HTTPException(404, f'kênh không có trong pool nguồn: {", ".join(sorted(thieu))}')
        trung = [r['title'] or r['yt_id'] for r in c.execute(
            f'SELECT yt_id, title FROM channels WHERE workspace_id=? '
            f'AND yt_id IN ({",".join("?"*len(ids))})', (body.to_ws, *ids))]
        if trung: raise HTTPException(409, f'pool đích đã có kênh: {", ".join(trung)}')
        moved_videos = 0
        gone = {r2['yt_id'] for r2 in c.execute(       # video yt_id của các kênh sắp chuyển — dọn board nguồn (khuôn remove_channel)
            f'SELECT yt_id FROM videos WHERE workspace_id=? '
            f'AND channel_yt_id IN ({",".join("?"*len(ids))})', (ws, *ids))}
        with c:
            for r in rows:
                c.execute('UPDATE channels SET workspace_id=? WHERE id=?', (body.to_ws, r['id']))
                moved_videos += c.execute('UPDATE videos SET workspace_id=? WHERE workspace_id=? '
                                          'AND channel_yt_id=?', (body.to_ws, ws, r['yt_id'])).rowcount
                # nhịp kênh (giữ vĩnh viễn) đi theo kênh — trùng bucket ở đích (trùng tên kênh) thì cộng dồn
                c.execute('INSERT INTO channel_stats(workspace_id, bucket_ts, ch, dviews) '
                          'SELECT ?, bucket_ts, ch, dviews FROM channel_stats WHERE workspace_id=? AND ch=? '
                          'ON CONFLICT(workspace_id, bucket_ts, ch) DO UPDATE SET dviews=dviews+excluded.dviews',
                          (body.to_ws, ws, r['title']))
                c.execute('DELETE FROM channel_stats WHERE workspace_id=? AND ch=?', (ws, r['title']))
                c.execute('INSERT INTO channel_snap(workspace_id, day, ch_yt_id, subs, total_views, video_count, ts) '
                          'SELECT ?, day, ch_yt_id, subs, total_views, video_count, ts FROM channel_snap '
                          'WHERE workspace_id=? AND ch_yt_id=? ON CONFLICT DO NOTHING',
                          (body.to_ws, ws, r['yt_id']))
                c.execute('DELETE FROM channel_snap WHERE workspace_id=? AND ch_yt_id=?', (ws, r['yt_id']))
            board = db.kv_get(c, ws, 'board', None)
            if board and gone:          # dọn board nguồn NGAY (khuôn remove_channel); board đích tự có ở chu kỳ kế
                for co in board.get('cohorts', []):
                    co['videos'] = [v for v in co['videos'] if v['yt_id'] not in gone]
                    co['size'] = len(co['videos'])
                board['allages'] = [v for v in board.get('allages', []) if v['yt_id'] not in gone]
                db.kv_set(c, ws, 'board', board)
            ke = {'ts': time.time(), 'kind': 'pool_change', 'by': u['email'],
                  'moved_channels': ids, 'moved_videos': moved_videos}
            db.append_events(c, ws, [{**ke, 'moved_to': body.to_ws}])
            db.append_events(c, body.to_ws, [{**ke, 'moved_from': ws}])
        return {'moved': ids, 'moved_videos': moved_videos, 'to_ws': body.to_ws,
                'note': 'lịch sử kênh/video đi theo; nhịp pool đích tích từ giờ trở đi'}

# ---------------- config ----------------
CONFIG_EDITABLE = {'T1_vph', 'T2_vph', 'T3_vph', 'T4_vph', 'T1_frac', 'T2_rank', 'T2_daily_cap',
                   'allages_vpd_floor', 'min_duration_s', 'thumb_cap', 'purge_min',
                   'ntfy_topic', 'ntfy_enabled', 'cadence'}

@app.get('/api/workspaces/{ws}/config')
def get_config(ws: int, request: Request):
    with get_conn() as c:
        u = auth.require_user(c, request)
        auth.ws_for_user(c, ws, u['id'])
        return db.get_config(c, ws)

@app.put('/api/workspaces/{ws}/config')
def put_config(ws: int, body: dict, request: Request):
    bad = set(body) - CONFIG_EDITABLE
    if bad: raise HTTPException(422, f'trường không cho sửa: {sorted(bad)}')
    with get_conn() as c:
        u = auth.require_user(c, request)
        auth.ws_for_user(c, ws, u['id'], 'leader')
        cfg = db.get_config(c, ws)
        old = {k: cfg.get(k) for k in body}
        cfg.update(body)
        with c:
            db.set_config(c, ws, cfg, actor=u['email'])
            db.append_events(c, ws, [{'ts': time.time(), 'kind': 'config_change', 'old': old, 'new': body, 'by': u['email']}])
        return cfg

# ---------------- chart sóng video T2+ (roadmap Phase 3.5) ----------------
def _t2_video_or_404(c, ws, yt_id):
    """Video của workspace nếu đã/từng đạt T2+ — chart và AI-đọc-chart chung một cổng."""
    v = c.execute('SELECT * FROM videos WHERE workspace_id=? AND yt_id=?', (ws, yt_id)).fetchone()
    if not v: raise HTTPException(404, 'video không có trong workspace')
    reached_t2 = v['tier'] >= 2 or v['pushed'] >= 2
    if not reached_t2:          # từng đạt T2+ trong quá khứ cũng được xem
        for r in c.execute("SELECT payload FROM events WHERE workspace_id=? AND kind='tier' "
                           'AND video_yt_id=?', (ws, yt_id)):
            try:
                if json.loads(r['payload']).get('to', 0) >= 2: reached_t2 = True; break
            except Exception: pass
    if not reached_t2: raise HTTPException(404, 'chart chỉ mở cho video đã đạt T2 trở lên')
    return v

@app.get('/api/workspaces/{ws}/videos/{yt_id}/series')
def video_series(ws: int, yt_id: str, request: Request):
    with get_conn() as c:
        u = auth.require_user(c, request)
        auth.ws_for_user(c, ws, u['id'])
        v = _t2_video_or_404(c, ws, yt_id)
        return series.video_series(c, ws, v, time.time())

@app.post('/api/workspaces/{ws}/videos/{yt_id}/explain')
def explain_chart(ws: int, yt_id: str, request: Request):
    """Phase 7: AI đọc biểu đồ sóng — diễn giải đúng dữ liệu chart đang vẽ, leader trở lên."""
    with get_conn() as c:
        u = auth.require_user(c, request)
        w = auth.ws_for_user(c, ws, u['id'], 'leader')
        v = _t2_video_or_404(c, ws, yt_id)
        cfg = llm.org_llm(c, w['org_id'])
        if not cfg: raise HTTPException(400, 'org chưa cấu hình LLM — owner vào tab Quản trị thêm key')
        remaining = _llm_quota(u['id'])
        data = series.video_series(c, ws, v, time.time())
        try:
            answer = llm.explain_series(cfg, data)
        except RuntimeError as e:
            raise HTTPException(502, str(e))
        return {'answer': answer, 'remaining_today': remaining}

# ---------------- gửi thử push (kiểm tra điện thoại đã subscribe đúng chưa) ----------------
@app.post('/api/workspaces/{ws}/push-test')
def push_test(ws: int, request: Request):
    with get_conn() as c:
        u = auth.require_user(c, request)
        w = auth.ws_for_user(c, ws, u['id'], 'leader')
        cfg = db.get_config(c, ws)
        if not cfg.get('ntfy_topic'): raise HTTPException(400, 'workspace chưa có ntfy topic')
        try:
            scan.ntfy_send(cfg['ntfy_topic'], f"Radary — tin thử ({w['name']})",
                           'Nhận được tin này = điện thoại đã kết nối đúng ✅',
                           priority=4, tags=('white_check_mark',))
        except Exception as e:
            raise HTTPException(502, f'gửi tới ntfy.sh thất bại: {e}')
        return {'sent': True, 'note': 'kiểm tra điện thoại trong vài giây tới; không kêu = subscribe sai topic'}

# ---------------- chạy chu kỳ thủ công ----------------
@app.post('/api/workspaces/{ws}/run')
def run_now(ws: int, request: Request, budget: float = 120.0):
    with get_conn() as c:
        u = auth.require_user(c, request)
        auth.ws_for_user(c, ws, u['id'], 'leader')
        if not scheduler.LOCK.acquire(timeout=180):
            raise HTTPException(423, 'đang có chu kỳ khác chạy — thử lại sau')
        try:
            return scan.run_cycle(c, ws, min(budget, 570.0))
        except RuntimeError as e:      # API YouTube từ chối — trả lỗi đọc được thay vì 500 trần
            msg = str(e)
            if 'quota' in msg.lower() or '403' in msg:
                raise HTTPException(503, 'YouTube API hết quota ngày trên TẤT CẢ key — quota tự hồi 14:00 giờ VN. '
                                         'Lưu ý: nhiều key chung 1 dự án Google Cloud vẫn chỉ có 10K/ngày; '
                                         'muốn nhân quota phải tạo key từ các DỰ ÁN khác nhau.')
            raise HTTPException(502, f'YouTube API lỗi: {msg[:200]}')
        finally:
            scheduler.LOCK.release()

# ---------------- xóa workspace (hành động hủy — bắt xác nhận đúng tên) ----------------
@app.delete('/api/workspaces/{ws}')
def delete_workspace(ws: int, request: Request, confirm: str = ''):
    with get_conn() as c:
        u = auth.require_user(c, request)
        # 04/08/2026: 'owner' → 'manager' — xóa workspace là VẬN HÀNH nặng (Manager bộ phận
        # chủ quản làm được), khác quản trị org (key/thành viên/LLM vẫn owner-only).
        w = auth.ws_for_user(c, ws, u['id'], 'manager')
        if confirm != w['name']:
            raise HTTPException(422, f'phải xác nhận đúng tên workspace (confirm={w["name"]!r}) mới được xóa')
        with c:
            c.execute('DELETE FROM verdicts WHERE event_id IN (SELECT id FROM events WHERE workspace_id=?)', (ws,))
            c.execute('DELETE FROM ticks WHERE video_id IN (SELECT id FROM videos WHERE workspace_id=?)', (ws,))
            c.execute('DELETE FROM title_hist WHERE video_id IN (SELECT id FROM videos WHERE workspace_id=?)', (ws,))
            c.execute('DELETE FROM thumb_hist WHERE video_id IN (SELECT id FROM videos WHERE workspace_id=?)', (ws,))
            for t in ('videos', 'channels', 'events', 'jobs', 'kv', 'pool_stats'):
                c.execute(f'DELETE FROM {t} WHERE workspace_id=?', (ws,))
            c.execute('DELETE FROM members WHERE workspace_id=?', (ws,))          # thành viên bị giới hạn vào ws này
            c.execute('DELETE FROM invites WHERE workspace_id=? AND used_by IS NULL', (ws,))
            c.execute('DELETE FROM workspaces WHERE id=?', (ws,))
        return {'deleted': ws, 'name': w['name'], 'note': 'ảnh thumbnail/report trên đĩa giữ lại tại data/'}

# ---------------- HARVEST (spec_harvest_1 ĐÓNG BĂNG 23/07/2026 — read-only, advisory) ----------------
class HarvestKeysBulkIn(BaseModel):
    keys_text: str                      # nhiều key, mỗi dòng một key

class HarvestStartIn(BaseModel):
    text: str
    mode: str = ''                      # '' = tự chọn theo số kênh; 'SEED'|'POOL' = ghi đè
    audience: bool = True
    confirm: bool = False               # bắt buộc khi đè job cũ chưa xong

class HarvestSelectIn(BaseModel):
    groups: list
    merge: bool = False

class HarvestRemoveChIn(BaseModel):
    gkey: str
    ch_id: str

@app.post('/api/orgs/{org}/keys/harvest-bulk', status_code=201)
def add_harvest_keys_bulk(org: int, body: HarvestKeysBulkIn, request: Request):
    _sso_quan_tri_dong()   # V3: quan tri org ve mot cua OUTLIERY (API Keys + Permissions)
    """Dán NHIỀU key Harvest một lần (mỗi dòng 1 key) — kho TÁCH RIÊNG, radar không đụng."""
    with get_conn() as c:
        u = auth.require_user(c, request)
        auth.require_role(c, u['id'], org, 'owner')
        have = {crypto.decrypt(r['key']) for r in
                c.execute('SELECT key FROM api_keys WHERE org_id=?', (org,))}
        added, dup, bad = 0, 0, 0
        with c:
            for ln in body.keys_text.splitlines():
                k = ln.strip()
                if not k: continue
                if len(k) < 20: bad += 1; continue
                if k in have: dup += 1; continue        # hàng rào key trùng giữ nguyên
                c.execute('INSERT INTO api_keys(org_id, key, note, harvest) VALUES(?,?,?,1)',
                          (org, crypto.encrypt(k), 'harvest'))
                have.add(k); added += 1
        return {'added': added, 'duplicate': dup, 'invalid': bad}

def _harvest_job_view(c, org):
    job = harvest_runner.current_job(c, org)
    if not job: return {'job': None, 'groups': [], 'results': []}
    groups = []
    for g in c.execute('SELECT * FROM harvest_groups WHERE job_id=? ORDER BY gkey', (job['id'],)):
        meta = json.loads(g['meta'])
        groups.append({'gkey': g['gkey'], 'lang': g['lang'], 'fmt': g['fmt'], 'n': g['n'],
                       'selected': g['selected'], 'desc': meta.get('desc', ''),
                       'keywords': meta.get('keywords', []), 'reps': meta.get('reps', []),
                       'small': meta.get('small'), 'rounds': meta.get('rounds', []),
                       'subs_min': meta.get('subs_min', 0), 'subs_max': meta.get('subs_max', 0),
                       'channels': [{k: ch.get(k) for k in ('id', 'title', 'subs', 'long_ratio')}
                                    for ch in meta.get('channels', [])]})
    results = [dict(r) for r in c.execute(
        'SELECT * FROM harvest_results WHERE job_id=? ORDER BY tier, voc DESC', (job['id'],))]
    t = harvest_runner._threads.get(org)
    return {'job': {k: job[k] for k in ('id', 'mode', 'status', 'audience', 'quota_used',
                                        'quota_est', 'created_ts', 'note')},
            'groups': groups, 'results': results, 'running': bool(t and t.is_alive())}

@app.get('/api/orgs/{org}/harvest')
def harvest_current(org: int, request: Request):
    with get_conn() as c:
        u = auth.require_user(c, request)
        auth.require_role(c, u['id'], org, 'leader')    # 23/07: user siết — viewer không vào Harvest
        return _harvest_job_view(c, org)

@app.post('/api/orgs/{org}/harvest', status_code=201)
def harvest_start(org: int, body: HarvestStartIn, request: Request):
    with get_conn() as c:
        u = auth.require_user(c, request)
        auth.require_role(c, u['id'], org, 'leader')    # tốn quota key → leader trở lên
        if not db.harvest_keys(c, org):
            raise HTTPException(400, 'Kho Key Harvest trống — dán key ở tab Setting (mục Key Harvest) trước')
        parsed = harvest_runner.parse_lines(body.text)
        n = sum(1 for k, *_ in parsed if k != 'bad')
        if not n: raise HTTPException(400, 'không nhận diện được kênh nào trong danh sách dán vào')
        old = harvest_runner.current_job(c, org)
        if old and old['status'] not in ('DONE', 'ERROR') and not body.confirm:
            raise HTTPException(409, f'đang có job {old["status"]} chưa xong — xác nhận mới được đè')
        mode = body.mode if body.mode in ('SEED', 'POOL') else ('SEED' if n <= 5 else 'POOL')
    harvest_runner.start(org, body.text, mode, body.audience)
    return {'mode': mode, 'channels_input': n,
            'bad_lines': [raw for k, _, raw in parsed if k == 'bad']}

@app.post('/api/orgs/{org}/harvest/select')
def harvest_select(org: int, body: HarvestSelectIn, request: Request):
    """User cắt cây: chọn nhóm để snowball (NP5 — máy trưng, người cắt)."""
    with get_conn() as c:
        u = auth.require_user(c, request)
        auth.require_role(c, u['id'], org, 'leader')
        job = harvest_runner.current_job(c, org)
        if not job or job['status'] != 'CLASSIFIED':
            raise HTTPException(409, 'job không ở bước Phân loại Workspace')
        if not body.groups: raise HTTPException(400, 'chưa chọn nhóm nào')
        with c:
            c.execute('UPDATE harvest_groups SET selected=0 WHERE job_id=?', (job['id'],))
            for gk in body.groups:
                c.execute('UPDATE harvest_groups SET selected=1 WHERE job_id=? AND gkey=?',
                          (job['id'], gk))
            ck = json.loads(job['checkpoint'] or '{}')
            ck['merge'] = bool(body.merge); ck['state'] = None
            c.execute('UPDATE harvest_jobs SET status=?, checkpoint=? WHERE id=?',
                      ('SNOWBALL', json.dumps(ck), job['id']))
    harvest_runner.spawn(org)
    return {'ok': True}

@app.post('/api/orgs/{org}/harvest/resume')
def harvest_resume(org: int, request: Request):
    with get_conn() as c:
        u = auth.require_user(c, request)
        auth.require_role(c, u['id'], org, 'leader')
        job = harvest_runner.current_job(c, org)
        if not job or job['status'] not in ('PAUSED', 'ERROR', 'RESOLVING', 'SNOWBALL'):
            raise HTTPException(409, 'không có job đang dở để chạy tiếp')
    started = harvest_runner.spawn(org)
    return {'resumed': started}

@app.post('/api/orgs/{org}/harvest/remove-channel')
def harvest_remove_channel(org: int, body: HarvestRemoveChIn, request: Request):
    """Curation ở bước Phân loại: ✕ kênh khỏi bản nháp — centroid dựng từ phần còn lại."""
    with get_conn() as c:
        u = auth.require_user(c, request)
        auth.require_role(c, u['id'], org, 'leader')
        job = harvest_runner.current_job(c, org)
        if not job or job['status'] != 'CLASSIFIED':
            raise HTTPException(409, 'chỉ loại kênh được ở bước Phân loại Workspace')
        g = c.execute('SELECT meta FROM harvest_groups WHERE job_id=? AND gkey=?',
                      (job['id'], body.gkey)).fetchone()
        if not g: raise HTTPException(404, 'không thấy nhóm')
        meta = json.loads(g['meta'])
        left = [ch for ch in meta.get('channels', []) if ch.get('id') != body.ch_id]
        if len(left) == len(meta.get('channels', [])): raise HTTPException(404, 'kênh không trong nhóm')
        meta['channels'] = left
        with c:
            c.execute('UPDATE harvest_groups SET meta=?, n=? WHERE job_id=? AND gkey=?',
                      (json.dumps(meta), len(left), job['id'], body.gkey))
        return {'gkey': body.gkey, 'n': len(left)}

@app.get('/api/orgs/{org}/harvest/report.md', response_class=PlainTextResponse)
def harvest_report(org: int, request: Request):
    with get_conn() as c:
        u = auth.require_user(c, request)
        auth.require_role(c, u['id'], org, 'leader')    # 23/07: user siết — viewer không vào Harvest
        job = harvest_runner.current_job(c, org)
        if not job: raise HTTPException(404, 'chưa có job Harvest nào')
        md = harvest_runner.report_md(c, job)
    return PlainTextResponse(md, headers={
        'Content-Disposition': f'attachment; filename="harvest_report_{job["id"]}.md"'})

@app.delete('/api/orgs/{org}/harvest')
def harvest_discard(org: int, request: Request, confirm: str = ''):
    with get_conn() as c:
        u = auth.require_user(c, request)
        auth.require_role(c, u['id'], org, 'leader')
        job = harvest_runner.current_job(c, org)
        if not job: raise HTTPException(404, 'không có job nào')
        if confirm != '1': raise HTTPException(422, 'cần confirm=1 — hủy job là xóa bản nháp Harvest')
        with c:
            harvest_runner._purge(c, job['id'])
        return {'discarded': job['id']}

# ---------------- frontend (mount CUỐI CÙNG — mọi route /api ở trên thắng) ----------------
if os.path.isdir(WEB_DIR):
    app.mount('/', StaticFiles(directory=WEB_DIR, html=True), name='web')
