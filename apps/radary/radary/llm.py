"""Lớp LLM diễn giải (Phase 7) — adapter đa provider (Claude / GLM) qua urllib thuần.

RANH GIỚI CỨNG (roadmap Phase 7 + niche_report_spec.md §5 + nguyên tắc 5):
- LLM KHÔNG sinh số: mọi con số phải trích từ dữ liệu được cung cấp trong prompt.
- LLM KHÔNG khuyên "nên đánh/không đánh" — radar báo sóng, người thẩm định sóng.
- Lỗi/thiếu key → caller phải chạy tiếp như không có LLM (không chặn pipeline).
Key lưu mã hóa Fernet trong bảng llm_config (org-level, owner quản ở tab Quản trị).
"""
import json, urllib.error, urllib.request
from . import crypto, db

PROVIDERS = ('claude', 'glm')
DEFAULT_MODEL = {'claude': 'claude-opus-4-8', 'glm': 'glm-4-plus'}

ASK_SYSTEM = (
    'Bạn là trợ lý đọc số liệu của Radary — radar phát hiện video outlier YouTube trên pool kênh đối thủ. '
    'Nhiệm vụ duy nhất: DIỄN GIẢI chỉ số cho người vận hành.\n'
    'LUẬT CỨNG:\n'
    '1. Chỉ dùng số liệu trong phần DỮ LIỆU bên dưới — tuyệt đối không bịa số, không ngoại suy số mới.\n'
    '2. TUYỆT ĐỐI không khuyên "nên đánh/không nên đánh" hay bất kỳ quyết định sản xuất nào — đó là việc của người. '
    'Nếu bị hỏi, từ chối nhẹ nhàng và chỉ nêu các dữ kiện liên quan để người tự quyết.\n'
    '3. Trả lời tiếng Việt, ngắn gọn, mỗi nhận định kèm con số làm căn cứ.\n'
    '4. Dữ liệu không đủ để trả lời thì nói thẳng là không đủ — không đoán.'
)

NARRATIVE_SYSTEM = (
    'Bạn viết lớp tường thuật cho báo cáo phân tích ngách YouTube (tự sinh từ dữ liệu quét). '
    'LUẬT CỨNG: mọi con số trong bài viết phải trích NGUYÊN VĂN từ báo cáo được cung cấp — không sinh số mới, '
    'không ngoại suy; không khuyên quyết định sản xuất; viết tiếng Việt tự nhiên, dễ đọc.'
)


def org_llm(conn, org_id):
    """Config LLM của org (key đã giải mã) hoặc None nếu chưa cấu hình."""
    r = conn.execute('SELECT * FROM llm_config WHERE org_id=?', (org_id,)).fetchone()
    if not r or not r['key']: return None
    return {'provider': r['provider'], 'model': r['model'] or DEFAULT_MODEL.get(r['provider'], ''),
            'key': crypto.decrypt(r['key'])}


def _post(url, headers, body, timeout):
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={'Content-Type': 'application/json', **headers}, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        try: detail = json.load(e).get('error', {}).get('message', '')
        except Exception: detail = ''
        raise RuntimeError(f'LLM API {e.code}: {detail or e.reason}')
    except Exception as e:
        raise RuntimeError(f'không gọi được LLM API: {e}')


def complete(cfg, system, user_text, max_tokens=1500, timeout=120):
    """Một lượt hỏi-đáp, trả text. cfg = org_llm(...). Raise RuntimeError khi lỗi."""
    if cfg['provider'] == 'claude':
        d = _post('https://api.anthropic.com/v1/messages',
                  {'x-api-key': cfg['key'], 'anthropic-version': '2023-06-01'},
                  {'model': cfg['model'], 'max_tokens': max_tokens, 'system': system,
                   'messages': [{'role': 'user', 'content': user_text}]}, timeout)
        if d.get('stop_reason') == 'refusal':
            raise RuntimeError('LLM từ chối trả lời yêu cầu này')
        text = ''.join(b.get('text', '') for b in d.get('content', []) if b.get('type') == 'text')
    elif cfg['provider'] == 'glm':
        d = _post('https://open.bigmodel.cn/api/paas/v4/chat/completions',
                  {'Authorization': f"Bearer {cfg['key']}"},
                  {'model': cfg['model'], 'max_tokens': max_tokens,
                   'messages': [{'role': 'system', 'content': system},
                                {'role': 'user', 'content': user_text}]}, timeout)
        text = ((d.get('choices') or [{}])[0].get('message') or {}).get('content', '')
    else:
        raise RuntimeError(f"provider không hỗ trợ: {cfg['provider']}")
    if not (text or '').strip():
        raise RuntimeError('LLM trả về rỗng')
    return text.strip()


