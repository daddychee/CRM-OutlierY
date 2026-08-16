"""NGHIỆM THU PHASE 4 — multi-user + phân tách org + mã hóa key + Docker + phân quyền (Phase 5).

Tiêu chí chốt trước:
  1. Chưa đăng nhập → API 401 (trang login vẫn public)
  2. Đăng ký/đăng nhập hoạt động; 2 tài khoản KHÔNG thấy dữ liệu của nhau
  3. Tài khoản migrate (chưa mật khẩu) bootstrap được; email đã có mật khẩu → 409
  4. API key lưu trong DB là bản mã hóa Fernet — plaintext không nằm trong DB
  5. Docker files sẵn sàng (build thật cần Docker — báo SKIP nếu máy chưa cài)
  6. Phase 5: 3 bậc vai (viewer 403 mọi endpoint ghi, leader không xem key, owner toàn quyền)
     + mã mời (vào đúng org đúng vai, cháy sau 1 lần, hết hạn → lỗi rõ)
  7. Phase 5: tab Báo cáo (tổng quan sống → đóng băng trước tuần đầu, chặn id lạ)
Chạy: .venv/bin/python verify_phase4.py  (server cổng 8739, scheduler TẮT, tự dọn user test)
"""
import json, os, shutil, signal, sqlite3, subprocess, sys, time, urllib.request, urllib.error

BASE = os.path.dirname(os.path.abspath(__file__))
PORT = 8739
URL = f'http://127.0.0.1:{PORT}'
DB = os.path.join(BASE, 'data', 'radary.db')
FAILS = []
def check(name, ok, detail=''):
    print(f"  {'✓' if ok else '✗ FAIL'} {name}" + (f' — {detail}' if detail and not ok else ''))
    if not ok: FAILS.append(name)

def req(method, path, body=None, cookie=''):
    r = urllib.request.Request(URL + path, method=method,
                               data=json.dumps(body).encode() if body is not None else None,
                               headers={'Content-Type': 'application/json',
                                        **({'Cookie': 'radary_session=' + cookie} if cookie else {})})
    try:
        with urllib.request.urlopen(r, timeout=60) as resp:
            raw = resp.read().decode()
            ck = resp.headers.get('Set-Cookie', '')
            tok = ck.split('radary_session=')[1].split(';')[0] if 'radary_session=' in ck else ''
            return resp.status, (json.loads(raw) if resp.headers.get_content_type() == 'application/json' else raw), tok
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(), ''

EMAIL_A, EMAIL_B, EMAIL_BOOT = 'a@verify.test', 'b@verify.test', 'boot@verify.test'
EMAIL_V, EMAIL_E, EMAIL_V2 = 'viewer@verify.test', 'editor@verify.test', 'v2@verify.test'
EMAIL_P, EMAIL_PBOOT, EMAIL_S = 'pub@verify.test', 'pboot@verify.test', 'scoped@verify.test'
EMAILS = (EMAIL_A, EMAIL_B, EMAIL_BOOT, EMAIL_V, EMAIL_E, EMAIL_V2, EMAIL_P, EMAIL_PBOOT, EMAIL_S)
def cleanup():
    c = sqlite3.connect(DB)
    ids = [r[0] for r in c.execute(f"SELECT id FROM users WHERE email IN ({','.join('?'*len(EMAILS))})", EMAILS)]
    for uid in ids:
        orgs = [r[0] for r in c.execute('SELECT org_id FROM members WHERE user_id=?', (uid,))]
        c.execute('DELETE FROM sessions WHERE user_id=?', (uid,))
        c.execute('DELETE FROM members WHERE user_id=?', (uid,))
        c.execute('DELETE FROM invites WHERE created_by=? OR used_by=?', (uid, uid))
        c.execute('DELETE FROM pw_resets WHERE user_id=? OR created_by=?', (uid, uid))
        for og in orgs:
            if not c.execute('SELECT 1 FROM members WHERE org_id=?', (og,)).fetchone():   # org không còn ai
                c.execute('DELETE FROM api_keys WHERE org_id=?', (og,))
                c.execute('DELETE FROM invites WHERE org_id=?', (og,))
                c.execute('DELETE FROM llm_config WHERE org_id=?', (og,))
                c.execute('DELETE FROM channels WHERE workspace_id IN (SELECT id FROM workspaces WHERE org_id=?)', (og,))
                c.execute('DELETE FROM kv WHERE workspace_id IN (SELECT id FROM workspaces WHERE org_id=?)', (og,))
                c.execute('DELETE FROM jobs WHERE workspace_id IN (SELECT id FROM workspaces WHERE org_id=?)', (og,))
                c.execute('DELETE FROM workspaces WHERE org_id=?', (og,))
                c.execute('DELETE FROM orgs WHERE id=?', (og,))
        c.execute('DELETE FROM users WHERE id=?', (uid,))
    c.commit(); c.close()

