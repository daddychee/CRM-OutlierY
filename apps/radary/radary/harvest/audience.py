"""Tầng 2 — khán giả chung qua co-occurrence author comment (methodology §1, §5.1).

Chỉ XẾP HẠNG, không có quyền loại kênh. Khử thiên vị: trộn order relevance+time,
nhiều trang, báo cỡ mẫu N; N<30 gắn cờ thin (⚠), không phạt.
`api` là đối tượng có .get(endpoint, params, cost) — bơm từ ngoài (test được offline).
"""

def channel_authors(api, video_ids, pages=2, max_videos=3):
    """Set authorChannelId từ comment của các video gần nhất của kênh.
    Sự cố thật 23/07/2026: allThreadsRelatedToChannelId bị YouTube trả 400 (đã bỏ) →
    đổi sang commentThreads theo videoId. MỌI lỗi comment (400/403 tắt comment/quota)
    chỉ làm thiếu dữ liệu khán giả, KHÔNG được giết job — Tầng 2 chỉ xếp hạng."""
    authors = set()
    for vid in (video_ids or [])[:max_videos]:
        for order in ('relevance', 'time'):
            tok = None
            for _ in range(pages):
                p = {'part': 'snippet', 'videoId': vid, 'maxResults': 100,
                     'order': order, 'textFormat': 'plainText'}
                if tok: p['pageToken'] = tok
                try:
                    d = api.get('commentThreads', p) or {}
                except Exception:
                    d = {}                     # comment tắt/lỗi API → bỏ video này, đi tiếp
                for it in d.get('items', []):
                    a = ((it.get('snippet', {}).get('topLevelComment', {}).get('snippet', {})
                          or {}).get('authorChannelId') or {}).get('value')
                    if a: authors.add(a)
                tok = d.get('nextPageToken')
                if not tok: break
    return authors

def score(cand_authors, seed_authors, pool_authors):
    """core = giao với khán giả SEED gốc (mỏ neo) · broad = giao với cả pool hiện tại."""
    return {'core': len(cand_authors & seed_authors),
            'broad': len(cand_authors & pool_authors),
            'n_auth': len(cand_authors),
            'thin': len(cand_authors) < 30}

if __name__ == '__main__':   # tự kiểm offline: python -m radary.harvest.audience
    class Fake:
        def get(s, ep, p, cost=1):
            assert ep == 'commentThreads' and p.get('videoId')
            page2 = {'items': [{'snippet': {'topLevelComment': {'snippet':
                     {'authorChannelId': {'value': f'A{i}'}}}}} for i in (3, 4)]}
            if p.get('pageToken'): return page2
            return {'items': [{'snippet': {'topLevelComment': {'snippet':
                    {'authorChannelId': {'value': f'A{i}'}}}}} for i in (1, 2)],
                    'nextPageToken': 'x'}
    au = channel_authors(Fake(), ['v1'], pages=2)
    assert au == {'A1', 'A2', 'A3', 'A4'}, au
    sc = score(au, seed_authors={'A1', 'A2', 'Z'}, pool_authors={'A1', 'A2', 'A3', 'Z'})
    assert sc == {'core': 2, 'broad': 3, 'n_auth': 4, 'thin': True}
    class Dead:                       # comment 400/tắt → raise — PHẢI nuốt êm, không crash
        def get(s, ep, p, cost=1): raise RuntimeError('HTTP 400 (fake)')
    assert channel_authors(Dead(), ['v1', 'v2']) == set()
    print('audience OK —', sc)
