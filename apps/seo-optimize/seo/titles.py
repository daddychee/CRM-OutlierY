"""Title stage — hybrid marketing-first → 3 title có điểm. Theo title-definition.md.

LLM: map desire (Schwartz) + engine FAB/PAS + awareness → sinh candidate (ngôn ngữ nội dung).
Python: đo ký tự/từ, chấm điểm 'khớp pattern + guardrail', hard-gate ≤100 ký tự, lấy top 3.
Double Down (competitor titles) = bằng chứng tham khảo, không lái.
"""
from __future__ import annotations

import json
import re

from . import digest, llm

# ── KẾT HỢP LẠI TỪ TITLE ĐỐI THỦ (user chốt 2026-07-29: bỏ tầng SOP, chỉ giữ mix & match) ──
# LLM phải TỰ KHAI: kết hợp từ title nào · dùng ngòi nổ nào · bám pattern nào.
# Python đối chiếu cả ba với dữ liệu THẬT — khai sai thì xoá field. LLM hiểu, Python đo.
HOOK_HEAD_CHARS = 65        # ngòi nổ nên nằm trong 65 ký tự đầu (YouTube cắt "…" sau đó)

# KHÔNG hỏi `from_title`/`method` nữa: Python suy được từ `trace_blocks` (title góp cụm dài nhất
# = khung), chính xác hơn lời khai và bớt ~30 token/item. LLM khai `from_title` là nơi lấy CỤM
# GHÉP chứ không phải nơi lấy KHUNG — đo LIVE trên tập FINLAND thì lệch hẳn nguồn.
_MIX_FIELDS = (
    "\"hook\":<từ/cụm ngòi nổ, PHẢI lấy từ `hook_bank`, copy NGUYÊN VĂN>,"
    "\"changed\":<cụm bạn đã ĐỔI so với title gốc, TỐI ĐA 6 TỪ>,"
    "\"pattern_used\":<công thức trong `niche_format.patterns` bạn bám theo, copy NGUYÊN VĂN>"
)
_MIX_RULE = (
    " CÁCH LÀM — kết hợp lại từ chính title đối thủ user đưa vào, KHÔNG tự sáng tác:\n"
    "0. Coi MỖI title trong `competitor_titles_reference` là một dãy Ô tháo lắp được (ô chủ đề, ô định vị, "
    "ô đối tượng, ô bổ nghĩa, ô đuôi). Ô nào xuất hiện ở NHIỀU title là ô BẤT BIẾN — giữ nguyên, cấm đụng.\n"
    "1. Với MỖI title, chọn 1 title làm KHUNG GỐC, rồi tạo BIẾN THỂ theo tỉ lệ 80/20:\n"
    "   · GIỮ NGUYÊN ~80%: thứ tự từ, cụm mở đầu, cấu trúc câu, dấu câu, các từ neo.\n"
    "   · CHỈ ĐỔI ~20%: THÁO 1-2 ô của khung gốc ra và LẮP ô tương ứng LẤY TỪ MỘT TITLE KHÁC "
    "trong danh sách vào đúng chỗ đó. Copy NGUYÊN VĂN cụm đó, KHÔNG tự nghĩ cụm mới, KHÔNG viết lại cho hay hơn.\n"
    "   Ví dụ: khung \"... with EXTREMELY BEAUTIFUL Women and PRISTINE NATURE\" + ô \"WARM-HEARTED GIRLS\" "
    "của title khác → \"... with EXTREMELY BEAUTIFUL Women and WARM-HEARTED GIRLS\".\n"
    "   Không viết lại câu, không đảo trật tự, không \"cải tiến\" cú pháp — giữ khung là chính.\n"
    "2. TỪ NGỮ: chỉ dùng ngòi nổ trong `hook_bank` (rút từ chính các title đó). "
    "CẤM tự nghĩ từ mới. Copy nguyên văn từ đã chọn vào `hook`.\n"
    "3. CẤU TRÚC: bám `niche_format.patterns` (đo từ video outlier THẬT của kênh đối thủ). "
    "Giữ nguyên khung slot, chỉ thay biến số. Ghi vào `pattern_used`.\n"
    "4. CẤM chép y hệt: phải đổi ít nhất 1 cụm biến số, title mới KHÔNG được trùng khít title gốc.\n"
    "5. MỌI CHỮ trong title mới phải tìm được trong `competitor_titles_reference` (trừ chủ thể riêng "
    "của video này lấy từ kịch bản). Máy sẽ truy nguyên từng cụm về title nguồn — cụm nào không "
    "truy được coi là BỊA và bị loại thẳng.\n"
    "6. Đừng lặp từ nối ở chỗ ghép (\"and AND\") — nhưng nếu lỡ, máy tự dọn.\n"
    "7. BA KIỂU BỊ LOẠI THẲNG (đo được trên máy, không thương lượng):\n"
    "   a) Cắt ngắn 1 title đối thủ rồi coi là bản mới — phải ĐỔI ít nhất 1 ô, và ô mới phải "
    "đến từ MỘT TITLE KHÁC trong danh sách.\n"
    "   b) Thêm dữ kiện/tính từ mới không có trong danh sách title (kể cả đúng sự thật theo kịch bản): "
    "\"52 Days of Total Darkness\", \"Hidden\", \"Secret\", \"Stunning\"…\n"
    "   c) Thêm từ PHỦ ĐỊNH / ĐẢO NGHĨA mà danh sách title không có: NOT · NO · NEVER · WITHOUT · "
    "\"No One Talks About\". Chỉ dùng nếu chính title đối thủ có sẵn từ đó.\n"
    "8. Kịch bản phải deliver được đúng lời hứa."
)


_BASE_FIELDS = (
    "\"text\":<title>,\"desire\":<desire/emotion thật, TỐI ĐA 8 TỪ>,\"technique\":<FAB|PAS|Personification|"
    "Identification|Redefinition|Intensification>,\"awareness\":<Unaware|Problem-aware|Solution-aware>,"
    "\"proof\":<true nếu kịch bản deliver được>"
)


# Xin dư để còn chỗ loại. Đo LIVE 2026-07-29 trên niche title dài (95-100 ký tự): chỉ 1/5 ứng viên
# sống sót — 5 là không đủ, user nhận 1 title thay vì 3. Mỗi item thêm ~300 token output.
N_ASK = 8


_BANK_RULE = (
    " Input có thêm `niche_slots`: các Ô RỜI cắt sẵn từ title THẬT khác trong cùng niche.\n"
    "   · Đây là NGUYÊN LIỆU để LẮP VÀO, không phải title để chép. Copy nguyên văn cả ô, "
    "đừng viết lại.\n"
    "   · KHUNG GỐC vẫn PHẢI lấy từ `competitor_titles_reference` — video đối thủ trực tiếp "
    "của tập này.\n"
    "   · Nhờ kho ô này mà mỗi bản lắp một ô KHÁC nhau → nhiều biến thể mà vẫn giữ khung của tập."
)

# Dấu tách Ô trong title: `:` `|` `-` `—` `(` `)` `[` `]` `!` `?` `,` `…`
_SLOT_SPLIT = re.compile(r"[|:\-–—()\[\]!?,…]+|\.\.\.")
SLOT_MIN_W, SLOT_MAX_W = 2, 4      # 1 từ thì vô nghĩa; ≥5 từ đã gần một khung câu


def slots_from(titles: list[str], cap: int = 40) -> list[str]:
    """Cắt title thành các Ô RỜI để làm nguyên liệu lắp.

    **Vì sao phải cắt (đo LIVE 2026-08-02):** trước đây tool đưa nguyên 24 title kho cho LLM,
    cạnh vỏn vẹn 4 title của tập — tỉ lệ cám dỗ 6:1. LLM làm đúng thứ người ta sẽ làm: lấy
    title đã nổ của chính kênh đó làm khung rồi thay biến. Python loại thẳng ⇒ **85% số bản
    bị loại đều vì một lý do "khung gốc lấy từ KHO THAM KHẢO"**, và 1/3 lần chạy có kênh
    KHÔNG ra title nào. Đưa Ô thay vì title thì **không còn khung nào để chép**, mà thứ kho
    thật sự có ích (chất liệu cho 20% ô lắp) vẫn nguyên.

    **KHÔNG đụng tới `trace_blocks`.** Phần truy nguyên chống bịa vẫn chạy trên `_ref_titles`
    đầy đủ trong `result.json` — đây chỉ là đổi thứ GỬI CHO LLM, không đổi thứ ĐEM RA ĐỐI CHIẾU.

    Python chỉ CẮT CHUỖI, không ghép, không sinh nghĩa — đúng ranh giới "Python đo · LLM hiểu".
    Để Python tự ghép title từ kho thì nó đẻ ra "The Mystery of Time | Through the Wormhole" +
    Voyager = vô nghĩa, mà không tầng nào bắt được.
    """
    per: list[list[str]] = []
    for t in titles or []:
        cur = []
        for raw in _SLOT_SPLIT.split(t or ""):
            ws = raw.split()
            if SLOT_MIN_W <= len(ws) <= SLOT_MAX_W:
                cur.append(" ".join(ws))
        if cur:
            per.append(cur)
    # ĐAN XEN giữa các title, KHÔNG xếp liền theo từng title (sửa 2026-08-02 sau khi đo hỏng
    # lần đầu). Xếp liền thì các ô của CÙNG một title nằm cạnh nhau, LLM chỉ cần nối 2 ô kề
    # là dựng lại nguyên khung — đo được: vẫn 12 bản bị loại vì "khung lấy từ kho", trong đó
    # có `"Launched in 1977"` + `"Where is Voyager 1 Right Now"` ghép lại thành đúng title gốc.
    # Đan xen thì không nhìn ra ô nào vốn đứng cạnh ô nào.
    out, seen = [], set()
    for i in range(max((len(x) for x in per), default=0)):
        for col in per:
            if i >= len(col):
                continue
            k = col[i].lower()
            if k in seen:
                continue
            seen.add(k)
            out.append(col[i])
            if len(out) >= cap:
                return out
    return out


