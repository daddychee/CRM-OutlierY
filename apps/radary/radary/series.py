"""Dữ liệu chart cho video T2+ (roadmap Phase 3.5): chuỗi VPH, xu hướng, marker packaging,
dải phân vị tham chiếu từ sóng lịch sử. Chỉ ĐỌC — không đụng luật core.py.

Phương pháp VPH giữ nguyên triết lý engine: delta trên cửa sổ nhìn lùi >=2h (khử răng cưa
cache API), điểm chưa đủ cửa sổ dùng VPH-since-publish gắn cờ ước lượng.
"""
import json

BACK_H, MIN_H = 3, 2          # cùng hằng số cửa sổ với core.calc_vph
BUCKET_H = 6                  # dải tham chiếu gom theo giỏ 6h tuổi
MAX_AGE_H = 7 * 24            # sóng chỉ so trong 7 ngày đầu (đời sống cohort)
MIN_WAVES = 3                 # <3 sóng lịch sử → không vẽ dải (chống tự lừa)

def vph_series(ticks, pub_ts):
    """[[age_h, vph, est], ...] — VPH tại từng tick theo tuổi video."""
    out = []
    for i in range(1, len(ticks)):
        t_i, v_i = ticks[i]
        cands = [t for t in ticks[:i] if t_i - t[0] >= MIN_H * 3600]
        if cands:
            target = t_i - BACK_H * 3600
            ref = min(cands, key=lambda t: abs(t[0] - target))
            vph = max((v_i - ref[1]) / ((t_i - ref[0]) / 3600.0), 0.0)
            est = False
        else:
            vph = v_i / max((t_i - pub_ts) / 3600.0, 0.01)
            est = True
        out.append([round((t_i - pub_ts) / 3600.0, 2), round(vph, 1), est])
    return out

def trend(series):
    """Mức 1 — đạo hàm: VPH hiện tại so với ~3-6h trước → up/flat/down (ngưỡng ±15%)."""
    if len(series) < 2:
        return {'dir': 'flat', 'pct': 0.0, 'basis_h': 0.0}
    last_age, last_vph, _ = series[-1]
    refs = [s for s in series[:-1] if 3 <= last_age - s[0] <= 6]
    ref = min(refs, key=lambda s: abs(last_age - s[0] - 4.5)) if refs else series[-2]
    base = ref[1]
    pct = (last_vph - base) / base if base > 0 else 0.0
    d = 'up' if pct > 0.15 else 'down' if pct < -0.15 else 'flat'
    return {'dir': d, 'pct': round(pct, 3), 'basis_h': round(last_age - ref[0], 1)}

def packaging_markers(conn, video_id, pub_ts):
    """Mốc đổi title/thumbnail theo tuổi video. thumb_hist bỏ dòng đầu (bản chụp đầu ≠ lần đổi)."""
    out = []
    for r in conn.execute('SELECT ts, old_title FROM title_hist WHERE video_id=? ORDER BY ts', (video_id,)):
        out.append({'age_h': round((r['ts'] - pub_ts) / 3600.0, 2), 'kind': 'retitle', 'old': r['old_title']})
    thumbs = conn.execute('SELECT ts FROM thumb_hist WHERE video_id=? ORDER BY ts', (video_id,)).fetchall()
    for r in thumbs[1:]:
        out.append({'age_h': round((r['ts'] - pub_ts) / 3600.0, 2), 'kind': 'rethumb'})
    return sorted(out, key=lambda m: m['age_h'])

def _pct(vals, p):
    return round(vals[min(int(len(vals) * p), len(vals) - 1)], 1)

