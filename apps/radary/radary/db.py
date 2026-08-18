"""SQLite multi-tenant: org → members → workspace → channels/videos/ticks/events.

Hợp đồng dữ liệu cho web/app (Phase 2+). Video trong bộ nhớ giữ NGUYÊN hình dạng dict
của engine cũ (ticks list, pub, dur, tier, ...) để logic core dùng chung và so parity được.
"""
import json, os, secrets, sqlite3, string, threading, time

# V3: RADARY_DATA_DIR trỏ kho dữ liệu ra ngoài cây code (data/radary) — Luật 6
_DATA = os.environ.get('RADARY_DATA_DIR') or os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
DEFAULT_DB = os.path.join(_DATA, 'radary.db')

SCHEMA = """
CREATE TABLE IF NOT EXISTS orgs (
  id INTEGER PRIMARY KEY, name TEXT NOT NULL, created_ts REAL NOT NULL);
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY, email TEXT UNIQUE NOT NULL, name TEXT DEFAULT '',
  password_hash TEXT DEFAULT '', created_ts REAL NOT NULL);
CREATE TABLE IF NOT EXISTS sessions (
  token TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
  created_ts REAL NOT NULL, expires_ts REAL NOT NULL);
CREATE TABLE IF NOT EXISTS members (
  org_id INTEGER NOT NULL REFERENCES orgs(id), user_id INTEGER NOT NULL REFERENCES users(id),
  role TEXT NOT NULL DEFAULT 'owner',
  workspace_id INTEGER,                                -- NULL = toàn org; số = bị giới hạn 1 niche (Phase 5)
  PRIMARY KEY (org_id, user_id));
CREATE TABLE IF NOT EXISTS api_keys (
  id INTEGER PRIMARY KEY, org_id INTEGER NOT NULL REFERENCES orgs(id),
  key TEXT NOT NULL, note TEXT DEFAULT '',             -- Phase 4: mã hóa Fernet
  workspace_id INTEGER,                                -- Phase 5.1: NULL = toàn org; số = chỉ niche đó
  backup INTEGER NOT NULL DEFAULT 0);                  -- Phase 5.1: 1 = dự phòng, chỉ dùng khi key chính cạn
CREATE TABLE IF NOT EXISTS workspaces (
  id INTEGER PRIMARY KEY, org_id INTEGER NOT NULL REFERENCES orgs(id),
  name TEXT NOT NULL, tz TEXT NOT NULL DEFAULT 'Asia/Ho_Chi_Minh',
  config TEXT NOT NULL DEFAULT '{}', created_ts REAL NOT NULL,
  market TEXT NOT NULL DEFAULT '',                    -- mã thị trường TT-xx từ đế ('' = pool cũ chưa gán)
  ngach TEXT NOT NULL DEFAULT '');                    -- mã ngách N-xxx từ đế — nhóm các pool thị trường cùng ngách
CREATE TABLE IF NOT EXISTS channels (
  id INTEGER PRIMARY KEY, workspace_id INTEGER NOT NULL REFERENCES workspaces(id),
  yt_id TEXT NOT NULL, title TEXT DEFAULT '', uploads_playlist TEXT DEFAULT '',
  active INTEGER NOT NULL DEFAULT 1,
  favorite INTEGER NOT NULL DEFAULT 0,                 -- Phase 3.10: kênh yêu thích ⭐
  UNIQUE (workspace_id, yt_id));
CREATE TABLE IF NOT EXISTS videos (
  id INTEGER PRIMARY KEY, workspace_id INTEGER NOT NULL REFERENCES workspaces(id),
  yt_id TEXT NOT NULL, channel_yt_id TEXT DEFAULT '', channel_title TEXT DEFAULT '',
  title TEXT DEFAULT '', pub_ts REAL NOT NULL DEFAULT 0, duration_s INTEGER,
  tier INTEGER NOT NULL DEFAULT 0, fail INTEGER NOT NULL DEFAULT 0,
  pushed INTEGER NOT NULL DEFAULT 0, last_vph REAL NOT NULL DEFAULT 0,
  confirm_due REAL NOT NULL DEFAULT 0, dead INTEGER NOT NULL DEFAULT 0,
  thumb_ck REAL NOT NULL DEFAULT 0, UNIQUE (workspace_id, yt_id));
CREATE TABLE IF NOT EXISTS ticks (
  video_id INTEGER NOT NULL REFERENCES videos(id), ts REAL NOT NULL, views INTEGER NOT NULL,
  PRIMARY KEY (video_id, ts));
CREATE TABLE IF NOT EXISTS events (                    -- append-only, không UPDATE/DELETE
  id INTEGER PRIMARY KEY, workspace_id INTEGER NOT NULL, ts REAL NOT NULL,
  kind TEXT NOT NULL, video_yt_id TEXT DEFAULT '', payload TEXT NOT NULL DEFAULT '{}');
CREATE TABLE IF NOT EXISTS title_hist (
  video_id INTEGER NOT NULL REFERENCES videos(id), ts REAL NOT NULL, old_title TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS thumb_hist (
  video_id INTEGER NOT NULL REFERENCES videos(id), ts REAL NOT NULL, hash TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS verdicts (                  -- vòng tự chấm: user đánh dấu alert
  event_id INTEGER PRIMARY KEY REFERENCES events(id),
  action TEXT NOT NULL,                                -- acted | ignored
  ts REAL NOT NULL);
CREATE TABLE IF NOT EXISTS jobs (
  workspace_id INTEGER NOT NULL, name TEXT NOT NULL, due_ts REAL NOT NULL DEFAULT 0,
  PRIMARY KEY (workspace_id, name));
CREATE TABLE IF NOT EXISTS kv (
  workspace_id INTEGER NOT NULL, k TEXT NOT NULL, v TEXT NOT NULL DEFAULT '{}',
  PRIMARY KEY (workspace_id, k));
CREATE TABLE IF NOT EXISTS pool_stats (                -- Phase 3.13: nhịp pool nén 6h căn giờ VN, GIỮ VĨNH VIỄN
  workspace_id INTEGER NOT NULL, bucket_ts REAL NOT NULL,
  dviews INTEGER NOT NULL DEFAULT 0,                   -- views cộng thêm trong bucket (phân bổ tuyến tính)
  vph_avg REAL NOT NULL DEFAULT 0,                     -- Δviews/giờ/video của video 0-6d tuổi
  n_young INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (workspace_id, bucket_ts));
CREATE TABLE IF NOT EXISTS channel_stats (             -- Phase 3.13: nhịp theo KÊNH (Top kênh/ngày), GIỮ VĨNH VIỄN
  workspace_id INTEGER NOT NULL, bucket_ts REAL NOT NULL,
  ch TEXT NOT NULL,                                    -- tên kênh (hiển thị)
  dviews INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (workspace_id, bucket_ts, ch));
CREATE TABLE IF NOT EXISTS channel_snap (              -- Metrics (23/07/2026): hồ sơ kênh chụp 1 lần/ngày, GIỮ VĨNH VIỄN
  workspace_id INTEGER NOT NULL, day TEXT NOT NULL,    -- YYYY-MM-DD theo tz workspace
  ch_yt_id TEXT NOT NULL,
  subs INTEGER,                                        -- NULL = kênh ẩn subscriber / YouTube không trả
  total_views INTEGER, video_count INTEGER,            -- viewCount/videoCount trọn đời kênh
  ts REAL NOT NULL,
  PRIMARY KEY (workspace_id, day, ch_yt_id));
CREATE TABLE IF NOT EXISTS harvest_jobs (              -- HARVEST (spec_harvest_1): 1 job hiện hành/org
  id INTEGER PRIMARY KEY, org_id INTEGER NOT NULL REFERENCES orgs(id),
  mode TEXT NOT NULL DEFAULT 'SEED',                   -- SEED | POOL
  status TEXT NOT NULL DEFAULT 'RESOLVING',            -- RESOLVING|CLASSIFIED|SNOWBALL|PAUSED|DONE|ERROR
  input_raw TEXT NOT NULL DEFAULT '',
  audience INTEGER NOT NULL DEFAULT 1,                 -- đo khán giả (tắt được từng job)
  quota_used INTEGER NOT NULL DEFAULT 0, quota_est INTEGER NOT NULL DEFAULT 0,
  created_ts REAL NOT NULL, note TEXT NOT NULL DEFAULT '',
  checkpoint TEXT NOT NULL DEFAULT '{}');              -- state snowball resumable
CREATE TABLE IF NOT EXISTS harvest_groups (            -- cây phân loại workspace (bản nháp)
  job_id INTEGER NOT NULL REFERENCES harvest_jobs(id), gkey TEXT NOT NULL,
  lang TEXT DEFAULT '', fmt TEXT DEFAULT '', n INTEGER DEFAULT 0,
  selected INTEGER NOT NULL DEFAULT 0,
  meta TEXT NOT NULL DEFAULT '{}',                     -- centroid/desc/keywords/reps/kênh nháp
  PRIMARY KEY (job_id, gkey));
CREATE TABLE IF NOT EXISTS harvest_results (           -- report cuối — advisory, user tự áp dụng
  job_id INTEGER NOT NULL REFERENCES harvest_jobs(id), gkey TEXT NOT NULL,
  ch_id TEXT NOT NULL, title TEXT DEFAULT '', subs INTEGER DEFAULT 0,
  voc INTEGER DEFAULT 0, long_ratio REAL DEFAULT 0,
  core INTEGER DEFAULT 0, broad INTEGER DEFAULT 0, n_auth INTEGER DEFAULT 0,
  round INTEGER DEFAULT 0, tier TEXT DEFAULT 'B',
  why TEXT DEFAULT '', risk TEXT DEFAULT '',
  PRIMARY KEY (job_id, gkey, ch_id));
CREATE TABLE IF NOT EXISTS cycles (                    -- nhật ký quét: 1 dòng/chu kỳ
  id INTEGER PRIMARY KEY, workspace_id INTEGER NOT NULL, ts REAL NOT NULL,
  payload TEXT NOT NULL DEFAULT '{}');
CREATE TABLE IF NOT EXISTS channel_info (              -- hồ sơ kênh, cache 24h
  channel_id INTEGER PRIMARY KEY REFERENCES channels(id),
  fetched_ts REAL NOT NULL, payload TEXT NOT NULL DEFAULT '{}');
CREATE TABLE IF NOT EXISTS invites (                   -- mã mời vào org (Phase 5): 1 lần dùng, có hạn
  id INTEGER PRIMARY KEY, org_id INTEGER NOT NULL REFERENCES orgs(id),
  code TEXT UNIQUE NOT NULL, role TEXT NOT NULL DEFAULT 'viewer',
  created_by INTEGER NOT NULL REFERENCES users(id), created_ts REAL NOT NULL,
  expires_ts REAL NOT NULL, used_by INTEGER, used_ts REAL,
  workspace_id INTEGER);                               -- NULL = toàn org; số = mời vào đúng 1 niche
CREATE TABLE IF NOT EXISTS pw_resets (                 -- Phase 5.2: mã reset mật khẩu do owner phát, 1 lần/24h
  id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
  code TEXT UNIQUE NOT NULL, created_by INTEGER NOT NULL,
  created_ts REAL NOT NULL, expires_ts REAL NOT NULL, used_ts REAL);
CREATE TABLE IF NOT EXISTS llm_config (                -- Phase 7: LLM diễn giải, BYO key theo org
  org_id INTEGER PRIMARY KEY REFERENCES orgs(id),
  provider TEXT NOT NULL DEFAULT 'claude',             -- claude | glm
  model TEXT NOT NULL DEFAULT '',
  key TEXT NOT NULL DEFAULT '',                        -- mã hóa Fernet như api_keys
  updated_ts REAL NOT NULL DEFAULT 0);
CREATE INDEX IF NOT EXISTS idx_cycles_ws ON cycles(workspace_id, ts);
CREATE INDEX IF NOT EXISTS idx_videos_ws ON videos(workspace_id, dead);
CREATE INDEX IF NOT EXISTS idx_ticks_video ON ticks(video_id, ts);
CREATE INDEX IF NOT EXISTS idx_events_ws ON events(workspace_id, ts);
"""