_FORM_RULE = (
    " Input có thêm `niche_title_forms`: CÔNG THỨC tiêu đề của niche, `{NAME}`/`{CAPS}` là chỗ "
    "giữ chỗ (`{CAPS}` = cụm VIẾT HOA).\n"
    "   · Dùng làm KHUÔN CÂU: thứ tự các ô, dấu câu, chỗ nào viết hoa.\n"
    "   · **Điền vào chỗ giữ chỗ bằng cụm CÓ THẬT** lấy từ `competitor_titles_reference` hoặc "
    "`niche_slots` — công thức KHÔNG phải nguồn chữ, nó chỉ là khuôn. Tự nghĩ cụm mới để "
    "điền vào là bịa, máy sẽ loại.\n"
    "   · Đừng in ra dấu `{}` trong title."
)


def _sys(n_ask: int, spread: bool, has_bank: bool = False) -> str:
    """System prompt. `spread`=True khi cần N title cho N KÊNH khác nhau → ép đa dạng để né trùng."""
    s = (
        "Bạn là chuyên gia đặt tiêu đề YouTube theo MARKETING (Eugene Schwartz mass-desire: kênh dẫn "
        "nhu cầu/cảm xúc CÓ THẬT của người có nhu cầu; FAB cho nhu cầu, PAS cho cảm xúc; khớp awareness "
        "& sophistication). "
        + llm.OUTPUT_LANG_RULE +
        " ĐỘ DÀI LÀ RÀNG BUỘC CỨNG: ĐẾM ký tự trước khi trả, TUYỆT ĐỐI ≤ 100 (lý tưởng ≤ 60). "
        "Title đối thủ trong danh sách đã dài 95-100 ký tự sẵn — ghép thêm 1 ô vào là VƯỢT NGAY, "
        "nên khi lắp ô mới thì phải THÁO BỚT ô cũ, đừng nối thêm. "
        "honest (kịch bản phải deliver được — "
        f"không giật tít sai). Trả JSON array {n_ask} phần tử: "
        f"[{{{_BASE_FIELDS},{_MIX_FIELDS}}}]." + _MIX_RULE
    )
    if has_bank:
        s += _BANK_RULE
    if spread:
        s += (" CÙNG 1 video này sẽ đăng lên NHIỀU kênh khác nhau → mỗi title phải khai thác MỘT desire "
              "và MỘT công thức KHÁC nhau, khác cả cách mở đầu. Tuyệt đối không ra 2 title na ná nhau.")
    return s
_NICHE_RULE = (
    " Input có thêm `niche_format`: pattern title thống kê từ video OUTLIER THẬT của niche, kèm rules. "
    "Dùng pattern làm KHUNG (bám công thức/độ dài/anchor), TUÂN THỦ rules.must, TRÁNH rules.avoid."
)


def generate_raw(brief: dict | str, competitor_titles: list[str], fmt: dict | None = None,
                 n_ask: int = N_ASK, spread: bool = False,
                 ref_titles: list[str] | None = None,
                 ref_patterns: list[str] | None = None) -> list[dict]:
    content = digest.payload(brief, "") if isinstance(brief, dict) else digest.payload({}, brief)
    payload = {**content, "competitor_titles_reference": competitor_titles[:12]}
    ref = [t for t in (ref_titles or []) if t and t not in competitor_titles]
    if ref:
        # Gửi Ô RỜI, KHÔNG gửi title nguyên vẹn — xem `slots_from`. Gửi nguyên title thì LLM
        # lấy luôn một title niche làm khung, Python loại, tốn cả lượt sinh (đo được: 85% số
        # bản bị loại đều vì lý do đó).
        payload["niche_slots"] = slots_from(ref)
    bank = hook_bank(competitor_titles + ref)
    if bank:
        payload["hook_bank"] = bank        # kho ngòi nổ RÚT TỪ title thật — LLM chỉ được chọn trong đây
    sysmsg = _sys(n_ask, spread, bool(ref))
    if fmt and (fmt.get("title_patterns") or fmt.get("rules")):
        # Gửi ĐÚNG thứ LLM cần để dựng khung, bỏ phần chỉ để người đọc.
        # `example` là chỗ phí nhất: 115 token gửi đi rồi lại dặn "đừng chép nguyên văn" — vừa tốn
        # vừa dụ model chép. Từ khi có `trace_blocks`, title phải ghép từ pool của TẬP chứ không
        # phải từ example của Format, nên example hết vai trò. `support`/`example_verified` là số
        # liệu cho board, LLM không dùng. `title_note` là văn phân tích, pattern đã nói đủ.
        # Đo trên Format thật: 965 → ~620 token/call, × 3 nhóm = bớt ~1.000 token input mỗi lần chạy.
        payload["niche_format"] = {
            "patterns": [{k: v for k, v in (p or {}).items() if k in ("pattern", "desire", "technique")}
                         for p in (fmt.get("title_patterns") or [])[:6]],
            "rules": fmt.get("rules") or {}}
        sysmsg += _NICHE_RULE
    # CÔNG THỨC user khai cho niche (`{NAME} in {CAPS}! - …`). Chỉ vào PROMPT làm khung —
    # TUYỆT ĐỐI không vào `ref_titles`: chỗ giữ chỗ `{NAME}` nằm trong kho truy nguyên thì LLM
    # điền gì cũng "truy được", chốt chống bịa mất sạch răng.
    rp = [p for p in (ref_patterns or []) if p]
    if rp:
        payload["niche_title_forms"] = rp[:12]
        sysmsg += _FORM_RULE
    user = json.dumps(payload, ensure_ascii=False)
    # Ngân sách/item phải tính CẢ phần LLM chép nguyên văn: `from_title` là MỘT TITLE ĐỐI THỦ
    # đầy đủ (tới 100 ký tự ≈ 30 token) và `pattern_used` là cả công thức. Cộng text + 6 field
    # mô tả ⇒ ~280 token/item. Để 170 là cắt cụt JSON giữa chừng — đã cắn LIVE 2026-07-29 trên
    # tập FINLAND (chạm trần 1150, mất dấu } đóng, hỏng nguyên call sau khi đã tiêu quota YouTube).
    # Nới trần KHÔNG đủ: prompt phải chốt độ dài từng field (xem `changed`/`desire`), nếu không
    # model lại viết dài ra cho vừa trần mới.
    out = llm.call_json(sysmsg, user, max_tokens=400 + 300 * n_ask, temperature=0.7)
    return [it for it in llm.as_list(out) if isinstance(it, dict)]


_CAPS_RE = None      # khởi tạo lười ở hook_bank (cần re, tránh import thừa ở đầu file)


def hook_bank(titles_: list[str]) -> list[str]:
    """KHO NGÒI NỔ rút từ chính title đối thủ user đưa vào (SOP Bước 0).

    Thuần Python, KHÔNG có từ điển do tôi tự nghĩ ra — mọi từ đều phải xuất hiện trong title THẬT.
    Xếp theo độ mạnh, nhưng NHẬN HẾT: luật của user là "dùng từ của video tôi đưa", không phải
    "chỉ dùng từ lặp lại".
      1. token IN HOA (DANGEROUS, NEVER) — cách đối thủ nhấn mạnh
      2. con số / đơn vị (0.125g, 100) — điểm neo mạnh
      3. từ lặp ở ≥2 title (anchor) — bằng chứng thống kê
      4. từ nội dung còn lại — vẫn là từ CỦA HỌ, chỉ yếu hơn

    Chỉ lấy 1-3 thì hụt: pool 2-3 video thì gần như không có gì lặp, kho teo lại và mọi ngòi nổ
    hợp lệ đều bị xoá oan (đã cắn: "Radioactive" chỉ có ở 1 title nên bị loại).
    """
    import re
    caps = re.compile(r"\b[0-9A-ZÀ-Ỹ][0-9A-ZÀ-Ỹ'’%.-]{1,}\b")
    num = re.compile(r"\b\d[\d.,]*\s?[a-zA-Z%]{0,3}\b")
    word = re.compile(r"[0-9A-Za-zÀ-ỹ']{3,}")
    out: list[str] = []
    seen: set[str] = set()

    def add(x: str) -> None:
        x = x.strip(" .,!?—-")
        if x and x.lower() not in seen:
            seen.add(x.lower())
            out.append(x)

    freq: dict[str, int] = {}
    for t in titles_:
        for m in caps.findall(t or ""):
            if len(m) > 2 and m.upper() == m:              # bỏ "A", "I", và từ viết hoa đầu câu
                add(m)
        for m in num.findall(t or ""):
            add(m)
        for w in {x.lower() for x in word.findall(t or "")}:
            freq[w] = freq.get(w, 0) + 1
    for w, n in sorted(freq.items(), key=lambda kv: (-kv[1], kv[0])):
        if w in _WEAK_HOOK or len(w) < 3:                  # từ phổ thông không phải ngòi nổ
            continue
        add(w)                                             # lặp nhiều đứng trước, nhưng nhận hết
    return out[:40]


