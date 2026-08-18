# -*- coding: utf-8 -*-
"""Phân loại kênh pool GỐC RadarY theo NGÔN NGỮ TIÊU ĐỀ đã quét (0 quota YouTube).

Cách dùng:  python scripts/phan_loai_thi_truong_radary.py [ws_goc]
Chỉ ĐỌC db + in bảng gợi ý + ghi ket_qua_phan_loai_ws<id>.json cạnh db —
KHÔNG tự chuyển kênh (áp dụng = gọi API /channels/move theo file kết quả,
người duyệt trước; tiền lệ chia LIFE IN 19/08 — docs/RADARY_THI_TRUONG.md).

Luật user 19/08: kênh CHƯA CHẮC → để lại "Chưa phân loại". Ngưỡng bảo thủ:
≥5 title chấm được + ≥80% một ngôn ngữ; loại nếu lẫn hệ chữ khác (Hangul/CJK/
Ả Rập/Kirin/Thái/Devanagari >10%) hoặc tiếng Việt (>20%).
LUẬT BỔ SUNG user 19/08: kênh tiếng BỒ/BRAZIL gộp chung thị trường TÂY BAN NHA
(cùng họ ngôn ngữ) — pt cộng vào es khi chấm kênh, vẫn đếm riêng để báo cáo;
kênh Hàn/Nga user gỡ khỏi pool TAY (script chỉ báo, không tự gỡ)."""
import io
import json
import os
import re
import sqlite3
import sys
import unicodedata

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

DB = os.path.join(os.environ.get('RADARY_DATA_DIR')
                  or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                  'data', 'radary'), 'radary.db')
WS_GOC = int(sys.argv[1]) if len(sys.argv) > 1 else 1

ES_TU = {'el', 'la', 'los', 'las', 'un', 'una', 'unos', 'unas', 'de', 'del', 'en',
         'que', 'por', 'para', 'con', 'se', 'su', 'sus', 'es', 'esta', 'estan',
         'como', 'mas', 'pero', 'vida', 'pais', 'paises', 'que', 'y', 'asi',
         'anos', 'ciudad', 'gente', 'mundo', 'donde', 'este', 'estos', 'estas',
         'al', 'lo', 'le', 'les', 'muy', 'sin', 'sobre', 'entre', 'hasta',
         'desde', 'cuando', 'porque', 'tambien', 'todo', 'toda', 'todos', 'todas',
         'no', 'si', 'son', 'ser', 'hay', 'fue', 'era', 'te', 'me', 'nos'}
EN_TU = {'the', 'of', 'in', 'and', 'to', 'a', 'is', 'are', 'how', 'why', 'what',
         'this', 'that', 'with', 'for', 'on', 'at', 'from', 'you', 'your',
         'life', 'country', 'world', 'people', 'most', 'city', 'island',
         'inside', 'living', 'i', 'we', 'it', 'was', 'were', 'be', 'have',
         'has', 'do', 'does', 'not', 'but', 'they', 'their', 'my', 'our'}
VI_CHU = set('ăâđêôơưạảấầẩẫậắằẳẵặẹẻẽếềểễệỉịọỏốồổỗộớờởỡợụủứừửữựỳỵỷỹ')
ES_CHU = set('ñ¿¡')
# Tiếng Bồ Đào Nha dùng chung nhiều từ chức năng với TBN (de/que/por/para/se…)
# → dò dấu hiệu RIÊNG của PT để khỏi chấm nhầm kênh BR sang Spain (chưa chắc = để lại)
PT_CHU = set('ãõç')
PT_TU = {'em', 'do', 'da', 'dos', 'das', 'nao', 'voce', 'sao', 'uma', 'muito',
         'isso', 'isto', 'foco', 'feito'}


def bo_dau(s):
    return ''.join(c for c in unicodedata.normalize('NFD', s)
                   if not unicodedata.combining(c))


def la_han(t):
    """Hangul \u2014 LIFE IN khai th\u1ecb tr\u01b0\u1eddng Korea n\u00ean ti\u1ebfng H\u00e0n l\u00e0 NH\u00c3N ri\u00eang (19/08)."""
    return sum(1 for c in t if '\uac00' <= c <= '\ud7af' or '\u1100' <= c <= '\u11ff') >= 2


