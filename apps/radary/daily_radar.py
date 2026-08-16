#!/usr/bin/env python3
"""DAILY RADAR — video outlier on niche (radar_spec.md v3, đóng băng 07/07/2026)

Chạy:
  python3 daily_radar.py init     # lần đầu: resolve kênh (kể cả @handle), seed state
  python3 daily_radar.py          # chu kỳ thường — cron gọi mỗi 30 phút
  python3 daily_radar.py status   # in nhanh trạng thái

Cron (máy 24/7):  */30 * * * *  cd /duong/dan/Thumbnail && python3 daily_radar.py >> radar_state/daily/cron.log 2>&1

Chỉ dùng stdlib. State: radar_state/daily/ · Output: radar_reports/
"""
import json, os, re, sys, time, math, random, string, hashlib, urllib.request, urllib.parse
from datetime import datetime, timedelta, timezone
try:
    from zoneinfo import ZoneInfo
    TZ = ZoneInfo('Asia/Ho_Chi_Minh')
except Exception:
    TZ = timezone(timedelta(hours=7))

BASE = os.path.dirname(os.path.abspath(__file__))
ST   = os.path.join(BASE, 'radar_state', 'daily')
RP   = os.path.join(BASE, 'radar_reports')
WK   = os.path.join(RP, 'weekly')
TH   = os.path.join(ST, 'thumbs')
for d in (ST, RP, WK, TH): os.makedirs(d, exist_ok=True)
COMPETITORS = os.path.join(BASE, 'radar_state', 'competitors.txt')
BUDGET = float(os.environ.get('RADAR_BUDGET', '9999'))   # giây; đặt ~25 khi test sandbox
T0 = time.time()
NOW = time.time()

# ---------------- tiện ích ----------------
def jload(name, default):
    try:
        with open(os.path.join(ST, name)) as f: return json.load(f)
    except Exception: return default
def jsave(name, obj):
    tmp = os.path.join(ST, name + '.tmp')
    with open(tmp, 'w') as f: json.dump(obj, f, ensure_ascii=False)
    os.replace(tmp, os.path.join(ST, name))
def over_budget(): return time.time() - T0 > BUDGET
def now_local(): return datetime.now(TZ)
def fmt_ts(ts=None): return datetime.fromtimestamp(ts or time.time(), TZ).strftime('%Y-%m-%d %H:%M')
def parse_pub(p):
    try: return datetime.fromisoformat(p.replace('Z', '+00:00')).timestamp()
    except Exception: return 0
def parse_dur(d):
    m = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', d or '')
    if not m: return 0
    h, mi, s = (int(x) if x else 0 for x in m.groups()); return h*3600 + mi*60 + s

class API:
    def __init__(s, keys): s.keys = keys; s.i = 0; s.used = 0
    def get(s, ep, params, cost=1):
        last = None
        for _ in range(max(len(s.keys)*2, 2)):
            q = dict(params); q['key'] = s.keys[s.i % len(s.keys)]
            url = f'https://www.googleapis.com/youtube/v3/{ep}?' + urllib.parse.urlencode(q)
            try:
                r = json.load(urllib.request.urlopen(url, timeout=20)); s.used += cost; return r
            except urllib.error.HTTPError as e:
                last = e
                if e.code in (403, 429): s.i += 1; continue
                if e.code == 404: return {}
                raise
            except Exception as e:
                last = e; time.sleep(2)
        raise RuntimeError(f'API failed: {last}')

def load_inputs():
    keys, ids, handles, users = [], [], [], []
    for ln in open(COMPETITORS, encoding='utf-8', errors='ignore'):
        ln = ln.strip()
        if not ln: continue
        if ln.startswith('AIza'): keys.append(ln); continue
        m = re.search(r'/channel/(UC[\w-]{10,})', ln)
        if m: ids.append(m.group(1)); continue
        m = re.search(r'@([\w.\-]+)', ln)
        if m: handles.append(m.group(1)); continue
        m = re.search(r'/user/([\w.\-]+)', ln)
        if m: users.append(m.group(1))
    return keys, list(dict.fromkeys(ids)), list(dict.fromkeys(handles)), list(dict.fromkeys(users))

