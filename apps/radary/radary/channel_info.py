"""Hồ sơ kênh cho modal Pool (roadmap Phase 3.8).

Hai nguồn, hai mức tin cậy:
- Số liệu (subs/videos/views/description/quốc gia/ngày lập): CHÍNH NGẠCH qua YouTube API.
- Links ngoài (TikTok/Spotify/…): BEST-EFFORT bóc từ trang About công khai — API không có
  mục này. Hợp đồng: gãy thì links_ok=False và UI tự ẩn mục Links, KHÔNG chết modal.
Cache 24h/bảng channel_info — quota ~1 unit/kênh/ngày.
"""
import json, re, time, urllib.request

CACHE_TTL = 24 * 3600
UA = ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/126.0 Safari/537.36')

def _unescape(s):
    try: return json.loads(f'"{s}"')
    except Exception: return s

def fetch_links(yt_id):
    """Bóc links ngoài từ ytInitialData của trang About. Pattern kiểm chứng sống 08/07/2026."""
    req = urllib.request.Request(f'https://www.youtube.com/channel/{yt_id}/about',
                                 headers={'User-Agent': UA, 'Accept-Language': 'en-US,en;q=0.9'})
    html = urllib.request.urlopen(req, timeout=15).read().decode('utf-8', 'ignore')
    out, seen = [], set()
    for m in re.finditer(r'"channelExternalLinkViewModel":\{"title":\{"content":"([^"]+)"\},'
                         r'"link":\{"content":"([^"]+)"', html):
        title, url = _unescape(m.group(1)).strip(), _unescape(m.group(2)).strip()
        if not url or url in seen: continue
        seen.add(url)
        out.append({'title': title, 'url': url,
                    'href': url if url.startswith('http') else 'https://' + url})
    return out

def get_info(conn, ch_row, api):
    """Hồ sơ đầy đủ 1 kênh (row bảng channels) — đọc cache trước, hết hạn mới fetch."""
    row = conn.execute('SELECT payload, fetched_ts FROM channel_info WHERE channel_id=?',
                       (ch_row['id'],)).fetchone()
    if row and time.time() - row['fetched_ts'] < CACHE_TTL:
        return json.loads(row['payload'])
    d = api.get('channels', {'part': 'snippet,statistics', 'id': ch_row['yt_id']})
    items = d.get('items', [])
    if not items:
        raise LookupError('kênh không còn tồn tại trên YouTube (xóa/đổi?)')
    sn = items[0]['snippet']; st = items[0].get('statistics', {})
    links, links_ok = [], True
    try:
        links = fetch_links(ch_row['yt_id'])
    except Exception:
        links_ok = False                      # best-effort: gãy thì ẩn, không chết
    info = {'yt_id': ch_row['yt_id'], 'title': sn.get('title', ''),
            'handle': sn.get('customUrl', ''), 'description': sn.get('description', ''),
            'country': sn.get('country', ''), 'published_at': sn.get('publishedAt', ''),
            'avatar': (sn.get('thumbnails', {}).get('medium') or
                       sn.get('thumbnails', {}).get('default') or {}).get('url', ''),
            'subs': int(st.get('subscriberCount') or 0),
            'subs_hidden': bool(st.get('hiddenSubscriberCount')),
            'videos': int(st.get('videoCount') or 0), 'views': int(st.get('viewCount') or 0),
            'links': links, 'links_ok': links_ok, 'fetched_ts': time.time()}
    with conn:
        conn.execute('INSERT OR REPLACE INTO channel_info(channel_id, fetched_ts, payload) VALUES(?,?,?)',
                     (ch_row['id'], info['fetched_ts'], json.dumps(info, ensure_ascii=False)))
    return info
