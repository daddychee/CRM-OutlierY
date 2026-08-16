"""Vân tay nội dung kênh — thuần stdlib, không I/O (spec_harvest §5, methodology §1).

Ba việc: (1) phát hiện ngôn ngữ qua function-word + dấu đặc trưng,
(2) vân tay từ khóa title → centroid ngách → điểm voc (số từ khóa trùng),
(3) long-form ratio / độ dài trung vị. Mọi hàm thuần — test được offline.
"""
import re
from collections import Counter

# ponytail: chỉ EN/ES/PT như methodology đã kiểm chứng — thêm ngôn ngữ = thêm bộ từ vào FUNC
FUNC = {
    'en': {'the', 'of', 'in', 'to', 'and', 'a', 'is', 'how', 'why', 'what', 'this', 'that',
           'with', 'for', 'on', 'you', 'your', 'from', 'are', 'was', 'we', 'they', 'it'},
    'es': {'el', 'la', 'los', 'las', 'de', 'del', 'en', 'y', 'que', 'como', 'por', 'para',
           'un', 'una', 'es', 'su', 'con', 'se', 'más', 'este', 'esta', 'qué', 'cómo'},
    'pt': {'o', 'os', 'as', 'do', 'da', 'dos', 'das', 'em', 'e', 'que', 'como', 'por',
           'para', 'um', 'uma', 'é', 'seu', 'sua', 'com', 'se', 'mais', 'este', 'esta', 'não'},
}
_PT_MARKS = 'ãõçâê'
_ES_MARKS = 'ñ¿¡'

def tokenize(text):
    return re.findall(r"[a-záéíóúüñãõçâêôàè]+", (text or '').lower())

def detect_lang(titles):
    """Ngôn ngữ chính của kênh từ list title. Trả 'en'/'es'/'pt'/'other'."""
    votes = Counter()
    for t in titles:
        low = (t or '').lower()
        toks = set(tokenize(low))
        for lang, words in FUNC.items():
            hit = len(toks & words)
            if hit: votes[lang] += hit
        # dấu đặc trưng gỡ hòa ES/PT (nhiều function word trùng nhau)
        votes['pt'] += 2 * sum(low.count(c) for c in _PT_MARKS)
        votes['es'] += 2 * sum(low.count(c) for c in _ES_MARKS)
    if not votes: return 'other'
    lang, n = votes.most_common(1)[0]
    return lang if n >= max(3, len(titles) // 4) else 'other'

def fingerprint(titles, lang=None):
    """Counter từ-khóa-nội-dung của kênh (bỏ function word + từ 1-2 ký tự + số)."""
    lang = lang or detect_lang(titles)
    drop = FUNC.get(lang, set()) | FUNC['en']
    fp = Counter()
    for t in titles:
        for w in tokenize(t):
            if len(w) > 2 and w not in drop: fp[w] += 1
    return fp

def centroid(fps, top=50):
    """Centroid ngách = top từ khóa theo SỐ KÊNH chứa nó (df — chống 1 kênh spam từ)."""
    df = Counter()
    for fp in fps: df.update(set(fp))
    return {w for w, _ in df.most_common(top)}

def voc(fp, cent):
    """Điểm vân tay: số từ khóa của kênh trùng centroid."""
    return len(set(fp) & cent)

def cosine(a, b):
    """Cosine 2 Counter — dùng đo coherence khi phân rã."""
    if not a or not b: return 0.0
    common = set(a) & set(b)
    num = sum(a[w] * b[w] for w in common)
    den = (sum(v * v for v in a.values()) ** 0.5) * (sum(v * v for v in b.values()) ** 0.5)
    return num / den if den else 0.0

def length_profile(durs):
    """(long_ratio >180s, median giây) — bỏ None (video chưa biết duration)."""
    ds = sorted(d for d in durs if d)
    if not ds: return 0.0, 0
    lr = sum(1 for d in ds if d > 180) / len(ds)
    return round(lr, 3), ds[len(ds) // 2]

def format_bucket(lr, med):
    """4 nhóm định dạng cứng (spec §5): sleep/ambient trước vì med là dấu hiệu mạnh nhất."""
    if med >= 2400: return 'sleep-ambient'
    if lr >= 0.7: return 'long-form'
    if lr <= 0.3: return 'short-form'
    return 'mixed'

def title_queries(titles, lang, used, top=4):
    """Rút bigram đặc trưng từ title THẬT làm query search (bỏ số/từ chức năng, bỏ query đã dùng)."""
    drop = FUNC.get(lang, set()) | FUNC['en']
    grams = Counter()
    for t in titles:
        ws = [w for w in tokenize(t) if len(w) > 2 and w not in drop]
        for i in range(len(ws) - 1): grams[ws[i] + ' ' + ws[i + 1]] += 1
    return [g for g, n in grams.most_common(top * 5) if n >= 2 and g not in used][:top]

if __name__ == '__main__':   # tự kiểm nhanh: python -m radary.harvest.fingerprint
    en = ['How the Universe Works', 'Why Black Holes Are Terrifying', 'The James Webb Discoveries']
    es = ['¿Cómo funciona el universo?', 'La verdad del agujero negro', 'El telescopio más grande']
    pt = ['Como funciona o universo', 'A verdade não contada do buraco negro', 'São Paulo à noite']
    assert detect_lang(en) == 'en' and detect_lang(es) == 'es' and detect_lang(pt) == 'pt'
    fps = [fingerprint([t]) for t in en]
    c = centroid(fps + [fingerprint(['Black Holes and the Universe Explained'])], top=10)
    assert voc(fingerprint(['Universe Black Holes Special']), c) >= 2
    assert format_bucket(*length_profile([3000, 2500, 2800])) == 'sleep-ambient'
    assert format_bucket(*length_profile([600, 700, 800, 100])) == 'long-form'
    assert format_bucket(*length_profile([60, 90, 60, 700])) == 'short-form'
    assert format_bucket(*length_profile([600, 100, 90, 700])) == 'mixed'
    assert cosine(fingerprint(en), fingerprint(en)) > 0.99
    q = title_queries(en + en, 'en', used=set())
    assert q and all(' ' in g for g in q)
    print('fingerprint OK —', len(c), 'từ centroid, query mẫu:', q[:2])