# ---------------- metrics ----------------
def age_h(v): return max((NOW - v['pub']) / 3600.0, 0.01)
def latest_views(v): return v['ticks'][-1][1] if v['ticks'] else 0
def pick_tick(v, back_h, min_h):
    """tick gần mốc (now-back_h) nhất nhưng cách tick cuối >= min_h."""
    if len(v['ticks']) < 2: return None
    t_last = v['ticks'][-1][0]
    cands = [t for t in v['ticks'][:-1] if t_last - t[0] >= min_h*3600]
    if not cands: return None
    target = t_last - back_h*3600
    return min(cands, key=lambda t: abs(t[0]-target))
def calc_vph(v):
    """(vph, estimated?)"""
    if not v['ticks']: return 0.0, True
    t_last, v_last = v['ticks'][-1]
    ref = pick_tick(v, 3, 2)
    if ref: return max((v_last - ref[1]) / ((t_last - ref[0])/3600.0), 0.0), False
    return v_last / age_h(v), True          # <2h dữ liệu → since-publish, cờ ước lượng
def calc_vpd(v):
    if not v['ticks']: return 0.0, True
    t_last, v_last = v['ticks'][-1]
    ref = pick_tick(v, 24, 18)
    if ref:
        d = (v_last - ref[1]) / ((t_last - ref[0])/86400.0)
        return max(d, 0.0), False
    vph, est = calc_vph(v); return vph*24, True

# ---------------- init ----------------
def cmd_init():
    keys, ids, handles, users = load_inputs()
    if not keys: print('KHÔNG thấy API key trong', COMPETITORS); return
    api = API(keys)
    ch = jload('channels.json', {})
    for i in range(0, len(ids), 50):
        d = api.get('channels', {'part': 'snippet,contentDetails', 'id': ','.join(ids[i:i+50]), 'maxResults': 50})
        for it in d.get('items', []):
            ch[it['id']] = {'title': it['snippet']['title'], 'uploads': it['contentDetails']['relatedPlaylists'].get('uploads')}
    for h in handles:
        d = api.get('channels', {'part': 'snippet,contentDetails', 'forHandle': h})
        for it in d.get('items', []):
            ch[it['id']] = {'title': it['snippet']['title'], 'uploads': it['contentDetails']['relatedPlaylists'].get('uploads')}
    for u in users:
        d = api.get('channels', {'part': 'snippet,contentDetails', 'forUsername': u})
        for it in d.get('items', []):
            ch[it['id']] = {'title': it['snippet']['title'], 'uploads': it['contentDetails']['relatedPlaylists'].get('uploads')}
    jsave('channels.json', ch)
    # seed từ state radar tuần nếu có (ticks mốc)
    V = jload('videos.json', {})
    old = os.path.join(BASE, 'radar_state', 'videos.json')
    if os.path.exists(old) and not V:
        for vid, o in json.load(open(old)).items():
            ticks = []
            for dstr, views in sorted(o.get('snaps', {}).items()):
                ts = datetime.strptime(dstr, '%Y-%m-%d').replace(hour=12, tzinfo=TZ).timestamp()
                ticks.append([ts, int(views or 0)])
            V[vid] = {'ch': o['ch'], 'chId': o.get('chId',''), 'title': o['title'], 'pub': parse_pub(o['p']),
                      'dur': o.get('dur'), 'ticks': ticks, 'tier': 0, 'fail': 0, 'pushed': 0,
                      'last_vph': 0.0, 'confirm_due': 0, 'dead': False}
    jsave('videos.json', V)
    cfg = jload('config.json', None)
    if not cfg:
        cfg = {'ntfy_topic': 'radar-lifein-' + ''.join(random.choices(string.ascii_lowercase+string.digits, k=12)),
               'ntfy_enabled': False,
               'T1_vph': 400, 'T2_vph': 1200, 'T3_vph': 4000, 'T4_vph': 12000,
               'T1_frac': 0.20, 'T2_rank': 3, 'T2_daily_cap': 5,
               'allages_vpd_floor': 10000}
        jsave('config.json', cfg)
    jobs = {'discover': 0, 'hot': 0, 't1': 0, 'd01': 0, 'd26': 0, 'allages': 0, 'weekly': next_sunday_8am()}
    jsave('jobs.json', jobs)
    print(f'INIT xong: {len(ch)} kênh (đã resolve handle), {len(V)} video seed, topic ntfy gợi ý: {cfg["ntfy_topic"]}')

