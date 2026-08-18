"""Migrate niche Life in X (state JSON của daily_radar.py) → workspace #1 trong SQLite.

CHỈ ĐỌC state cũ — không sửa/xóa gì trong radar_state/. Chạy lại an toàn (từ chối nếu
workspace đã tồn tại). Thứ tự nạp video giữ đúng thứ tự trong videos.json để ranking
ổn định y hệt engine cũ khi VPH hòa nhau.

  python3 -m radary.migrate_legacy [email_chủ_org]
"""
import json, os, re, shutil, sys
from . import db
from .scan import DATA

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEGACY = os.path.join(BASE, 'radar_state', 'daily')
COMPETITORS = os.path.join(BASE, 'radar_state', 'competitors.txt')

def jload(name, default):
    try:
        with open(os.path.join(LEGACY, name), encoding='utf-8') as f: return json.load(f)
    except Exception: return default

def legacy_keys():
    keys = []
    for ln in open(COMPETITORS, encoding='utf-8', errors='ignore'):
        ln = ln.strip()
        if ln.startswith('AIza'): keys.append(ln)
    return keys

def run(email='congthanh267@gmail.com', ws_name='Life in X'):
    conn = db.connect()
    if conn.execute('SELECT 1 FROM workspaces WHERE name=?', (ws_name,)).fetchone():
        print(f'Workspace "{ws_name}" đã tồn tại — không migrate lại (tránh nhân đôi dữ liệu).'); return
    V = jload('videos.json', {}); ch = jload('channels.json', {}); cfg = jload('config.json', {})
    if not V or not ch:
        print('Không thấy state cũ trong', LEGACY); return
    with conn:
        org = db.create_org(conn, 'Outliery', email)
        for k in legacy_keys():
            conn.execute('INSERT INTO api_keys(org_id, key, note) VALUES(?,?,?)', (org, k, 'migrate từ competitors.txt'))
        ws = db.create_workspace(conn, org, ws_name, cfg)
        conn.executemany('INSERT INTO channels(workspace_id, yt_id, title, uploads_playlist) VALUES(?,?,?,?)',
                         [(ws, cid, c.get('title', ''), c.get('uploads', '')) for cid, c in ch.items()])
        n_ticks = n_th = n_tt = 0
        for yt_id, v in V.items():        # giữ thứ tự file → id tăng dần cùng thứ tự
            vid_row = conn.execute(
                '''INSERT INTO videos(workspace_id, yt_id, channel_yt_id, channel_title, title, pub_ts,
                   duration_s, tier, fail, pushed, last_vph, confirm_due, dead, thumb_ck)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                (ws, yt_id, v.get('chId', ''), v['ch'], v['title'], v['pub'], v['dur'],
                 v['tier'], v['fail'], v['pushed'], v['last_vph'], v['confirm_due'],
                 int(v['dead']), v.get('thumb_ck', 0))).lastrowid
            if v['ticks']:
                conn.executemany('INSERT OR REPLACE INTO ticks(video_id, ts, views) VALUES(?,?,?)',
                                 [(vid_row, t[0], t[1]) for t in v['ticks']])
                n_ticks += len(v['ticks'])
            for ts, old in v.get('title_hist', []):
                conn.execute('INSERT INTO title_hist(video_id, ts, old_title) VALUES(?,?,?)', (vid_row, ts, old)); n_tt += 1
            for ts, h in v.get('thumb_hist', []):
                conn.execute('INSERT INTO thumb_hist(video_id, ts, hash) VALUES(?,?,?)', (vid_row, ts, h)); n_th += 1
        db.set_jobs(conn, ws, jload('jobs.json', {}))
        db.kv_set(conn, ws, 'progress', jload('progress.json', {}))
        db.kv_set(conn, ws, 'push_count', jload('push_count.json', {'date': '', 't2': 0}))
        db.append_events(conn, ws, [dict(e, kind='tier') for e in jload('alerts_log.json', [])])
    # copy kho ảnh (bản gốc giữ nguyên)
    src = os.path.join(LEGACY, 'thumbs'); dst = os.path.join(DATA, 'thumbs', str(ws))
    n_img = 0
    if os.path.isdir(src):
        os.makedirs(dst, exist_ok=True)
        for f in os.listdir(src):
            if f.endswith('.jpg') and not os.path.exists(os.path.join(dst, f)):
                shutil.copy2(os.path.join(src, f), os.path.join(dst, f)); n_img += 1
    nev = conn.execute('SELECT COUNT(*) n FROM events WHERE workspace_id=?', (ws,)).fetchone()['n']
    print(f'MIGRATE xong → workspace #{ws} "{ws_name}": {len(ch)} kênh, {len(V)} video, {n_ticks} tick, '
          f'{nev} event, {n_tt} title_hist, {n_th} thumb_hist, {n_img} ảnh copy, {len(legacy_keys())} API key.')
    conn.close()

if __name__ == '__main__':
    run(*(sys.argv[1:2]))