# config mặc định của một workspace = số liệu spec v3 (niche testbed Life in X)
DEFAULT_CFG = {
    'ntfy_topic': '', 'ntfy_enabled': False,
    'T1_vph': 400, 'T2_vph': 1200, 'T3_vph': 4000, 'T4_vph': 12000,
    'T1_frac': 0.20, 'T2_rank': 3, 'T2_daily_cap': 5,
    'allages_vpd_floor': 10000, 'min_duration_s': 180, 'purge_min': 3,
    'cadence': {'discover': 3*3600, 'hot': 1800, 't1': 3600,
                'd01': 2*3600, 'd26': 4*3600, 'allages': 24*3600},
    'thumb_cap': 150,
}

# Schema + migration chỉ chạy MỘT LẦN mỗi tiến trình cho mỗi db (sửa 31/07/2026):
# trước đây chạy trên MỌI connect() — mà _migrate kết thúc bằng 2 UPDATE, tức là mọi
# request (kể cả GET thuần đọc) đều xin KHÓA GHI SQLite; gặp lúc vòng quét giữ khóa
# lâu là nổ "database is locked" 500 hàng loạt (15 lần trong log 30/07).
_DA_NAP_SCHEMA: set = set()
_NAP_SCHEMA_LOCK = threading.Lock()