cleanup()      # dọn tàn dư lần chạy trước (nếu có)
env = dict(os.environ, PORT=str(PORT), RADARY_SCHEDULER='0')
srv = subprocess.Popen([os.path.join(BASE, '.venv', 'bin', 'python'), 'server.py'],
                       cwd=BASE, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    for _ in range(60):
        time.sleep(0.5)
        try:
            s, *_ = req('GET', '/api/health')
            if s == 200: break
        except Exception: pass
    else:
        print('✗ server không lên nổi'); sys.exit(1)

    print('1. CỔNG KHÓA')
    s, _, _ = req('GET', '/api/workspaces')
    check('chưa đăng nhập → 401', s == 401, f'{s}')
    s, page, _ = req('GET', '/')
    check('trang login vẫn public (UI tự xử lý)', s == 200 and 'RADARY' in page)
    s, _, _ = req('GET', '/api/workspaces', cookie='token-gia-mao')
    check('cookie giả → 401', s == 401, f'{s}')

    print('2. HAI TÀI KHOẢN — PHÂN TÁCH DỮ LIỆU')
    s, ra, ck_a = req('POST', '/api/auth/register', {'email': EMAIL_A, 'password': 'matkhau-a-123', 'org_name': 'Org A'})
    check('đăng ký A', s == 201 and ck_a, f'{s}')
    s, wsl, _ = req('GET', '/api/workspaces', cookie=ck_a)
    check('A KHÔNG thấy Life in X (khác org)', s == 200 and all(w['name'] != 'Life in X' for w in wsl))
    s, wsa, _ = req('POST', '/api/workspaces', {'name': 'WS-A'}, cookie=ck_a)
    check('A tạo được workspace', s == 201, f'{s}')
    s, rb, ck_b = req('POST', '/api/auth/register', {'email': EMAIL_B, 'password': 'matkhau-b-123'})
    s, wsl_b, _ = req('GET', '/api/workspaces', cookie=ck_b)
    check('B không thấy WS-A trong danh sách', s == 200 and all(w['name'] != 'WS-A' for w in wsl_b))
    s, _, _ = req('GET', f"/api/workspaces/{wsa['id']}/status", cookie=ck_b)
    check('B truy cập thẳng WS-A → 404 (không lộ tồn tại)', s == 404, f'{s}')
    s, _, _ = req('PUT', f"/api/workspaces/{wsa['id']}/config", {'T2_daily_cap': 99}, cookie=ck_b)
    check('B sửa config WS-A → 404', s == 404, f'{s}')
    s, _, _ = req('POST', '/api/auth/login', {'email': EMAIL_A, 'password': 'sai-mat-khau'})
    check('sai mật khẩu → 401', s == 401, f'{s}')

    print('3. BOOTSTRAP TÀI KHOẢN MIGRATE + CHỐNG CHIẾM EMAIL')
    c = sqlite3.connect(DB)
    c.execute("INSERT INTO users(email, password_hash, created_ts) VALUES(?, '', ?)", (EMAIL_BOOT, time.time()))
    c.commit(); boot_id = c.execute('SELECT id FROM users WHERE email=?', (EMAIL_BOOT,)).fetchone()[0]; c.close()
    s, _, ck_boot = req('POST', '/api/auth/register', {'email': EMAIL_BOOT, 'password': 'matkhau-boot-1'})
    c = sqlite3.connect(DB)
    same = c.execute('SELECT id FROM users WHERE email=?', (EMAIL_BOOT,)).fetchone()[0] == boot_id; c.close()
    check('email migrate chưa mật khẩu → đăng ký = đặt mật khẩu, giữ nguyên user', s == 201 and same)
    s, _, _ = req('POST', '/api/auth/register', {'email': EMAIL_A, 'password': 'chiem-tai-khoan'})
    check('email đã có mật khẩu → 409', s == 409, f'{s}')

    print('4. API KEY MÃ HÓA FERNET')
    FAKE = 'AIzaVERIFY_FAKE_KEY_abcdefghijk123456'
    org_a = ra['orgs'][0]['id']
    s, kr, _ = req('POST', f'/api/orgs/{org_a}/keys', {'key': FAKE}, cookie=ck_a)
    check('thêm key qua API', s == 201, f'{s}')
    s, kl, _ = req('GET', f'/api/orgs/{org_a}/keys', cookie=ck_a)
    check('GET keys chỉ trả bản che (masked)', s == 200 and FAKE not in json.dumps(kl))
    c = sqlite3.connect(DB)
    rows = [r[0] for r in c.execute('SELECT key FROM api_keys').fetchall()]; c.close()
    check('MỌI key trong DB đã mã hóa (gAAAA…)', all(k.startswith('gAAAA') for k in rows), f'{sum(1 for k in rows if not k.startswith("gAAAA"))} plaintext')
    check('plaintext không nằm trong DB', all(FAKE not in k for k in rows))
    sys.path.insert(0, BASE)
    from radary import crypto
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
    dec = [crypto.decrypt(r['key']) for r in c.execute('SELECT key FROM api_keys')]; c.close()
    check('giải mã lại được (engine vẫn quét bình thường)', FAKE in dec and all(d.startswith('AIza') for d in dec))
    s, _, _ = req('GET', f'/api/orgs/{org_a}/keys', cookie=ck_b)
    check('B xem key org A → 404', s == 404, f'{s}')

    print('5. PHÂN QUYỀN 3 BẬC + MÃ MỜI (Phase 5)')
    wsa_id = wsa['id']
    s, inv_v, _ = req('POST', f'/api/orgs/{org_a}/invites', {'role': 'viewer'}, cookie=ck_a)
    check('owner tạo mã mời viewer', s == 201 and inv_v.get('code', '').startswith('rdy-'), f'{s}')
    s, inv_e, _ = req('POST', f'/api/orgs/{org_a}/invites', {'role': 'leader'}, cookie=ck_a)
    check('owner tạo mã mời leader', s == 201, f'{s}')
    s, _, _ = req('POST', f'/api/orgs/{org_a}/invites', {'role': 'owner'}, cookie=ck_a)
    check('mã mời owner → 422 (không mời owner qua mã)', s == 422, f'{s}')
    s, rv, ck_v = req('POST', '/api/auth/register', {'email': EMAIL_V, 'password': 'matkhau-v-123', 'invite': inv_v['code']})
    check('đăng ký bằng mã viewer → vào org A đúng vai', s == 201 and
          any(o['id'] == org_a and o['role'] == 'viewer' for o in rv.get('orgs', [])), f'{s}')
    check('người vào bằng mã KHÔNG có org riêng', len(rv.get('orgs', [])) == 1)
    s, _, _ = req('POST', '/api/auth/register', {'email': EMAIL_V2, 'password': 'matkhau-v2-12', 'invite': inv_v['code']})
    check('mã đã dùng → 422', s == 422, f'{s}')
    s, re_, ck_e = req('POST', '/api/auth/register', {'email': EMAIL_E, 'password': 'matkhau-e-123', 'invite': inv_e['code']})
    check('đăng ký bằng mã leader', s == 201, f'{s}')
    s, inv_x, _ = req('POST', f'/api/orgs/{org_a}/invites', {'role': 'viewer'}, cookie=ck_a)
    c = sqlite3.connect(DB); c.execute('UPDATE invites SET expires_ts=0 WHERE code=?', (inv_x['code'],)); c.commit(); c.close()
    s, _, _ = req('POST', '/api/auth/register', {'email': EMAIL_V2, 'password': 'matkhau-v2-12', 'invite': inv_x['code']})
    check('mã hết hạn → 422', s == 422, f'{s}')
    s, _, _ = req('GET', f'/api/workspaces/{wsa_id}/status', cookie=ck_v)
    check('viewer XEM được workspace của org', s == 200, f'{s}')
    s, _, _ = req('PUT', f'/api/workspaces/{wsa_id}/config', {'T2_daily_cap': 9}, cookie=ck_v)
    check('viewer sửa config → 403', s == 403, f'{s}')
    s, _, _ = req('POST', f'/api/workspaces/{wsa_id}/channels', {'items': ['@x']}, cookie=ck_v)
    check('viewer thêm kênh → 403', s == 403, f'{s}')
    s, _, _ = req('POST', f'/api/workspaces/{wsa_id}/run', None, cookie=ck_v)
    check('viewer chạy quét → 403', s == 403, f'{s}')
    s, _, _ = req('GET', f'/api/orgs/{org_a}/keys', cookie=ck_v)
    check('viewer xem keys → 403', s == 403, f'{s}')
    s, _, _ = req('GET', f'/api/orgs/{org_a}/keys', cookie=ck_e)
    check('leader xem keys → 403 (chỉ owner)', s == 403, f'{s}')
    s, _, _ = req('PUT', f'/api/workspaces/{wsa_id}/config', {'T2_daily_cap': 6}, cookie=ck_e)
    check('leader sửa config OK', s == 200, f'{s}')
    s, _, _ = req('DELETE', f'/api/workspaces/{wsa_id}?confirm=WS-A', cookie=ck_e)
    check('leader xóa workspace → 403 (chỉ owner)', s == 403, f'{s}')
    s, _, _ = req('POST', f'/api/orgs/{org_a}/invites', {'role': 'viewer'}, cookie=ck_e)
    check('leader tạo mã mời → 403', s == 403, f'{s}')
    s, ml, _ = req('GET', f'/api/orgs/{org_a}/members', cookie=ck_a)
    check('owner thấy danh sách thành viên đủ 3 người', s == 200 and len(ml) == 3, f'{s} n={len(ml) if s==200 else "?"}')
    # --- phạm vi theo niche + sửa thành viên TẠI CHỖ (lệnh user 08/07/2026) ---
    uid_v = next(m['id'] for m in ml if m['email'] == EMAIL_V)
    uid_a = next(m['id'] for m in ml if m['email'] == EMAIL_A)
    s, wsb, _ = req('POST', '/api/workspaces', {'name': 'WS-B'}, cookie=ck_a)
    check('owner tạo WS-B (nền test phạm vi)', s == 201, f'{s}')
    s, _, _ = req('PATCH', f'/api/orgs/{org_a}/members/{uid_v}', {'role': 'leader'}, cookie=ck_e)
    check('leader sửa thành viên → 403 (chỉ owner)', s == 403, f'{s}')
    s, _, _ = req('PATCH', f'/api/orgs/{org_a}/members/{uid_a}', {'role': 'leader'}, cookie=ck_a)
    check('owner tự sửa chính mình → 422', s == 422, f'{s}')
    s, _, _ = req('PATCH', f'/api/orgs/{org_a}/members/{uid_v}', {'role': 'leader'}, cookie=ck_a)
    check('owner nâng viewer → leader tại chỗ', s == 200, f'{s}')
    s, _, _ = req('PUT', f'/api/workspaces/{wsa_id}/config', {'T2_daily_cap': 7}, cookie=ck_v)
    check('người vừa nâng hạng sửa được config ngay', s == 200, f'{s}')
    s, _, _ = req('PATCH', f'/api/orgs/{org_a}/members/{uid_v}', {'workspace_id': wsb['id']}, cookie=ck_a)
    check('owner gán phạm vi: chỉ WS-B', s == 200, f'{s}')
    s, wsl_v, _ = req('GET', '/api/workspaces', cookie=ck_v)
    check('bị giới hạn → danh sách CHỈ còn WS-B', s == 200 and [w['name'] for w in wsl_v] == ['WS-B'])
    s, _, _ = req('GET', f'/api/workspaces/{wsa_id}/status', cookie=ck_v)
    check('truy cập thẳng niche ngoài phạm vi → 404 (không lộ tồn tại)', s == 404, f'{s}')
    s, _, _ = req('POST', '/api/workspaces', {'name': 'WS-C'}, cookie=ck_v)
    check('leader bị giới hạn 1 niche → không tạo được niche mới (403)', s == 403, f'{s}')
    s, inv_s, _ = req('POST', f'/api/orgs/{org_a}/invites', {'role': 'viewer', 'workspace_id': wsb['id']}, cookie=ck_a)
    check('owner tạo mã mời gắn phạm vi WS-B', s == 201 and inv_s.get('workspace_id') == wsb['id'], f'{s}')
    s, _, ck_s = req('POST', '/api/auth/register', {'email': EMAIL_S, 'password': 'matkhau-s-123', 'invite': inv_s['code']})
    s, wsl_s, _ = req('GET', '/api/workspaces', cookie=ck_s)
    check('đăng ký bằng mã theo phạm vi → chỉ thấy WS-B', s == 200 and [w['name'] for w in wsl_s] == ['WS-B'])
    s, _, _ = req('PATCH', f'/api/orgs/{org_a}/members/{uid_v}', {'role': 'viewer', 'workspace_id': 0}, cookie=ck_a)
    check('owner hạ vai + mở lại toàn org', s == 200, f'{s}')

    print('5b. KEY THEO NICHE + KEY DỰ PHÒNG (Phase 5.1)')
    FAKE_B = 'AIzaVERIFY_BACKUP_abcdefghijk123456'
    FAKE_W = 'AIzaVERIFY_WSONLY_abcdefghijk123456'
    s, kb, _ = req('POST', f'/api/orgs/{org_a}/keys', {'key': FAKE_B, 'backup': True}, cookie=ck_a)
    check('thêm key DỰ PHÒNG toàn org', s == 201 and kb.get('backup') == 1, f'{s}')
    s, kw, _ = req('POST', f'/api/orgs/{org_a}/keys', {'key': FAKE_W, 'workspace_id': wsb['id']}, cookie=ck_a)
    check('thêm key gán riêng WS-B', s == 201 and kw.get('workspace_id') == wsb['id'], f'{s}')
    from radary import db as rdb0
    c2 = rdb0.connect()
    ka_keys = rdb0.api_keys(c2, wsa_id)
    kb_keys = rdb0.api_keys(c2, wsb['id'])
    c2.close()
    check('WS-A: KHÔNG thấy key riêng của WS-B, dự phòng xếp CUỐI vòng xoay',
          FAKE_W not in ka_keys and ka_keys[-1] == FAKE_B)
    check('WS-B: có key riêng + key toàn org, dự phòng vẫn cuối',
          FAKE_W in kb_keys and kb_keys[-1] == FAKE_B)
    s, _, _ = req('PATCH', f'/api/orgs/{org_a}/keys/{kw["id"]}', {'workspace_id': 0, 'backup': 1}, cookie=ck_a)
    check('PATCH đổi phạm vi/loại key tại chỗ', s == 200, f'{s}')
    s, _, _ = req('PATCH', f'/api/orgs/{org_a}/keys/{kw["id"]}', {'workspace_id': 99999999}, cookie=ck_a)
    check('PATCH gán workspace lạ → 404', s == 404, f'{s}')
    s, gk, _ = req('GET', f'/api/orgs/{org_a}/keys', cookie=ck_a)
    check('GET keys trả đủ phạm vi/loại, vẫn chỉ bản che',
          s == 200 and all('masked' in x and 'backup' in x for x in gk) and FAKE_B not in json.dumps(gk))
    s, _, _ = req('POST', f'/api/orgs/{org_a}/keys', {'key': FAKE_B, 'workspace_id': wsa_id}, cookie=ck_a)
    check('dán key ĐÃ TỒN TẠI → 409 (chống nhầm key cũ)', s == 409, f'{s}')
    s, _, _ = req('POST', f'/api/orgs/{org_a}/keys/{kb["id"]}/test', None, cookie=ck_e)
    check('leader kiểm key → 403 (chỉ owner)', s == 403, f'{s}')

    print('6. TAB BÁO CÁO (Phase 5 — tổng quan ngách = tài liệu ghim đầu)')
    s, rl, _ = req('GET', f'/api/workspaces/{wsa_id}/reports', cookie=ck_v)
    check('danh sách luôn có tổng quan ghim đầu (rỗng khi chưa dán)',
          s == 200 and rl[0]['id'] == 'overview' and rl[0]['pinned'] and rl[0]['empty'], f'{s}')
    DOC = '# Niche Analytics — TEST\n\nTC1 tách cung khỏi cầu.'
    s, _, _ = req('PUT', f'/api/workspaces/{wsa_id}/overview', {'md': DOC}, cookie=ck_v)
    check('viewer sửa tổng quan → 403', s == 403, f'{s}')
    s, _, _ = req('PUT', f'/api/workspaces/{wsa_id}/overview', {'md': DOC}, cookie=ck_e)
    check('leader lưu tổng quan OK', s == 200, f'{s}')
    s, doc, _ = req('GET', f'/api/workspaces/{wsa_id}/reports/overview', cookie=ck_v)
    check('viewer đọc được tổng quan vừa lưu', s == 200 and doc.get('md') == DOC, f'{s}')
    s, _, _ = req('GET', f'/api/workspaces/{wsa_id}/reports/xxx', cookie=ck_v)
    check('id lạ → 404 (whitelist chặn path tùy ý)', s == 404, f'{s}')
    wkdir = os.path.join(BASE, 'data', 'reports', str(wsa_id), 'weekly')
    os.makedirs(wkdir, exist_ok=True)
    open(os.path.join(wkdir, '2026-07-05.md'), 'w').write('# BÁO CÁO TUẦN — 2026-07-05 08:00')
    s, rl2, _ = req('GET', f'/api/workspaces/{wsa_id}/reports', cookie=ck_v)
    check('có tuần: tổng quan VẪN ghim đầu, tuần xếp ngay dưới',
          s == 200 and rl2[0]['id'] == 'overview' and not rl2[0]['empty'] and rl2[1]['id'] == '2026-07-05', f'{s}')
    s, wd, _ = req('GET', f'/api/workspaces/{wsa_id}/reports/2026-07-05', cookie=ck_v)
    check('đọc được báo cáo tuần', s == 200 and 'BÁO CÁO TUẦN' in wd.get('md', ''), f'{s}')
    # --- refresh báo cáo ngách tự sinh (Phase 6) ---
    c = sqlite3.connect(DB)
    c.execute('INSERT OR IGNORE INTO channels(workspace_id, yt_id, title, active) VALUES(?,?,?,1)',
              (wsa_id, 'UCverify0000000000000000', 'Kênh test'))
    c.commit(); c.close()
    s, _, _ = req('POST', f'/api/workspaces/{wsa_id}/overview/refresh', None, cookie=ck_v)
    check('viewer sinh báo cáo ngách → 403', s == 403, f'{s}')
    s, rr, _ = req('POST', f'/api/workspaces/{wsa_id}/overview/refresh', None, cookie=ck_e)
    check('leader sinh báo cáo → 202 chạy nền', s == 202, f'{s}')
    st = None
    for _ in range(60):                      # key giả → pipeline phải KẾT THÚC với error rõ, không treo
        time.sleep(0.5)
        s, rl3, _ = req('GET', f'/api/workspaces/{wsa_id}/reports', cookie=ck_e)
        st = ((rl3[0].get('meta') or {}) if s == 200 else {}).get('state')
        if st in ('done', 'error'): break
    check('key giả → trạng thái error tường minh (không treo, không fake done)', st == 'error', f'state={st}')
    # --- gỡ kênh = xóa video kèm theo (lệnh user 08/07/2026) ---
    c = sqlite3.connect(DB)
    vid_id = c.execute("INSERT INTO videos(workspace_id, yt_id, channel_yt_id, channel_title, title, pub_ts) "
                       "VALUES(?, 'vVERIFY0001', 'UCverify0000000000000000', 'Kênh test', 'video test', ?)",
                       (wsa_id, time.time())).lastrowid
    c.execute('INSERT INTO ticks(video_id, ts, views) VALUES(?,?,100)', (vid_id, time.time()))
    c.commit(); c.close()
    s, _, _ = req('DELETE', f'/api/workspaces/{wsa_id}/channels/UCverify0000000000000000', cookie=ck_v)
    check('viewer gỡ kênh → 403', s == 403, f'{s}')
    s, rmv, _ = req('DELETE', f'/api/workspaces/{wsa_id}/channels/UCverify0000000000000000', cookie=ck_e)
    check('leader gỡ kênh → xóa video kèm theo', s == 200 and rmv.get('purged_videos') == 1, f'{s} {rmv}')
    c = sqlite3.connect(DB)
    left_v = c.execute('SELECT COUNT(*) FROM videos WHERE workspace_id=?', (wsa_id,)).fetchone()[0]
    left_t = c.execute('SELECT COUNT(*) FROM ticks WHERE video_id=?', (vid_id,)).fetchone()[0]
    ch_soft = c.execute("SELECT active FROM channels WHERE workspace_id=? AND yt_id='UCverify0000000000000000'",
                        (wsa_id,)).fetchone()
    ev = c.execute("SELECT COUNT(*) FROM events WHERE workspace_id=? AND kind='pool_change'", (wsa_id,)).fetchone()[0]
    c.close()
    check('video + tick đã xóa sạch, kênh còn dòng soft (active=0), event giữ nguyên',
          left_v == 0 and left_t == 0 and ch_soft is not None and ch_soft[0] == 0 and ev >= 1)
    # --- kênh yêu thích ⭐ (Phase 3.10) ---
    s, _, _ = req('POST', f'/api/workspaces/{wsa_id}/channels/UCverify0000000000000000/favorite',
                  {'favorite': True}, cookie=ck_v)
    check('viewer bật ⭐ → 403', s == 403, f'{s}')
    s, _, _ = req('POST', f'/api/workspaces/{wsa_id}/channels/UCverify0000000000000000/favorite',
                  {'favorite': True}, cookie=ck_e)
    check('leader bật ⭐ cho kênh', s == 200, f'{s}')
    s, chl, _ = req('GET', f'/api/workspaces/{wsa_id}/channels', cookie=ck_e)
    check('danh sách kênh trả favorite=1',
          s == 200 and any(x['yt_id'] == 'UCverify0000000000000000' and x['favorite'] == 1 for x in chl))
    s, _, _ = req('GET', f'/api/workspaces/{wsa_id}/channels', cookie=ck_v)
    check('viewer xem Data Pool → 403 (23/07: leader trở lên)', s == 403, f'{s}')
    s, _, _ = req('GET', f'/api/orgs/{org_a}/harvest', cookie=ck_v)
    check('viewer vào Harvest → 403 (23/07: leader trở lên)', s == 403, f'{s}')
    c = sqlite3.connect(DB)
    c.execute('INSERT OR REPLACE INTO kv(workspace_id, k, v) VALUES(?,?,?)', (wsa_id, 'board', json.dumps(
        {'generated_ts': time.time(), 'quota_used': 0, 'push_t2_today': 0, 'push_t2_cap': 5,
         'ntfy_enabled': False, 'allages': [], 'jobs': {},
         'cohorts': [{'day': 0, 'size': 1, 'videos': [
             {'yt_id': 'x1', 'title': 't', 'channel': 'Kênh test', 'ch_id': 'UCverify0000000000000000',
              'tier': 0, 'vph': 1, 'vpd': 1, 'est': False, 'views': 1, 'age_h': 1, 'rank': 1, 'url': 'u'}]}]})))
    c.commit(); c.close()
    s, bd, _ = req('GET', f'/api/workspaces/{wsa_id}/board', cookie=ck_v)
    check('board gắn cờ fav cho video của kênh ⭐',
          s == 200 and bd['cohorts'][0]['videos'][0].get('fav') is True, f'{s}')

    print('6b. LLM DIỄN GIẢI (Phase 7 — quyền + mã hóa, không gọi API thật)')
    s, _, _ = req('GET', f'/api/orgs/{org_a}/llm', cookie=ck_e)
    check('leader xem config LLM → 403 (chỉ owner)', s == 403, f'{s}')
    s, _, _ = req('POST', f'/api/workspaces/{wsa_id}/ask', {'q': 'test'}, cookie=ck_v)
    check('viewer Hỏi Radar → 403', s == 403, f'{s}')
    s, _, _ = req('POST', f'/api/workspaces/{wsa_id}/ask', {'q': 'test'}, cookie=ck_e)
    check('chưa cấu hình LLM → 400 rõ ràng', s == 400, f'{s}')
    s, _, _ = req('PUT', f'/api/orgs/{org_a}/llm',
                  {'provider': 'claude', 'model': '', 'key': 'sk-test-verify-123456'}, cookie=ck_a)
    check('owner lưu config LLM', s == 200, f'{s}')
    c = sqlite3.connect(DB)
    row = c.execute('SELECT key, model FROM llm_config WHERE org_id=?', (org_a,)).fetchone(); c.close()
    check('key LLM mã hóa trong DB + model tự điền mặc định',
          row is not None and row[0].startswith('gAAAA') and row[1] == 'claude-opus-4-8')
    s, gl, _ = req('GET', f'/api/orgs/{org_a}/llm', cookie=ck_a)
    check('GET config chỉ trả bản che', s == 200 and 'sk-test-verify-123456' not in json.dumps(gl))
    s, _, _ = req('PUT', f'/api/orgs/{org_a}/llm', {'provider': 'xxx', 'key': 'k' * 20}, cookie=ck_a)
    check('provider lạ → 422', s == 422, f'{s}')
    s, _, _ = req('POST', f'/api/workspaces/{wsa_id}/videos/vidxxx/explain', None, cookie=ck_v)
    check('viewer AI đọc biểu đồ → 403', s == 403, f'{s}')
    s, _, _ = req('POST', f'/api/workspaces/{wsa_id}/videos/vidxxx/explain', None, cookie=ck_e)
    check('AI đọc biểu đồ video không tồn tại → 404', s == 404, f'{s}')

    print('7. GIA CỐ KHI LỘ INTERNET (rate-limit + invite-only — deploy_vps.md §8)')
    last = 0
    for _ in range(21):
        last, _, _ = req('POST', '/api/auth/login', {'email': 'ratelimit@verify.test', 'password': 'sai-be-bet-1'})
    check('brute-force login → 429 sau 20 lần thử/5 phút', last == 429, f'{last}')
    s, inv_p, _ = req('POST', f'/api/orgs/{org_a}/invites', {'role': 'viewer'}, cookie=ck_a)
    URL_MAIN = URL
    env2 = dict(os.environ, PORT=str(PORT + 1), RADARY_SCHEDULER='0', RADARY_INVITE_ONLY='1')
    srv2 = subprocess.Popen([os.path.join(BASE, '.venv', 'bin', 'python'), 'server.py'],
                            cwd=BASE, env=env2, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        URL = f'http://127.0.0.1:{PORT + 1}'          # req() trỏ sang server INVITE_ONLY
        for _ in range(60):
            time.sleep(0.5)
            try:
                s, *_ = req('GET', '/api/health')
                if s == 200: break
            except Exception: pass
        s, _, _ = req('POST', '/api/auth/register', {'email': EMAIL_P, 'password': 'matkhau-p-123'})
        check('INVITE_ONLY: người lạ đăng ký không mã → 403', s == 403, f'{s}')
        s, _, _ = req('POST', '/api/auth/register', {'email': EMAIL_P, 'password': 'matkhau-p-123', 'invite': inv_p['code']})
        check('INVITE_ONLY: có mã mời → đăng ký được', s == 201, f'{s}')
        c = sqlite3.connect(DB)
        c.execute("INSERT INTO users(email, password_hash, created_ts) VALUES(?, '', ?)", (EMAIL_PBOOT, time.time()))
        c.commit(); c.close()
        s, _, _ = req('POST', '/api/auth/register', {'email': EMAIL_PBOOT, 'password': 'matkhau-pb-12'})
        check('INVITE_ONLY: bootstrap tài khoản migrate vẫn được', s == 201, f'{s}')
    finally:
        URL = URL_MAIN
        srv2.send_signal(signal.SIGTERM); srv2.wait(timeout=10)

    print('7b. RESET MẬT KHẨU (Phase 5.2)')
    s, _, _ = req('POST', f'/api/orgs/{org_a}/members/{uid_v}/pwreset', None, cookie=ck_e)
    check('leader phát mã reset → 403 (chỉ owner)', s == 403, f'{s}')
    s, rst, _ = req('POST', f'/api/orgs/{org_a}/members/{uid_v}/pwreset', None, cookie=ck_a)
    check('owner phát mã reset rs-…', s == 201 and rst.get('code', '').startswith('rs-'), f'{s}')
    s, _, _ = req('POST', '/api/auth/reset', {'email': EMAIL_V, 'code': 'rs-sai-be-bet', 'new_password': 'matkhau-moi-99'})
    check('mã sai → 422', s == 422, f'{s}')
    s, _, ck_v2 = req('POST', '/api/auth/reset', {'email': EMAIL_V, 'code': rst['code'], 'new_password': 'matkhau-moi-99'})
    check('đặt lại mật khẩu + tự đăng nhập luôn', s == 200 and ck_v2, f'{s}')
    s, _, _ = req('GET', '/api/auth/me', cookie=ck_v)
    check('session cũ bị hủy sau reset → 401 (đăng xuất mọi thiết bị)', s == 401, f'{s}')
    s, _, ck_v3 = req('POST', '/api/auth/login', {'email': EMAIL_V, 'password': 'matkhau-moi-99'})
    check('đăng nhập bằng mật khẩu MỚI OK', s == 200 and ck_v3, f'{s}')
    s, _, _ = req('POST', '/api/auth/login', {'email': EMAIL_V, 'password': 'matkhau-v-123'})
    check('mật khẩu cũ → 401', s == 401, f'{s}')
    s, _, _ = req('POST', '/api/auth/reset', {'email': EMAIL_V, 'code': rst['code'], 'new_password': 'matkhau-moi-88'})
    check('mã dùng lại → 422 (1 lần duy nhất)', s == 422, f'{s}')

    print('8. DOCKER')
    check('Dockerfile + docker-compose.yml + .dockerignore sẵn sàng',
          all(os.path.exists(os.path.join(BASE, f)) for f in ('Dockerfile', 'docker-compose.yml', '.dockerignore')))
    have_docker = subprocess.run(['which', 'docker'], capture_output=True).returncode == 0
    if have_docker:
        b = subprocess.run(['docker', 'build', '-q', '-t', 'radary:verify', '.'], cwd=BASE, capture_output=True, timeout=600)
        check('docker build', b.returncode == 0, b.stderr.decode()[-200:])
    else:
        print('  ⊘ SKIP docker build — máy chưa cài Docker (files đã sẵn, build khi cài Docker Desktop/VPS)')
finally:
    srv.send_signal(signal.SIGTERM); srv.wait(timeout=10)
    cleanup()
    try:      # dọn folder report + work dir niche của workspace test (WS-A)
        if 'wsa' in dir() and isinstance(wsa, dict):
            shutil.rmtree(os.path.join(BASE, 'data', 'reports', str(wsa['id'])), ignore_errors=True)
            shutil.rmtree(os.path.join(BASE, 'data', 'niche', str(wsa['id'])), ignore_errors=True)
    except Exception: pass

print()
if FAILS:
    print(f'✗ NGHIỆM THU PHASE 4 THẤT BẠI — {len(FAILS)} mục: {FAILS}'); sys.exit(1)
print('✓ NGHIỆM THU PHASE 4 ĐẠT — auth + phân tách org + key mã hóa hoạt động.')
