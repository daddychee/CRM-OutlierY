"""NGHIỆM THU PHASE 2 — backend FastAPI phục vụ đúng dữ liệu engine qua HTTP.

Tiêu chí chốt trước:
  1. Server sống, liệt kê workspace Life in X đúng số liệu DB
  2. POST /run chạy chu kỳ thật → board.md qua API khớp TỪNG BYTE file engine ghi
  3. Board JSON (hợp đồng dữ liệu Phase 3) đủ trường, heartbeat tươi
  4. Config PUT có audit trail (event config_change); alerts đọc được lịch sử migrate
  5. Lỗi trả đúng mã (404 workspace ma, 422 config sai trường)
Chạy: python3 verify_phase2.py  (tự khởi động server cổng 8737, scheduler TẮT, tự dọn)
"""
import json, os, secrets, signal, sqlite3, subprocess, sys, time, urllib.request, urllib.error

BASE = os.path.dirname(os.path.abspath(__file__))
PORT = 8737
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
            return resp.status, (json.loads(raw) if resp.headers.get_content_type() == 'application/json' else raw)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()

env = dict(os.environ, PORT=str(PORT), RADARY_SCHEDULER='0')
srv = subprocess.Popen([os.path.join(BASE, '.venv', 'bin', 'python'), 'server.py'],
                       cwd=BASE, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    for _ in range(60):
        time.sleep(0.5)
        try:
            s, h = req('GET', '/api/health')
            if s == 200: break
        except Exception: pass
    else:
        print('✗ server không lên nổi'); sys.exit(1)

    print('1. WORKSPACE & DỮ LIỆU')
    s, ws_list = req('GET', '/api/workspaces')
    w1 = next((w for w in ws_list if w['name'] == 'Life in X'), None)
    check('GET /workspaces có Life in X', s == 200 and w1 is not None)
    import sqlite3
    alive = sqlite3.connect(os.path.join(BASE, 'data', 'radary.db')).execute(
        'SELECT COUNT(*) FROM videos WHERE workspace_id=? AND dead=0', (w1['id'],)).fetchone()[0]
    check('số video sống khớp DB', w1 and w1['videos'] == alive, f"API {w1 and w1['videos']} vs DB {alive}")
    s, chans = req('GET', f"/api/workspaces/{w1['id']}/channels")
    check('GET /channels = 77 kênh', s == 200 and len(chans) == 77, f'{len(chans) if s==200 else s}')

    print('2. CHU KỲ QUÉT QUA API + PARITY BOARD')
    s, run = req('POST', f"/api/workspaces/{w1['id']}/run?budget=120")
    check('POST /run chạy được', s == 200 and run.get('tag') in ('DONE', 'PAUSE'), f'{s} {run}')
    s, md_api = req('GET', f"/api/workspaces/{w1['id']}/board.md")
    md_file = open(os.path.join(BASE, 'data', 'reports', str(w1['id']), 'radar_board.md')).read()
    check('board.md qua API khớp TỪNG BYTE file engine ghi', s == 200 and md_api == md_file)
    s, cycs = req('GET', f"/api/workspaces/{w1['id']}/cycles?limit=5")
    need_cy = {'ts', 'tag', 'ran', 'quota', 'pool', 'ch_scanned', 'refreshed', 'notes', 'special'}
    check('nhật ký quét ghi lại chu kỳ đủ trường', s == 200 and len(cycs) >= 1 and not (need_cy - set(cycs[0])),
          f'{s} thiếu {need_cy - set(cycs[0]) if s == 200 and cycs else cycs}')
    check('nhật ký có số kênh/pool', s == 200 and cycs[0]['pool'] > 0)

    print('3. BOARD JSON (hợp đồng dữ liệu Phase 3)')
    s, bd = req('GET', f"/api/workspaces/{w1['id']}/board")
    check('GET /board trả JSON', s == 200 and isinstance(bd, dict))
    need = {'generated_ts', 'cohorts', 'allages', 'jobs', 'push_t2_today', 'push_t2_cap', 'ntfy_enabled'}
    check('đủ trường hợp đồng', not (need - set(bd)), f'thiếu {need - set(bd)}')
    check('heartbeat tươi (<5 phút)', time.time() - bd['generated_ts'] < 300)
    v0 = bd['cohorts'][0]['videos'][0] if bd['cohorts'] and bd['cohorts'][0]['videos'] else {}
    vneed = {'yt_id', 'title', 'channel', 'tier', 'vph', 'vpd', 'views', 'age_h', 'rank', 'url', 'est', 'est_vpd'}
    check('video trong cohort đủ trường', not (vneed - set(v0)), f'thiếu {vneed - set(v0)}')
    s, st = req('GET', f"/api/workspaces/{w1['id']}/status")
    check('GET /status: heartbeat + jobs + tiers', s == 200 and st['heartbeat_ts'] > 0 and st['jobs'] and 'tiers' in st)

    print('3b. NHỊP POOL (Phase 3.13)')
    dbc = sqlite3.connect(os.path.join(BASE, 'data', 'radary.db'))
    n_ps = dbc.execute('SELECT COUNT(*) FROM pool_stats WHERE workspace_id=?', (w1['id'],)).fetchone()[0]
    check('pool_stats có bucket sau chu kỳ quét', n_ps > 0, f'{n_ps}')
    bad = dbc.execute('SELECT COUNT(*) FROM pool_stats WHERE workspace_id=? AND bucket_ts>=? '
                      'AND CAST(bucket_ts + 25200 AS INTEGER) % 21600 != 0',
                      (w1['id'], time.time() - 14 * 86400)).fetchone()[0]
    check('bucket 14 ngày gần căn giờ VN chuẩn (00-06-12-18)', bad == 0, f'{bad} bucket lệch múi')
    n_cs = dbc.execute('SELECT COUNT(*) FROM channel_stats WHERE workspace_id=?', (w1['id'],)).fetchone()[0]
    check('channel_stats có nhịp theo kênh', n_cs > 0, f'{n_cs}')
    dbc.close()
    s, pu = req('GET', f"/api/workspaces/{w1['id']}/pulse?days=7")
    check('GET /pulse 7 ngày: điểm 6h đủ trường', s == 200 and pu['res'] == '6h' and len(pu['points']) > 0
          and not ({'ts', 'dviews', 'vph_avg', 'n'} - set(pu['points'][0])), f'{s} {pu if s != 200 else len(pu["points"])}')
    s, pu30 = req('GET', f"/api/workspaces/{w1['id']}/pulse?days=30")
    check('GET /pulse 30 ngày: gộp theo ngày', s == 200 and pu30['res'] == 'day' and pu30['since_ts'], f'{s}')
    check('range 30 ngày bao trùm 7 ngày: tổng dviews dài ≥ ngắn',
          sum(p['dviews'] for p in pu30['points']) >= sum(p['dviews'] for p in pu['points']))
    s, _ = req('GET', f"/api/workspaces/{w1['id']}/pulse?start=2026-13-01")
    check('pulse ngày sai định dạng → 400', s == 400, f'{s}')

    print('3d. HEATMAP GIỜ ĐĂNG (brief §7)')
    import urllib.parse as _up
    s, hma = req('GET', f"/api/workspaces/{w1['id']}/heatmap?days=0")
    check('tổng ô = tổng video hợp lệ (không mất, không nhân đôi)',
          s == 200 and hma['total'] > 0 and sum(c[2] for c in hma['cells']) == hma['total'],
          f"{s} {hma if s != 200 else hma['total']}")
    s, hm90 = req('GET', f"/api/workspaces/{w1['id']}/heatmap?days=90")
    check('lọc 90 ngày là tập con của tất cả', s == 200 and hm90['total'] <= hma['total'])
    s, hmu = req('GET', f"/api/workspaces/{w1['id']}/heatmap?days=0&tz=utc")
    check('đổi múi VN↔UTC: tổng không đổi, ô dịch giờ', s == 200 and hmu['total'] == hma['total']
          and (hmu['cells'] != hma['cells'] or hma['total'] == 0))
    ch0 = hma['channels'][0][0]
    s, hmc = req('GET', f"/api/workspaces/{w1['id']}/heatmap?days=0&channel={_up.quote(ch0)}")
    check('lọc theo kênh: tổng = đúng số video kênh đó', s == 200 and hmc['total'] == hma['channels'][0][1])
    s, _ = req('GET', f"/api/workspaces/{w1['id']}/heatmap?days=7")
    check('days lạ → 400', s == 400, f'{s}')

    print('3e. METRICS (mockup kiểu vidIQ user duyệt 23/07/2026 — thay Top kênh/ngày)')
    check('/pulse đã gọn: không còn top_channels (bảng cũ thay bằng Metrics)', 'top_channels' not in pu)
    check('heatmap có peak cho tile Most posted hours', bool(hma.get('peak')) and 0 <= hma['peak']['h'] < 24
          and isinstance(hma['peak']['dows'], list), f"{hma.get('peak')}")
    # --- unit offline: snap_channels với Fake API (0 quota, DB :memory:) ---
    from radary import core as rcore, db as rdb, scan as rscan
    mem = sqlite3.connect(':memory:'); mem.row_factory = sqlite3.Row
    mem.executescript(rdb.SCHEMA)
    mem.executemany('INSERT INTO channels(workspace_id, yt_id, title) VALUES (1,?,?)',
                    [('UCa', 'A'), ('UCb', 'B'), ('UCc', 'C')])
    class FakeStatsAPI:
        calls = 0
        def get(s, ep, params, cost=1):
            FakeStatsAPI.calls += 1
            return {'items': [
                {'id': 'UCa', 'statistics': {'subscriberCount': '100', 'viewCount': '5000', 'videoCount': '10'}},
                {'id': 'UCb', 'statistics': {'hiddenSubscriberCount': True, 'viewCount': '7000'}},
                {'id': 'UCc'}]}                        # thiếu hẳn statistics — không được crash
    tzvn = rcore.tzinfo('Asia/Ho_Chi_Minh')
    rows = rscan.snap_channels(mem, FakeStatsAPI(), 1, tzvn, time.time())
    check('snap_channels: 3 kênh → 3 dòng, trường thiếu → NULL (không crash, không bịa)',
          len(rows) == 3 and rows[0][3] == 100 and rows[0][4] == 5000
          and rows[1][3] is None and rows[1][4] == 7000 and rows[2][4] is None, f'{rows}')
    mem.executemany('INSERT OR IGNORE INTO channel_snap VALUES (?,?,?,?,?,?,?)', rows)
    n_calls = FakeStatsAPI.calls
    rows2 = rscan.snap_channels(mem, FakeStatsAPI(), 1, tzvn, time.time())
    check('snap_channels idempotent: đã có bản hôm nay → [] và 0 lời gọi API',
          rows2 == [] and FakeStatsAPI.calls == n_calls, f'{len(rows2)} dòng, thêm {FakeStatsAPI.calls - n_calls} call')
    mem.close()
    # --- E2E /metrics ---
    s, mt = req('GET', f"/api/workspaces/{w1['id']}/metrics")
    need_m = {'scope', 'n_channels', 'snap_day', 'channel_yt_id', 'total_views', 'total_views_pct',
              'subs', 'subs_pct', 'gain7', 'gain7_pct', 'videos_tracked', 'avg_len_m', 'upload_wk',
              'avg_vph', 'n_young', 'surging', 'outlier', 'rank'}
    check('GET /metrics toàn pool: đủ trường hợp đồng', s == 200 and not (need_m - set(mt)),
          f'{s} thiếu {need_m - set(mt) if s == 200 else mt}')
    dbc = sqlite3.connect(os.path.join(BASE, 'data', 'radary.db')); dbc.row_factory = sqlite3.Row
    alive2 = dbc.execute('SELECT COUNT(*) FROM videos WHERE workspace_id=? AND dead=0', (w1['id'],)).fetchone()[0]
    g7 = dbc.execute('SELECT COALESCE(SUM(dviews),0) FROM channel_stats WHERE workspace_id=? AND bucket_ts>?',
                     (w1['id'], time.time() - 7 * 86400)).fetchone()[0]
    check('videos_tracked khớp DB · gain7 khớp channel_stats (số đo thật)',
          mt['videos_tracked'] == alive2 and abs(mt['gain7'] - g7) <= max(g7 * 0.02, 1000),
          f"API {mt['videos_tracked']}/{mt['gain7']} vs DB {alive2}/{g7}")
    # --- % snapshot: bơm 2 ngày tương-lai-xa (thắng MAX(day)) rồi dọn — kiểm số học giao 2 tập kênh ---
    seed = [(w1['id'], '2999-01-08', 'UCX1', 110, 1100, 5, 0), (w1['id'], '2999-01-08', 'UCX2', None, 2200, 5, 0),
            (w1['id'], '2999-01-01', 'UCX1', 100, 1000, 5, 0), (w1['id'], '2999-01-01', 'UCX2', None, 2000, 5, 0)]
    dbc.executemany('INSERT OR REPLACE INTO channel_snap VALUES (?,?,?,?,?,?,?)', seed); dbc.commit()
    s, mt2 = req('GET', f"/api/workspaces/{w1['id']}/metrics")
    check('Total views/Subscribers + % so ~7 ngày trước: đúng số học, kênh ẩn subs bị loại khỏi %',
          s == 200 and mt2['total_views'] == 3300 and mt2['total_views_pct'] == 10.0
          and mt2['subs'] == 110 and mt2['subs_pct'] == 10.0,
          f"{mt2.get('total_views')} {mt2.get('total_views_pct')} {mt2.get('subs')} {mt2.get('subs_pct')}")
    dbc.execute('DELETE FROM channel_snap WHERE workspace_id=? AND day LIKE ?', (w1['id'], '2999%')); dbc.commit()
    dbc.close()
    ch0m = hma['channels'][0][0]
    s, mt3 = req('GET', f"/api/workspaces/{w1['id']}/metrics?channel={_up.quote(ch0m)}")
    check('phạm vi kênh: scope đúng + videos_tracked ⊆ pool + rank hợp lệ',
          s == 200 and mt3['scope'] == ch0m and mt3['videos_tracked'] <= mt['videos_tracked']
          and (mt3['rank'] is None or 1 <= mt3['rank']['pos'] <= mt3['rank']['of']),
          f"{s} {mt3 if s != 200 else (mt3['scope'], mt3['videos_tracked'], mt3['rank'])}")
    check('phạm vi kênh trả channel_yt_id (UC…) cho nút mở YouTube · toàn pool = None',
          mt3.get('channel_yt_id', '').startswith('UC') and mt['channel_yt_id'] is None,
          f"kênh={mt3.get('channel_yt_id')} pool={mt['channel_yt_id']}")

    print('3c. HARVEST API (bề mặt — engine đã nghiệm thu riêng ở verify_harvest.py)')
    org1 = w1['org_id']
    s, hv = req('GET', f'/api/orgs/{org1}/harvest')
    check('GET /harvest: chưa có job → job null', s == 200 and hv.get('job') is None, f'{s} {hv}')
    s, e = req('POST', f'/api/orgs/{org1}/harvest', {'text': '@somechannel', 'audience': False})
    check('POST /harvest khi kho key Harvest trống → 400 có chỉ đường',
          s == 400 and 'Key Harvest' in str(e), f'{s} {e}')
    s, _ = req('GET', f'/api/orgs/{org1}/harvest/report.md')
    check('report.md chưa có job → 404', s == 404, f'{s}')
    s, r = req('POST', f'/api/orgs/{org1}/keys/harvest-bulk', {'keys_text': 'ngắn\n'})
    check('bulk key: dòng <20 ký tự bị đếm invalid', s == 201 and r.get('invalid') == 1, f'{s} {r}')

    print('4. CONFIG + AUDIT TRAIL + ALERTS')
    s, cfg = req('GET', f"/api/workspaces/{w1['id']}/config")
    check('GET /config có ngưỡng T1-T4', s == 200 and all(k in cfg for k in ('T1_vph', 'T2_vph', 'T3_vph', 'T4_vph')))
    s, cfg2 = req('PUT', f"/api/workspaces/{w1['id']}/config", {'T2_daily_cap': cfg['T2_daily_cap']})
    check('PUT /config hợp lệ', s == 200 and cfg2['T2_daily_cap'] == cfg['T2_daily_cap'])
    s, cfgev = req('GET', f"/api/workspaces/{w1['id']}/alerts?kind=config_change")
    check('audit trail: event config_change ghi lại (mode=flat)',
          s == 200 and cfgev.get('mode') == 'flat' and len(cfgev['rows']) >= 1, f'{s} {cfgev}')

    print('4b. CẢNH BÁO GOM THEO ĐƠN VỊ (mockup user duyệt 24/07/2026)')
    s, wv = req('GET', f"/api/workspaces/{w1['id']}/alerts?kind=tier")
    ok = (s == 200 and wv.get('mode') == 'waves' and isinstance(wv.get('alive'), list)
          and isinstance(wv.get('ended'), list))
    check('kind=tier → mode=waves, có Đang sống / Đã lắng', ok, f'{s} {wv if not ok else ""}')
    if ok:
        allw = wv['alive'] + wv['ended']
        need_w = {'yt', 'title', 'ch', 'cur', 'peak', 'n_ev', 'traj', 'views', 'vph',
                  'verdict', 'verdict_eid', 'alive', 'retitle', 'rethumb'}
        w0 = allw[0] if allw else {}
        check('thẻ sóng đủ trường + chỉ T2+ (peak>=2) + gộp nhiều event',
              bool(allw) and not (need_w - set(w0)) and all(x['peak'] >= 2 for x in allw),
              f'thiếu {need_w - set(w0) if w0 else "KHÔNG CÓ SÓNG"}')
        # gộp thật: tổng event trong các thẻ < số dòng nếu để phẳng (mỗi video từng lặp nhiều)
        n_cards, n_events = len(allw), sum(x['n_ev'] for x in allw)
        check('gộp giảm số dòng: N thẻ < tổng event bậc', n_cards < n_events, f'{n_cards} thẻ / {n_events} event')
        # verdict theo video: chấm event đại diện rồi đọc lại thấy verdict trên thẻ
        vt = next((x for x in allw if x['verdict_eid']), None)
        if vt:
            s2, _ = req('POST', f"/api/workspaces/{w1['id']}/alerts/{vt['verdict_eid']}/verdict", {'action': 'acted'})
            s3, wv2 = req('GET', f"/api/workspaces/{w1['id']}/alerts?kind=tier")
            back = next((x for x in wv2['alive'] + wv2['ended'] if x['yt'] == vt['yt']), {})
            check('verdict theo video: chấm event đại diện → thẻ hiện đã chấm',
                  s2 == 200 and back.get('verdict') == 'acted', f'{s2} {back.get("verdict")}')
    s, chn = req('GET', f"/api/workspaces/{w1['id']}/alerts?kind=retitle")
    ok2 = (s == 200 and chn.get('mode') == 'channels' and chn.get('kind') == 'retitle'
           and isinstance(chn.get('rows'), list))
    check('kind=retitle → mode=channels (gom theo kênh)', ok2, f'{s} {chn if not ok2 else ""}')
    if ok2 and chn['rows']:
        r0 = chn['rows'][0]
        check('dòng kênh đủ trường (kênh · số lần · số video)',
              not ({'ch', 'count', 'vids', 'last_ts'} - set(r0)) and r0['count'] >= 1, f'{r0}')
    s, alld = req('GET', f"/api/workspaces/{w1['id']}/alerts")
    check('không còn tab Tất cả: kind rỗng → về waves (tab mặc định Thăng/hạ bậc)',
          s == 200 and alld.get('mode') == 'waves', f"{s} {alld.get('mode')}")

    print('5. LỖI TRẢ ĐÚNG MÃ')
    s, _ = req('GET', '/api/workspaces/99/board')
    check('workspace ma → 404', s == 404, f'{s}')
    s, _ = req('PUT', f"/api/workspaces/{w1['id']}/config", {'hack_field': 1})
    check('config trường lạ → 422', s == 422, f'{s}')
    s, _ = req('POST', f"/api/workspaces/{w1['id']}/channels", {'items': []})
    check('thêm kênh items rỗng → 400', s == 400, f'{s}')
finally:
    srv.send_signal(signal.SIGTERM); srv.wait(timeout=10)
    c = sqlite3.connect(os.path.join(BASE, 'data', 'radary.db'))
    c.execute('DELETE FROM sessions WHERE token=?', (SESSION,)); c.commit(); c.close()

print()
if FAILS:
    print(f'✗ NGHIỆM THU PHASE 2 THẤT BẠI — {len(FAILS)} mục: {FAILS}'); sys.exit(1)
print('✓ NGHIỆM THU PHASE 2 ĐẠT — backend FastAPI phục vụ đúng engine qua HTTP.')