def next_sunday_8am():
    n = now_local()
    days = (6 - n.weekday()) % 7
    cand = (n + timedelta(days=days)).replace(hour=8, minute=0, second=0, microsecond=0)
    if cand <= n: cand += timedelta(days=7)
    return cand.timestamp()

# ---------------- kho packaging (thumbnail + title — không backfill được, phải lưu từ bây giờ) ----------------
THUMB_CAP = int(os.environ.get('RADAR_THUMB_CAP', '150'))   # trần download/lần chạy — backfill dần, không nghẽn cron
_thumb_n = 0
def snap_thumb(vid, v, force=False):
    """Lưu ảnh thumbnail khi nội dung ảnh ĐỔI (so hash) — 0 unit quota (i.ytimg.com không tính API)."""
    global _thumb_n
    due = force or not v.get('thumb_hist') or (v.get('tier', 0) >= 1 and NOW - v.get('thumb_ck', 0) > 86400)
    if not due or _thumb_n >= THUMB_CAP or over_budget(): return
    try:
        data = urllib.request.urlopen(f'https://i.ytimg.com/vi/{vid}/hqdefault.jpg', timeout=10).read()
    except Exception: return
    _thumb_n += 1; v['thumb_ck'] = NOW
    h = hashlib.md5(data).hexdigest()[:10]
    hist = v.setdefault('thumb_hist', [])
    if not hist or hist[-1][1] != h:
        with open(os.path.join(TH, f'{vid}_{h}.jpg'), 'wb') as f: f.write(data)
        hist.append([NOW, h])

# ---------------- jobs ----------------
def refresh_videos(api, V, vids):
    # bỏ qua video vừa tick <15 phút (resume sau PAUSE không fetch lại phần đã làm)
    vids = [x for x in vids if x in V and not V[x]['dead']
            and not (V[x]['ticks'] and NOW - V[x]['ticks'][-1][0] < 900)]
    for i in range(0, len(vids), 50):
        if over_budget(): return False
        batch = vids[i:i+50]
        d = api.get('videos', {'part': 'snippet,statistics,contentDetails', 'id': ','.join(batch), 'maxResults': 50})
        got = set()
        for it in d.get('items', []):
            v = V[it['id']]; got.add(it['id'])
            if v['dur'] is None: v['dur'] = parse_dur(it['contentDetails']['duration'])
            new_title = it.get('snippet', {}).get('title', '')
            if new_title and new_title != v['title']:
                v.setdefault('title_hist', []).append([NOW, v['title']]); v['title'] = new_title
                snap_thumb(it['id'], v, force=True)   # đổi title thường đi kèm đổi thumb
            else:
                snap_thumb(it['id'], v)
            views = int(it.get('statistics', {}).get('viewCount') or 0)
            if not v['ticks'] or views != v['ticks'][-1][1] or NOW - v['ticks'][-1][0] > 1800:
                v['ticks'].append([NOW, views])
        for x in batch:
            if x not in got: V[x]['dead'] = True
    return True

