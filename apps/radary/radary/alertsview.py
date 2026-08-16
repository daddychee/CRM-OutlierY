"""Tầng TRÌNH BÀY tab Cảnh báo (user duyệt mockup 24/07/2026). Chỉ ĐỌC — không đụng
sổ cái `events` (append-only). Gom sự kiện theo ĐƠN VỊ hợp lý cho từng sub-tab:

  - tier (MẶC ĐỊNH)          → theo SÓNG (video): thẻ + quỹ đạo, chia Đang sống / Đã lắng
  - retitle / rethumb        → theo KÊNH: 1 kênh/dòng, đếm số lần + số video
  - dead/channel_purge/pool_change/config_change → danh sách phẳng 1 dòng/sự kiện
  (Không có tab "Tất cả" — user chốt 24/07/2026: chức năng tab nào ở tab đó.)

Verdict (tự chấm) gắn vào event T2+ ĐẠI DIỆN của video (id mới nhất có to>=2) — dùng lại
bảng verdicts sẵn có, không thêm bảng. Sóng chỉ tính video từng chạm T2+ (dưới ngưỡng = nhiễu).
"""
import json, time

ALIVE_S = 7 * 86400        # còn "đang sống" nếu vẫn T2+ hoặc mới cập nhật < 7 ngày


def _loads(s):
    try: return json.loads(s)
    except Exception: return {}


def waves(conn, ws, now=None):
    """Gom kind='tier' theo video → thẻ sóng. Trả {'mode','alive','ended'}."""
    now = now or time.time()
    by = {}
    for r in conn.execute("SELECT id, ts, video_yt_id, payload FROM events "
                          "WHERE workspace_id=? AND kind='tier' AND video_yt_id!='' ORDER BY ts", (ws,)):
        p = _loads(r['payload']); to = p.get('to', 0)
        w = by.setdefault(r['video_yt_id'], {'traj': [], 'peak': 0, 'first_t2_ts': None,
                                             'last_ts': 0, 'verdict_eid': None})
        w['traj'].append({'ts': r['ts'], 'from': p.get('from', 0), 'to': to,
                          'note': p.get('note', ''), 'pushed': bool(p.get('pushed'))})
        w['peak'] = max(w['peak'], to); w['last_ts'] = r['ts']
        if to >= 2:
            if w['first_t2_ts'] is None: w['first_t2_ts'] = r['ts']
            w['verdict_eid'] = r['id']
    hot = {yt: w for yt, w in by.items() if w['peak'] >= 2}
    if not hot:
        return {'mode': 'waves', 'alive': [], 'ended': []}
    qm = ','.join('?' * len(hot))
    # gom phụ trợ trong 1 lượt/loại — tránh N+1
    vids = {r['yt_id']: r for r in conn.execute(
        f'SELECT *, (SELECT views FROM ticks t WHERE t.video_id=videos.id ORDER BY ts DESC LIMIT 1) cur_views '
        f'FROM videos WHERE workspace_id=? AND yt_id IN ({qm})', (ws, *hot))}
    def cnt(kind):
        d = {}
        for r in conn.execute(f"SELECT video_yt_id, COUNT(*) n FROM events WHERE workspace_id=? AND kind=? "
                              f"AND video_yt_id IN ({qm}) GROUP BY video_yt_id", (ws, kind, *hot)):
            d[r['video_yt_id']] = r['n']
        return d
    rt, th = cnt('retitle'), cnt('rethumb')
    verdicts = {}              # video -> action mới nhất trên event T2+
    for r in conn.execute(f"SELECT e.video_yt_id yt, e.payload, vd.action, vd.ts FROM events e "
                          f"JOIN verdicts vd ON vd.event_id=e.id WHERE e.workspace_id=? AND e.kind='tier' "
                          f"AND e.video_yt_id IN ({qm}) ORDER BY vd.ts", (ws, *hot)):
        if _loads(r['payload']).get('to', 0) >= 2:
            verdicts[r['yt']] = r['action']
    out = []
    for yt, w in hot.items():
        v = vids.get(yt)
        if not v: continue
        alive = (v['tier'] >= 2 or (now - w['last_ts']) < ALIVE_S) and not v['dead']
        out.append({
            'yt': yt, 'title': v['title'], 'ch': v['channel_title'], 'cur': v['tier'],
            'peak': w['peak'], 'dead': bool(v['dead']), 'views': v['cur_views'] or 0,
            'vph': round(v['last_vph']), 'age_h': round((now - v['pub_ts']) / 3600, 1) if v['pub_ts'] else 0,
            'n_ev': len(w['traj']), 'traj': w['traj'], 'first_t2_ts': w['first_t2_ts'], 'last_ts': w['last_ts'],
            'retitle': rt.get(yt, 0), 'rethumb': th.get(yt, 0),
            'pushed': any(t['pushed'] for t in w['traj']),
            'verdict': verdicts.get(yt), 'verdict_eid': w['verdict_eid'], 'alive': alive})
    out.sort(key=lambda w: (not w['alive'], -w['peak'], -w['last_ts']))
    return {'mode': 'waves', 'alive': [w for w in out if w['alive']], 'ended': [w for w in out if not w['alive']]}