def he_chu_khac(t):
    return any(('\u4e00' <= c <= '\u9fff') or ('\u3040' <= c <= '\u30ff')
               or ('\u0600' <= c <= '\u06ff') or ('\u0400' <= c <= '\u04ff')
               or ('\u0900' <= c <= '\u097f') or ('\u0e00' <= c <= '\u0e7f')
               for c in t)


def cham_title(t):
    tl = t.lower()
    if la_han(tl):
        return 'ko'
    if he_chu_khac(tl):
        return 'khac'
    if sum(1 for c in tl if c in VI_CHU) >= 2:
        return 'vi'
    tu = re.findall(r'[a-záéíóúüñà-ÿ]+', bo_dau(tl) if False else tl)
    tu_khong_dau = [bo_dau(w) for w in tu]
    if any(c in PT_CHU for c in tl) or sum(1 for w in tu_khong_dau if w in PT_TU) >= 2:
        return 'pt'
    es = sum(1 for w in tu_khong_dau if w in ES_TU) + (2 if any(c in ES_CHU for c in tl) else 0)
    en = sum(1 for w in tu_khong_dau if w in EN_TU)
    if es > en and es >= 2:
        return 'es'
    if en > es and en >= 2:
        return 'en'
    return None


conn = sqlite3.connect('file:' + DB + '?mode=ro', uri=True)
conn.row_factory = sqlite3.Row
kenh = conn.execute('SELECT yt_id, title FROM channels WHERE workspace_id=? AND active=1 '
                    'ORDER BY title', (WS_GOC,)).fetchall()
ket_qua = []
for c in kenh:
    ts = [r['title'] for r in conn.execute(
        'SELECT title FROM videos WHERE workspace_id=? AND channel_yt_id=?',
        (WS_GOC, c['yt_id']))]
    d = {'en': 0, 'es': 0, 'vi': 0, 'pt': 0, 'ko': 0, 'khac': 0, 'none': 0}
    for t in ts:
        v = cham_title(t or '')
        d[v or 'none'] += 1
    tong = len(ts)
    info = conn.execute('SELECT ci.payload FROM channel_info ci JOIN channels ch ON ch.id=ci.channel_id '
                        'WHERE ch.workspace_id=? AND ch.yt_id=?', (WS_GOC, c['yt_id'])).fetchone()
    country = ''
    if info:
        try: country = (json.loads(info['payload']) or {}).get('country') or ''
        except Exception: pass
    cham = d['en'] + d['es']
    cham = cham + d['pt'] + d['ko']       # PT gộp Spain (luật 19/08); Hàn = thị trường Korea
    es_hop = d['es'] + d['pt']
    if tong == 0 or cham < 5:
        kq = 'DE_LAI (it du lieu)'
    elif d['khac'] / tong > 0.10:
        kq = 'DE_LAI (lan he chu khac)'
    elif d['vi'] / tong > 0.20:
        kq = 'DE_LAI (tieng Viet)'
    elif d['ko'] / cham >= 0.80:
        kq = 'KOREA'
    elif es_hop / cham >= 0.80:
        kq = 'SPAIN'
    elif d['en'] / cham >= 0.80:
        kq = 'US'
    else:
        kq = 'DE_LAI (lan EN/ES)'
    ket_qua.append({'yt_id': c['yt_id'], 'ten': c['title'], 'video': tong,
                    'en': d['en'], 'es': d['es'], 'vi': d['vi'], 'pt': d['pt'],
                    'ko': d['ko'], 'khac': d['khac'], 'country': country, 'kq': kq})
conn.close()

for r in ket_qua:
    print(f"{r['kq']:<26} {r['ten'][:38]:<40} vid={r['video']:<4} en={r['en']:<4} "
          f"es={r['es']:<4} pt={r['pt']:<4} ko={r['ko']:<4} vi={r['vi']:<3} "
          f"khac={r['khac']:<3} {r['country']}")
tk = {}
for r in ket_qua:
    k = r['kq'].split(' ')[0]
    tk[k] = tk.get(k, 0) + 1
print('---TONG KET---', tk)
duong_kq = os.path.join(os.path.dirname(DB), f'ket_qua_phan_loai_ws{WS_GOC}.json')
with io.open(duong_kq, 'w', encoding='utf-8') as f:
    json.dump(ket_qua, f, ensure_ascii=False, indent=1)
print('ghi ket qua:', duong_kq)
