"""Logic lõi radar — THUẦN, không I/O, không phụ thuộc DB/API.

Port nguyên trạng từ daily_radar.py (spec v3 đóng băng). Khác biệt duy nhất:
- NOW toàn cục → tham số `now` (test được, nhiều workspace chạy chung tiến trình)
- push() gọi trực tiếp → callback `push_fn(tier, v, m, vid) -> bool` (tách I/O khỏi luật)
- hằng số 180s/999 → cfg['min_duration_s'] (niche-agnostic, mặc định giữ nguyên spec)
Mọi thay đổi công thức ở đây PHẢI qua radar_spec.md trước và chạy lại verify parity.
"""
import math
from datetime import timedelta, timezone

def tzinfo(name='Asia/Ho_Chi_Minh'):
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(name)
    except Exception:
        return timezone(timedelta(hours=7))

# ---------------- metrics ----------------
def age_h(v, now): return max((now - v['pub']) / 3600.0, 0.01)
def latest_views(v): return v['ticks'][-1][1] if v['ticks'] else 0

def pick_tick(v, back_h, min_h):
    """tick gần mốc (now-back_h) nhất nhưng cách tick cuối >= min_h."""
    if len(v['ticks']) < 2: return None
    t_last = v['ticks'][-1][0]
    cands = [t for t in v['ticks'][:-1] if t_last - t[0] >= min_h*3600]
    if not cands: return None
    target = t_last - back_h*3600
    return min(cands, key=lambda t: abs(t[0]-target))

def calc_vph(v, now):
    """(vph, estimated?)"""
    if not v['ticks']: return 0.0, True
    t_last, v_last = v['ticks'][-1]
    ref = pick_tick(v, 3, 2)
    if ref: return max((v_last - ref[1]) / ((t_last - ref[0])/3600.0), 0.0), False
    return v_last / age_h(v, now), True     # <2h dữ liệu → since-publish, cờ ước lượng

def calc_vpd(v, now):
    if not v['ticks']: return 0.0, True
    t_last, v_last = v['ticks'][-1]
    ref = pick_tick(v, 24, 18)
    if ref:
        d = (v_last - ref[1]) / ((t_last - ref[0])/86400.0)
        return max(d, 0.0), False
    vph, est = calc_vph(v, now); return vph*24, True

