"""NGHIỆM THU PHASE 1 — engine mới (radary/) phải CÙNG HÀNH VI với engine cũ.

Nguyên tắc: parity đo trên CÙNG MỘT INPUT (state JSON production) — bất biến vĩnh viễn,
chạy lại sau mọi thay đổi core.py/report.py. Khác biệt dữ liệu giữa 2 kho (JSON vs SQLite)
chỉ là DRIFT vận hành (2 engine chạy độc lập sau migrate) — in ra để biết, không phải lỗi.

  1. evaluate(): metrics (vph/vpd/rank/cohort/bậc) + events + state sau mutate
  2. Board markdown: từng dòng (trừ dòng heartbeat có timestamp lúc render)
  3. Drift report: lệch dữ liệu JSON vs SQLite (thông tin)
Chạy: python3 verify_phase1.py   (chỉ ĐỌC — không gọi API, không ghi state nào)
"""
import copy, json, os, sys, time

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import daily_radar as dr                     # engine cũ
from radary import core, db, report          # engine mới

SCRATCH = '/private/tmp/claude-501/-Users-daddychee-Desktop-Claude-Tool-Radary/20e2b5a2-c5ff-4f15-8175-f11428f98387/scratchpad/verify_p1'
os.makedirs(SCRATCH, exist_ok=True)
FAILS = []
def check(name, ok, detail=''):
    print(f"  {'✓' if ok else '✗ FAIL'} {name}" + (f' — {detail}' if detail and not ok else ''))
    if not ok: FAILS.append(name)

NOW = time.time()
dr.NOW = NOW                                  # đóng băng thời gian cho engine cũ

# CÙNG INPUT cho cả hai engine: state JSON production
V_src = json.load(open(os.path.join(BASE, 'radar_state', 'daily', 'videos.json')))
cfg = json.load(open(os.path.join(BASE, 'radar_state', 'daily', 'config.json')))
jobs = json.load(open(os.path.join(BASE, 'radar_state', 'daily', 'jobs.json')))

print('1. PARITY EVALUATE (luật T1-T4, cùng input)')
Va, Vb = copy.deepcopy(V_src), copy.deepcopy(V_src)
pca, pcb = {'date': 'x', 't2': 0}, {'date': 'x', 't2': 0}
ev_a, m_a = dr.evaluate(Va, cfg, pca)
ev_b, m_b = core.evaluate(Vb, cfg, pcb, NOW)
check('cùng tập video được chấm', set(m_a) == set(m_b), f'{len(set(m_a) ^ set(m_b))} lệch')
bad = [k for k in m_a if k in m_b and any(m_a[k][f] != m_b[k][f] for f in ('vph', 'vpd', 'rank', 'cohort', 'est', 'calc_tier'))]
check('vph/vpd/rank/cohort/bậc từng video khớp tuyệt đối', not bad,
      f'{len(bad)} lệch, vd {[(k, m_a[k], m_b[k]) for k in bad[:2]]}')
check('events giống hệt', ev_a == ev_b, f'{len(ev_a)} vs {len(ev_b)}: {ev_a[:1]} vs {ev_b[:1]}')
bad = [k for k in Va if (Va[k]['tier'], Va[k]['fail'], round(Va[k]['last_vph'], 9), Va[k]['confirm_due'])
       != (Vb[k]['tier'], Vb[k]['fail'], round(Vb[k]['last_vph'], 9), Vb[k]['confirm_due'])]
check('state sau evaluate (tier/fail/last_vph/confirm_due)', not bad, f'{len(bad)} lệch, vd {bad[:3]}')
check('bộ đếm push T2 khớp', pca['t2'] == pcb['t2'])

print('2. PARITY BOARD (markdown, cùng input)')
dr.RP = SCRATCH                               # engine cũ render vào scratch, KHÔNG đụng board production
dr.render_board(Va, cfg, m_a, jobs, 0, pca)
board_old = open(os.path.join(SCRATCH, 'radar_board.md')).read().split('\n')
cfg_b = dict(cfg); cfg_b.setdefault('min_duration_s', 180)
board_new = report.board_lines(Vb, cfg_b, m_b, jobs, 0, pcb, NOW, core.tzinfo())
check('số dòng board', len(board_old) == len(board_new), f'{len(board_old)} vs {len(board_new)}')
diff = [i for i in range(1, min(len(board_old), len(board_new))) if board_old[i] != board_new[i]]
check('nội dung từng dòng (trừ dòng heartbeat)', not diff,
      f'dòng {diff[:3]}: cũ={board_old[diff[0]] if diff else ""!r} mới={board_new[diff[0]] if diff else ""!r}')

print('3. DRIFT JSON vs SQLite (thông tin — 2 kho chạy độc lập sau migrate, lệch là bình thường)')
conn = db.connect()
row = conn.execute('SELECT id FROM workspaces WHERE name=?', ('Life in X',)).fetchone()
if row:
    V_db = db.load_videos(conn, row['id'])
    only_db = len(set(V_db) - set(V_src)); only_js = len(set(V_src) - set(V_db))
    difft = sum(1 for k in V_src if k in V_db and V_src[k]['ticks'] != V_db[k]['ticks'])
    print(f'  video: JSON {len(V_src)} | SQLite {len(V_db)} | chỉ-DB {only_db} | chỉ-JSON {only_js} | lệch ticks {difft}')
conn.close()

print()
if FAILS:
    print(f'✗ NGHIỆM THU THẤT BẠI — {len(FAILS)} mục: {FAILS}'); sys.exit(1)
print('✓ NGHIỆM THU ĐẠT — engine mới cùng hành vi engine cũ trên cùng input.')