def _pkg_by_channel(conn, ws):
    """Gom retitle+rethumb theo kênh (dùng cho sub-tab Đổi title/thumbnail + feed Tất cả)."""
    by = {}
    for r in conn.execute("SELECT ts, kind, video_yt_id, payload FROM events "
                          "WHERE workspace_id=? AND kind IN ('retitle','rethumb') ORDER BY ts", (ws,)):
        p = _loads(r['payload']); ch = p.get('ch', '') or '(không rõ kênh)'
        a = by.setdefault(ch, {'ch': ch, 'retitle': 0, 'rethumb': 0, 'rt_vids': set(), 'th_vids': set(),
                               'last_ts': 0, 'last_old': '', 'last_new': ''})
        if r['kind'] == 'retitle':
            a['retitle'] += 1; a['rt_vids'].add(r['video_yt_id'])
        else:
            a['rethumb'] += 1; a['th_vids'].add(r['video_yt_id'])
        if r['ts'] >= a['last_ts']:
            a['last_ts'] = r['ts']
            if r['kind'] == 'retitle': a['last_old'], a['last_new'] = p.get('old', ''), p.get('new', '')
    return by


def channels_pkg(conn, ws, kind):
    """Sub-tab Đổi title (kind='retitle') hoặc Đổi thumbnail (kind='rethumb') — gom theo kênh."""
    vk = 'rt_vids' if kind == 'retitle' else 'th_vids'
    rows = [{'ch': a['ch'], 'count': a[kind], 'vids': len(a[vk]), 'last_ts': a['last_ts'],
             'last_old': a['last_old'], 'last_new': a['last_new']}
            for a in _pkg_by_channel(conn, ws).values() if a[kind] > 0]
    rows.sort(key=lambda a: -a['last_ts'])
    return {'mode': 'channels', 'kind': kind, 'rows': rows}


def flat(conn, ws, kind, limit=100, offset=0):
    """Sub-tab dead/channel_purge/pool_change/config_change — danh sách phẳng, mới nhất trước."""
    rows = []
    for r in conn.execute('SELECT id, ts, kind, video_yt_id, payload FROM events '
                          'WHERE workspace_id=? AND kind=? ORDER BY ts DESC, id DESC LIMIT ? OFFSET ?',
                          (ws, kind, min(limit, 500), offset)):
        rows.append(dict(_loads(r['payload']), id=r['id'], ts=r['ts'], kind=r['kind'], vid=r['video_yt_id']))
    return {'mode': 'flat', 'kind': kind, 'rows': rows}


def view(conn, ws, kind='', limit=100, offset=0):
    """Điều phối theo sub-tab. Kind lạ/rỗng → waves (tab mặc định)."""
    if kind in ('retitle', 'rethumb'): return channels_pkg(conn, ws, kind)
    if kind in ('dead', 'channel_purge', 'pool_change', 'config_change'): return flat(conn, ws, kind, limit, offset)
    return waves(conn, ws)


