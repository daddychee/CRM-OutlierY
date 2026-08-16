"""GĐ2 — Snowball có kiểm soát: centroid ĐÓNG BĂNG, cửa 3 (search title thật) là động cơ,
dừng khi vòng đẻ ≤1 kênh mới đạt chuẩn hoặc chạm trần vòng (spec §4, methodology §3).

`api` bơm từ ngoài (interface .get như scan.API). Mọi trường response .get() phòng thủ.
"""
from . import audience
from . import fingerprint as fp

DEFAULTS = {'voc_min': 15, 'long_min': 0.6, 'subs_min': 5000,   # tầng 1 (spec §5)
            'queries_per_round': 3, 'max_rounds': 6}            # trần cứng chống ngách rộng

def measure_channel(api, ch_id):
    """Đo 1 kênh: title/subs + ~20 title & duration video gần nhất (~3 units). None nếu không đọc được."""
    d = api.get('channels', {'part': 'snippet,statistics,contentDetails', 'id': ch_id}) or {}
    items = d.get('items') or []
    if not items: return None
    it = items[0]
    up = ((it.get('contentDetails') or {}).get('relatedPlaylists') or {}).get('uploads')
    subs = int((it.get('statistics') or {}).get('subscriberCount') or 0)
    title = (it.get('snippet') or {}).get('title') or ch_id
    titles, vids = [], []
    if up:
        pl = api.get('playlistItems', {'part': 'contentDetails,snippet',
                                       'playlistId': up, 'maxResults': 20}) or {}
        for x in pl.get('items') or []:
            vid = (x.get('contentDetails') or {}).get('videoId')
            t = (x.get('snippet') or {}).get('title')
            if vid and t: vids.append(vid); titles.append(t)
    durs = []
    if vids:
        dv = api.get('videos', {'part': 'contentDetails', 'id': ','.join(vids[:50])}) or {}
        by_id = {v.get('id'): (v.get('contentDetails') or {}).get('duration')
                 for v in dv.get('items') or []}
        from ..scan import parse_dur
        durs = [parse_dur(by_id[v]) if by_id.get(v) else None for v in vids]
    return {'id': ch_id, 'title': title, 'subs': subs, 'titles': titles, 'durs': durs,
            'vids': vids[:5]}                          # cho audience đọc comment theo video

def tier1(ch, cent, cfg):
    """Cổng IN/OUT (quyết định) — gắn điểm lên ch để report dùng."""
    f = fp.fingerprint(ch['titles'])
    ch['voc'] = fp.voc(f, cent)
    ch['long_ratio'], ch['med_s'] = fp.length_profile(ch['durs'])
    return (ch['voc'] >= cfg['voc_min'] and ch['long_ratio'] >= cfg['long_min']
            and (ch.get('subs') or 0) >= cfg['subs_min'])

def featured(api, ch_id):
    """Cửa 1 — featured channels: rẻ (~1 unit) nhưng thường rỗng (YouTube ẩn từ ~2023)."""
    d = api.get('channelSections', {'part': 'contentDetails', 'channelId': ch_id}) or {}
    out = []
    for s in d.get('items') or []:
        out += (s.get('contentDetails') or {}).get('channels') or []
    return out

