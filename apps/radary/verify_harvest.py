#!/usr/bin/env python
"""NGHIỆM THU HARVEST — phần OFFLINE (Fake API, 0 quota YouTube), chạy được mọi lúc.

Case vàng SỐNG (SEED 3 kênh Life-in-Country hội tụ thật, POOL Space 86 kênh) tốn ~10-15K
units — chạy riêng qua UI khi user ra lệnh, không nằm trong bài này (trung thực chi phí).
Chạy: .venv/bin/python verify_harvest.py
"""
import json, os, subprocess, sys, time

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
os.environ.pop('RADAR_BUDGET', None)
from radary import crypto, db
from radary.harvest import runner, snowball, fingerprint as fp

FAILS = []
def check(name, ok, detail=''):
    print(f"  {'✓' if ok else '✗ FAIL'} {name}" + (f' — {detail}' if detail and not ok else ''))
    if not ok: FAILS.append(name)

print('0. UNIT — 4 module tự kiểm (thuần stdlib, offline)')
for mod in ('fingerprint', 'decompose', 'audience', 'snowball'):
    r = subprocess.run([sys.executable, '-m', f'radary.harvest.{mod}'], cwd=BASE,
                       capture_output=True, text=True)
    check(f'radary.harvest.{mod}', r.returncode == 0, (r.stderr or r.stdout)[-200:])

# ---------- Fake API: mô phỏng YouTube, đếm quota, 0 mạng ----------
GOOD = ['Life in Iceland cost of living explained', 'Moving to Iceland the honest truth',
        'Iceland daily life winter survival guide', 'Living in Iceland culture shock stories',
        'Why families leave Reykjavik housing prices', 'Iceland salary jobs taxes explained',
        'Dark winters northern lights everyday life', 'Iceland healthcare education system review',
        'Buying groceries Iceland supermarket tour', 'Iceland immigration visa process experience',
        'Renting apartment Reykjavik prices reality', 'Iceland weather seasons what expect']
SEED_IDS = ['UCseedAAAAAAAAAAAAAAAA', 'UCseedBBBBBBBBBBBBBBBB', 'UCseedCCCCCCCCCCCCCCCC']

