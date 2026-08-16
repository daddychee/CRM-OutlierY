"""Scheduler trong app — thay cron: mỗi phút kiểm workspace nào có job đến hạn thì chạy chu kỳ.

Budget mỗi chu kỳ nhỏ (mặc định 120s) để server luôn phản hồi; job lớn tự PAUSE
và phút sau chạy nốt (cơ chế resumable có sẵn của engine). Một chu kỳ một thời điểm
(LOCK) — SQLite một người ghi, nhiều người đọc (WAL).
Tắt scheduler khi cần test: RADARY_SCHEDULER=0.
"""
import os, threading, time, traceback
from . import db, scan

LOCK = threading.Lock()          # api.py POST /run dùng chung lock này
_started = False

def _due_any(conn, ws):
    jobs = db.get_jobs(conn, ws)
    now = time.time()
    return not jobs or any(now >= t for t in jobs.values())

def _loop(interval):
    budget = float(os.environ.get('RADAR_BUDGET', '120'))
    while True:
        try:
            conn = db.connect()
            for w in conn.execute('SELECT id, name FROM workspaces').fetchall():
                if not _due_any(conn, w['id']):
                    continue
                try:      # cô lập lỗi theo workspace: 1 pool lỗi (vd hết quota) không chặn pool còn lại
                    with LOCK:
                        r = scan.run_cycle(conn, w['id'], budget)
                    if r['ran'] or r['tag'] != 'DONE':
                        print(f"[scheduler ws{w['id']} {w['name']}] {r['tag']} | jobs: {','.join(r['ran']) or '-'} | "
                              f"events: {r['events']} | quota ~{r['quota']}", flush=True)
                except RuntimeError as e:      # API failed (quota/403) — báo gọn, không spam traceback mỗi phút
                    print(f"[scheduler ws{w['id']} {w['name']}] LỖI API: {str(e)[:120]}", flush=True)
                except Exception:
                    traceback.print_exc()
            conn.close()
        except Exception:
            traceback.print_exc()
        time.sleep(interval)

def start(interval=60):
    global _started
    if _started: return
    _started = True
    threading.Thread(target=_loop, args=(interval,), daemon=True, name='radary-scheduler').start()