def run(api, state, cfg=None, on_round=None, audience_on=True):
    """Snowball đến hội tụ. state (mutable — runner checkpoint được):
    {'pool': {id: ch}, 'seen': set, 'used_queries': set, 'centroid': set ĐÓNG BĂNG,
     'lang': str, 'seed_authors': set, 'pool_authors': set, 'rounds': [n_mới/vòng]}
    on_round(state) gọi sau MỖI vòng (checkpoint/budget) — trả False để tạm dừng (PAUSE)."""
    cfg = {**DEFAULTS, **(cfg or {})}
    while len(state['rounds']) < cfg['max_rounds']:
        titles = [t for c in state['pool'].values() for t in c['titles']]
        queries = fp.title_queries(titles, state['lang'], state['used_queries'],
                                   top=cfg['queries_per_round'])
        cand = []
        if not state['rounds']:                       # vòng 0: thử cửa 1 vì rẻ
            for cid in list(state['pool']):
                cand += [c for c in featured(api, cid) if c not in state['seen']]
        for q in queries:
            state['used_queries'].add(q)
            for extra in ({'type': 'channel'}, {'type': 'video', 'videoDuration': 'long'}):
                d = api.get('search', {'part': 'snippet', 'q': q, 'maxResults': 25, **extra},
                            cost=100) or {}
                for it in d.get('items') or []:
                    cid = (it.get('snippet') or {}).get('channelId')
                    if cid and cid not in state['seen']: cand.append(cid)
        new = 0
        for cid in dict.fromkeys(cand):               # khử trùng lặp, giữ thứ tự
            state['seen'].add(cid)
            ch = measure_channel(api, cid)
            if not ch or not tier1(ch, state['centroid'], cfg): continue
            if audience_on:
                au = audience.channel_authors(api, ch.get('vids'))
                ch.update(audience.score(au, state['seed_authors'], state['pool_authors']))
                state['pool_authors'] |= au
            ch['round'] = len(state['rounds']) + 1
            state['pool'][cid] = ch; new += 1
        state['rounds'].append(new)
        if on_round and on_round(state) is False: return state    # PAUSE giữa chừng
        if new <= 1: break                            # hội tụ hình học
    return state

if __name__ == '__main__':   # tự kiểm hội tụ offline: python -m radary.harvest.snowball
    GOOD = ['Life in Iceland cost living', 'Moving to Iceland truth', 'Iceland daily life explained',
            'Living in Iceland winter survival', 'Iceland life culture shock stories'] * 4
    class Fake:                                       # vòng 1 đẻ 3 kênh chuẩn, vòng 2 đẻ 1 → dừng
        def __init__(s): s.round_new = [[f'N1{i}' for i in range(3)], ['N21'], ['N31']]; s.calls = 0
        def get(s, ep, p, cost=1):
            if ep == 'search':
                s.calls += 1
                batch = s.round_new[min((s.calls - 1) // 6, len(s.round_new) - 1)]
                return {'items': [{'snippet': {'channelId': c}} for c in batch]}
            if ep == 'channels':
                return {'items': [{'snippet': {'title': p['id']}, 'statistics': {'subscriberCount': '9000'},
                        'contentDetails': {'relatedPlaylists': {'uploads': 'UU' + p['id']}}}]}
            if ep == 'playlistItems':
                return {'items': [{'contentDetails': {'videoId': f'v{i}'}, 'snippet': {'title': t}}
                                  for i, t in enumerate(GOOD[:8])]}
            if ep == 'videos':
                return {'items': [{'id': f'v{i}', 'contentDetails': {'duration': 'PT10M'}} for i in range(8)]}
            return {}
    seed_fps = [fp.fingerprint(GOOD)]
    st = {'pool': {}, 'seen': set(), 'used_queries': set(), 'centroid': fp.centroid(seed_fps, top=30),
          'lang': 'en', 'seed_authors': set(), 'pool_authors': set(), 'rounds': []}
    for i in range(3):                                # seed 3 kênh đã đo sẵn
        st['pool'][f'S{i}'] = {'id': f'S{i}', 'title': f'S{i}', 'subs': 50000,
                               'titles': GOOD[:8], 'durs': [600] * 8, 'round': 0}
        st['seen'].add(f'S{i}')
    out = run(Fake(), st, cfg={'voc_min': 3}, audience_on=False)
    assert out['rounds'][-1] <= 1 and len(out['rounds']) >= 2, out['rounds']
    assert len(out['pool']) >= 6, len(out['pool'])    # 3 seed + ≥3 kênh mới
    assert all('voc' in c and 'long_ratio' in c for c in out['pool'].values() if c['round'])
    hit = 0                                           # on_round trả False → PAUSE ngay
    st2 = {**st, 'pool': dict(st['pool']), 'rounds': [], 'seen': set(st['seen']), 'used_queries': set()}
    out2 = run(Fake(), st2, cfg={'voc_min': 3}, audience_on=False,
               on_round=lambda s: False)
    assert len(out2['rounds']) == 1                   # dừng sau đúng 1 vòng
    print('snowball OK — đà vòng:', out['rounds'], '· pool cuối:', len(out['pool']))