def connect(path=DEFAULT_DB):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fresh = not os.path.exists(path)
    # timeout 15s (mặc định 5s): chờ khóa ghi lâu hơn thay vì nổ lỗi ngay
    conn = sqlite3.connect(path, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA foreign_keys=ON')
    key = os.path.abspath(path)
    if fresh or key not in _DA_NAP_SCHEMA:
        with _NAP_SCHEMA_LOCK:
            if fresh or key not in _DA_NAP_SCHEMA:
                conn.executescript(SCHEMA)
                _migrate(conn)
                _DA_NAP_SCHEMA.add(key)
    if fresh:
        try: os.chmod(path, 0o600)      # DB chứa API key — chỉ chủ máy đọc được
        except OSError: pass
    return conn

def _migrate(conn):
    """Migration nhẹ cho DB tạo trước — thêm cột còn thiếu, không đụng dữ liệu."""
    cols = {r['name'] for r in conn.execute('PRAGMA table_info(users)')}
    if 'password_hash' not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN password_hash TEXT DEFAULT ''")
        conn.commit()
    for t in ('members', 'invites'):    # Phase 5: phạm vi theo niche — NULL = toàn org (nghĩa cũ giữ nguyên)
        cols = {r['name'] for r in conn.execute(f'PRAGMA table_info({t})')}
        if 'workspace_id' not in cols:
            conn.execute(f'ALTER TABLE {t} ADD COLUMN workspace_id INTEGER')
            conn.commit()
    cols = {r['name'] for r in conn.execute('PRAGMA table_info(channels)')}
    if 'favorite' not in cols:          # Phase 3.10: kênh yêu thích ⭐
        conn.execute('ALTER TABLE channels ADD COLUMN favorite INTEGER NOT NULL DEFAULT 0')
        conn.commit()
    cols = {r['name'] for r in conn.execute('PRAGMA table_info(api_keys)')}
    if 'workspace_id' not in cols:      # Phase 5.1: key theo niche + key dự phòng
        conn.execute('ALTER TABLE api_keys ADD COLUMN workspace_id INTEGER')
        conn.execute('ALTER TABLE api_keys ADD COLUMN backup INTEGER NOT NULL DEFAULT 0')
        conn.commit()
    if 'harvest' not in cols:           # Harvest: kho key TÁCH RIÊNG — radar không bao giờ tiêu
        conn.execute('ALTER TABLE api_keys ADD COLUMN harvest INTEGER NOT NULL DEFAULT 0')
        conn.commit()
    cols = {r['name'] for r in conn.execute('PRAGMA table_info(workspaces)')}
    if 'market' not in cols:            # 18/08/2026: pool theo THỊ TRƯỜNG (RADARY_THI_TRUONG.md)
        conn.execute("ALTER TABLE workspaces ADD COLUMN market TEXT NOT NULL DEFAULT ''")
        conn.commit()
    if 'ngach' not in cols:             # 18/08/2026: pool thuộc NGÁCH đế — tab nhỏ Pool theo thị trường của ngách
        conn.execute("ALTER TABLE workspaces ADD COLUMN ngach TEXT NOT NULL DEFAULT ''")
        conn.commit()
    # 23/07/2026: đổi tên vai editor → leader (idempotent — dữ liệu cũ tự nâng khi khởi động)
    conn.execute("UPDATE members SET role='leader' WHERE role='editor'")
    conn.execute("UPDATE invites SET role='leader' WHERE role='editor'")
    conn.commit()

# ---------------- workspace / org ----------------
def create_org(conn, name, owner_email):
    ts = time.time()
    org = conn.execute('INSERT INTO orgs(name, created_ts) VALUES(?,?)', (name, ts)).lastrowid
    u = conn.execute('SELECT id FROM users WHERE email=?', (owner_email,)).fetchone()
    uid = u['id'] if u else conn.execute('INSERT INTO users(email, created_ts) VALUES(?,?)', (owner_email, ts)).lastrowid
    conn.execute('INSERT OR IGNORE INTO members(org_id, user_id, role) VALUES(?,?,?)', (org, uid, 'owner'))
    return org

def new_ntfy_topic():
    """Spec §6: topic ntfy = chuỗi dài ngẫu nhiên (topic công khai theo tên — đoán được là đọc được)."""
    return 'radar-' + ''.join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(16))