# ---------------- tier engine ----------------
def evaluate(V, cfg, pushes_today, now, push_fn=None):
    """Xếp cohort + thăng/hạ bậc + quyết định push. Trả (events, metrics). Mutate V như engine cũ."""
    push_fn = push_fn or (lambda tier, v, m, vid: False)
    min_dur = cfg.get('min_duration_s', 180)
    events = []
    young = [(vid, v) for vid, v in V.items()
             if not v['dead'] and (v['dur'] or 999) > min_dur and age_h(v, now) < 168 and v['ticks']]
    cohorts = {}
    for vid, v in young: cohorts.setdefault(int(age_h(v, now)//24), []).append((vid, v))
    metrics = {}
    for d, members in cohorts.items():
        scored = []
        for vid, v in members:
            vph, e1 = calc_vph(v, now); vpd, e2 = calc_vpd(v, now)
            scored.append((vid, v, vph, vpd, e1, e2))
        scored.sort(key=lambda t: -t[2])
        n = len(scored)
        for rank, (vid, v, vph, vpd, est, est_vpd) in enumerate(scored, 1):
            t = 0
            if vph >= cfg['T4_vph']: t = 4
            elif rank == 1 and vph >= cfg['T3_vph']: t = 3
            elif rank <= cfg['T2_rank'] and vph >= cfg['T2_vph']: t = 2
            elif rank <= max(math.ceil(cfg['T1_frac']*n), 1) and vph >= cfg['T1_vph']: t = 1
            metrics[vid] = {'vph': vph, 'vpd': vpd, 'rank': rank, 'cohort': d, 'est': est,
                            'est_vpd': est_vpd, 'calc_tier': t}   # est_vpd: VPD = vph×24 kỳ vọng (chưa đủ 24h dữ liệu)
    for vid, m in metrics.items():
        v = V[vid]; old = v['tier']; new = m['calc_tier']
        if new > old:
            vph_driven = m['vph'] > v['last_vph'] * 1.02 or v['last_vph'] == 0
            v['tier'] = new; v['fail'] = 0
            ev = {'ts': now, 'vid': vid, 'from': old, 'to': new, 'vph': round(m['vph']), 'vpd': round(m['vpd']),
                  'views': latest_views(v), 'age_h': round(age_h(v, now), 1), 'rank': m['rank'], 'cohort': m['cohort'],
                  'ch': v['ch'], 'title': v['title'], 'pushed': False, 'note': ''}
            if not vph_driven:
                ev['note'] = 'di cư cohort — không push'
            elif new == 4:
                ev['pushed'] = push_fn(4, v, m, vid); v['pushed'] = max(v['pushed'], 4)
            elif new == 3 and v['pushed'] < 3:
                v['confirm_due'] = now + 20*60; ev['note'] = 'chờ xác nhận 20ph'
            elif new == 2 and v['pushed'] < 2:
                if pushes_today['t2'] < cfg['T2_daily_cap']:
                    ev['pushed'] = push_fn(2, v, m, vid)
                    if ev['pushed']: v['pushed'] = max(v['pushed'], 2); pushes_today['t2'] += 1
                else: ev['note'] = 'quá trần T2/ngày — chỉ ghi board'
            events.append(ev)
        elif new < old:
            v['fail'] += 1
            if v['fail'] >= 2:      # hysteresis
                events.append({'ts': now, 'vid': vid, 'from': old, 'to': new, 'vph': round(m['vph']),
                               'vpd': round(m['vpd']), 'views': latest_views(v), 'age_h': round(age_h(v, now), 1),
                               'rank': m['rank'], 'cohort': m['cohort'], 'ch': v['ch'], 'title': v['title'],
                               'pushed': False, 'note': 'hạ bậc (2 kỳ)'})
                v['tier'] = new; v['fail'] = 0
        else: v['fail'] = 0
        v['last_vph'] = m['vph']
    # xác nhận T3 đến hạn
    for vid, v in V.items():
        if v['confirm_due'] and now >= v['confirm_due'] and not v['dead']:
            m = metrics.get(vid)
            v['confirm_due'] = 0
            if m and m['vph'] >= cfg['T3_vph'] and v['pushed'] < 3:
                ok = push_fn(3, v, m, vid); v['pushed'] = max(v['pushed'], 3)
                events.append({'ts': now, 'vid': vid, 'from': 3, 'to': 3, 'vph': round(m['vph']), 'vpd': round(m['vpd']),
                               'views': latest_views(v), 'age_h': round(age_h(v, now), 1), 'rank': m['rank'], 'cohort': m['cohort'],
                               'ch': v['ch'], 'title': v['title'], 'pushed': ok, 'note': 'T3 XÁC NHẬN'})
            else:
                events.append({'ts': now, 'vid': vid, 'from': 3, 'to': v['tier'], 'vph': round(m['vph']) if m else 0,
                               'vpd': 0, 'views': latest_views(v), 'age_h': round(age_h(v, now), 1), 'rank': 0, 'cohort': -1,
                               'ch': v['ch'], 'title': v['title'], 'pushed': False, 'note': 'T3 KHÔNG giữ được — hủy'})
    return events, metrics

def prune(V, now):
    """Tick >14 ngày nén thành nến ngày. Trả danh sách yt_id có ticks bị đổi (để lưu DB)."""
    from datetime import datetime
    tz = tzinfo()
    cut = now - 14*86400
    dirty = []
    for vid, v in V.items():
        old = [t for t in v['ticks'] if t[0] < cut]
        if not old: continue
        keep = [t for t in v['ticks'] if t[0] >= cut]
        byday = {}
        for t in old: byday[datetime.fromtimestamp(t[0], tz).strftime('%Y-%m-%d')] = t
        merged = sorted(byday.values()) + keep
        if merged != v['ticks']:
            v['ticks'] = merged; dirty.append(vid)
    return dirty
