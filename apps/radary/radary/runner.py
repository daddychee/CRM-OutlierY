"""CLI của engine mới — tương đương daily_radar.py nhưng đa workspace.

  python3 -m radary.runner run [ws_id]     # chạy chu kỳ (mặc định: mọi workspace)
  python3 -m radary.runner status
Budget giây qua env RADAR_BUDGET (như bản cũ). DB: data/radary.db.
"""
import os, sys
from datetime import datetime
from . import core, db, scan

BUDGET = float(os.environ.get('RADAR_BUDGET', '9999'))

def workspaces(conn, only=None):
    q = 'SELECT id, name FROM workspaces' + (' WHERE id=?' if only else '')
    return conn.execute(q, (only,) if only else ()).fetchall()

def cmd_run(conn, only=None):
    for w in workspaces(conn, only):
        r = scan.run_cycle(conn, w['id'], BUDGET)
        print(f"[ws{w['id']} {w['name']}] {r['tag']} | jobs: {','.join(r['ran']) or 'none-due'} | "
              f"events: {r['events']} | quota ~{r['quota']} | videos: {r.get('videos', '?')}")

def cmd_status(conn, only=None):
    for w in workspaces(conn, only):
        tz = core.tzinfo(conn.execute('SELECT tz FROM workspaces WHERE id=?', (w['id'],)).fetchone()['tz'])
        tiers = {r['tier']: r['n'] for r in conn.execute(
            'SELECT tier, COUNT(*) n FROM videos WHERE workspace_id=? GROUP BY tier', (w['id'],))}
        nvid = sum(tiers.values())
        jobs = ', '.join(f"{k}@{datetime.fromtimestamp(t, tz).strftime('%Y-%m-%d %H:%M')}"
                         for k, t in db.get_jobs(conn, w['id']).items())
        nev = conn.execute('SELECT COUNT(*) n FROM events WHERE workspace_id=?', (w['id'],)).fetchone()['n']
        print(f"[ws{w['id']} {w['name']}] videos: {nvid} | tiers: {tiers} | events: {nev}\n  jobs kế tiếp: {jobs}")

if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'run'
    only = int(sys.argv[2]) if len(sys.argv) > 2 else None
    conn = db.connect()
    {'run': cmd_run, 'status': cmd_status}.get(cmd, cmd_run)(conn, only)
    conn.close()