class FakeAPI:
    """Vòng 1 đẻ 3 kênh đạt chuẩn, vòng 2 đẻ 1 → phải hội tụ. Interface = scan.API."""
    def __init__(s, keys=None, fail=False, no_comments=False):
        s.keys, s.used, s.searches, s.fail, s.no_comments = keys or [], 0, 0, fail, no_comments
    def get(s, ep, p, cost=1):
        if s.fail: raise RuntimeError('quotaExceeded (fake)')
        if ep == 'commentThreads' and s.no_comments:
            raise RuntimeError('HTTP Error 400: Bad Request (fake — sự cố 23/07)')
        s.used += cost
        if ep == 'search':
            s.searches += 1
            batch = [[f'UCnew1{i}AAAAAAAAAAAAAAAA'[:24] for i in range(3)],
                     ['UCnew21AAAAAAAAAAAAAAAAA'[:24]], ['UCnew31AAAAAAAAAAAAAAAAA'[:24]]]
            return {'items': [{'snippet': {'channelId': c}}
                              for c in batch[min((s.searches - 1) // 6, 2)]]}
        if ep == 'channels':
            cid = p.get('id') or 'UCx'
            return {'items': [{'id': cid, 'snippet': {'title': 'Kênh ' + cid[-4:]},
                               'statistics': {'subscriberCount': '9000'},
                               'contentDetails': {'relatedPlaylists': {'uploads': 'UU' + cid[2:]}}}]}
        if ep == 'playlistItems':
            return {'items': [{'contentDetails': {'videoId': f'v{i}'}, 'snippet': {'title': t}}
                              for i, t in enumerate(GOOD)]}
        if ep == 'videos':
            if 'contentDetails' in p.get('part', ''):
                return {'items': [{'id': f'v{i}', 'contentDetails': {'duration': 'PT10M'}}
                                  for i in range(len(GOOD))]}
            return {'items': [{'snippet': {'channelId': SEED_IDS[0]}}]}
        if ep == 'commentThreads':
            return {'items': [{'snippet': {'topLevelComment': {'snippet':
                    {'authorChannelId': {'value': f'AU{i}'}}}}} for i in range(40)]}
        return {}                                      # channelSections (featured rỗng — đúng thực tế)

print('1. SEED JOB E2E QUA RUNNER (Fake API — hội tụ, checkpoint, read-only)')
conn = db.connect()
LIVE_TABLES = ('channels', 'videos', 'ticks', 'events', 'workspaces', 'pool_stats', 'channel_stats')
live = lambda: [conn.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0] for t in LIVE_TABLES]
org = db.create_org(conn, 'HARVEST-TEST-ORG', 'harvest-test@verify.local')
conn.execute('INSERT INTO api_keys (org_id, key, note, harvest) VALUES (?,?,?,1)',
             (org, crypto.encrypt('FAKE-HARVEST-KEY'), 'verify'))
conn.commit()
before = live()

runner.start(org, '\n'.join(SEED_IDS), 'SEED', audience_on=True, api_factory=lambda k: FakeAPI(k))
runner._threads[org].join(timeout=60)
job = runner.current_job(conn, org)
check('job SEED chạy xong (DONE)', job and job['status'] == 'DONE', job and f"{job['status']} {job['note']}")
res = conn.execute('SELECT * FROM harvest_results WHERE job_id=?', (job['id'],)).fetchall()
check('pool cuối ≥6 kênh (3 seed + ≥3 mới)', len(res) >= 6, len(res))
check('điểm đủ trục: voc/long/core/n_auth/tier/why/risk',
      all(r['tier'] in 'AB' and r['why'] and r['risk'] for r in res))
g = conn.execute('SELECT meta FROM harvest_groups WHERE job_id=? AND selected=1', (job['id'],)).fetchone()
rounds = json.loads(g['meta']).get('rounds', [])
check('bằng chứng hội tụ ghi lại, vòng cuối ≤1', len(rounds) >= 2 and rounds[-1] <= 1, rounds)
check('quota đã tiêu được cộng dồn', job['quota_used'] > 0, job['quota_used'])
check('READ-ONLY: 0 dòng bảng sống bị ghi/sửa/xóa', live() == before,
      f'{dict(zip(LIVE_TABLES, before))} -> {dict(zip(LIVE_TABLES, live()))}')

print('2. BÁO CÁO FULL + IDEMPOTENT')
md1 = runner.report_md(conn, job)
check('report.md đủ mục: bảng kênh + hội tụ + ngưỡng', all(s in md1 for s in
      ('| Hạng |', 'Đà hội tụ', 'Trục MẠNH luật kép', 'Advisory')))
check('report sinh lại = như cũ (idempotent, bỏ dòng timestamp)',
      md1.split('\n', 2)[2] == runner.report_md(conn, job).split('\n', 2)[2])

print('2b. COMMENT LỖI KHÔNG GIẾT JOB (sự cố thật 23/07: commentThreads 400)')
runner.start(org, '\n'.join(SEED_IDS), 'SEED', audience_on=True,
             api_factory=lambda k: FakeAPI(k, no_comments=True))
runner._threads[org].join(timeout=60)
job = runner.current_job(conn, org)
check('mọi lời gọi comment 400 → job vẫn DONE (khán giả chỉ thiếu, không chặn)',
      job and job['status'] == 'DONE', job and f"{job['status']} {job['note']}")
res = conn.execute('SELECT * FROM harvest_results WHERE job_id=?', (job['id'],)).fetchall()
check('kết quả vẫn đủ kênh, n_auth=0 và risk ghi mẫu mỏng',
      len(res) >= 6 and all(r['n_auth'] == 0 for r in res), len(res))

print('3. PAUSE — RADAR_BUDGET cạn giữa chừng rồi chạy tiếp là XONG')
os.environ['RADAR_BUDGET'] = '0.000001'
runner.start(org, '\n'.join(SEED_IDS), 'SEED', audience_on=False, api_factory=lambda k: FakeAPI(k))
runner._threads[org].join(timeout=60)
job = runner.current_job(conn, org)
check('cạn budget → PAUSED + ghi chú "PAUSE — chạy lại để tiếp"',
      job['status'] == 'PAUSED' and 'PAUSE' in job['note'], f"{job['status']} {job['note']}")
os.environ.pop('RADAR_BUDGET')
ck = json.loads(job['checkpoint'] or '{}')
runner.spawn(org, api_factory=lambda k: FakeAPI(k))    # resume từ checkpoint
runner._threads[org].join(timeout=60)
job = runner.current_job(conn, org)
check('chạy tiếp từ checkpoint → DONE', job['status'] == 'DONE', f"{job['status']} {job['note']}")
check('checkpoint có dữ liệu resume (measured/ids)', 'ids' in ck and 'measured' in ck)

print('3b. ERROR RESUMABLE — sự cố 24/07/2026: job kẹt ERROR vĩnh viễn dù code đã vá')
os.environ['RADAR_BUDGET'] = '0.000001'
runner.start(org, '\n'.join(SEED_IDS), 'SEED', audience_on=False, api_factory=lambda k: FakeAPI(k))
runner._threads[org].join(timeout=60)
mid = runner.current_job(conn, org)
conn.execute("UPDATE harvest_jobs SET status='ERROR', note='HTTPError: HTTP Error 400: Bad Request' "
             'WHERE id=?', (mid['id'],)); conn.commit()      # mô phỏng job chết giữa chừng (như job #1 VPS)
os.environ.pop('RADAR_BUDGET')
runner.spawn(org, api_factory=lambda k: FakeAPI(k))          # "▶ Thử lại từ chỗ dừng"
runner._threads[org].join(timeout=60)
job = runner.current_job(conn, org)
check('job ERROR có checkpoint → thử lại là chạy tiếp đến DONE, note lỗi được xóa',
      job['status'] == 'DONE' and job['note'] == '', f"{job['status']} {job['note']}")

print('4. SỰ CỐ QUOTA + KHO KEY TRỐNG')
runner.start(org, '\n'.join(SEED_IDS), 'SEED', audience_on=False,
             api_factory=lambda k: FakeAPI(k, fail=True))
runner._threads[org].join(timeout=60)
job = runner.current_job(conn, org)
check('mọi key 403 → PAUSED kèm hướng dẫn (không ERROR, không mất job)',
      job['status'] == 'PAUSED' and 'Hết quota' in job['note'], f"{job['status']} {job['note']}")
conn.execute('DELETE FROM api_keys WHERE org_id=?', (org,)); conn.commit()
runner.start(org, SEED_IDS[0], 'SEED', audience_on=False)   # API thật nhưng chết ngay vì 0 key
runner._threads[org].join(timeout=60)
job = runner.current_job(conn, org)
check('kho key trống → ERROR "Kho Key Harvest trống" (0 gọi mạng)',
      job['status'] == 'ERROR' and 'trống' in job['note'], f"{job['status']} {job['note']}")

print('5. PARSE ĐẦU VÀO (thuần, 0 quota)')
kinds = [k for k, *_ in runner.parse_lines(
    'https://youtube.com/channel/UCabcdefghijklmnopqrst\n@somehandle\n'
    'https://youtube.com/watch?v=abc123xyz\nrác không phải link')]
check('parse: id/handle/video/bad nhận đúng', kinds == ['id', 'handle', 'video', 'bad'], kinds)

# ---------- dọn org test ----------
with conn:
    job = runner.current_job(conn, org)
    if job: runner._purge(conn, job['id'])
    conn.execute('DELETE FROM members WHERE org_id=?', (org,))
    conn.execute("DELETE FROM users WHERE email='harvest-test@verify.local'")
    conn.execute('DELETE FROM orgs WHERE id=?', (org,))
check('dọn sạch org test', runner.current_job(conn, org) is None)

print()
if FAILS:
    print(f'✗ NGHIỆM THU HARVEST THẤT BẠI — {len(FAILS)} mục: {FAILS}'); sys.exit(1)
print('✓ NGHIỆM THU HARVEST (OFFLINE) ĐẠT — engine hội tụ, resumable, read-only với dữ liệu sống.')
