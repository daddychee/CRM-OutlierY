"""Heatmap giờ ĐĂNG × thứ (heatmap_build_brief.md, user chốt 23/07/2026).

Thuần stdlib, CHỈ ĐỌC bảng videos, 0 quota — dùng lại pub_ts (publishedAt) đã lưu.
Đây là giờ ĐĂNG, không phải giờ xem (giờ xem kênh đối thủ là bất khả thi qua API).
Chỉ long-form >180s (phạm vi Radary); video thiếu pub_ts bị bỏ qua, không crash.
"""
import time
from collections import Counter
from datetime import datetime, timedelta, timezone

DOW = ['T2', 'T3', 'T4', 'T5', 'T6', 'T7', 'CN']

def compute(conn, ws, days=90, tz_off=7, channel='', now=None):
    """Ma trận (thứ × giờ) + phân rã kênh từng ô + dòng đọc-hộ (mô tả, không khuyên — NP5)."""
    now = now or time.time()
    q = ('SELECT pub_ts, channel_title FROM videos WHERE workspace_id=? AND pub_ts>0 '
         'AND (duration_s IS NULL OR duration_s>180)')
    args = [ws]
    if days: q += ' AND pub_ts>?'; args.append(now - days * 86400)
    if channel: q += ' AND channel_title=?'; args.append(channel)
    tz = timezone(timedelta(hours=tz_off))
    M, per_cell, per_ch, oldest = Counter(), {}, Counter(), None
    for r in conn.execute(q, args):
        ts, ch = r['pub_ts'], r['channel_title']
        d = datetime.fromtimestamp(ts, tz)
        k = (d.weekday(), d.hour)
        M[k] += 1
        per_cell.setdefault(k, Counter())[ch] += 1
        per_ch[ch] += 1
        oldest = ts if oldest is None or ts < oldest else oldest
    note, peak = '', None
    if M:
        win = Counter()                                # cửa sổ trượt 3h tìm cụm dày
        for (dw, h), n in M.items():
            for s in (h - 1, h, h + 1): win[s % 24] += n
        best = max(win, key=win.get)
        (bd, bh), bn = max(M.items(), key=lambda x: x[1])
        note = (f'Cụm dày quanh {(best - 1) % 24:02d}h–{(best + 2) % 24:02d}h · '
                f'ô đông nhất {DOW[bd]} {bh:02d}h ({bn} video). '
                f'Mô tả nhịp đăng của pool — không phải khuyến nghị giờ đăng.')
        dows = Counter()                               # thứ dày nhất trong cụm ±1h (tile Most posted hours)
        for (dw, h), n in M.items():
            if min((h - best) % 24, (best - h) % 24) <= 1: dows[dw] += n
        peak = {'h': best, 'dows': [DOW[d] for d, _ in dows.most_common(2)]}
    return {'days': days, 'total': sum(M.values()), 'max': max(M.values()) if M else 0,
            'oldest_ts': oldest, 'note': note, 'peak': peak,
            'cells': [[dw, h, n, per_cell[(dw, h)].most_common(8)]
                      for (dw, h), n in sorted(M.items())],
            'channels': per_ch.most_common()}

if __name__ == '__main__':   # tự kiểm offline: python -m radary.heatmap
    import sqlite3
    c = sqlite3.connect(':memory:'); c.row_factory = sqlite3.Row
    c.execute('CREATE TABLE videos (workspace_id INT, pub_ts REAL, channel_title TEXT, duration_s INT)')
    base = datetime(2026, 7, 20, 21, 0, tzinfo=timezone(timedelta(hours=7))).timestamp()  # T2 21h VN
    rows = [(1, base, 'Kênh A', 600), (1, base, 'Kênh A', 700), (1, base + 3600, 'Kênh B', 900),
            (1, 0, 'Thiếu pub_ts', 600),          # pub_ts=0 → bỏ qua, không crash
            (1, base, 'Video ngắn', 60),          # ≤180s → loại theo phạm vi Radary
            (2, base, 'Khác workspace', 600)]
    c.executemany('INSERT INTO videos VALUES (?,?,?,?)', rows)
    r = compute(c, 1, days=0)
    assert r['total'] == 3 == sum(x[2] for x in r['cells']), r     # không mất, không nhân đôi
    assert r['max'] == 2 and r['cells'][0][:3] == [0, 21, 2], r['cells']
    assert ('Kênh A', 2) in r['cells'][0][3]
    ru = compute(c, 1, days=0, tz_off=0)                           # VN 21h = UTC 14h cùng thứ
    assert ru['cells'][0][:2] == [0, 14] and ru['total'] == 3, ru['cells']
    assert compute(c, 1, days=0, channel='Kênh B')['total'] == 1
    assert compute(c, 99)['total'] == 0 and compute(c, 99)['note'] == ''   # pool rỗng — êm
    assert compute(c, 99)['peak'] is None                                  # rỗng → peak None, không bịa
    assert r['peak'] and r['peak']['h'] in (21, 22) and 'T2' in r['peak']['dows'], r['peak']
    assert 'khuyến nghị' in r['note']
    print('heatmap OK —', r['note'])