def create_workspace(conn, org_id, name, cfg=None, tz='Asia/Ho_Chi_Minh', market='', ngach=''):
    c = dict(DEFAULT_CFG); c.update(cfg or {})
    if not c.get('ntfy_topic'):
        c['ntfy_topic'] = new_ntfy_topic()      # sinh sẵn — user chỉ việc subscribe rồi bật
    return conn.execute('INSERT INTO workspaces(org_id, name, tz, config, created_ts, market, ngach) VALUES(?,?,?,?,?,?,?)',
                        (org_id, name, tz, json.dumps(c, ensure_ascii=False), time.time(), market, ngach)).lastrowid

def get_config(conn, ws):
    row = conn.execute('SELECT config FROM workspaces WHERE id=?', (ws,)).fetchone()
    c = dict(DEFAULT_CFG); c.update(json.loads(row['config']))
    return c

def set_config(conn, ws, cfg, actor=''):
    conn.execute('UPDATE workspaces SET config=? WHERE id=?', (json.dumps(cfg, ensure_ascii=False), ws))
    append_events(conn, ws, [{'ts': time.time(), 'kind': 'config_change', 'payload': {'by': actor}}])

def org_of(conn, ws):
    return conn.execute('SELECT org_id FROM workspaces WHERE id=?', (ws,)).fetchone()['org_id']

