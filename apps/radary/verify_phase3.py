"""NGHIỆM THU PHASE 3 — dashboard được serve + luồng "tạo niche mới không đụng file" chạy E2E.

Tiêu chí chốt trước:
  1. FastAPI serve frontend: /, /app.js, vendor modules — 200 và đúng nội dung
  2. Luồng onboarding (đúng các call UI thực hiện): tạo workspace → thêm kênh (resolve
     bằng YouTube API thật) → quét lần đầu → board có dữ liệu — KHÔNG đụng file nào
  3. Vòng tự chấm: verdict ghi được, đọc lại được qua alerts
  4. Calibration trả phân phối + đề xuất sàn
  5. Xóa workspace test: sai tên xác nhận → 422, đúng tên → biến mất
Chạy: python3 verify_phase3.py  (server tự bật cổng 8738, scheduler TẮT, quota ~5 units)
"""
import json, os, secrets, signal, sqlite3, subprocess, sys, time, urllib.request, urllib.error

BASE = os.path.dirname(os.path.abspath(__file__))
PORT = 8738
URL = f'http://127.0.0.1:{PORT}'
FAILS = []
def check(name, ok, detail=''):
    print(f"  {'✓' if ok else '✗ FAIL'} {name}" + (f' — {detail}' if detail and not ok else ''))
    if not ok: FAILS.append(name)

def make_session():
    """Session hợp lệ cho user sở hữu Life in X — bơm thẳng DB, không đụng mật khẩu."""
    c = sqlite3.connect(os.path.join(BASE, 'data', 'radary.db'))
    uid = c.execute("SELECT m.user_id FROM workspaces w JOIN members m ON m.org_id=w.org_id "
                    "WHERE w.name='Life in X' LIMIT 1").fetchone()[0]
    tok = secrets.token_urlsafe(32)
    c.execute('INSERT INTO sessions(token, user_id, created_ts, expires_ts) VALUES(?,?,?,?)',
              (tok, uid, time.time(), time.time() + 3600))
    c.commit(); c.close()
    return tok
SESSION = make_session()

def req(method, path, body=None):
    r = urllib.request.Request(URL + path, method=method,
                               data=json.dumps(body).encode() if body is not None else None,
                               headers={'Content-Type': 'application/json',
                                        'Cookie': 'radary_session=' + SESSION})
    try:
        with urllib.request.urlopen(r, timeout=630) as resp:
            raw = resp.read().decode()
            ct = resp.headers.get_content_type()
            return resp.status, (json.loads(raw) if ct == 'application/json' else raw)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()