# ---------------- (A) narrative cho báo cáo ngách ----------------
def report_narrative(cfg, report_md):
    """Viết 'Tóm tắt điều hành' từ báo cáo thuần số. Caller tự bọc try/except (fallback êm)."""
    user = (f'Đây là báo cáo thuần số:\n\n{report_md[:24000]}\n\n'
            'Viết phần "Tóm tắt điều hành" 150-250 từ: bức tranh chung của ngách, '
            '2-3 điểm đáng chú ý nhất (từ outlier / keyword LIFT / bảng cược), '
            'và 1-2 giới hạn dữ liệu cần nhớ khi đọc. '
            'Chỉ trả về nội dung markdown của phần tóm tắt, không lặp lại tiêu đề báo cáo.')
    return complete(cfg, NARRATIVE_SYSTEM, user, max_tokens=2000, timeout=180)


# ---------------- (B) Hỏi Radar — diễn giải chỉ số thời gian thực ----------------
def _ask_context(conn, ws):
    """Gom dữ liệu sống, cắt gọn để prompt không phình: board top-N + alerts + calibration."""
    parts = []
    board = db.kv_get(conn, ws, 'board', None)
    if board:
        slim = {'generated_ts': board.get('generated_ts'),
                'push_t2_today': board.get('push_t2_today'), 'push_t2_cap': board.get('push_t2_cap'),
                'cohorts': [{'day': c['day'], 'size': c['size'], 'top': c['videos'][:8]}
                            for c in board.get('cohorts', [])],
                'allages_top': board.get('allages', [])[:10]}
        parts.append('BOARD HIỆN TẠI (top mỗi cohort):\n' + json.dumps(slim, ensure_ascii=False))
    rows = conn.execute('SELECT ts, kind, video_yt_id, payload FROM events WHERE workspace_id=? '
                        'ORDER BY ts DESC LIMIT 15', (ws,)).fetchall()
    parts.append('15 SỰ KIỆN GẦN NHẤT:\n' + json.dumps(
        [{'ts': r['ts'], 'kind': r['kind'], 'vid': r['video_yt_id'],
          **json.loads(r['payload'])} for r in rows], ensure_ascii=False)[:6000])
    cfg = db.get_config(conn, ws)
    parts.append('SÀN BẬC ĐANG ÁP (VPH): ' + json.dumps(
        {k: cfg[k] for k in ('T1_vph', 'T2_vph', 'T3_vph', 'T4_vph', 'T2_daily_cap')}))
    return '\n\n'.join(parts)


def ask(conn, ws, llm_cfg, question):
    ctx = _ask_context(conn, ws)
    user = f'DỮ LIỆU:\n{ctx}\n\nCÂU HỎI CỦA NGƯỜI VẬN HÀNH: {question.strip()[:500]}'
    return complete(llm_cfg, ASK_SYSTEM, user, max_tokens=1200, timeout=90)


# ---------------- AI đọc biểu đồ sóng (chart modal) ----------------
def _thin(seq, n=40):
    """Rút gọn chuỗi điểm để prompt không phình — giữ điểm đầu/cuối, lấy mẫu đều ở giữa."""
    seq = list(seq or [])
    if len(seq) <= n: return seq
    step = len(seq) / n
    return [seq[int(i * step)] for i in range(n - 1)] + [seq[-1]]


def explain_series(llm_cfg, data):
    """Diễn giải đúng dữ liệu chart đang vẽ (series.video_series) — không thêm số nào khác."""
    d = {'video': data['video'], 'trend': data['trend'],
         'vph_theo_tuoi_gio': _thin(data.get('vph_series')),
         'views_tich_luy': _thin(data.get('ticks'), 25),
         'markers_doi_packaging': data.get('markers', []),
         'tien_le_niche': {'n_waves': data['reference']['n_waves'],
                           'vph_bands_p25_p50_p75_p90': _thin(data['reference'].get('bands'), 20),
                           'views_tichluy_bands': _thin(data['reference'].get('views_bands'), 12)}}
    user = ('DỮ LIỆU BIỂU ĐỒ SÓNG của 1 video (VPH theo tuổi video tính bằng giờ; bands = phân vị '
            'các sóng T2+ đã kết thúc cùng niche):\n' + json.dumps(d, ensure_ascii=False) +
            '\n\nĐọc biểu đồ cho người vận hành, gạch đầu dòng ngắn gọn: '
            '(1) pha hiện tại của sóng (tăng tốc / đi ngang / tàn) kèm số dẫn chứng; '
            '(2) đang chạy nhanh hay chậm hơn tiền lệ P50/P90 của niche (nếu có bands; không có thì nói rõ chưa đủ tiền lệ); '
            '(3) marker đổi title/thumbnail có trùng thời điểm VPH đổi hướng không; '
            '(4) chốt 1 dòng "kết luận này sai trong trường hợp nào".')
    return complete(llm_cfg, ASK_SYSTEM, user, max_tokens=900, timeout=90)