def api_keys(conn, ws):
    """Key cho workspace: gán riêng cho nó + toàn org, LOẠI key harvest (kho tách riêng).
    Key CHÍNH trước, DỰ PHÒNG cuối — scan.API xoay vòng khi 403/quota (Phase 5.1)."""
    from . import crypto
    return [crypto.decrypt(r['key']) for r in conn.execute(
        'SELECT key FROM api_keys WHERE org_id=? AND harvest=0 '
        'AND (workspace_id IS NULL OR workspace_id=?) ORDER BY backup, id', (org_of(conn, ws), ws))]

def harvest_keys(conn, org):
    """Kho key riêng của Harvest — radar không đụng, Harvest không đụng key radar."""
    from . import crypto
    return [crypto.decrypt(r['key']) for r in conn.execute(
        'SELECT key FROM api_keys WHERE org_id=? AND harvest=1 ORDER BY id', (org,))]

# ---------------- videos: DB ⇄ dict hình dạng engine cũ ----------------
def load_videos(conn, ws):
    """Trả dict {yt_id: video-dict} — ORDER BY id giữ đúng thứ tự nạp ban đầu (ổn định ranking khi VPH hòa)."""
    V = {}
    for r in conn.execute('SELECT * FROM videos WHERE workspace_id=? ORDER BY id', (ws,)):
        V[r['yt_id']] = {'_id': r['id'], 'ch': r['channel_title'], 'chId': r['channel_yt_id'],
                         'title': r['title'], 'pub': r['pub_ts'], 'dur': r['duration_s'],
                         'ticks': [], 'tier': r['tier'], 'fail': r['fail'], 'pushed': r['pushed'],
                         'last_vph': r['last_vph'], 'confirm_due': r['confirm_due'],
                         'dead': bool(r['dead']), 'thumb_ck': r['thumb_ck']}
    ids = {v['_id']: v for v in V.values()}
    for r in conn.execute('SELECT video_id, ts, views FROM ticks WHERE video_id IN '
                          '(SELECT id FROM videos WHERE workspace_id=?) ORDER BY ts', (ws,)):
        ids[r['video_id']]['ticks'].append([r['ts'], r['views']])
    return V