if __name__ == '__main__':   # tự kiểm offline: python -m radary.alertsview
    import sqlite3
    from . import db
    c = sqlite3.connect(':memory:'); c.row_factory = sqlite3.Row
    c.executescript(db.SCHEMA)
    now = 1_700_000_000.0
    c.execute('INSERT INTO workspaces(id, org_id, name, created_ts) VALUES (1,1,"W",0)')
    # 1 video sóng T2+ nhảy lên xuống nhiều lần (A) + 1 video chỉ T1 (B, phải bị loại khỏi sóng)
    c.execute('INSERT INTO videos(id, workspace_id, yt_id, channel_title, title, pub_ts, tier, last_vph) '
              'VALUES (10,1,"vA","Kênh 1","Video A",?,3,500)', (now - 5 * 86400,))
    c.execute('INSERT INTO videos(id, workspace_id, yt_id, channel_title, title, pub_ts, tier, last_vph) '
              'VALUES (11,1,"vB","Kênh 2","Video B",?,1,50)', (now - 40 * 86400,))
    c.execute('INSERT INTO ticks VALUES (10,?,120000)', (now,))
    def ev(kind, ts, **p):
        c.execute('INSERT INTO events(workspace_id, ts, kind, video_yt_id, payload) VALUES (1,?,?,?,?)',
                  (ts, kind, p.pop('vid', ''), json.dumps(p)))
    for i, (fr, to) in enumerate([(0, 2), (2, 3), (3, 2), (2, 3)]):    # A: 4 lần đổi bậc, đỉnh T3
        ev('tier', now - (4 - i) * 3600, vid='vA', **{'from': fr, 'to': to, 'ch': 'Kênh 1', 'title': 'Video A'})
    ev('tier', now - 100 * 86400, vid='vB', **{'from': 0, 'to': 1, 'ch': 'Kênh 2', 'title': 'Video B'})
    ev('retitle', now - 2 * 3600, vid='vA', ch='Kênh 1', title='Video A', old='cũ', new='mới')
    ev('retitle', now - 3600, vid='vB', ch='Kênh 1', title='Video B', old='x', new='y')   # cùng Kênh 1, video khác
    ev('rethumb', now - 3600, vid='vA', ch='Kênh 2', title='Video A')
    ev('dead', now - 500, vid='vD', title='Video chết', ch='Kênh 3')
    c.commit()

    w = waves(c, 1, now)
    assert len(w['alive']) == 1 and not w['ended'], w                      # chỉ A (T2+), B bị loại
    a = w['alive'][0]
    assert a['yt'] == 'vA' and a['peak'] == 3 and a['n_ev'] == 4, a         # gộp 4 event → 1 thẻ, đỉnh T3
    assert a['views'] == 120000 and a['retitle'] == 1 and a['verdict'] is None
    assert a['verdict_eid'] is not None                                     # có event T2+ đại diện để chấm

    ch = channels_pkg(c, 1, 'retitle')                                     # 2 retitle của Kênh 1 (2 video) → 1 dòng
    assert ch['mode'] == 'channels' and len(ch['rows']) == 1, ch
    assert ch['rows'][0]['ch'] == 'Kênh 1' and ch['rows'][0]['count'] == 2 and ch['rows'][0]['vids'] == 2, ch['rows']

    fl = flat(c, 1, 'dead')
    assert fl['mode'] == 'flat' and len(fl['rows']) == 1 and fl['rows'][0]['title'] == 'Video chết'
    assert view(c, 1, '')['mode'] == 'waves' and view(c, 1, 'lạ')['mode'] == 'waves'   # kind rỗng/lạ → tab mặc định
    print('alertsview OK — sóng đỉnh T%d gộp %d event · %d kênh đổi title' % (a['peak'], a['n_ev'], len(ch['rows'])))