env = dict(os.environ, PORT=str(PORT), RADARY_SCHEDULER='0')
srv = subprocess.Popen([os.path.join(BASE, '.venv', 'bin', 'python'), 'server.py'],
                       cwd=BASE, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
test_ws = None
try:
    for _ in range(60):
        time.sleep(0.5)
        try:
            s, _ = req('GET', '/api/health')
            if s == 200: break
        except Exception: pass
    else:
        print('✗ server không lên nổi'); sys.exit(1)

    print('1. SERVE FRONTEND')
    s, htmlpg = req('GET', '/')
    check('GET / trả trang RADARY', s == 200 and 'RADARY' in htmlpg and 'app.js' in htmlpg)
    s, js = req('GET', '/app.js')
    check('GET /app.js có đủ 5 màn hình', s == 200 and all(x in js for x in ('Board', 'Alerts', 'Pool', 'Settings', 'NewNiche')))
    ok_vendor = all(req('GET', f'/vendor/{f}')[0] == 200 for f in ('preact.module.js', 'hooks.module.js', 'htm.module.js'))
    check('vendor Preact/htm serve được', ok_vendor)
    # chốt chặn 24/07/2026: '<' + số trong text template htm bị parse thành TAG "<7" → createElement crash
    # cả tab (sự cố tab Alerts sập vì "<7 ngày"). Text phải viết "dưới 7"/"&lt;" — không bao giờ '<' thô.
    import re as _re
    bad_lt = _re.findall(r'<\d[^=]', js)
    check("app.js không có '<'+số thô trong template (htm parse thành tag → crash render)",
          not bad_lt, f'{bad_lt[:3]}')

    print('2. LUỒNG ONBOARDING NICHE MỚI (như UI bấm, không đụng file)')
    # lấy 1 kênh thật từ pool Life in X làm kênh test (resolve bằng UC-id, ~1 unit)
    s, chans = req('GET', '/api/workspaces/1/channels')
    seed = chans[0]['yt_id']
    s, w = req('POST', '/api/workspaces', {'name': 'VERIFY-P3'})
    test_ws = w.get('id')
    check('POST /workspaces tạo được', s == 201 and test_ws)
    s, r = req('POST', f'/api/workspaces/{test_ws}/channels', {'items': [seed]})
    check('thêm kênh resolve qua YouTube API thật', s == 200 and r['added'], f'{s} {r}')
    s, r2 = req('POST', f'/api/workspaces/{test_ws}/channels', {'items': [seed]})
    check('thêm kênh TRÙNG → báo đã tồn tại, không thêm lại', s == 200 and r2['existing'] and not r2['added'], f'{s} {r2}')
    s, run = req('POST', f'/api/workspaces/{test_ws}/run?budget=300')
    check('quét lần đầu DONE', s == 200 and run.get('tag') == 'DONE', f'{s} {run}')
    check('quét có nạp video (discover)', run.get('videos', 0) > 0, f"{run.get('videos')}")
    s, bd = req('GET', f'/api/workspaces/{test_ws}/board')
    check('board niche mới trả JSON hợp đồng', s == 200 and 'cohorts' in bd and 'jobs' in bd)

    print('3. VÒNG TỰ CHẤM (verdict theo video — mode=waves)')
    s, wv = req('GET', '/api/workspaces/1/alerts?kind=tier')
    allw = (wv.get('alive', []) + wv.get('ended', [])) if s == 200 else []
    cand = next((w for w in allw if w.get('verdict_eid')), None)
    eid = cand['verdict_eid'] if cand else None
    s, _ = req('POST', f'/api/workspaces/1/alerts/{eid}/verdict', {'action': 'acted'})
    check('POST verdict acted', s == 200)
    s, wv2 = req('GET', '/api/workspaces/1/alerts?kind=tier')
    back = next((w for w in (wv2.get('alive', []) + wv2.get('ended', [])) if w['yt'] == cand['yt']), {}) if cand else {}
    check('verdict đọc lại được qua thẻ sóng', s == 200 and back.get('verdict') == 'acted')
    s, _ = req('POST', f'/api/workspaces/1/alerts/{eid}/verdict', {'action': 'sai'})
    check('action lạ → 422', s == 422, f'{s}')

    print('4. CALIBRATION (căn cứ chỉnh sàn)')
    s, cal = req('GET', '/api/workspaces/1/calibration')
    need = {'n', 'p50', 'p90', 'p95', 'p99', 'current', 'suggested', 'days_of_data', 'reliable'}
    check('đủ trường phân phối + đề xuất', s == 200 and not (need - set(cal)), f'thiếu {need - set(cal) if s==200 else s}')
    check('có dữ liệu VPH thực (n>0)', s == 200 and cal['n'] > 0, f"n={cal.get('n')}")

    print('5. CHART SÓNG T2+ (Phase 3.5)')
    dbc = sqlite3.connect(os.path.join(BASE, 'data', 'radary.db'))
    t2 = dbc.execute('SELECT yt_id FROM videos WHERE workspace_id=1 AND (tier>=2 OR pushed>=2) LIMIT 1').fetchone()
    cold = dbc.execute("SELECT yt_id FROM videos WHERE workspace_id=1 AND tier=0 AND pushed=0 AND yt_id NOT IN "
                       "(SELECT video_yt_id FROM events WHERE kind='tier') LIMIT 1").fetchone()
    dbc.close()
    s, sr = req('GET', f'/api/workspaces/1/videos/{t2[0]}/series')
    need = {'video', 'ticks', 'vph_series', 'trend', 'markers', 'tier_events', 'reference'}
    check('GET series video T2+ đủ trường', s == 200 and not (need - set(sr)), f'{s} thiếu {need - set(sr) if s==200 else sr}')
    check('vph_series nhất quán với ticks (n−1 điểm; cold-start 1 tick → 0 điểm là hợp lệ)',
          s == 200 and len(sr['vph_series']) == max(0, len(sr['ticks']) - 1),
          f"vph={len(sr.get('vph_series', []))} ticks={len(sr.get('ticks', []))}")
    check('trend hợp lệ (up/flat/down)', s == 200 and sr['trend']['dir'] in ('up', 'flat', 'down'))
    check('reference có n_waves + bands', s == 200 and 'n_waves' in sr['reference'] and isinstance(sr['reference']['bands'], list))
    s, _ = req('GET', f'/api/workspaces/1/videos/{cold[0]}/series')
    check('video chưa đạt T2 → 404', s == 404, f'{s}')
    check('app.js có VideoModal + LineChart', all(x in js for x in ('VideoModal', 'LineChart', 'viz-mk-title')))
    check('series có trạng thái Xóa/Ẩn (dead + dead_age_h)', 'dead' in sr['video'] and 'dead_age_h' in sr['video'])
    from radary.scan import purge_events
    pe = purge_events([{'kind': 'dead', 'ch': 'K', 'vid': str(i)} for i in range(3)]
                      + [{'kind': 'dead', 'ch': 'L', 'vid': 'x'}, {'kind': 'retitle', 'ch': 'K', 'vid': 'y'}], 0, 3)
    check('gộp cấp kênh: 3 Xóa/Ẩn cùng kênh → 1 tín hiệu; kênh 1 video → không',
          len(pe) == 1 and pe[0]['ch'] == 'K' and pe[0]['count'] == 3, f'{pe}')
    check('UI có filter channel_purge + nhãn Xóa/Ẩn', 'channel_purge' in js and 'Xóa/Ẩn' in js)
    check('UI có panel Nhật ký quét', 'Nhật ký quét' in js)

    print('5b. HỒ SƠ KÊNH (Phase 3.8 — API chính ngạch + links best-effort)')
    s, chans1 = req('GET', '/api/workspaces/1/channels')
    ch0 = chans1[0]['yt_id']
    s, info = req('GET', f'/api/workspaces/1/channels/{ch0}/info')
    need_i = {'title', 'description', 'subs', 'videos', 'views', 'published_at', 'links', 'links_ok', 'fetched_ts'}
    check('GET /info đủ trường', s == 200 and not (need_i - set(info)), f'{s} thiếu {need_i - set(info) if s==200 else info}')
    check('số liệu thật (views > 0)', s == 200 and info['views'] > 0)
    check('links best-effort: links_ok bool + links list', s == 200 and isinstance(info['links_ok'], bool) and isinstance(info['links'], list))
    s2, info2 = req('GET', f'/api/workspaces/1/channels/{ch0}/info')
    check('cache 24h hoạt động (lần 2 trả cùng fetched_ts, không tốn quota)', s2 == 200 and info2['fetched_ts'] == info['fetched_ts'])
    s, _ = req('GET', '/api/workspaces/1/channels/UCkhongtontai000000000000/info')
    check('kênh ngoài pool → 404', s == 404, f'{s}')
    check('UI có ChannelModal', 'ChannelModal' in js)

    print('6. XÓA WORKSPACE TEST (chốt an toàn)')
    s, _ = req('DELETE', f'/api/workspaces/{test_ws}?confirm=sai-ten')
    check('sai tên xác nhận → 422', s == 422, f'{s}')
    s, _ = req('DELETE', f'/api/workspaces/{test_ws}?confirm=VERIFY-P3')
    check('đúng tên → xóa được', s == 200)
    s, _ = req('GET', f'/api/workspaces/{test_ws}/status')
    check('workspace đã biến mất → 404', s == 404, f'{s}')
    test_ws = None
finally:
    if test_ws:      # dọn nếu test gãy giữa chừng
        try: req('DELETE', f'/api/workspaces/{test_ws}?confirm=VERIFY-P3')
        except Exception: pass
    srv.send_signal(signal.SIGTERM); srv.wait(timeout=10)
    c = sqlite3.connect(os.path.join(BASE, 'data', 'radary.db'))
    c.execute('DELETE FROM sessions WHERE token=?', (SESSION,)); c.commit(); c.close()

print()
if FAILS:
    print(f'✗ NGHIỆM THU PHASE 3 THẤT BẠI — {len(FAILS)} mục: {FAILS}'); sys.exit(1)
print('✓ NGHIỆM THU PHASE 3 ĐẠT — dashboard sống, tạo niche mới hoàn toàn qua API/UI, không đụng file.')
