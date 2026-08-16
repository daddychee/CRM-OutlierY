"""GĐ1 — Phân rã pool hỗn tạp thành cây 2 tầng CỨNG: ngôn ngữ → định dạng độ dài.

Thuần — nhận list kênh đã đo (dict), không gọi API. Rẻ nhất, sạch nhất (methodology §2).
Mỗi kênh: {'id','title','subs','titles': [str], 'durs': [int|None]}.
"""
from . import fingerprint as fp

def decompose(channels):
    """Trả dict group_key -> group. group_key = 'en/long-form'…"""
    groups = {}
    for ch in channels:
        lang = fp.detect_lang(ch['titles'])
        lr, med = fp.length_profile(ch['durs'])
        key = f"{lang}/{fp.format_bucket(lr, med)}"
        g = groups.setdefault(key, {'lang': lang, 'fmt': key.split('/')[1], 'channels': []})
        g['channels'].append(dict(ch, lang=lang, long_ratio=lr, med_s=med,
                                  fp=fp.fingerprint(ch['titles'], lang)))
    for key, g in groups.items():
        chs = g['channels']
        g['n'] = len(chs)
        g['centroid'] = fp.centroid([c['fp'] for c in chs])
        g['subs_min'] = min(c.get('subs') or 0 for c in chs)
        g['subs_max'] = max(c.get('subs') or 0 for c in chs)
        g['keywords'] = _top_keywords(chs)
        g['reps'] = [c['title'] for c in sorted(chs, key=lambda c: -(c.get('subs') or 0))[:3]]
        g['small'] = g['n'] < 3                     # cờ "quá nhỏ — cân nhắc gộp" (spec GĐ1)
        g['desc'] = _describe(key, g)
    return groups

def _top_keywords(chs, top=8):
    df = {}
    for c in chs:
        for w in set(c['fp']): df[w] = df.get(w, 0) + 1
    return [w for w, _ in sorted(df.items(), key=lambda x: -x[1])[:top]]

def _fmt_subs(v):
    return f'{v/1e6:.1f}M' if v >= 1e6 else f'{v/1e3:.0f}K' if v >= 1e3 else str(v)

def _describe(key, g):
    """Mô tả tự sinh để user dán khi tự tạo workspace (spec GĐ3)."""
    return (f"Ngách {key}: {g['n']} kênh, subs {_fmt_subs(g['subs_min'])}–{_fmt_subs(g['subs_max'])}, "
            f"từ khóa: {', '.join(g['keywords'][:6])}. Đại diện: {', '.join(g['reps'])}.")

if __name__ == '__main__':   # tự kiểm offline: python -m radary.harvest.decompose
    mk = lambda i, ts, ds, subs=10000: {'id': f'UC{i}', 'title': f'Ch{i}', 'subs': subs,
                                        'titles': ts, 'durs': ds}
    en_doc = ['How Black Holes Work', 'The Universe Explained', 'Why Stars Die']
    es_doc = ['El universo explicado', '¿Cómo mueren las estrellas?', 'La verdad del cosmos']
    chans = ([mk(i, en_doc, [900, 1200, 800]) for i in range(4)] +
             [mk(10 + i, es_doc, [900, 1100, 950]) for i in range(3)] +
             [mk(20, en_doc, [3600, 5400, 4000])] +            # sleep/ambient
             [mk(21, en_doc, [60, 90, 45, 700])])              # short-form
    gs = decompose(chans)
    assert set(gs) == {'en/long-form', 'es/long-form', 'en/sleep-ambient', 'en/short-form'}, set(gs)
    assert gs['en/long-form']['n'] == 4 and gs['es/long-form']['n'] == 3
    assert gs['en/sleep-ambient']['small'] and not gs['en/long-form'].get('small')
    assert 'black' in gs['en/long-form']['keywords'] or 'holes' in gs['en/long-form']['keywords']
    assert 'Ngách en/long-form: 4 kênh' in gs['en/long-form']['desc']
    print('decompose OK —', {k: g['n'] for k, g in gs.items()})