# ── HAI danh sách, HAI việc khác nhau — gộp làm một là thủng (đã cắn 2026-07-29) ──
# _GLUE: keo dán ngữ pháp thuần tuý. LLM buộc phải có nó để câu thành câu, và nó KHÔNG đổi được
# nghĩa của câu → miễn trừ khỏi chốt chống bịa.
_GLUE = {"the", "a", "an", "of", "in", "on", "at", "to", "for", "and", "or", "with", "from",
         "this", "that", "it", "its", "as", "by", "into", "about", "so", "then",
         "is", "are", "was", "were", "be", "been", "am", "have", "has",
         "there", "here", "it's", "there's", "here's", "that's",
         "you", "your", "we", "us", "our", "my", "me", "he", "she", "his", "her",
         "they", "them", "their",
         "và", "của", "là", "có", "cho", "một", "những", "các", "được", "trong", "với", "khi",
         "này", "đó", "về", "từ", "sẽ", "đã", "thì", "mà", "hay", "hoặc", "tôi", "bạn"}
# _ASK: từ dựng khung câu hỏi / tương phản — yếu với vai ngòi nổ, nhưng vẫn đổi được khung câu.
_ASK = {"what", "why", "how", "when", "who", "which", "if", "than", "but",
        "will", "can", "does", "did", "sao", "tại", "vì", "nhưng"}
# _NEG: từ PHỦ ĐỊNH — mạnh với vai ngòi nổ (NEVER, STOP) nhưng lật ngược hẳn lời khẳng định.
_NEG = {"not", "no", "never", "without", "stop", "don't", "doesn't", "isn't", "aren't",
        "won't", "can't", "không", "chưa", "đừng"}
# CHỈ `_NEG` mới bị loại thẳng. Tự chèn "NOT/NEVER" là nói NGƯỢC đối thủ trong khi mọi chữ vẫn
# "của họ" ⇒ tool báo "100% chữ của đối thủ" cho một title phản bác chính bằng chứng — bằng chứng giả.
# `_ASK` thì KHÔNG: "How BEAUTIFUL WOMEN Survive…" chẳng lật ngược gì cả, nó chỉ dựng khung câu hỏi.
# Cắn LIVE 2026-07-30: gộp `_ASK` vào đây làm CHẾT 2/3 kênh — Format "Country Documentary" và
# "Actual Space" có khuôn bắt đầu bằng How/What, nên MỌI ứng viên bị loại và kênh ra title RỖNG.
# Chúng vẫn nằm trong `invented` nên chèn 3 từ hỏi vẫn bị chặn bởi INVENT_MAX — chỉ không loại thẳng.
_FLIP = _NEG
# Kho ngòi nổ chỉ bỏ keo dán + từ hỏi. NEVER/STOP/NO **vẫn vào kho** vì chúng là ngòi nổ THẬT —
# luật ở đây là "không được TỰ CHÈN", không phải "không được dùng". Lấy từ title đối thủ thì cứ dùng.
_WEAK_HOOK = _GLUE | _ASK


KEEP_LO, KEEP_HI = 0.65, 0.92     # giữ 80% ± dung sai; ≥0.98 coi như chép nguyên văn


def keep_ratio(new: str, src: str) -> dict:
    """Giữ lại bao nhiêu % cấu trúc của title gốc — đo bằng difflib trên CHUỖI TỪ.

    Dùng SequenceMatcher chứ không phải giao tập hợp: nó tính cả THỨ TỰ, nên đảo lộn câu mà
    vẫn đủ từ sẽ KHÔNG được coi là giữ cấu trúc. Đúng tinh thần Double Down: giữ khung, xoay
    biến số — không "cải tiến" cú pháp.

    Trả thêm `changed`/`added` để board chỉ rõ ĐỔI ĐÚNG CHỖ NÀO, không chỉ đưa con số.
    """
    import difflib
    import re
    w = lambda t: re.findall(r"[0-9A-Za-zÀ-ỹ']+", (t or ""))   # noqa: E731
    a, b = w(src), w(new)
    if not a or not b:
        return {"ratio": 0.0, "kept": 0, "changed": [], "added": [], "ok": False, "copy": False}
    sm = difflib.SequenceMatcher(None, [x.lower() for x in a], [x.lower() for x in b])
    kept = sum(bl.size for bl in sm.get_matching_blocks())
    ratio = round(kept / len(a), 3)
    changed, added = [], []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag in ("replace", "delete"):
            changed += a[i1:i2]
        if tag in ("replace", "insert"):
            added += b[j1:j2]
    return {"ratio": ratio, "kept": kept, "changed": changed, "added": added,
            "copy": ratio >= 0.98, "ok": KEEP_LO <= ratio <= KEEP_HI}


# Chốt "còn là kết hợp hay đã là tự viết". ĐẾM CHỮ LẠ chứ không lấy % trần: title 6 từ đổi 2 từ
# đã tụt còn 67% trong khi title 15 từ đổi 2 từ vẫn 87% — cùng một hành vi mà bị phạt khác nhau.
INVENT_MAX = 2            # quá 2 chữ không truy được về đâu = LLM đang tự viết câu mới
COVER_MIN = 0.55          # chặn thêm ca title dài mà chữ lạ rải khắp

# Giữ gạch nối TRONG từ ("WARM-HEARTED" là 1 cụm, không phải 2 từ rời) — khác `keep_ratio`,
# nơi cần tách nhỏ để đo cấu trúc. Hai mục đích khác nhau nên hai cách tách khác nhau.
_TOKEN_RE = None


def _norm_words(s: str) -> list[str]:
    global _TOKEN_RE
    if _TOKEN_RE is None:
        import re
        _TOKEN_RE = re.compile(r"[0-9A-Za-zÀ-ỹ']+(?:-[0-9A-Za-zÀ-ỹ']+)*")
    return [w.lower() for w in _TOKEN_RE.findall(s or "")]


def trace_blocks(new: str, pool: list[str]) -> dict:
    """TRUY NGUYÊN title mới về pool title đối thủ, theo CỤM DÀI NHẤT (tham lam).

    Đây là chốt chống bịa cho chính CHỮ trong title (khác 3 chốt kia — chúng soi *lời khai*).
    User chốt 2026-07-29: "mix 3 tiêu đề vào với nhau" → mọi cụm phải tháo ra từ title có thật,
    không phải LLM tự viết câu mới rồi khai bừa là kết hợp.

    Tham lam cụm dài nhất chứ không dò từng từ: cụm càng dài thì càng chứng minh giữ được KHUNG
    của đối thủ. Dò từng từ thì "the/of/and" ở đâu cũng khớp → phủ 100% mà chẳng giữ khung nào.

    Trả: blocks[{text, src, n}] · cover (tỉ lệ từ truy được) · sources (chỉ số title đã dùng)
         · untraced (từ không có trong pool — connector vẫn tính, tầng trên tự lọc).
    """
    nw = _norm_words(new)
    pw = [_norm_words(p) for p in pool]
    if not nw or not any(pw):
        return {"blocks": [], "cover": 0.0, "sources": [], "n_blocks": 0, "untraced": [], "words": len(nw)}
    blocks, untraced, i = [], [], 0
    while i < len(nw):
        best_len, best_src = 0, -1
        for pi, p in enumerate(pw):
            n = 0
            while i + n < len(nw):
                seg = nw[i:i + n + 1]
                if any(p[j:j + len(seg)] == seg for j in range(len(p) - len(seg) + 1)):
                    n += 1
                else:
                    break
            if n > best_len:
                best_len, best_src = n, pi
        if best_len == 0:                                  # từ này không có ở BẤT KỲ title nào
            untraced.append(nw[i])
            blocks.append({"text": nw[i], "src": None, "n": 1})
            i += 1
        else:
            blocks.append({"text": " ".join(nw[i:i + best_len]), "src": best_src, "n": best_len})
            i += best_len
    traced = sum(b["n"] for b in blocks if b["src"] is not None)
    return {"blocks": blocks, "cover": round(traced / len(nw), 3),
            "sources": sorted({b["src"] for b in blocks if b["src"] is not None}),
            "n_blocks": len(blocks), "untraced": untraced, "words": len(nw)}


_OWN_FIELDS = ("topic", "entities", "keywords")     # chủ thể video — KHÔNG lấy beats/desires/promise


def _own_bank(brief: dict | str) -> set[str]:
    """Vốn từ RIÊNG của video này — cửa hợp lệ duy nhất ngoài title đối thủ.

    Chỉ lấy chủ đề + tên riêng + từ khoá. `beats`/`desires`/`promise` là VĂN XUÔI tóm tắt, mọi
    tính từ giật gân đều nằm trong đó → lấy cả brief là chốt chống bịa mất răng.
    Đo thật trên brief FINLAND: cả brief = 66 từ, `secret/stunning/nordic/hidden` LỌT cả 4;
    siết còn topic+entities+keywords = 19 từ, chặn cả 4 mà "Lapland" vẫn qua.
    """
    if not isinstance(brief, dict):
        return set(_norm_words(str(brief or "")))    # kịch bản ngắn chưa nén → không có gì để tách
    parts: list[str] = []
    for k in _OWN_FIELDS:
        v = brief.get(k)
        parts += [str(x) for x in v] if isinstance(v, list) else ([str(v)] if v else [])
    return set(_norm_words(" ".join(parts)))