def reference_bands(conn, ws, now, exclude_yt=''):
    """Mức 2 — dải phân vị VPH theo tuổi từ các sóng T2+ ĐÃ KẾT THÚC (rớt khỏi T2+ hoặc >7 ngày).
    Video đang xem bị loại khỏi tập tham chiếu của chính nó."""
    waves = set()
    for r in conn.execute("SELECT video_yt_id, payload FROM events WHERE workspace_id=? AND kind='tier'", (ws,)):
        try:
            p = json.loads(r['payload'])
        except Exception:
            continue
        if p.get('to', 0) >= 2 and r['video_yt_id'] and r['video_yt_id'] != exclude_yt:
            waves.add(r['video_yt_id'])
    if not waves:
        return {'n_waves': 0, 'bands': [], 'views_bands': []}
    qm = ','.join('?' * len(waves))
    buckets, vbuckets, n_ended = {}, {}, 0
    for v in conn.execute(f'SELECT id, pub_ts, tier FROM videos WHERE workspace_id=? AND yt_id IN ({qm})',
                          (ws, *waves)):
        age_h = (now - v['pub_ts']) / 3600.0
        if age_h <= MAX_AGE_H and v['tier'] >= 2:
            continue                       # sóng còn đang chạy — chưa phải tiền lệ
        ticks = [[r['ts'], r['views']] for r in conn.execute(
            'SELECT ts, views FROM ticks WHERE video_id=? ORDER BY ts', (v['id'],))]
        s = vph_series(ticks, v['pub_ts'])
        if not s:
            continue
        n_ended += 1
        for age, vph, est in s:
            if age > MAX_AGE_H:
                break
            buckets.setdefault(int(age // BUCKET_H), []).append(vph)
        for t, views in ticks:             # cùng bộ sóng: phân vị VIEWS TÍCH LŨY theo tuổi
            age = (t - v['pub_ts']) / 3600.0
            if age > MAX_AGE_H:
                break
            vbuckets.setdefault(int(age // BUCKET_H), []).append(views)
    if n_ended < MIN_WAVES:
        return {'n_waves': n_ended, 'bands': [], 'views_bands': []}
    def _bands(src):
        return [{'age_h': (b + 0.5) * BUCKET_H,
                 'p25': _pct(sorted(vals), .25), 'p50': _pct(sorted(vals), .50),
                 'p75': _pct(sorted(vals), .75), 'p90': _pct(sorted(vals), .90)}
                for b, vals in sorted(src.items()) if len(vals) >= 3]
    return {'n_waves': n_ended, 'bands': _bands(buckets), 'views_bands': _bands(vbuckets)}

def video_series(conn, ws, v, now):
    """Gói dữ liệu đầy đủ cho modal chart của 1 video (row `videos` đã kiểm quyền + T2+)."""
    ticks = [[r['ts'], r['views']] for r in conn.execute(
        'SELECT ts, views FROM ticks WHERE video_id=? ORDER BY ts', (v['id'],))]
    s = vph_series(ticks, v['pub_ts'])
    # trạng thái Xóa/Ẩn: thời điểm lấy từ event dead; thiếu event (chết từ thời engine cũ) → xấp xỉ tick cuối
    dead_age = None
    if v['dead']:
        r = conn.execute("SELECT ts FROM events WHERE workspace_id=? AND kind='dead' AND video_yt_id=? "
                         'ORDER BY ts LIMIT 1', (ws, v['yt_id'])).fetchone()
        base_ts = r['ts'] if r else (ticks[-1][0] if ticks else None)
        if base_ts is not None:
            dead_age = round((base_ts - v['pub_ts']) / 3600.0, 2)
    mk = packaging_markers(conn, v['id'], v['pub_ts'])
    if dead_age is not None:
        mk.append({'age_h': dead_age, 'kind': 'dead'})
    tier_ev = []
    for r in conn.execute("SELECT ts, payload FROM events WHERE workspace_id=? AND kind='tier' "
                          'AND video_yt_id=? ORDER BY ts', (ws, v['yt_id'])):
        try:
            p = json.loads(r['payload'])
            tier_ev.append({'age_h': round((r['ts'] - v['pub_ts']) / 3600.0, 2),
                            'from': p.get('from', 0), 'to': p.get('to', 0)})
        except Exception:
            pass
    return {
        'video': {'yt_id': v['yt_id'], 'title': v['title'], 'channel': v['channel_title'],
                  'tier': v['tier'], 'views': ticks[-1][1] if ticks else 0,
                  'age_h': round((now - v['pub_ts']) / 3600.0, 1),
                  'dead': bool(v['dead']), 'dead_age_h': dead_age,
                  'url': f"https://youtu.be/{v['yt_id']}"},
        'ticks': [[round((t - v['pub_ts']) / 3600.0, 2), views] for t, views in ticks],
        'vph_series': s,
        'trend': trend(s),
        'markers': mk,
        'tier_events': tier_ev,
        'reference': reference_bands(conn, ws, now, exclude_yt=v['yt_id']),
    }