def upsert_video(conn, ws, yt_id, v):
    """Thêm video mới hoặc cập nhật trường mutable; trả về id. Ticks lưu riêng qua save_ticks."""
    if '_id' in v:
        conn.execute('''UPDATE videos SET channel_title=?, title=?, duration_s=?, tier=?, fail=?,
                        pushed=?, last_vph=?, confirm_due=?, dead=?, thumb_ck=? WHERE id=?''',
                     (v['ch'], v['title'], v['dur'], v['tier'], v['fail'], v['pushed'],
                      v['last_vph'], v['confirm_due'], int(v['dead']), v.get('thumb_ck', 0), v['_id']))
        return v['_id']
    v['_id'] = conn.execute('''INSERT INTO videos(workspace_id, yt_id, channel_yt_id, channel_title,
                               title, pub_ts, duration_s, tier, fail, pushed, last_vph, confirm_due, dead, thumb_ck)
                               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                            (ws, yt_id, v.get('chId', ''), v['ch'], v['title'], v['pub'], v['dur'],
                             v['tier'], v['fail'], v['pushed'], v['last_vph'], v['confirm_due'],
                             int(v['dead']), v.get('thumb_ck', 0))).lastrowid
    return v['_id']

def save_ticks(conn, v):
    """Đồng bộ toàn bộ ticks của 1 video (gọi khi list ticks đổi — append hoặc prune)."""
    conn.execute('DELETE FROM ticks WHERE video_id=?', (v['_id'],))
    conn.executemany('INSERT OR REPLACE INTO ticks(video_id, ts, views) VALUES(?,?,?)',
                     [(v['_id'], t[0], t[1]) for t in v['ticks']])

def save_state(conn, ws, V, dirty_ticks=()):
    with conn:
        for yt_id, v in V.items():
            upsert_video(conn, ws, yt_id, v)
        for yt_id in dirty_ticks:
            save_ticks(conn, V[yt_id])

# ---------------- events / jobs / kv ----------------
def append_events(conn, ws, events):
    conn.executemany('INSERT INTO events(workspace_id, ts, kind, video_yt_id, payload) VALUES(?,?,?,?,?)',
                     [(ws, e['ts'], e.get('kind', 'tier'), e.get('vid', ''),
                       json.dumps({k: x for k, x in e.items() if k not in ('ts', 'kind', 'vid')},
                                  ensure_ascii=False)) for e in events])

def get_jobs(conn, ws):
    return {r['name']: r['due_ts'] for r in conn.execute('SELECT name, due_ts FROM jobs WHERE workspace_id=?', (ws,))}

def set_jobs(conn, ws, jobs):
    conn.executemany('INSERT OR REPLACE INTO jobs(workspace_id, name, due_ts) VALUES(?,?,?)',
                     [(ws, k, t) for k, t in jobs.items()])

def kv_get(conn, ws, k, default):
    r = conn.execute('SELECT v FROM kv WHERE workspace_id=? AND k=?', (ws, k)).fetchone()
    return json.loads(r['v']) if r else default

def kv_set(conn, ws, k, val):
    conn.execute('INSERT OR REPLACE INTO kv(workspace_id, k, v) VALUES(?,?,?)',
                 (ws, k, json.dumps(val, ensure_ascii=False)))

def append_cycle(conn, ws, summary):
    conn.execute('INSERT INTO cycles(workspace_id, ts, payload) VALUES(?,?,?)',
                 (ws, summary['ts'], json.dumps(summary, ensure_ascii=False)))

def recent_cycles(conn, ws, limit=20):
    return [json.loads(r['payload']) for r in conn.execute(
        'SELECT payload FROM cycles WHERE workspace_id=? ORDER BY ts DESC, id DESC LIMIT ?', (ws, limit))]