def trim_to_limit(text: str, pool: list[str], limit: int = 100) -> tuple[str, bool]:
    """Quá 100 ký tự thì CẮT BỚT Ô CUỐI thay vì vứt cả title đi.

    Niche của user có title đối thủ dài 95-100 ký tự; ghép 2 ô vào là tràn ngay. Đo LIVE
    2026-07-29: 3/5 ứng viên chết vì 105-111 ký tự, có lần chết cả 5 → user nhận 0 title mà
    không biết vì sao. Bản ghép vẫn tốt, chỉ thừa đuôi.

    Cắt ĐÚNG BIÊN GIỚI Ô (không cắt giữa cụm, không cắt giữa từ) nên phần giữ lại vẫn truy
    nguyên được 100%. Giữ nguyên hoa/thường của bản gốc. Còn < 5 từ thì thà bỏ.
    """
    if len(text) <= limit or not pool:
        return text, False
    m = trace_blocks(text, pool)
    if not m["blocks"]:
        return text, False
    _norm_words("")                                    # đảm bảo _TOKEN_RE đã khởi tạo
    spans = [x.span() for x in _TOKEN_RE.finditer(text)]
    cut, seen = 0, 0
    for b in m["blocks"]:
        seen += b["n"]
        if seen - 1 >= len(spans):
            break
        end = spans[seen - 1][1]
        if len(text[:end].strip()) <= limit:
            cut = end                                  # lấy tiền tố DÀI NHẤT còn vừa
        else:
            break
    if not cut:
        return text, False
    import re
    out = text[:cut].rstrip(" ,;:-–—&/|·")
    # Cắt xong hay dính từ nối lơ lửng ("…Women and") vì biên ô rơi ngay sau nó → bỏ nốt.
    while True:
        tail = re.search(r"[0-9A-Za-zÀ-ỹ']+\s*$", out)
        if not tail or tail.group(0).strip().lower() not in _GLUE:
            break
        out = out[:tail.start()].rstrip(" ,;:-–—&/|·")
    if len(out.split()) < 5:
        return text, False
    # Cắt xong mà thành ĐÚNG một khúc liền của MỘT title đối thủ thì thà đừng cắt: lúc đó nó không
    # còn là bản ghép nữa mà là title của họ bị cắt ngắn — chốt chép nguyên văn sẽ loại, đúng.
    after = trace_blocks(out, pool)
    if after["n_blocks"] == 1 and after["cover"] == 1.0:
        return text, False
    return out, True


def fix_seams(text: str) -> str:
    """Dọn vết ghép ở chỗ tháo-lắp ô. Việc ĐẾM ĐƯỢC → Python làm, đừng bắt LLM lo.

    Ví dụ thật của user: "...Women and AND WARM-HEARTED GIRLS" — lặp từ nối `and` ở đúng chỗ
    nối hai ô, và chính 4 ký tự thừa đó đẩy title từ 98 lên 102 → vượt hard-gate 100 của YouTube.

    Chỉ gộp từ nối lặp (`_WEAK_HOOK`), KHÔNG đụng từ nội dung: "That That" hiếm nhưng có thể cố ý.
    """
    import re
    out, prev = [], ""
    for tok in re.split(r"(\s+)", (text or "").strip()):
        w = tok.strip()
        if not w:
            out.append(tok)
            continue
        key = w.strip(".,!?—-").lower()
        if key and key == prev and key in _GLUE:           # từ nối lặp ngay sau chính nó
            while out and not out[-1].strip():
                out.pop()
            continue
        prev = key
        out.append(tok)
    s = re.sub(r"\s+", " ", "".join(out)).strip()
    return re.sub(r"\s+([,.!?])", r"\1", s)


def hook_pos(text: str, hook: str) -> int:
    """Ngòi nổ KẾT THÚC ở ký tự thứ mấy. -1 = không tìm thấy trong title (LLM khai sai).

    Đo thật bằng `find`, không tin lời LLM nói: nó hay khai một cụm không có trong title.
    """
    t, h = (text or "").lower(), (hook or "").strip().lower()
    if not h:
        return -1
    i = t.find(h)
    return -1 if i < 0 else i + len(h)


_MAX = 20 + 14 + 10 + 12 + 10 + 8 + 14 + 8 + 6 + 6 + 10 + 10 + 8   # + phủ pool + mix ≥2 nguồn