def job_discover(api, V, ch, prog):
    done = prog.get('discover_done', [])
    for cid, info in ch.items():
        if cid in done or not info.get('uploads'): continue
        if over_budget(): prog['discover_done'] = done; return False
        d = api.get('playlistItems', {'part': 'contentDetails,snippet', 'playlistId': info['uploads'], 'maxResults': 20})
        for it in d.get('items', []):
            vid = it['contentDetails']['videoId']
            if vid not in V:
                sn = it['snippet']
                V[vid] = {'ch': sn.get('channelTitle', info['title']), 'chId': cid, 'title': sn.get('title', ''),
                          'pub': parse_pub(it['contentDetails'].get('videoPublishedAt', sn.get('publishedAt', ''))),
                          'dur': None, 'ticks': [], 'tier': 0, 'fail': 0, 'pushed': 0,
                          'last_vph': 0.0, 'confirm_due': 0, 'dead': False}
        done.append(cid)
    prog['discover_done'] = []
    new = [vid for vid, v in V.items() if not v['ticks'] and not v['dead']]
    return refresh_videos(api, V, new)

def select_ids(V, pred): return [vid for vid, v in V.items() if not v['dead'] and pred(v)]

# ---------------- tier engine ----------------
def evaluate(V, cfg, pushes_today):
    events = []
    young = [(vid, v) for vid, v in V.items() if not v['dead'] and (v['dur'] or 999) > 180 and age_h(v) < 168 and v['ticks']]
    cohorts = {}
    for vid, v in young: cohorts.setdefault(int(age_h(v)//24), []).append((vid, v))
    metrics = {}
    for d, members in cohorts.items():
        scored = []
        for vid, v in members:
            vph, e1 = calc_vph(v); vpd, e2 = calc_vpd(v)
            scored.append((vid, v, vph, vpd, e1))
        scored.sort(key=lambda t: -t[2])
        n = len(scored)
        for rank, (vid, v, vph, vpd, est) in enumerate(scored, 1):
            t = 0
            if vph >= cfg['T4_vph']: t = 4
            elif rank == 1 and vph >= cfg['T3_vph']: t = 3
            elif rank <= cfg['T2_rank'] and vph >= cfg['T2_vph']: t = 2
            elif rank <= max(math.ceil(cfg['T1_frac']*n), 1) and vph >= cfg['T1_vph']: t = 1
            metrics[vid] = {'vph': vph, 'vpd': vpd, 'rank': rank, 'cohort': d, 'est': est, 'calc_tier': t}
    for vid, m in metrics.items():
        v = V[vid]; old = v['tier']; new = m['calc_tier']
        if new > old:
            vph_driven = m['vph'] > v['last_vph'] * 1.02 or v['last_vph'] == 0
            v['tier'] = new; v['fail'] = 0
            ev = {'ts': NOW, 'vid': vid, 'from': old, 'to': new, 'vph': round(m['vph']), 'vpd': round(m['vpd']),
                  'views': latest_views(v), 'age_h': round(age_h(v), 1), 'rank': m['rank'], 'cohort': m['cohort'],
                  'ch': v['ch'], 'title': v['title'], 'pushed': False, 'note': ''}
            if not vph_driven:
                ev['note'] = 'di cư cohort — không push'
            elif new == 4:
                ev['pushed'] = push(cfg, 4, v, m, vid); v['pushed'] = max(v['pushed'], 4)
            elif new == 3 and v['pushed'] < 3:
                v['confirm_due'] = NOW + 20*60; ev['note'] = 'chờ xác nhận 20ph'
            elif new == 2 and v['pushed'] < 2:
                if pushes_today['t2'] < cfg['T2_daily_cap']:
                    ev['pushed'] = push(cfg, 2, v, m, vid)
                    if ev['pushed']: v['pushed'] = max(v['pushed'], 2); pushes_today['t2'] += 1
                else: ev['note'] = 'quá trần T2/ngày — chỉ ghi board'
            events.append(ev)
        elif new < old:
            v['fail'] += 1
            if v['fail'] >= 2:      # hysteresis
                events.append({'ts': NOW, 'vid': vid, 'from': old, 'to': new, 'vph': round(m['vph']),
                               'vpd': round(m['vpd']), 'views': latest_views(v), 'age_h': round(age_h(v),1),
                               'rank': m['rank'], 'cohort': m['cohort'], 'ch': v['ch'], 'title': v['title'],
                               'pushed': False, 'note': 'hạ bậc (2 kỳ)'})
                v['tier'] = new; v['fail'] = 0
        else: v['fail'] = 0
        v['last_vph'] = m['vph']
    # xác nhận T3 đến hạn
    for vid, v in V.items():
        if v['confirm_due'] and NOW >= v['confirm_due'] and not v['dead']:
            m = metrics.get(vid)
            v['confirm_due'] = 0
            if m and m['vph'] >= cfg['T3_vph'] and v['pushed'] < 3:
                ok = push(cfg, 3, v, m, vid); v['pushed'] = max(v['pushed'], 3)
                events.append({'ts': NOW, 'vid': vid, 'from': 3, 'to': 3, 'vph': round(m['vph']), 'vpd': round(m['vpd']),
                               'views': latest_views(v), 'age_h': round(age_h(v),1), 'rank': m['rank'], 'cohort': m['cohort'],
                               'ch': v['ch'], 'title': v['title'], 'pushed': ok, 'note': 'T3 XÁC NHẬN'})
            else:
                events.append({'ts': NOW, 'vid': vid, 'from': 3, 'to': v['tier'], 'vph': round(m['vph']) if m else 0,
                               'vpd': 0, 'views': latest_views(v), 'age_h': round(age_h(v),1), 'rank': 0, 'cohort': -1,
                               'ch': v['ch'], 'title': v['title'], 'pushed': False, 'note': 'T3 KHÔNG giữ được — hủy'})
    return events, metrics

def push(cfg, tier, v, m, vid=''):
    if not cfg.get('ntfy_enabled') or not cfg.get('ntfy_topic'): return False
    names = {2: 'T2 ỨNG VIÊN', 3: 'T3 SÓNG — SẢN XUẤT', 4: 'T4 BÙNG NỔ'}
    body = (f"{v['title'][:90]}\n{v['ch']} | VPH {m['vph']:,.0f} | VPD {m['vpd']:,.0f} | "
            f"tuổi {age_h(v)/24:.1f}d | hạng {m['rank']} cohort D{m['cohort']}\nhttps://youtu.be/{vid}")
    try:
        # JSON publish: header HTTP chỉ nhận latin-1 — title tiếng Việt phải đi qua body (bug vá 08/07/2026)
        payload = json.dumps({'topic': cfg['ntfy_topic'], 'title': names[tier], 'message': body,
                              'priority': 5 if tier == 4 else 4, 'tags': ['rotating_light']}, ensure_ascii=False)
        req = urllib.request.Request('https://ntfy.sh', data=payload.encode('utf-8'),
                                     headers={'Content-Type': 'application/json'})
        urllib.request.urlopen(req, timeout=10); return True
    except Exception: return False

# ---------------- outputs ----------------
def render_board(V, cfg, metrics, jobs, api_used, pushes_today):
    L = [f"# RADAR BOARD — {fmt_ts()}  (heartbeat)", '',
         f"Quota dùng lần chạy này: ~{api_used} units | Push T2 hôm nay: {pushes_today['t2']}/{cfg['T2_daily_cap']} | ntfy: {'BẬT' if cfg.get('ntfy_enabled') else 'TẮT (log-only)'}", '']
    by_cohort = {}
    for vid, m in metrics.items(): by_cohort.setdefault(m['cohort'], []).append((vid, m))
    for d in sorted(by_cohort):
        rowsx = sorted(by_cohort[d], key=lambda t: t[1]['rank'])[:12]
        L.append(f"## Cohort D{d}  ({len(by_cohort[d])} video)")
        L.append('| # | Bậc | VPH | VPD | Views | Tuổi | Kênh | Video |')
        L.append('|---|---|---|---|---|---|---|---|')
        for vid, m in rowsx:
            v = V[vid]; tier = ['—','T1','T2','T3','T4'][v['tier']]
            est = '~' if m['est'] else ''
            L.append(f"| {m['rank']} | {tier} | {est}{m['vph']:,.0f} | {m['vpd']:,.0f} | {latest_views(v):,} | "
                     f"{age_h(v)/24:.1f}d | {v['ch'][:18]} | [{v['title'][:55]}](https://youtu.be/{vid}) |")
        L.append('')
    # VPD cao mọi tuổi
    olds = []
    for vid, v in V.items():
        if v['dead'] or (v['dur'] or 999) <= 180 or age_h(v) < 168 or len(v['ticks']) < 2: continue
        vpd, est = calc_vpd(v)
        if vpd >= cfg['allages_vpd_floor']: olds.append((vid, v, vpd, est))
    olds.sort(key=lambda t: -t[2])
    L.append(f"## VPD CAO MỌI TUỔI (≥{cfg['allages_vpd_floor']:,}/ngày — 'còn VPD là còn đáng làm')")
    L.append('| VPD | Views | Tuổi | Kênh | Video |'); L.append('|---|---|---|---|---|')
    for vid, v, vpd, est in olds[:15]:
        L.append(f"| {'~' if est else ''}{vpd:,.0f} | {latest_views(v):,} | {age_h(v)/24:.0f}d | {v['ch'][:18]} | [{v['title'][:55]}](https://youtu.be/{vid}) |")
    L.append('')
    nx = {k: fmt_ts(t) for k, t in jobs.items()}
    L.append(f"*Lịch kế tiếp: discover {nx['discover']} · hot {nx['hot']} · D0-1 {nx['d01']} · D2-6 {nx['d26']} · all-ages {nx['allages']} · weekly {nx['weekly']}*")
    open(os.path.join(RP, 'radar_board.md'), 'w').write('\n'.join(L))

def append_alerts(events):
    if not events: return
    with open(os.path.join(RP, 'alerts.log'), 'a') as f:
        for e in events:
            f.write(f"{fmt_ts(e['ts'])} | T{e['from']}→T{e['to']} | VPH {e['vph']:,} | VPD {e['vpd']:,} | views {e['views']:,} | "
                    f"{e['age_h']/24:.1f}d | rank{e['rank']}/D{e['cohort']} | {e['ch'][:20]} | {e['title'][:60]} | "
                    f"{'PUSHED' if e['pushed'] else e['note']} | https://youtu.be/{e['vid']}\n")
    log = jload('alerts_log.json', [])
    log.extend(events); jsave('alerts_log.json', log)

def job_weekly(V, cfg):
    log = jload('alerts_log.json', [])
    wstart = time.time() - 7*86400
    week = [e for e in log if e['ts'] >= wstart]
    ups = [e for e in week if e['to'] >= 2 and e['to'] > e['from']]
    L = [f"# BÁO CÁO TUẦN — {now_local().strftime('%Y-%m-%d')} 08:00", '',
         f"Sự kiện bậc trong tuần: {len(week)} | Lên T2+: {len(ups)} | Push: {sum(1 for e in week if e.get('pushed'))}", '',
         '## Sổ cái sóng (video lên T2+ và số phận hiện tại)', '',
         '| Ngày | Bậc | Video | Kênh | VPH lúc alert | Views lúc alert | Views hiện tại | Kết cục |', '|---|---|---|---|---|---|---|---|']
    for e in sorted(ups, key=lambda x: -x['vph']):
        v = V.get(e['vid'], {})
        cur = latest_views(v) if v else 0
        grew = cur / max(e['views'], 1)
        verdict = 'SÓNG THẬT' if cur >= 300000 or grew >= 3 else ('đang chạy' if grew >= 1.3 else 'xẹp')
        L.append(f"| {fmt_ts(e['ts'])[:10]} | T{e['to']} | {e['title'][:45]} | {e['ch'][:16]} | {e['vph']:,} | {e['views']:,} | {cur:,} | {verdict} |")
    vphs = sorted([e['vph'] for e in week if e['vph'] > 0])
    if vphs:
        L += ['', f"## Hiệu chỉnh: phân phối VPH các sự kiện tuần — P50={vphs[len(vphs)//2]:,} P90={vphs[int(len(vphs)*.9)]:,}",
              f"Sàn hiện tại: T1={cfg['T1_vph']} T2={cfg['T2_vph']} T3={cfg['T3_vph']} T4={cfg['T4_vph']} — cân nhắc chỉnh nếu P90 lệch xa."]
    open(os.path.join(WK, now_local().strftime('%Y-%m-%d') + '.md'), 'w').write('\n'.join(L))

def prune(V):
    cut = NOW - 14*86400
    for v in V.values():
        old = [t for t in v['ticks'] if t[0] < cut]
        keep = [t for t in v['ticks'] if t[0] >= cut]
        byday = {}
        for t in old: byday[datetime.fromtimestamp(t[0], TZ).strftime('%Y-%m-%d')] = t
        v['ticks'] = sorted(byday.values()) + keep

# ---------------- main ----------------
def cmd_run():
    keys, *_ = load_inputs()
    api = API(keys)
    V = jload('videos.json', {}); ch = jload('channels.json', {}); cfg = jload('config.json', {})
    jobs = jload('jobs.json', {}); prog = jload('progress.json', {})
    if not V or not ch or not cfg: print('Chưa init — chạy: python3 daily_radar.py init'); return
    today = now_local().strftime('%Y-%m-%d')
    pc = jload('push_count.json', {'date': today, 't2': 0})
    if pc['date'] != today: pc = {'date': today, 't2': 0}
    CAD = {'discover': 3*3600, 'hot': 1800, 't1': 3600, 'd01': 2*3600, 'd26': 4*3600, 'allages': 24*3600}
    ran = []
    def due(j): return NOW >= jobs.get(j, 0)
    ok = True
    if due('discover'):
        ok = job_discover(api, V, ch, prog); ran.append('discover')
        if ok: jobs['discover'] = NOW + CAD['discover']
    if ok and due('hot'):
        ids = select_ids(V, lambda v: v['tier'] >= 2 or v['confirm_due'])
        ok = refresh_videos(api, V, ids); ran.append('hot')
        if ok: jobs['hot'] = NOW + CAD['hot']
    if ok and due('t1'):
        ids = select_ids(V, lambda v: v['tier'] == 1)
        ok = refresh_videos(api, V, ids); ran.append('t1')
        if ok: jobs['t1'] = NOW + CAD['t1']
    if ok and due('d01'):
        ids = select_ids(V, lambda v: age_h(v) < 48 and v['tier'] < 2)
        ok = refresh_videos(api, V, ids); ran.append('d01')
        if ok: jobs['d01'] = NOW + CAD['d01']
    if ok and due('d26'):
        ids = select_ids(V, lambda v: 48 <= age_h(v) < 168 and v['tier'] < 1)
        ok = refresh_videos(api, V, ids); ran.append('d26')
        if ok: jobs['d26'] = NOW + CAD['d26']
    if ok and due('allages'):
        ids = select_ids(V, lambda v: age_h(v) >= 168 and (v['dur'] or 999) > 180)
        ok = refresh_videos(api, V, ids); ran.append('allages')
        if ok: jobs['allages'] = NOW + CAD['allages']; prune(V)
    events, metrics = evaluate(V, cfg, pc)
    if due('weekly'):
        job_weekly(V, cfg); jobs['weekly'] = next_sunday_8am(); ran.append('weekly')
    render_board(V, cfg, metrics, jobs, api.used, pc)
    append_alerts(events)
    jsave('videos.json', V); jsave('jobs.json', jobs); jsave('progress.json', prog); jsave('push_count.json', pc)
    tag = 'PAUSE — chạy lại để tiếp' if not ok else 'DONE'
    print(f"{tag} | jobs: {','.join(ran) or 'none-due'} | events: {len(events)} | quota ~{api.used} | videos: {len(V)}")

def cmd_status():
    V = jload('videos.json', {}); jobs = jload('jobs.json', {})
    tiers = {}
    for v in V.values(): tiers[v['tier']] = tiers.get(v['tier'], 0) + 1
    print(f"videos: {len(V)} | tiers: {tiers} | jobs kế tiếp: " + ', '.join(f"{k}@{fmt_ts(t)}" for k, t in jobs.items()))

if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'run'
    {'init': cmd_init, 'run': cmd_run, 'status': cmd_status}.get(cmd, cmd_run)()