def score(item: dict) -> dict:
    """Điểm 'khớp pattern + guardrail' (KHÔNG phải CTR). Hard-gate ký tự → score None (loại).

    Ba chốt soi LỜI KHAI, sai cái nào XOÁ field đó (user chốt: "cái nào bịa bỏ hết"):
      · `hook` phải có trong chính title VÀ thuộc `hook_bank` rút từ title đối thủ
      · `from_title` phải là title đối thủ có thật
      · `pattern_used` phải là pattern của Format kênh đang học theo

    Chốt thứ tư soi CHÍNH CHỮ trong title (`trace_blocks`): từng cụm phải tháo ra được từ title
    đối thủ có thật. Phủ < COVER_MIN → LOẠI, vì đó là LLM tự viết chứ không phải kết hợp.
    """
    # Dọn vết ghép TRƯỚC khi đo ký tự: "and AND" thừa 4 ký tự đủ đẩy title qua mốc 100.
    text = fix_seams(item.get("text") or "")
    # ── HAI KHO, HAI VAI (user chốt 2026-07-31) ───────────────────────────────────────
    # `_pool_titles` = title đối thủ CỦA TẬP  → nơi lấy KHUNG GỐC (80%). Bắt buộc.
    # `_ref_titles`  = kho THAM KHẢO của niche (outlier trong Format + báo cáo user dán)
    #                  → CHỈ được góp ô lắp vào (20%), KHÔNG được làm khung.
    # Gộp làm một là mất luôn ý nghĩa "bám chính theo link tập" — title sẽ trôi sang giọng của
    # niche chung. Nối EP trước REF nên chỉ số < n_ep là của tập, ≥ n_ep là kho tham khảo.
    ep_pool = [t for t in (item.get("_pool_titles") or []) if t]
    ref_pool = [t for t in (item.get("_ref_titles") or []) if t and t not in ep_pool]
    raw_pool = ep_pool + ref_pool
    n_ep = len(ep_pool)
    # Tràn 100 thì cắt bớt ô cuối rồi mới phán — vứt luôn là user nhận 0 title (đã cắn LIVE).
    text, trimmed = trim_to_limit(text, raw_pool)
    chars = len(text)
    words = len(text.split())
    if chars == 0 or chars > 100:                         # hard-gate YouTube
        return {**item, "text": text, "chars": chars, "score": None,
                "reject": f"{chars} ký tự — quá 100, cắt bớt ô cuối vẫn không vừa"}
    s = 0
    if item.get("desire"):
        s += 20                                            # đánh trúng desire thật
    if item.get("proof"):
        s += 14                                            # honest, kịch bản deliver
    if item.get("technique"):
        s += 10                                            # có cơ chế rõ
    if 6 <= words <= 10:
        s += 12                                            # PROMISE sweet spot
    if chars <= 60:
        s += 10                                            # hợp feed (mobile ~50-60)
    aw = str(item.get("awareness", ""))
    if aw and "⚠" not in aw:
        s += 8                                             # awareness-fit

    # ── kết hợp từ title đối thủ: LLM khai, Python đối chiếu ──
    hk = (item.get("hook") or "").strip()
    end = hook_pos(text, hk)                               # ngòi nổ có trong chính title không
    bank = [x.lower() for x in (item.get("_hook_bank") or [])]
    bank_ok = (not bank) or (hk.lower() in bank)           # kho rỗng thì không ép, kẻo chặn sạch
    hook_ok = 0 < end <= HOOK_HEAD_CHARS and bank_ok
    if hook_ok:
        s += 14                                            # ngòi nổ thật, đặt ở đầu câu

    # ── TRUY NGUYÊN CHỮ: từng cụm của title mới phải tháo ra từ title đối thủ có thật ──
    # Pool rỗng thì KHÔNG đo (cùng bài học với hook_bank: siết khi không có bằng chứng = chặn sạch).
    mix = trace_blocks(text, raw_pool) if raw_pool else {}
    if mix:
        own = {w for w in (item.get("_own_words") or [])}   # từ có trong kịch bản CỦA USER
        # Chữ HỢP LỆ = của đối thủ + của kịch bản mình + từ nối. Ngoài ba thứ đó mới là bịa.
        # Đừng gate bằng `cover` trần: title 6 từ đổi 2 từ đã tụt còn 67%, chủ thể thật của video
        # (tên nước/nhân vật) không bao giờ có trong title đối thủ → sẽ bị kết tội oan.
        # CHÉP NGUYÊN VĂN — bắt bằng CHÍNH TITLE, không qua lời khai. `keep_ratio` chỉ so với
        # `from_title` LLM tự khai, nên chép title ③ mà khai là lấy từ title ① thì lọt sạch
        # (đã cắn 2026-07-29). Cả title là MỘT đoạn liền của MỘT title đối thủ = chép, kể cả
        # khi chỉ cắt lấy một khúc — đăng lên vẫn là trùng metadata với họ.
        if mix["n_blocks"] == 1 and mix["cover"] == 1.0:
            return {**item, "text": text, "chars": chars, "score": None, "mix": mix,
                    "reject": "chép nguyên một đoạn liền của title đối thủ — không đổi biến số nào"}
        # Từ ĐẢO NGHĨA không có trong pool lẫn kịch bản → loại thẳng, KHÔNG tính vào INVENT_MAX:
        # nó không "thêm chữ" mà lật ngược lời khẳng định của title gốc.
        mix["flipped"] = [w for w in mix["untraced"] if w in _FLIP and w not in own]
        mix["invented"] = [w for w in mix["untraced"]
                           if w not in _WEAK_HOOK and w not in own]
        # BA trạng thái, không phải hai: của đối thủ · của kịch bản mình · bịa. Gộp hai loại sau
        # làm một là board tô đỏ oan đúng chủ thể video (vd "Lapland") — nhìn như lỗi mà không phải.
        _bad = set(mix["invented"]) | set(mix["flipped"])
        for b in mix["blocks"]:
            if b["src"] is None:
                b["own"] = b["text"] not in _bad
            else:
                # Cụm này lấy từ kho TẬP hay kho THAM KHẢO — board phải nói đúng xuất xứ.
                # Không đánh dấu thì chip "100% chữ của đối thủ" thành nửa sự thật: chữ có thật,
                # nhưng là của một video KHÁC niche chứ không phải video đối thủ của tập này.
                b["ref"] = b["src"] >= n_ep
        mix["n_ref_blocks"] = sum(1 for b in mix["blocks"] if b.get("ref"))
        mix["ref_used"] = mix["n_ref_blocks"] > 0
        mix["ep_sources"] = [i for i in mix["sources"] if i < n_ep]
        mix["ref_sources"] = [i - n_ep for i in mix["sources"] if i >= n_ep]
        nw = mix["words"] or 1
        mix["cover_eff"] = round((nw - len(_bad)) / nw, 3)
        if mix["flipped"]:
            return {**item, "text": text, "chars": chars, "score": None, "mix": mix,
                    "reject": "chèn từ đảo nghĩa không có ở title đối thủ lẫn kịch bản — "
                              "title nói ngược hẳn bằng chứng: " + ", ".join(mix["flipped"][:6])}
        if len(mix["invented"]) > INVENT_MAX or mix["cover_eff"] < COVER_MIN:
            return {**item, "text": text, "chars": chars, "score": None, "mix": mix,
                    "reject": "tự viết chứ không kết hợp — bịa "
                              f"{len(mix['invented'])} chữ không có trong title đối thủ lẫn kịch bản: "
                              + ", ".join(mix["invented"][:6])}
        if mix["cover"] >= 0.95:
            s += 10                                         # gần như mọi chữ đều của đối thủ
        if len(mix["sources"]) >= 2:
            s += 8                                          # MIX thật: ghép từ ≥2 title nguồn
        s -= 6 * len(mix["invented"])                       # chữ lạ trong ngưỡng: cho qua nhưng tụt hạng

    # ── KHUNG GỐC do PYTHON SUY, không hỏi LLM (đổi 2026-07-29 sau khi chạy LIVE) ──
    # LLM khai `from_title` là nơi nó lấy CỤM GHÉP, không phải nơi lấy KHUNG. Trên tập FINLAND
    # nó khai ③ trong khi khung thật là ① ⇒ keep_ratio đo nhầm gốc: 0.60 thay vì 0.86, rơi khỏi
    # dải 80/20 và title ĐÚNG bị trừ oan 10 điểm. Khung = title góp CỤM DÀI NHẤT — đo được, khỏi
    # hỏi, và bớt luôn một cửa bịa (LLM không còn field nào để khai sai).
    frame = max((b for b in mix.get("blocks", []) if b["src"] is not None),
                key=lambda b: b["n"], default=None) if mix else None
    # KHUNG PHẢI ĐẾN TỪ VIDEO ĐỐI THỦ CỦA TẬP (user chốt 2026-07-31: "vẫn sử dụng 80/20 bám
    # chính theo link tập đối thủ, kho tham khảo chạy SONG SONG"). Cụm dài nhất chính là khung;
    # nó rơi vào kho tham khảo nghĩa là title đang bám khuôn của một video KHÁC — đúng thứ
    # tách hai kho ra để ngăn. Loại thẳng, nói rõ lý do (không im lặng bỏ).
    if frame is not None and ref_pool and frame["src"] >= n_ep:
        return {**item, "text": text, "chars": chars, "score": None, "mix": mix,
                "reject": "khung gốc lấy từ KHO THAM KHẢO chứ không phải video đối thủ của tập — "
                          "80% phải bám title của tập, kho tham khảo chỉ được góp ô lắp vào"}
    src = raw_pool[frame["src"]] if frame else ""
    src_ok = bool(src)
    if src_ok:
        s += 8                                             # có khung từ title đối thủ thật
    # 1 nguồn = nâng cấp chính title đó; ≥2 nguồn = lắp ráp từ nhiều title.
    method = ("LẮP RÁP" if len(mix.get("sources") or []) >= 2 else "NÂNG CẤP") if src_ok else ""
    # 80/20: giữ khung title gốc, chỉ xoay biến số. Đo bằng difflib nên đảo trật tự không qua được.
    kr = keep_ratio(text, src) if src_ok else {"ratio": 0.0, "kept": 0, "changed": [], "added": [],
                                               "ok": False, "copy": False}
    if kr["copy"]:                                         # chép y hệt title đối thủ → LOẠI THẲNG
        return {**item, "text": text, "chars": chars, "score": None, "keep": kr,
                "reject": "trùng khít title đối thủ"}
    if kr["ok"]:
        s += 10                                            # nằm trong dải 80/20
    pat = (item.get("pattern_used") or "").strip()
    pats = [x.strip().lower() for x in (item.get("_patterns") or []) if x]
    # "KHÔNG CÓ GÌ để đối chiếu" khác hẳn "đã đối chiếu và KHỚP" — đừng gộp làm một.
    # Bản cũ viết `not pats or …` nên kênh chưa gắn Format (pats rỗng) làm MỌI lời khai đều
    # "đạt": board đóng dấu chip xanh "cấu trúc: … ✓" cho công thức LLM tự bịa, và cộng luôn
    # 6 điểm cho bằng chứng không tồn tại. Không đối chiếu được thì XOÁ, đúng luật "cái nào
    # bịa bỏ hết" — chỉ bỏ một dòng bằng chứng, KHÔNG loại title (khác với hook_bank rỗng,
    # chỗ đó ép là chặn sạch kết quả).
    pat_ok = bool(pat) and bool(pats) and pat.lower() in pats
    if pat_ok:
        s += 6                                             # bám cấu trúc Format
    if hk and bank and bank_ok:
        s += 6                                             # từ ngữ lấy đúng từ kho

    # XOÁ HẲN lời khai không kiểm chứng được — hiện "bằng chứng" giả còn tệ hơn không hiện
    if end < 0 or not bank_ok:
        hk = ""
    if not pat_ok:
        pat = ""
    return {"text": text, "chars": chars, "score": max(0, min(96, round(s / _MAX * 96))),
            "desire": item.get("desire", ""), "technique": item.get("technique", ""),
            "awareness": aw, "proof": bool(item.get("proof")),
            "hook": hk, "hook_end": end, "hook_in_head": hook_ok,
            "hook_from_bank": bool(hk) and bool(bank),
            "from_title": src, "from_verified": src_ok, "method": method,
            "pattern_used": pat, "pattern_verified": pat_ok, "keep": kr, "mix": mix,
            "ref_used": bool(mix.get("ref_used")), "trimmed": trimmed}


def generate(brief: dict | str, competitor_titles: list[str], n: int = 3,
             fmt: dict | None = None, spread: bool = False,
             report: dict | None = None, ref_titles: list[str] | None = None,
             ref_patterns: list[str] | None = None) -> list[dict]:
    """`spread`=True: N title cho N kênh khác nhau → xin dư 3 bản dự phòng + lọc trùng mặt chữ.

    `ref_titles` = KHO THAM KHẢO của niche (outlier trong Format + báo cáo user dán). Chạy
    SONG SONG với `competitor_titles`: góp thêm ô để tháo lắp → nhiều biến thể hơn, nhưng
    KHUNG GỐC vẫn phải là title đối thủ của tập (`score` loại thẳng nếu khung rơi vào kho này).
    """
    ref = [t for t in (ref_titles or []) if t and t not in competitor_titles]
    # Xin theo NHU CẦU chứ không phải hằng số: nhóm 1 kênh chỉ cần 1 title mà xin 8 là sinh ra
    # 7 bản để vứt. Đo LIVE 2026-07-30: ~66% ứng viên sống sót, nên xin gấp 3 lần nhu cầu là đủ
    # dư. Trần vẫn là N_ASK để nhóm nhiều kênh không phình.
    n_ask = min(N_ASK, max(4, n * 3))
    raw = generate_raw(brief, competitor_titles, fmt, n_ask, spread, ref, ref_patterns)
    # kèm dữ liệu THẬT để score() đối chiếu lời khai của LLM, không tin suông
    # hook_bank lấy từ CẢ HAI kho: ngòi nổ của niche vẫn là ngòi nổ có thật, chỉ khác chỗ lấy.
    bank = hook_bank(competitor_titles + ref)
    pats = [p.get("pattern", "") for p in ((fmt or {}).get("title_patterns") or []) if p.get("pattern")]
    pats += [p for p in (ref_patterns or []) if p]     # công thức user khai cũng là pattern CÓ THẬT
    # Chủ thể riêng của video này (tên nước/nhân vật/con số) nằm ở kịch bản chứ không ở title đối thủ
    # → phải coi là hợp lệ, nếu không mọi title đúng chủ đề đều bị kết tội bịa.
    own = _own_bank(brief)
    scored = [score({**it, "_pool_titles": competitor_titles, "_ref_titles": ref, "_own_words": own,
                     "_hook_bank": bank, "_patterns": pats}) for it in raw]
    ok = [x for x in scored if x["score"] is not None]
    ok.sort(key=lambda x: -x["score"])
    if spread:
        seen, uniq = set(), []
        for x in ok:                                       # né 2 kênh nhận title trùng nhau
            k = " ".join(x["text"].lower().split())
            if k not in seen:
                seen.add(k)
                uniq.append(x)
        ok = uniq
    # KHÔNG im lặng khi loại: user từng nhận 0 title mà không một chữ giải thích (LIVE 2026-07-29,
    # 5/5 ứng viên chết vì tràn 100 ký tự). Trả qua `report` chứ KHÔNG nhồi item giả vào danh sách —
    # board sẽ vẽ thẻ title rỗng.
    if report is not None:
        report["asked"] = len(scored)
        report["dropped"] = [{"text": x.get("text", "")[:110],
                              "why": x.get("reject") or f"{x.get('chars', 0)} ký tự — quá 100"}
                             for x in scored if x["score"] is None]
    return ok[:n]


if __name__ == "__main__":                                # self-test offline (seed giả)
    REAL = ["What Happens If You Drop 0.125 Grams Of Antimatter?",
            "The Most DANGEROUS Place On Earth",
            "NEVER Charge Your Phone Overnight — Here Is Why",
            "The Most Radioactive Place On Earth"]
    PATS = ["The Most [superlative] [entity] On [place]"]

    # ── KHO NGÒI NỔ rút từ title THẬT, không có từ điển tự nghĩ ──
    bank = hook_bank(REAL)
    low = [x.lower() for x in bank]
    assert "dangerous" in low and "never" in low, bank        # token IN HOA
    assert any(x.startswith("0.125") for x in low), bank      # con số
    assert "place" in low and "most" in low, bank             # từ lặp ≥2 title
    # từ đặc trưng chỉ xuất hiện 1 lần VẪN phải vào kho — nó vẫn là từ CỦA HỌ.
    # (đã cắn: pool 2 video thì gần như không có gì lặp, kho teo lại, xoá oan mọi ngòi nổ)
    assert "radioactive" in low and "antimatter" in low, bank
    assert "the" not in low and "you" not in low, bank        # từ phổ thông bị lọc
    assert low.index("dangerous") < low.index("radioactive"), "IN HOA phải xếp trước từ thường"
    assert hook_bank([]) == [] and hook_bank(["a"]) == []
    # keo dán ngữ pháp không bao giờ bị kết tội bịa — nhưng NOW/NEW vẫn phải là ngòi nổ thật
    for w in ("there's", "we", "his", "then"):
        assert w in _WEAK_HOOK, w
    for w in ("now", "new", "never", "stop", "no"):
        assert w not in _WEAK_HOOK, f"{w} là ngòi nổ THẬT, phải vào kho khi đối thủ có dùng"
    assert "why" in _WEAK_HOOK and "what" in _WEAK_HOOK, "từ hỏi thì yếu, không phải ngòi nổ"

    assert hook_pos("The Most DANGEROUS Cave", "dangerous") == 18   # không phân biệt hoa/thường
    assert hook_pos("abc", "xyz") == -1 and hook_pos("abc", "") == -1

    ok_item = {"text": "The Most DANGEROUS Cave On Earth", "desire": "d", "technique": "t",
               "awareness": "Unaware", "proof": True, "hook": "DANGEROUS",
               "from_title": REAL[1], "method": "NÂNG CẤP", "pattern_used": PATS[0],
               "_hook_bank": bank, "_patterns": PATS, "_pool_titles": REAL,
               # kịch bản của user: chủ thể "cave" là của video này, không có ở title đối thủ
               "_own_words": _norm_words("phóng sự quay trong một cave bỏ hoang")}
    good = score(ok_item)
    assert good["hook"] == "DANGEROUS" and good["hook_from_bank"], good
    assert good["from_title"] == REAL[1] and good["from_verified"], good
    assert good["pattern_used"] == PATS[0] and good["pattern_verified"], good

    # ── BỊA THÌ XOÁ: ngòi nổ tự nghĩ · title nguồn bịa · cấu trúc tự chế ──
    made = score({**ok_item, "text": "The Most SHOCKING Cave On Earth", "hook": "SHOCKING"})
    assert made["hook"] == "" and made["score"] < good["score"], made
    # `from_title` giờ do PYTHON SUY từ cụm dài nhất → LLM khai bừa cũng vô hại, bị bỏ qua thẳng
    liar = score({**ok_item, "from_title": "Title Tôi Bịa Ra", "method": "BỊA"})
    assert liar["from_title"] == REAL[1] and liar["method"] == "NÂNG CẤP", liar
    assert liar["score"] == good["score"], "lời khai sai không được ảnh hưởng tới điểm"
    offp = score({**ok_item, "pattern_used": "Công thức tự chế"})
    assert offp["pattern_used"] == "", offp
    assert liar["text"], "title VẪN GIỮ — chỉ bỏ phần bịa"

    # kho ngòi nổ rỗng → KHÔNG ép (ép là chặn sạch kết quả, đã cắn LIVE)…
    free = score({**ok_item, "_hook_bank": [], "_patterns": [], "_pool_titles": []})
    assert free["hook"] == "DANGEROUS", free
    # …NHƯNG chưa gắn Format thì `pattern_used` không có gì để đối chiếu ⇒ phải XOÁ, không
    # được để board đóng dấu ✓ xanh cho công thức LLM tự khai. Đây chỉ là bỏ một dòng bằng
    # chứng, title vẫn giữ nguyên.
    assert free["pattern_used"] == "" and not free["pattern_verified"], free
    assert free["text"] == ok_item["text"], "title KHÔNG được loại chỉ vì thiếu Format"
    assert free["score"] < good["score"], "bằng chứng không kiểm được thì đừng cộng điểm"

    # hard-gate >100 ký tự
    assert score({**ok_item, "text": "x" * 120})["score"] is None

    # ── prompt: có luật kết hợp, KHÔNG còn tầng SOP ──
    sysm = _sys(N_ASK, False)
    # NÂNG CẤP/LẮP RÁP đã BỎ khỏi prompt — Python suy từ số nguồn, không hỏi LLM nữa
    assert "from_title" not in sysm and "NÂNG CẤP" not in sysm, "còn hỏi field Python tự suy được"
    for must in ("hook_bank", "CẤM tự nghĩ từ mới",
                 "niche_format.patterns", "competitor_titles_reference"):
        assert must in sysm, must
    for gone in ("GÓC TÂM LÝ", "CCN", "Cây cầu nối", "thumbnail", "classic"):
        assert gone not in sysm, f"còn sót tầng SOP: {gone}"

    # ── generate: 1 bộ, bơm kho + pattern xuống chấm điểm ──
    seen = []
    llm.set_hook(lambda sy, u: (seen.append(u), json.dumps([ok_item, {**ok_item, "hook": "NEVER",
                 "text": "NEVER Enter The Most Radioactive Cave"}]))[1])
    res = generate("kịch bản...", REAL, n=3, fmt={"title_patterns": [{"pattern": PATS[0]}]})
    llm.set_hook(None)
    assert "hook_bank" in seen[-1], seen[-1][:200]
    assert len(res) == 2 and all(r["from_verified"] for r in res), res
    assert all("mode" not in r and "angle" not in r for r in res), "đã bỏ tầng SOP"

    # ── 80/20: giữ khung title gốc, chỉ xoay biến số ──
    SRC = "The Most Radioactive Place On Earth"
    k = keep_ratio("The Most Radioactive Cave On Earth", SRC)       # đổi 1/7 từ
    assert k["ratio"] > 0.8 and k["ok"] and not k["copy"], k
    assert k["changed"] == ["Place"] and k["added"] == ["Cave"], k  # chỉ rõ đổi chỗ nào

    same = keep_ratio(SRC, SRC)
    assert same["copy"] and not same["ok"], same                    # chép y hệt
    rewrite = keep_ratio("A Completely Different Sentence About Nuclear Waste", SRC)
    assert rewrite["ratio"] < KEEP_LO and not rewrite["ok"], rewrite  # viết lại quá nhiều
    # đảo trật tự mà đủ từ → KHÔNG được tính là giữ cấu trúc (difflib có thứ tự)
    shuffled = keep_ratio("Earth On Place Radioactive Most The", SRC)
    assert shuffled["ratio"] < same["ratio"], (shuffled["ratio"], same["ratio"])
    assert keep_ratio("", SRC)["ratio"] == 0.0 and keep_ratio("x", "")["ratio"] == 0.0

    in_band = score({**ok_item, "text": "The Most DANGEROUS Cave On Earth", "from_title": SRC})
    # text trùng khít 1 title trong pool → CHÉP, dù LLM khai nguồn là title khác
    assert score({**ok_item, "text": REAL[1], "from_title": SRC})["score"] is None
    too_far = score({**ok_item, "text": "A Wholly New Sentence With DANGEROUS Somewhere Inside It",
                     "from_title": SRC})
    assert in_band["keep"]["ok"], in_band["keep"]
    # Viết lại quá tay giờ bị chặn ở tầng CAO HƠN: chữ không truy được về đâu là loại thẳng,
    # không đợi keep_ratio phán. Chốt CHỮ mạnh hơn chốt TỈ LỆ nên nó bắt trước.
    assert too_far["score"] is None and "bịa" in too_far["reject"], too_far

    # CHÉP Y HỆT title đối thủ → LOẠI THẲNG, không phải chỉ trừ điểm
    copied = score({**ok_item, "text": SRC, "from_title": SRC})
    assert copied["score"] is None and copied["reject"], copied
    llm.set_hook(lambda sy, u: json.dumps([{**ok_item, "text": SRC, "from_title": SRC}]))
    assert generate("kb", REAL, n=3) == [], "title chép y hệt phải bị loại khỏi kết quả"
    llm.set_hook(None)

    assert "80/20" in _sys(N_ASK, False) and "GIỮ NGUYÊN ~80%" in _sys(N_ASK, False)

    # ── TRÀN 100 KÝ TỰ THÌ CẮT Ô CUỐI, không vứt cả title (đã cắn LIVE: user nhận 0 title) ──
    LONG = ["Life in FINLAND! - HAPPIEST Country on Earth with EXTREMELY BEAUTIFUL Women and PRISTINE NATURE",
            "Life In FINLAND - The Country of EXTREMELY BEAUTIFUL WOMEN and PRISTINE NATURE - Finland People Life",
            "Life in FINLAND in 2025 - A PARADISE OF EXTREMELY BEAUTIFUL AND WARM-HEARTED GIRLS [UNCENSORED]"]
    # ca THẬT của user, 105 ký tự
    OVER = "Life in FINLAND! - PARADISE of EXTREMELY BEAUTIFUL Women, PRISTINE NATURE & the HAPPIEST Country on Earth"
    assert len(OVER) > 100, len(OVER)
    cut, did = trim_to_limit(OVER, LONG)
    assert did and len(cut) <= 100, (did, len(cut), cut)
    assert OVER.startswith(cut), cut                        # chỉ cắt đuôi, không sửa chữ nào
    assert cut.split()[-1].lower() not in _GLUE, cut         # không để từ nối lơ lửng cuối câu
    assert trace_blocks(cut, LONG)["cover"] == 1.0, cut      # phần giữ lại vẫn truy nguyên 100%
    assert trim_to_limit("ngắn", LONG) == ("ngắn", False)
    assert trim_to_limit(OVER, []) == (OVER, False)         # không có pool thì không đoán mò
    assert len(trace_blocks(cut, LONG)["sources"]) >= 2, cut   # cắt xong VẪN là bản ghép
    # cắt xong mà thành khúc liền của MỘT title → thà đừng cắt (để chốt chép nguyên văn xử)
    PRE = "Life in FINLAND! - HAPPIEST Country on Earth with EXTREMELY BEAUTIFUL and WARM-HEARTED GIRLS [UNCENSORED]"
    assert trim_to_limit(PRE, LONG) == (PRE, False), trim_to_limit(PRE, LONG)
    long_item = {"desire": "d", "technique": "t", "awareness": "Unaware", "proof": True,
                 "hook": "", "_pool_titles": LONG, "_hook_bank": [], "_patterns": [], "_own_words": []}
    sc = score({**long_item, "text": OVER})
    assert sc["score"] is not None and sc["chars"] <= 100 and sc["trimmed"], sc

    # KHÔNG im lặng: bao nhiêu bản bị loại và vì sao
    rep: dict = {}
    llm.set_hook(lambda sy, u: json.dumps([{"text": "x" * 130, "desire": "d", "technique": "t",
                                            "awareness": "Unaware", "proof": True}]))
    got = generate("kb", LONG, n=3, report=rep)
    llm.set_hook(None)
    assert got == [] and rep["asked"] == 1 and len(rep["dropped"]) == 1, (got, rep)
    assert "100" in rep["dropped"][0]["why"], rep["dropped"]

    # ── MIX & MATCH CẤP CỤM: chạy trên chính ví dụ FINLAND user đưa 2026-07-29 ──
    FI = ["Life in FINLAND! - HAPPIEST Country on Earth with EXTREMELY BEAUTIFUL Women and PRISTINE NATURE",
          "Life in FINLAND in 2025 - A PARADISE OF EXTREMELY BEAUTIFUL AND WARM-HEARTED GIRLS [UNCENSORED]",
          "Life In FINLAND - The Country of EXTREMELY BEAUTIFUL WOMEN and PRISTINE NATURE - Finland People Life"]

    # dọn vết ghép: từ nối lặp bị gộp, từ nội dung KHÔNG bị đụng
    dirty = "Life in FINLAND! - HAPPIEST Country on Earth with EXTREMELY BEAUTIFUL Women and AND WARM-HEARTED GIRLS"
    clean = fix_seams(dirty)
    assert len(dirty) == 102 and len(clean) == 98, (len(dirty), len(clean))   # 4 ký tự thừa = vượt gate
    assert "and AND" not in clean and "WARM-HEARTED GIRLS" in clean, clean
    assert fix_seams("New York New York") == "New York New York"             # từ nội dung giữ nguyên
    assert fix_seams("A   b") == "A b" and fix_seams("") == ""

    # truy nguyên: mix của user = 100% phủ, 2 nguồn, ít cụm (giữ được khung dài)
    mx = trace_blocks(clean, FI)
    assert mx["cover"] == 1.0 and mx["sources"] == [0, 1] and mx["n_blocks"] == 2, mx
    assert mx["blocks"][-1]["text"] == "warm-hearted girls", mx["blocks"]     # gạch nối giữ nguyên cụm

    # LLM tự viết câu mới → phủ tụt, chỉ đúng tên từng từ bịa
    fake = trace_blocks("Life in FINLAND! - The SECRET Country of STUNNING Nordic Girls and Hidden Lakes", FI)
    assert set(fake["untraced"]) == {"secret", "stunning", "nordic", "hidden", "lakes"}, fake["untraced"]
    assert len(fake["untraced"]) > INVENT_MAX and fake["cover"] < 0.7, fake

    # chép nguyên 1 title → phủ 100% nhưng CHỈ 1 nguồn, 1 cụm → nhận ra là chép
    cp = trace_blocks(FI[2], FI)
    assert cp["cover"] == 1.0 and len(cp["sources"]) == 1 and cp["n_blocks"] == 1, cp

    fi_item = {"desire": "d", "technique": "t", "awareness": "Unaware", "proof": True,
               "hook": "", "from_title": FI[0], "method": "LẮP RÁP",
               "_pool_titles": FI, "_hook_bank": [], "_patterns": []}
    mixed = score({**fi_item, "text": dirty})                     # đưa bản LỖI vào
    assert mixed["chars"] == 98 and mixed["score"] is not None, mixed   # tự dọn rồi mới đo → lọt gate
    assert mixed["mix"]["cover"] == 1.0 and mixed["mix"]["invented"] == [], mixed["mix"]
    one_src = score({**fi_item, "text": "Life in FINLAND! - HAPPIEST Country on Earth with PRISTINE NATURE"})
    assert mixed["score"] > one_src["score"], "ghép ≥2 nguồn phải hơn biến thể 1 nguồn"

    # tự viết mới → LOẠI THẲNG kèm lý do đọc được
    made_up = score({**fi_item, "text": "Life in FINLAND! - The SECRET Country of STUNNING Nordic Girls"})
    assert made_up["score"] is None and "secret" in made_up["reject"], made_up   # gọi tên chữ bịa

    # chủ thể riêng của video (có trong KỊCH BẢN, không có ở title đối thủ) KHÔNG bị kết tội bịa
    own_ok = score({**fi_item, "_own_words": _norm_words("kịch bản quay ở Lapland mùa đông"),
                    "text": "Life in FINLAND! - HAPPIEST Country on Earth with EXTREMELY BEAUTIFUL Lapland Women"})
    assert own_ok["score"] is not None and own_ok["mix"]["invented"] == [], own_ok["mix"]
    lap = [b for b in own_ok["mix"]["blocks"] if b["src"] is None]
    assert lap and lap[0]["own"] is True, lap        # board phải tô "của kịch bản", KHÔNG tô đỏ bịa
    bia = [b for b in score({**fi_item, "text": "Life in FINLAND! - HAPPIEST Country on Earth with "
                             "EXTREMELY BEAUTIFUL Nordic Women"})["mix"]["blocks"] if b["src"] is None]
    assert bia and bia[0]["own"] is False, bia

    # Vốn từ riêng CHỈ lấy chủ thể, không lấy văn xuôi tóm tắt — kẻo chốt chống bịa mất răng
    BR = {"topic": "Cuộc sống ở Phần Lan", "entities": ["Finland", "Lapland"],
          "keywords": ["life in finland"], "desires": ["tò mò"],
          "beats": ["Cảnh hồ stunning, một hidden village, cô gái kể secret của nordic"],
          "promise": "Bạn sẽ thấy một Phần Lan rất khác"}
    ob = _own_bank(BR)
    assert "lapland" in ob and "finland" in ob, ob                  # chủ thể: qua
    for w in ("stunning", "hidden", "secret", "nordic"):
        assert w not in ob, f"{w} lọt từ beats/desires → chốt chống bịa mất răng"
    assert "lapland" in _own_bank("kịch bản thô nhắc Lapland")      # chưa nén thì lấy cả

    # ── Từ ĐẢO NGHĨA: LLM chèn "NOT"/"Why" là nói NGƯỢC đối thủ, mà chữ nào cũng "của họ" ──
    # (phản biện 2026-07-29 bắt được: cover_eff=1.0, invented=[], lọt sạch với score 55)
    for t in ("Why Life in FINLAND is NOT the HAPPIEST Country on Earth",
              "Life in FINLAND! - NOT the HAPPIEST Country on Earth, NOT EXTREMELY BEAUTIFUL Women"):
        r = score({**fi_item, "text": t})
        assert r["score"] is None and r["mix"]["flipped"], (t, r.get("mix"))
    assert "not" in _FLIP and "never" in _FLIP and "the" in _GLUE, "ba tập phải tách bạch"
    # Từ HỎI không lật ngược gì → KHÔNG được loại thẳng. Gộp vào _FLIP đã làm chết 2/3 kênh LIVE
    # vì Format "Country Documentary"/"Actual Space" có khuôn bắt đầu bằng How/What.
    for w in ("how", "what", "why", "which", "when"):
        assert w not in _FLIP, f"{w} là từ hỏi, không phải từ đảo nghĩa"
        assert w in _WEAK_HOOK, f"{w} vẫn phải bị lọc khỏi kho ngòi nổ"
    assert not (_GLUE & _FLIP), "một từ không thể vừa là keo dán vừa đảo nghĩa"
    assert "never" not in _WEAK_HOOK and "never" in _NEG, "NEVER: vào kho được, tự chèn thì không"
    # từ đảo nghĩa CÓ trong title đối thủ thì dùng thoải mái — chỉ cấm TỰ CHÈN
    okflip = score({**fi_item, "_pool_titles": FI + ["NEVER Visit FINLAND in Winter"],
                    "text": "NEVER Visit FINLAND - The Country of EXTREMELY BEAUTIFUL WOMEN"})
    assert okflip["score"] is not None, okflip

    # ── HAI KHO: kho TẬP giữ khung, kho THAM KHẢO chỉ được góp ô (user chốt 2026-07-31) ──
    REF = ["Life in NORWAY - The RICHEST Country on Earth with SPECTACULAR Fjords",
           "Inside JAPAN - A Land of ANCIENT Temples and MODERN Cities"]
    ref_item = {**fi_item, "_ref_titles": REF}

    # ô "SPECTACULAR Fjords" lấy từ kho tham khảo, KHUNG vẫn là title ① của tập → HỢP LỆ
    lap = score({**ref_item,
                 "text": "Life in FINLAND! - HAPPIEST Country on Earth with SPECTACULAR Fjords"})
    assert lap["score"] is not None, lap
    assert lap["ref_used"] is True and lap["mix"]["ref_sources"] == [0], lap["mix"]
    assert lap["from_title"] in FI, "khung phải là title CỦA TẬP"
    # CÙNG title đó mà KHÔNG có kho tham khảo: 2 chữ kia thành "bịa" → trừ điểm nặng.
    # (đúng 2 chữ nên chạm ngưỡng INVENT_MAX chứ chưa vượt ⇒ chưa bị loại, chỉ tụt hạng)
    no_bank = score({**fi_item,
                     "text": "Life in FINLAND! - HAPPIEST Country on Earth with SPECTACULAR Fjords"})
    assert no_bank["mix"]["invented"] == ["spectacular", "fjords"], no_bank["mix"]
    assert lap["mix"]["invented"] == [], lap["mix"]           # có kho → truy nguyên được, hết bịa
    assert lap["score"] > no_bank["score"], (lap["score"], no_bank["score"])
    # thêm 1 chữ lạ nữa là VƯỢT ngưỡng → lúc đó kho tham khảo mới là ranh giới sống/chết
    over = "Life in FINLAND! - HAPPIEST Country with SPECTACULAR ANCIENT Fjords"
    assert score({**fi_item, "text": over})["score"] is None                 # không kho → loại
    assert score({**ref_item, "text": over})["score"] is not None            # có kho → sống

    # lấy nguyên KHUNG của title trong kho tham khảo → LOẠI, dù mọi chữ đều có thật
    borrowed = score({**ref_item,
                      "text": "Life in NORWAY - The RICHEST Country on Earth with PRISTINE NATURE"})
    assert borrowed["score"] is None and "KHO THAM KHẢO" in borrowed["reject"], borrowed

    # kho tham khảo TRÙNG title của tập thì bỏ, không tự đẻ nguồn thứ hai giả
    dup_ref = score({**fi_item, "_ref_titles": [FI[0]], "text": dirty})
    assert not dup_ref["mix"].get("ref_used"), dup_ref["mix"]

    # prompt chỉ nhắc kho tham khảo KHI CÓ, và phải nói rõ khung vẫn lấy từ tập
    assert "niche_slots" not in _sys(4, False, False)
    assert "niche_slots" in _sys(4, False, True)
    assert "KHUNG GỐC vẫn PHẢI" in _sys(4, False, True)

    # ── KHO gửi cho LLM là Ô RỜI, KHÔNG phải title nguyên vẹn (2026-08-02) ──────────
    # Đo LIVE: gửi nguyên title thì 85% ứng viên bị loại vì "khung lấy từ kho tham khảo",
    # và 1/3 lần chạy có kênh KHÔNG ra title nào.
    REF = ["Launched in 1977: Where is Voyager 1 Right Now? (The Loneliest Object)",
           "An Epic Journey Around The Milky Way | Space Documentary 2024"]
    sl = slots_from(REF)
    assert sl, "phải cắt ra được ô"
    for x in sl:
        assert x not in REF, f"ô KHÔNG được bằng cả title: {x!r}"
        assert SLOT_MIN_W <= len(x.split()) <= SLOT_MAX_W, x
    assert "The Loneliest Object" in sl and "Space Documentary 2024" in sl, sl
    # ĐAN XEN: ô của hai title phải nằm xen kẽ, không xếp liền theo từng title — nếu liền thì
    # LLM nối 2 ô kề là dựng lại nguyên khung (đo hỏng lần đầu đúng vì lỗi này).
    src = {x: (0 if x in REF[0] else 1) for x in sl}
    assert len({src[sl[0]], src[sl[1]]}) == 2, f"2 ô đầu phải từ 2 title khác nhau: {sl[:2]}"
    # bỏ trùng, không phân biệt hoa/thường
    assert len(slots_from(REF + [r.upper() for r in REF])) == len(sl)
    assert slots_from([]) == [] and slots_from(["", None]) == []
    assert len(slots_from(REF, cap=3)) == 3, "phải tôn trọng trần"

    # payload thật sự gửi Ô, và TUYỆT ĐỐI không gửi title kho nguyên vẹn
    sent2 = {}
    llm.set_hook(lambda sy, u: sent2.update(user=u) or "[]")
    generate_raw("kb", FI, None, 4, False, REF)
    llm.set_hook(None)
    import json as _js0
    _pp = _js0.loads(sent2["user"])
    assert "niche_slots" in _pp and "niche_title_bank" not in _pp, list(_pp)
    for t in REF:
        assert t not in _pp["niche_slots"], "title kho NGUYÊN VẸN lọt vào payload"
        assert t not in _pp["competitor_titles_reference"]

    # ── CÔNG THỨC niche: vào PROMPT, TUYỆT ĐỐI không vào kho truy nguyên ──
    FORM = "{NAME} in {CAPS}! - {NAME} of {CAPS}"
    sent = {}
    llm.set_hook(lambda sy, u: sent.update(sys=sy, user=u) or "[]")
    generate_raw("kb", FI, None, 4, False, ["A Real Ref Title"], [FORM])
    llm.set_hook(None)
    assert FORM in sent["user"] and "niche_title_forms" in sent["user"], sent["user"][:300]
    assert "chỗ giữ chỗ" in sent["sys"], "prompt phải giải thích {NAME}/{CAPS} là khuôn"
    # công thức KHÔNG được nằm trong danh sách title dùng để truy nguyên
    import json as _js
    _p = _js.loads(sent["user"])
    assert FORM not in _p.get("niche_slots", []), "CÔNG THỨC lọt vào kho ô"
    assert FORM not in _p.get("competitor_titles_reference", []), _p["competitor_titles_reference"]
    # điền chữ BỊA vào khuôn vẫn bị loại — khuôn không phải giấy phép bịa
    faked = score({**fi_item, "_ref_titles": ["A Real Ref Title"],
                   "text": "Life in FINLAND! - SECRET Land of STUNNING Hidden Nordic Girls"})
    assert faked["score"] is None, faked
    # `pattern_used` khai đúng công thức user khai → được tính là có đối chiếu
    okpat = score({**fi_item, "_patterns": [FORM], "pattern_used": FORM, "text": dirty})
    assert okpat["pattern_verified"] and okpat["pattern_used"] == FORM, okpat

    # ── CHÉP NGUYÊN VĂN bắt bằng chính title, không qua lời khai from_title ──
    stolen = score({**fi_item, "text": FI[2], "from_title": FI[0]})   # chép ③, khai là lấy từ ①
    assert stolen["score"] is None and "chép nguyên" in stolen["reject"], stolen
    cut = score({**fi_item, "text": "Life in FINLAND! - HAPPIEST Country on Earth with EXTREMELY BEAUTIFUL Women"})
    assert cut["score"] is None, "cắt lấy khúc đầu title đối thủ vẫn là trùng metadata"

    # pool rỗng → KHÔNG đo, tránh chặn sạch (cùng bài học với hook_bank)
    assert score({**fi_item, "_pool_titles": [], "text": "Bất Kỳ Title Nào"})["score"] is not None

    for must in ("tháo lắp được", "LẤY TỪ MỘT TITLE KHÁC", "truy nguyên từng cụm"):
        assert must in _sys(N_ASK, False), must

    print("titles.py self-test OK - mix cap cum tu nhieu title, truy nguyen tung cum, tu don vet ghep")
