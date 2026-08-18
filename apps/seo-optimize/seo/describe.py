"""Description stage — fill Profile skeleton từ kịch bản + chapters(SRT). Theo description-definition.md.

LLM: sinh hook + summary (ngôn ngữ nội dung, keyword trong 125 đầu) + đặt tiêu đề chapter.
Python: parse SRT (timestamp thật), ráp theo skeleton, validate. Block cố định (link/CTA) KHÔNG ở
đây — nhập tay lúc export (Channel). LLM không sáng tác link.
"""
from __future__ import annotations

import json
import re

from . import chapters, digest, llm

# 1 call duy nhất cho cả hook/summary/chapter (trước là 2 call → tốn thêm 1 lượt system prompt).
# Tách 3 mảnh: phần nào user tự đưa thì KHÔNG ghép mảnh đó vào prompt. Để nguyên câu dặn
# "viết hook" trong khi đã có hook của user là vừa tốn token vừa dụ model trả field thừa.
_CORE = (
    "Bạn viết Description YouTube tối ưu SEO. " + llm.OUTPUT_LANG_RULE +
    " Đan related terms tự nhiên, KHÔNG keyword-stuffing. "
)
# ĐỘ DÀI KHÔNG CỐ ĐỊNH — bám số đo THẬT của đối thủ mà kênh đó học (user chốt 2026-07-30: "tuỳ biến").
# `niche_format` đã đo sẵn `description.blocks[].chars` từ video outlier thật, và MỖI KÊNH học một
# đối thủ khác nhau nên mục tiêu khác nhau: Amazing Global Discoveries SUMMARY 900 ký tự, Country
# Documentary 420, Actual Space 200. Một câu "2-4 câu" dùng chung là ép cả ba về một khuôn — và đó
# cũng là lý do description GLM ra ngắn đều nhau (432-690) bất kể kênh nào.
# Nhịp câu ĐO THẬT sau khi thêm lệnh "mỗi câu ~N từ" (LIVE 2026-07-31, GLM-5.2, 9 mẫu):
# ~80 ký tự/câu ở CẢ BA mục tiêu 200/300/900 — đều đặn, khác hẳn 111/137/149 hồi chỉ ra lệnh
# bằng số câu. Chính sự ĐỀU ĐẶN đó mới là cái lệnh "số từ" mua được.
#
# ĐỪNG tưởng con số "số từ" là một cái núm chỉnh: nâng 17 → 22 từ/câu mà output gần như đứng yên
# (148→168, 252→246, 660→706). Model viết ~80 ký tự/câu bất kể xin bao nhiêu từ. Cần điều khiển
# THẬT chỉ còn SỐ CÂU, nên CPS phải bằng nhịp thật đó chứ không phải nhịp mình mong muốn.
LONG_TARGET = 600    # từ mốc này trở lên: giữ luật cũ (đo được -2%, đừng đụng vào cái đang đúng)
CPS_LONG = 110       # nhịp câu khi KHÔNG ra lệnh số từ (model tự viết câu dài)
CPS_SHORT = 80       # nhịp câu khi CÓ ra lệnh số từ — thực đo, không phải mong muốn
CPW = 6              # ký tự/từ kể dấu cách (tiếng Anh) — đổi CPS sang số TỪ cho dễ đếm
LEN_TOL = 1.15       # quá ngưỡng này mới cắt; dưới nữa thì thà để nguyên còn hơn cụt ý
LEN_FLOOR = 0.6      # cắt xong mà ngắn hơn ngần này so với mục tiêu thì KHÔNG cắt


def _sent_plan(target: int) -> tuple[int, int]:
    """Mục tiêu ký tự → (số câu, số từ mỗi câu). `w == 0` nghĩa là ĐỪNG ra lệnh số từ.

    Bốn cấu hình đo LIVE trên GLM-5.2 (3 mẫu mỗi cấu hình, dao động ±4-9%):

        cấu hình                     200         300         900
        chỉ số câu, CPS=110      273 (+36%)  448 (+49%)  886 ( -2%)
        + số từ,    CPS=100      148 (-26%)  252 (-16%)  660 (-27%)
        + số từ,    CPS=100 (22) 168 (-16%)  246 (-18%)  706 (-22%)
        + số từ,    CPS=80       151 (-24%)  265 (-12%)  713 (-21%)

    Đọc ra hai điều, cả hai đều phản trực giác:
      · Lệnh "mỗi câu ~N từ" CHỮA bản ngắn (+49% → -12%) nhưng LÀM HỎNG bản dài (-2% → -21%):
        nó ép câu ngắn lại ở MỌI mức, mà bản dài vốn đã đúng.
      · Cả "số câu" lẫn "số từ" đều KHÔNG phải núm chỉnh tuyến tính — nâng 17→22 từ output gần
        như đứng yên (148→168); 900 xin 9 câu ra 660, xin 11 câu ra 713. Model có sẵn lượng ý
        muốn nói; ta chỉ nắn được nó, không đặt được nó.

    Nên KHÔNG có cấu hình đơn nào thắng cả ba → chia ngưỡng: bản dài giữ luật cũ (đang đúng,
    đừng đụng), bản ngắn mới dùng lệnh số từ.

    Giới hạn thật, không hứa quá: một câu ~80 ký tự, nên ở mục tiêu 200 thì MỘT câu đã là 40%
    mục tiêu — không cách nào bám sát hơn ~±20% bằng cách ra lệnh. `fit_len` chỉ chặn phía vượt.
    """
    target = max(1, int(target))
    if target >= LONG_TARGET:
        return max(1, round(target / CPS_LONG)), 0         # bản dài: chỉ số câu, đừng ép từ
    n = max(1, round(target / CPS_SHORT))
    return n, max(6, round(target / n / CPW))


def fit_len(text: str, target: int) -> tuple[str, bool]:
    """Cắt về mục tiêu ĐÚNG BIÊN CÂU. Trả (text, đã_cắt).

    Chốt cuối cùng sau prompt — prompt kéo gần được nhưng không đảm bảo. Ba hàng rào để việc
    cắt không tệ hơn việc vượt:
      · chỉ cắt khi vượt quá `LEN_TOL` (dư vài ký tự thì kệ, cắt là mất nguyên một câu)
      · KHÔNG BAO GIỜ cắt giữa câu — chỉ bỏ trọn câu ở cuối
      · giữ lại ít nhất 1 câu, và không để tụt dưới `LEN_FLOOR` × mục tiêu (một câu 400 ký tự
        cho mục tiêu 200 thì thà để nguyên còn hơn trả về đoạn cụt)
    """
    text = (text or "").strip()
    if not text or target <= 0 or len(text) <= target * LEN_TOL:
        return text, False
    sents = re.findall(r"[^.!?]+(?:[.!?]+|$)", text)
    keep, total = [], 0
    for s in sents:
        if keep and total + len(s) > target * LEN_TOL:
            break
        keep.append(s)
        total += len(s)
    cut = "".join(keep).strip()
    if not cut or len(cut) < target * LEN_FLOOR:
        return text, False                                 # cắt xong thành đoạn cụt → để nguyên
    # Cắt chỉ được phép khi nó kéo GẦN mục tiêu hơn. Bản đầu cắt hễ vượt ngưỡng, và cắn ngay ở
    # lần chạy LIVE đầu tiên: mục tiêu 200 bị cắt còn 139 (-30%) trong khi để nguyên chỉ ~+25%.
    # Bỏ một câu là bước nhảy ~80 ký tự, ở mục tiêu nhỏ thì nhảy qua luôn phía bên kia.
    if abs(len(cut) - target) >= abs(len(text) - target):
        return text, False
    return cut, len(cut) < len(text)


def _len_rule(channels: list[dict] | None) -> str:
    """Ra lệnh độ dài bằng CON SỐ ĐẶT THẲNG TRONG PROMPT, không chỉ nhét vào payload.

    Bản đầu chỉ để `do_dai` trong JSON input rồi dặn "bám sát ±20%" — đo LIVE 2026-07-30 thì model
    phớt lờ: kênh đặt 300 ký tự viết ra 1440. Nêu đích danh "bản k ≈ N ký tự" ngay trong system
    prompt thì model mới bám, vì nó đọc yêu cầu ở đó chứ không suy từ field lẻ trong input.
    """
    want = [(i, (c or {}).get("len") or {}) for i, c in enumerate(channels or [], 1)]
    want = [(i, d) for i, d in want if d.get("summary")]
    if not want:
        return ""
    # Ra lệnh bằng SỐ CÂU + SỐ TỪ MỖI CÂU, không bằng số ký tự: đo LIVE 2026-07-30 thì GLM đếm ký
    # tự rất kém — đặt 900 viết ra 1617, đặt 300 viết ra 628.
    #
    # Chỉ ra "số câu" thôi VẪN TRẬT ở mục tiêu ngắn, vì nhịp câu KHÔNG cố định: model có sẵn một
    # lượng ý muốn nói, cho ít câu thì nó nhồi câu dài ra. Đo lại chính output cũ:
    #     900 → 8 câu → 886 ký tự → 111 ký tự/câu   (khớp giả định 110)
    #     300 → 3 câu → 448 ký tự → 149 ký tự/câu   (vượt 49%)
    #     200 → 2 câu → 273 ký tự → 137 ký tự/câu   (vượt 37%)
    # Nên phải chốt luôn ĐỘ DÀI TỪNG CÂU. Dùng đơn vị TỪ (~6 ký tự/từ kể dấu cách) vì model đếm
    # từ tốt hơn hẳn đếm ký tự. `_sent_plan` chia mục tiêu ra rồi nói thẳng cả hai con số.
    parts = "; ".join(
        f"bản {i}: ĐÚNG {n} câu" + (f", mỗi câu ~{w} từ" if w else "")
        + f" (tổng ~{d['summary']} ký tự)"
        for i, d, (n, w) in ((i, d, _sent_plan(d["summary"])) for i, d in want))
    # Câu dặn "đếm số từ" chỉ được xuất hiện khi CÓ bản nào bị ra lệnh số từ — dặn suông cho
    # bản dài là chính thứ kéo nó tụt 20%.
    say_w = any(_sent_plan(d["summary"])[1] for _, d in want)
    mx = max(d["summary"] for _, d in want)
    return ("ĐỘ DÀI SUMMARY LÀ RÀNG BUỘC CỨNG, mỗi bản MỘT ĐỘ DÀI RIÊNG (đo từ chính kênh đối thủ "
            f"mà kênh đó học): {parts}. "
            "ĐẾM SỐ CÂU trước khi trả — đúng số câu là đúng độ dài. "
            # Câu dặn "viết câu ngắn" phải KHOANH ĐÚNG những bản có ghi số từ. Prompt dùng chung
            # cho mọi bản, nên dặn suông là bản dài cũng co câu lại — chính thứ kéo nó tụt 20%.
            + ("Bản nào CÓ ghi \"mỗi câu ~N từ\" thì đếm cả số từ và viết câu NGẮN THẬT (thà bỏ "
               "bớt ý còn hơn nhồi thêm mệnh đề); bản KHÔNG ghi số từ thì viết câu dài bình "
               "thường. " if say_w else "")
            +
            f"TUYỆT ĐỐI không bản nào vượt {round(mx * 1.3)} ký tự. "
            "KHÔNG viết mọi bản dài xấp xỉ nhau. ")


# ══ NGÔN NGỮ ĐÍCH CỦA KÊNH (06/08/2026) ══
# `llm.OUTPUT_LANG_RULE` chỉ bám NGÔN NGỮ KỊCH BẢN — đúng cho title/tag vì hai thứ đó lắp từ
# CỤM CHỮ THẬT của đúng thị trường (niche_slots/pool đối thủ đã ở sẵn ngôn ngữ thị trường,
# xem titles.py) nên tình cờ ra đúng dù kịch bản là bản DÙNG CHUNG (thường viết tiếng Anh cho
# nhiều kênh nhiều thị trường). DESCRIPTION không có cơ chế lắp-từ-kho tương đương — nó là văn
# bản LLM viết trơn từ đầu, nên KHÔNG có tín hiệu nào khác ngoài "theo kịch bản" ⇒ kênh thị
# trường Tây Ban Nha nhận kịch bản tiếng Anh thì description RA TIẾNG ANH (bug user báo
# 06/08/2026, tái hiện + xác nhận sửa bằng GLM thật, không phải MOCK). `profile.lang` (kênh
# thắng, thiếu thì lấy của niche — xem `niche_format.resolve`) là field DUY NHẤT của cả hệ
# thống mang ý nghĩa "ngôn ngữ thị trường kênh này nhắm tới", nên dùng lại nó làm NGUỒN SỰ
# THẬT, không suy đoán từ kịch bản/khuôn đối thủ.
def _lang_rule(channels: list[dict] | None) -> str:
    """Ngôn ngữ ĐÍCH của từng kênh — ƯU TIÊN HƠN ngôn ngữ kịch bản/khuôn đối thủ khi khác nhau.

    Kênh KHÔNG khai `lang` → bỏ qua hoàn toàn, description quay lại bám ngôn ngữ kịch bản như
    TRƯỚC ĐÂY (hành vi cũ giữ nguyên tuyệt đối cho mọi kênh chưa khai — test hồi quy chứng minh).
    """
    have = [(i, str(c.get("lang") or "").strip()) for i, c in enumerate(channels or [], 1)]
    have = [(i, lg) for i, lg in have if lg]
    if not have:
        return ""
    if len(have) == len(channels or []) and len({lg for _, lg in have}) == 1:
        lang = have[0][1]
        return (f"NGÔN NGỮ BẮT BUỘC CỦA KÊNH NÀY LÀ {lang.upper()} — ưu tiên HƠN ngôn ngữ của "
                f"kịch bản hay của khuôn đối thủ nếu chúng khác {lang}. Viết TOÀN BỘ output bằng "
                f"{lang} (dịch ý từ kịch bản/khuôn nếu cần), TUYỆT ĐỐI không trộn ngôn ngữ, không "
                f"viết bằng ngôn ngữ khác {lang}. ")
    parts = "; ".join(f"bản {i}: BẮT BUỘC {lg}" for i, lg in have)
    return (f"NGÔN NGỮ TỪNG BẢN LÀ RÀNG BUỘC CỨNG, ưu tiên HƠN ngôn ngữ kịch bản/khuôn đối thủ: "
            f"{parts}. Bản nào KHÔNG được nêu ở đây thì viết theo ngôn ngữ kịch bản như thường. ")


_HOOK_RULE = (
    "Dòng đầu (hook ~100-125 ký tự) chứa primary keyword TỰ NHIÊN, nói rõ video cho gì. "
    "Bám `script_opening` để giữ đúng giọng văn gốc. "
)
_CHAP_RULE = (
    "Input có `segments` (đoạn transcript theo thứ tự): đặt cho MỖI đoạn 1 tiêu đề chapter "
    "ngắn gọn, hấp dẫn, SEO-aware — đúng số đoạn, đúng thứ tự. "
)


_REWORK_RULE = (
    "Input có `hook_goc_cua_user`: đây là câu mở đầu CHÍNH USER viết. XÀO LẠI thành các bản khác "
    "nhau — GIỮ NGUYÊN Ý, con số và thông tin trong đó, CẤM thêm dữ kiện mới; chỉ đổi câu chữ, "
    "nhịp câu và cách vào đề. Input `kenh` cho biết mỗi bản viết cho kênh nào và kênh đó học Format "
    "đối thủ nào — viết bản thứ k hợp giọng kênh thứ k. Các bản phải KHÁC HẲN nhau về mặt chữ. "
)


# ══ CHẾ ĐỘ MIRROR (user chốt 06/08/2026): "description viết lại theo ĐÚNG format description
# của đối thủ" — khuôn là bản của VIDEO ĐỐI THỦ CHÍNH (link đầu tiên user dán vào tập), nội dung
# bám kịch bản tập + đan cụm khóa SEO đo từ chính các link đối thủ (desc_meta.phrases).
# Khác skeleton cũ (HOOK/SUMMARY học từ Format kênh — mất chi tiết cấu trúc): mirror đưa NGUYÊN
# VĂN bản đối thủ cho LLM soi cấu trúc từng khối. Video chính KHÔNG có description → tự rơi về
# đường skeleton cũ, không đổi hành vi.
DESC_MAX = 5000       # trần cứng description (giới hạn YouTube; user chốt 06/08 nâng lên 5000)

_MIRROR_RULE = (
    "Input có `description_doi_thu` — description NGUYÊN VĂN của video đối thủ CHÍNH (khuôn), có "
    "thể VIẾT BẰNG NGÔN NGỮ KHÁC ngôn ngữ output cần có. CHỈ HỌC CẤU TRÚC từ khuôn này — TUYỆT "
    "ĐỐI KHÔNG copy/dịch nguyên NGÔN NGỮ của khuôn; ngôn ngữ output theo đúng luật đã nêu ở trên "
    "(kịch bản, hoặc `NGÔN NGỮ BẮT BUỘC` nếu có), bất kể khuôn viết tiếng gì. "
    "PHÂN TÍCH cấu trúc bản đó: các khối theo thứ tự (mở đầu, tóm tắt, đoạn kể, kêu gọi…), độ dài "
    "tương đối từng khối, giọng văn, cách xuống dòng/ngắt đoạn. Rồi VIẾT LẠI description cho TẬP "
    "NÀY theo ĐÚNG cấu trúc đó: đối thủ có khối nào thì mình có khối đó, đúng thứ tự, độ dài từng "
    "khối tương đương. NỘI DUNG bám kịch bản/brief của tập, `primary_keyword` nằm tự nhiên trong "
    "125 ký tự đầu, đan `related_phrases` (cụm khóa đo từ chính đối thủ) không nhồi nhét. "
    "CẤM chép nguyên văn câu của đối thủ; CẤM bịa dữ kiện ngoài kịch bản. BỎ HẲN các phần đặc thù "
    "của kênh đối thủ: link/URL, social, tên kênh họ, mã tài trợ, dòng hashtag, dòng mục lục "
    "timestamp — các phần đó hệ thống tự ráp sau từ nguồn thật. "
)
_MIRROR_HOOK_RULE = (
    "Input có `hook_cua_user` — câu mở đầu CHÍNH USER viết: 1 bản thì dòng đầu dùng NGUYÊN VĂN "
    "không sửa một chữ; nhiều bản thì XÀO LẠI giữ nguyên ý/con số, cấm thêm dữ kiện. "
)

# Lưới sau LLM: dù prompt đã cấm, model vẫn hay bê link/hashtag/timestamp của khuôn sang.
# Link là của KÊNH ĐỐI THỦ (đăng lên là chỉ đường cho họ); hashtag + chapter hệ thống ráp
# từ nguồn thật (CTA kênh mình + SRT) — dòng LLM tự viết là đồ giả, phải gỡ chứ không tin.
_URL_LINE = re.compile(r"https?://|www\.", re.I)
_TAG_LINE = re.compile(r"^\s*(?:#\S+\s*)+$")
_TS_LINE = re.compile(r"^\s*(?:\d{1,2}:)?\d{1,2}:\d{2}\b")


def _scrub_mirror(text: str) -> str:
    keep = [ln for ln in (text or "").splitlines()
            if not (_URL_LINE.search(ln) or _TAG_LINE.match(ln) or _TS_LINE.match(ln))]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(keep)).strip()


def _sys_mirror(n: int, target: int, want_chaps: bool, has_hook: bool,
                channels: list[dict] | None = None) -> str:
    lang_rule = _lang_rule(channels)
    base = (_CORE + lang_rule + _MIRROR_RULE
            + f"Tổng độ dài bám bản đối thủ: ~{target} ký tự; TUYỆT ĐỐI không vượt {DESC_MAX}. "
            + (_MIRROR_HOOK_RULE if has_hook else "")
            + (_CHAP_RULE if want_chaps else ""))
    ch = ",\"chapters\":[<label theo thứ tự>]" if want_chaps else ""
    # NHẮC LẠI ngôn ngữ NGAY TRƯỚC khi xin JSON (recency — cùng nguyên tắc _len_rule: GLM bám
    # yêu cầu cụ thể đặt GẦN chỗ nó phải trả lời hơn là một dòng nêu suông ở đầu prompt).
    reminder = "NHẮC LẠI: ngôn ngữ output đúng như đã nêu ở NGÔN NGỮ BẮT BUỘC phía trên. " if lang_rule else ""
    if n <= 1:
        return base + reminder + f"Trả JSON {{\"text\":<description đầy đủ>{ch}}}."
    return base + (
        f"CÙNG 1 video này đăng lên {n} KÊNH khác nhau → viết ĐÚNG {n} bản KHÁC HẲN nhau về câu "
        "chữ (cùng cấu trúc khuôn, nội dung trung thực như nhau). "
        + ("Chapters chỉ cần 1 bộ dùng chung. " if want_chaps else "")
        + reminder
        + f"Trả JSON {{\"variants\":[{n} phần tử {{\"text\":<...>}}]{ch}}}.")


def gen_mirror(comp_desc: str, brief: dict | str, keyword: str, srt_text: str, opening: str = "",
               n: int = 1, user_hook: str = "", user_chapters: str = "",
               channels: list[dict] | None = None, phrases: list | None = None
               ) -> tuple[list[dict], list[dict]]:
    """1 call → N bản description theo khuôn đối thủ + chapters (nếu có SRT). Block trả về mang
    khóa `mirror_text` — `compose` thấy khóa này là đi đường mirror, không đụng skeleton."""
    content = digest.payload(brief, "") if isinstance(brief, dict) else digest.payload({}, brief)
    user_ch = parse_user_chapters(user_chapters)
    hook_fixed = (user_hook or "").strip()
    segs = [] if user_ch else _segments(srt_text)
    comp = (comp_desc or "").strip()[:DESC_MAX + 3000]     # khuôn quá dài thì cắt cho prompt gọn
    target = min(len(comp), DESC_MAX)
    payload = {**content, "primary_keyword": keyword, "description_doi_thu": comp}
    if phrases:
        payload["related_phrases"] = list(phrases)[:15]
    if opening and not hook_fixed:
        payload["script_opening"] = opening[:900]
    if hook_fixed:
        payload["hook_cua_user"] = hook_fixed
    if channels:
        payload["kenh"] = [{"ten": c.get("name", ""), "hoc_format": c.get("format", "")}
                           for c in channels][:n]
    if segs:
        payload["segments"] = [s["text"][:220] for s in segs]
    if n > 1:
        payload["n_variants"] = n
    # Trần token theo ĐỘ DÀI KHUÔN (5000 ký tự ≈ 1700 token/bản) — trần cũ 1200+500n là cho
    # hook/summary ngắn, mirror mà dùng nó là JSON đứt giữa chừng đúng bẫy _SYS_PACKAGE.
    per = 600 + target // 3
    hs = llm.call_json(_sys_mirror(n, target, want_chaps=bool(segs), has_hook=bool(hook_fixed),
                                   channels=channels),
                       json.dumps(payload, ensure_ascii=False),
                       max_tokens=min(12000, 400 + per * n), temperature=0.6)
    if not isinstance(hs, dict):
        hs = {}
    if user_ch:
        chaps = _user_chapter_block(user_ch, srt_text)
    else:
        chaps = _chapter_block(segs, llm.as_list(hs.get("chapters", []))) if segs else []
    if n > 1:
        texts = [str(v.get("text", "")).strip()
                 for v in llm.as_list(hs.get("variants", [])) if isinstance(v, dict)]
    else:
        texts = [str(hs.get("text", "")).strip()]
    out = [{"mirror_text": t} for t in texts if True]
    # 1 kênh + hook user: NGUYÊN VĂN là luật (user chốt 29/07) — LLM quên thì Python chèn lên đầu.
    if hook_fixed and n == 1 and out and out[0]["mirror_text"] \
            and not out[0]["mirror_text"].startswith(hook_fixed):
        out[0]["mirror_text"] = hook_fixed + "\n\n" + out[0]["mirror_text"]
    while len(out) < n:                                    # LLM trả thiếu → lặp bản đầu
        out.append(dict(out[0]) if out else {"mirror_text": ""})
    return out[:n], chaps


def _assemble_mirror(profile, block: dict, chaps: list[dict], keyword: str,
                     ch_ok: bool, ch_iss: list) -> dict:
    text = _scrub_mirror(block.get("mirror_text", ""))
    chap_txt = "⏱ CHAPTERS\n" + "\n".join(f"{c['t']} {c['label']}" for c in chaps) if chaps else ""
    if chap_txt:
        text = (text + "\n\n" + chap_txt).strip()          # timestamp THẬT từ SRT, nối cuối như lệ 04/08
    if len(text) > DESC_MAX:                               # trần cứng YouTube — cắt biên câu rồi mới slice
        text, _ = fit_len(text, DESC_MAX)
        text = text[:DESC_MAX]
    chars = len(text)
    kw_in_125 = (keyword.lower() in text[:125].lower()) if keyword else True
    s = 40 + (25 if kw_in_125 else 0) + (15 if chars >= 200 else 0)
    if chaps and ch_ok:
        s += 20
    elif chaps:
        s += 8
    return {"score": min(96, s), "chars": chars,
            "profile": (profile or {}).get("code") or "standard",
            "text": text, "chapters": chaps, "template": "doi_thu",
            "sigs": {"kw_in_125": kw_in_125, "chapters_ok": ch_ok, "chapters_issues": ch_iss}}


def build_mirror(profile: dict | None, comp_desc: str, brief: dict | str, keyword: str,
                 srt_text: str, opening: str = "", user_hook: str = "", user_chapters: str = "",
                 phrases: list | None = None) -> dict:
    """1 kênh, khuôn đối thủ — bộ đôi của `build` cho đường mirror.

    `profile` chính là `eff` đã resolve (giống `build`) nên đã có `lang` (kênh thắng, thiếu thì
    lấy của niche — xem `niche_format.resolve`) — truyền vào `channels` để `_lang_rule` bắt
    ngôn ngữ output đúng thị trường kênh, không rơi về ngôn ngữ khuôn đối thủ/kịch bản."""
    ch = [{"lang": (profile or {}).get("lang", "")}]
    blocks, chaps = gen_mirror(comp_desc, brief, keyword, srt_text, opening, n=1,
                               user_hook=user_hook, user_chapters=user_chapters, phrases=phrases,
                               channels=ch)
    return compose(profile, blocks[0], chaps, keyword)


def _sys_desc(n: int, want_hook: bool = True, want_chaps: bool = True, rework: bool = False,
              channels: list[dict] | None = None) -> str:
    """Chỉ xin thứ user CHƯA đưa. Xin thừa là vừa tốn token vừa mở thêm cửa cho LLM bịa."""
    lang_rule = _lang_rule(channels)
    base = _CORE + lang_rule + _len_rule(channels) \
        + (_REWORK_RULE if rework else (_HOOK_RULE if want_hook else "")) \
        + (_CHAP_RULE if want_chaps else "")
    hk = "\"hook\":<...>," if want_hook else ""
    ch = ",\"chapters\":[<label theo thứ tự>]" if want_chaps else ""
    # NHẮC LẠI ngôn ngữ NGAY TRƯỚC khi xin JSON (recency — xem chú thích ở _sys_mirror).
    reminder = "NHẮC LẠI: ngôn ngữ output đúng như đã nêu ở NGÔN NGỮ BẮT BUỘC phía trên. " if lang_rule else ""
    if n <= 1:
        return base + reminder + f"Trả JSON {{{hk}\"summary\":<...>{ch}}}."
    what = "hook+summary" if want_hook else "summary"
    return base + (
        f"CÙNG 1 video này đăng lên {n} KÊNH khác nhau → viết ĐÚNG {n} bản {what} KHÁC HẲN nhau: "
        "khác góc mở đầu, khác câu chữ, khác thứ tự thông tin (nội dung vẫn trung thực như nhau). "
        "Tuyệt đối không viết lại gần giống bản trước — sẽ bị coi là metadata trùng lặp. "
        + ("Chapters chỉ cần 1 bộ dùng chung. " if want_chaps else "")
        + reminder
        + f"Trả JSON {{\"variants\":[{n} phần tử {{{hk}\"summary\":<...>}}]{ch}}}."
    )
_STANDARD = ["HOOK", "SUMMARY", "CHAPTERS"]                # skeleton fallback nếu profile thiếu


def target_len(eff: dict) -> dict:
    """Độ dài mục tiêu cho HOOK/SUMMARY, lấy từ số ĐO THẬT của Format kênh đang học.

    `niche_format` đã đo `description.blocks[].chars` trên video outlier thật của đối thủ. Kênh
    học đối thủ viết SUMMARY 900 ký tự thì viết 900; học đối thủ viết 200 thì viết 200 — chứ không
    ép mọi kênh về cùng một độ dài (user chốt 2026-07-30: "description hãy tuỳ biến").

    `chars` có HAI DẠNG tuỳ nguồn, phải nhận cả hai:
      · Format (niche_format)  → số nguyên: 900
      · Profile kênh (profile.extract) → KHOẢNG dạng chuỗi: "200–400" (dấu gạch dài, không phải '-')
    Khoảng thì lấy điểm giữa — trung thực hơn là chọn bừa một đầu.

    Trả {} khi chưa đo được → prompt bỏ luôn luật độ dài, không bịa ra con số.
    """
    import re
    out = {}
    for b in (eff.get("blocks") or []):
        name = str(b.get("block", "")).upper()
        if name not in ("HOOK", "SUMMARY"):
            continue
        raw = b.get("chars")
        if isinstance(raw, (int, float)):
            n = int(raw)
        else:
            nums = [int(x) for x in re.findall(r"\d+", str(raw or ""))]
            n = round(sum(nums) / len(nums)) if nums else 0
        if n > 0:
            out[name.lower()] = n
    return out


def _segments(srt_text: str) -> list[dict]:
    """Số chapter bám theo ĐỘ DÀI VIDEO (`chapters.auto_n`), không phải hằng số 5."""
    cues = chapters.parse_srt(srt_text or "")
    return chapters.segment_cues(cues, n=chapters.auto_n(cues))


_TS_RE = None


def parse_user_chapters(text: str) -> list[dict]:
    """User tự đưa TÊN CHAPTER (user chốt 2026-07-29). Nhận cả 2 kiểu, mỗi dòng 1 chapter:

        Vì sao Phần Lan luôn đứng đầu          → chỉ tên, Python neo giờ từ SRT
        0:00 Vì sao Phần Lan luôn đứng đầu     → user đưa cả giờ, dùng nguyên giờ đó

    Trả [{label, start|None}]. Không có SRT mà user cũng không ghi giờ thì tầng trên tự lo.
    """
    global _TS_RE
    if _TS_RE is None:
        import re
        _TS_RE = re.compile(r"^\s*(?:(\d+):)?(\d{1,2}):(\d{2})\s*[-–—]?\s*(.*)$")
    out = []
    for line in (text or "").splitlines():
        line = line.strip().lstrip("-•·").strip()
        if not line:
            continue
        m = _TS_RE.match(line)
        if m and m.group(4).strip():
            h, mi, s = int(m.group(1) or 0), int(m.group(2)), int(m.group(3))
            out.append({"label": m.group(4).strip(), "start": float(h * 3600 + mi * 60 + s)})
        else:
            out.append({"label": line, "start": None})
    return out


def _user_chapter_block(user_ch: list[dict], srt_text: str) -> list[dict]:
    """Ghép tên chapter của user với timestamp.

    Ưu tiên giờ user ghi; dòng nào không ghi thì neo vào SRT — chia SRT thành ĐÚNG số chapter
    user đưa (không phải 5 cố định) rồi lấy mốc đầu mỗi đoạn theo thứ tự.
    """
    need = [c for c in user_ch if c["start"] is None]
    segs = chapters.segment_cues(chapters.parse_srt(srt_text or ""), n=len(user_ch)) if need else []
    out, si = [], 0
    for c in user_ch:
        st = c["start"]
        if st is None:
            st = segs[si]["start"] if si < len(segs) else (out[-1]["start"] + 30.0 if out else 0.0)
            si += 1
        out.append({"t": chapters.sec_to_ts(st), "start": st, "label": c["label"]})
    return out


def _chapter_block(segs: list[dict], labels: list) -> list[dict]:
    out = []
    for i, s in enumerate(segs):
        lab = str(labels[i]).strip() if i < len(labels) and str(labels[i]).strip() else f"Part {i + 1}"
        out.append({"t": s["ts"], "start": s["start"], "label": lab})
    return out


def gen_blocks(brief: dict | str, keyword: str, srt_text: str, opening: str = "",
               n: int = 1, user_hook: str = "", user_chapters: str = "",
               channels: list[dict] | None = None) -> tuple[list[dict], list[dict]]:
    """1 call → (N bản {hook,summary}, chapters). n>1 = 1 tập đăng N kênh, mỗi kênh 1 góc mở khác.

    `opening` = đoạn mở đầu NGUYÊN VĂN của kịch bản — brief nén mất giọng văn, mà hook/summary
    thì cần giọng thật, nên cấp thêm phần này (rẻ, ~900 ký tự).

    `user_hook` (user chốt 2026-07-29, sửa 2026-07-30):
      · **1 kênh** → dùng NGUYÊN VĂN, không hỏi LLM. Chữ user viết thì giữ đúng chữ user viết.
      · **≥2 kênh** → LLM **XÀO LẠI** thành N bản, giữ nguyên Ý và thông tin nhưng khác câu chữ,
        mỗi bản hợp giọng Format mà kênh đó học. Trước đây copy y nguyên cho mọi kênh ⇒ mọi kênh
        anh em có CÙNG câu mở đầu — đúng ca user lo. Không có thuật toán nào làm 1 câu thành N câu
        khác nhau mà vẫn "nguyên văn", nên phải chọn: user chốt cho máy xào.

    `channels` = [{name, format}] để LLM biết mỗi bản viết cho kênh nào, học đối thủ nào.
    `user_chapters`: luôn dùng nguyên văn (tên chapter là mốc nội dung, không phải câu chữ SEO).
    """
    content = digest.payload(brief, "") if isinstance(brief, dict) else digest.payload({}, brief)
    user_ch = parse_user_chapters(user_chapters)
    hook_fixed = (user_hook or "").strip()
    rework = bool(hook_fixed) and n > 1                 # ≥2 kênh thì xào, 1 kênh thì giữ nguyên văn
    verbatim = hook_fixed if (hook_fixed and not rework) else ""
    segs = [] if user_ch else _segments(srt_text)
    payload = {**content, "primary_keyword": keyword}
    if opening and not hook_fixed:
        payload["script_opening"] = opening[:900]      # chỉ cần khi LLM phải tự viết hook từ đầu
    if rework:
        payload["hook_goc_cua_user"] = hook_fixed
    if channels:
        payload["kenh"] = [{"ten": c.get("name", ""), "hoc_format": c.get("format", ""),
                            **({"do_dai": c["len"]} if c.get("len") else {})}
                           for c in channels][:n]
    if segs:
        payload["segments"] = [s["text"][:220] for s in segs]
    if n > 1:
        payload["n_variants"] = n
    hs = llm.call_json(_sys_desc(n, want_hook=not verbatim, want_chaps=bool(segs), rework=rework,
                                 channels=channels),
                       json.dumps(payload, ensure_ascii=False),
                       max_tokens=1200 + 500 * n, temperature=0.6)
    if not isinstance(hs, dict):
        hs = {}
    if user_ch:
        chaps = _user_chapter_block(user_ch, srt_text)
    else:
        chaps = _chapter_block(segs, llm.as_list(hs.get("chapters", []))) if segs else []
    if n > 1:
        vs = [v for v in llm.as_list(hs.get("variants", [])) if isinstance(v, dict)]
    else:
        vs = [{"hook": hs.get("hook", ""), "summary": hs.get("summary", "")}]
    out = [{"hook": verbatim or str(v.get("hook", "")).strip(),
            "summary": str(v.get("summary", "")).strip()} for v in vs]
    if rework:                                         # LLM trả thiếu/rỗng → thà dùng hook gốc
        out = [{**o, "hook": o["hook"] or hook_fixed} for o in out]
    while len(out) < n:                                    # LLM trả thiếu → lặp bản đầu (Python cảnh báo sau)
        out.append(dict(out[0]) if out else {"hook": "", "summary": ""})
    # Chốt cuối về độ dài: prompt kéo gần được nhưng KHÔNG đảm bảo (đo LIVE: mục tiêu 300 ra 448).
    # Python cắt đúng biên câu. Ghi luôn số đo thật + mục tiêu để board hiện — trượt mục tiêu thì
    # phải thấy được, đừng để user tưởng đã đúng phong cách kênh.
    for o, c in zip(out, channels or []):
        tgt = int(((c or {}).get("len") or {}).get("summary") or 0)
        if tgt > 0:
            o["summary"], o["summary_trimmed"] = fit_len(o["summary"], tgt)
            o["summary_target"] = tgt
        o["summary_len"] = len(o.get("summary") or "")
    return out[:n], chaps


def compose(profile: dict | None, block: dict, chaps: list[dict], keyword: str) -> dict:
    """Python ráp block sinh động vào skeleton + chấm điểm. Không gọi LLM.

    Block mang `mirror_text` (từ `gen_mirror`) → đi đường khuôn-đối-thủ; còn lại giữ đường
    skeleton cũ nguyên vẹn — mirror_text RỖNG (LLM hỏng) cũng rơi về skeleton, không nổ."""
    ch_ok, ch_iss = chapters.validate_chapters([{"start": c["start"], "label": c["label"]} for c in chaps]) \
        if chaps else (False, ["không có SRT"])
    if block.get("mirror_text"):
        return _assemble_mirror(profile, block, chaps, keyword, ch_ok, ch_iss)
    hook, summary = block.get("hook", ""), block.get("summary", "")
    return _assemble(profile, hook, summary, chaps, keyword, ch_ok, ch_iss)


def build(profile: dict | None, brief: dict | str, keyword: str, srt_text: str,
          opening: str = "", user_hook: str = "", user_chapters: str = "") -> dict:
    """1 kênh: sinh block rồi ráp (giữ nguyên API cũ).

    PHẢI tự truyền mục tiêu độ dài vào: `profile` ở đây chính là `eff` đã resolve nên đã có
    `blocks[].chars` để đo. Bản cũ không truyền ⇒ **cùng một kênh, cùng một Format, mà tick 1
    kênh thì description dài tuỳ hứng còn tick 2 kênh mới bám độ dài**. Số kênh được tick không
    được phép đổi luật viết của kênh.
    """
    ch = [{"len": target_len(profile or {}), "lang": (profile or {}).get("lang", "")}]
    blocks, chaps = gen_blocks(brief, keyword, srt_text, opening, n=1,
                               user_hook=user_hook, user_chapters=user_chapters, channels=ch)
    des = compose(profile, blocks[0], chaps, keyword)
    for k in ("summary_target", "summary_len", "summary_trimmed"):   # số đo phải tới result.json
        if k in blocks[0]:
            des[k] = blocks[0][k]
    return des


def _assemble(profile, hook, summary, chaps, keyword, ch_ok, ch_iss) -> dict:
    skeleton = (profile or {}).get("skeleton") or _STANDARD
    chap_txt = "⏱ CHAPTERS\n" + "\n".join(f"{c['t']} {c['label']}" for c in chaps) if chaps else ""
    parts: list[str] = []
    for b in skeleton:
        if b == "HOOK" and hook:
            parts.append(hook)
        elif b == "SUMMARY" and summary:
            parts.append(summary)
        elif b == "CHAPTERS" and chap_txt:
            parts.append(chap_txt)
        # HASHTAG/CTA/LINKS = block cố định → nhập tay lúc export, không sinh ở đây
    # SKELETON THIẾU "CHAPTERS" MÀ USER ĐÃ CẤP SRT/CHAPTER → vẫn NỐI chapter vào CUỐI
    # (user chốt 2026-08-04: "tôi đã nhập ở phần tập rồi mà không trả ra timestamps").
    # Skeleton học từ đối thủ là KHUÔN mặc định, nhưng SRT/chapter là thứ user chủ động nhập
    # cho ĐÚNG tập này — lời khai trực tiếp thắng khuôn học được, không được lặng lẽ vứt.
    # Nối cuối phần máy viết (trước block cố định lúc export) = vị trí chapter quen thuộc.
    if chap_txt and not any(str(b).strip().upper() == "CHAPTERS" for b in skeleton):
        parts.append(chap_txt)
    text = "\n\n".join(p for p in parts if p)

    chars = len(text)
    kw_in_125 = (keyword.lower() in text[:125].lower()) if keyword else True
    s = 40
    if kw_in_125:
        s += 25
    if hook and summary:
        s += 15
    if chaps and ch_ok:
        s += 20
    elif chaps:
        s += 8
    return {"score": min(96, s), "chars": chars,
            "profile": (profile or {}).get("code") or "standard",
            "text": text, "chapters": chaps,
            "sigs": {"kw_in_125": kw_in_125, "chapters_ok": ch_ok, "chapters_issues": ch_iss}}


if __name__ == "__main__":                                # self-test offline (seed giả)
    seen = []

    def hook(sysmsg, user):
        seen.append(user)                                 # đếm số call: phải là 1 (đã gộp chapter vào)
        return ('{"hook":"Sagittarius A* is the monster at the center of our galaxy.",'
                '"summary":"A dark documentary about the supermassive black hole. Event horizon, '
                'spaghettification, time dilation.",'
                '"chapters":["The Deception Overhead","A Monster of 4 Million Suns","The Event Horizon"]}')
    llm.set_hook(hook)
    srt = """1
00:00:00,000 --> 00:00:04,000
Look up.

2
00:02:00,000 --> 00:04:00,000
A monster of four million suns.

3
00:06:00,000 --> 00:09:40,000
The event horizon."""
    brief = {"topic": "Sagittarius A*", "beats": ["mở đầu", "quái vật", "chân trời sự kiện"]}
    d = build({"skeleton": ["HOOK", "SUMMARY", "CHAPTERS"], "code": "CL-01"},
              brief, "Sagittarius A*", srt, opening="Look up at the night sky.")
    llm.set_hook(None)
    assert d["sigs"]["kw_in_125"], d                      # keyword trong 125 đầu
    assert "⏱ CHAPTERS" in d["text"] and "0:00" in d["text"], d
    assert d["profile"] == "CL-01" and d["score"] >= 80, d
    assert len(seen) == 1, f"phải gộp còn 1 call, đang {len(seen)}"
    assert "content_brief" in seen[0] and "script_opening" in seen[0] and "segments" in seen[0], seen[0]
    assert "The Event Horizon" in d["text"], d             # label chapter lấy từ cùng 1 call

    # ── SKELETON THIẾU "CHAPTERS" mà user CÓ SRT → chapter vẫn phải vào text (04/08) ──
    llm.set_hook(hook)
    d_no = build({"skeleton": ["HOOK", "SUMMARY"], "code": "NS-01"},
                 brief, "Sagittarius A*", srt, opening="Look up.")
    llm.set_hook(None)
    assert "⏱ CHAPTERS" in d_no["text"] and "0:00" in d_no["text"], d_no["text"]
    assert d_no["text"].rstrip().endswith(d_no["text"].split("⏱ CHAPTERS")[-1].rstrip()), \
        "chapter phải nằm CUỐI phần máy viết"
    # ...còn KHÔNG có SRT thì vẫn không có gì để nối — van chống bịa giữ nguyên
    llm.set_hook(hook)
    d_dry = build({"skeleton": ["HOOK", "SUMMARY"], "code": "NS-01"}, brief, "Sagittarius A*", "")
    llm.set_hook(None)
    assert "⏱ CHAPTERS" not in d_dry["text"], d_dry["text"]

    # ── 1 tập → 3 kênh: 1 call ra 3 bản hook/summary khác nhau, chapters dùng chung ──
    seen.clear()
    llm.set_hook(lambda sy, u: (seen.append(u),
                                '{"variants":[{"hook":"Hook A","summary":"Sum A"},'
                                '{"hook":"Hook B","summary":"Sum B"},{"hook":"Hook C","summary":"Sum C"}],'
                                '"chapters":["c1","c2","c3"]}')[1])
    blocks, chaps = gen_blocks(brief, "Sagittarius A*", srt, n=3)
    llm.set_hook(None)
    assert len(seen) == 1 and len(blocks) == 3 and len(chaps) == 3, (len(seen), blocks)
    assert len({b["hook"] for b in blocks}) == 3, blocks   # 3 kênh, 3 hook khác nhau
    # ── USER TỰ ĐƯA hook + tên chapter (user chốt 2026-07-29) ──
    CH = "\n".join(["Vì sao Phần Lan đứng đầu", "0:30 Sauna và văn hoá", "- Giáo dục miễn phí"])
    uc = parse_user_chapters(CH)
    assert [c["label"] for c in uc] == ["Vì sao Phần Lan đứng đầu", "Sauna và văn hoá", "Giáo dục miễn phí"], uc
    assert uc[1]["start"] == 30.0 and uc[0]["start"] is None and uc[2]["start"] is None, uc
    assert parse_user_chapters("") == [] and parse_user_chapters("\n  \n") == []

    seen_sys = []
    llm.set_hook(lambda sy, u: (seen_sys.append((sy, u)), json.dumps({"summary": "Tóm tắt máy viết"}))[1])
    b2, c2 = gen_blocks("kb", "finland", srt, user_hook="HOOK CỦA TÔI", user_chapters=CH)
    llm.set_hook(None)
    sy, us = seen_sys[-1]
    assert "hook" not in sy and "chapters" not in sy, "đã có sẵn thì KHÔNG được hỏi lại LLM"
    assert "segments" not in us and "script_opening" not in us, "bớt payload khi user đã đưa"
    assert b2[0]["hook"] == "HOOK CỦA TÔI", b2                      # nguyên văn, không qua LLM
    assert [c["label"] for c in c2] == [c["label"] for c in uc], c2
    assert c2[1]["t"] == "0:30", c2                                 # giờ user ghi thì giữ nguyên
    assert c2[0]["start"] is not None and c2[2]["start"] is not None, c2   # còn lại neo từ SRT

    # ── ĐỘ DÀI TUỲ BIẾN theo số đo của Format từng kênh (user chốt 2026-07-30) ──
    assert target_len({}) == {}, "chưa đo được thì KHÔNG bịa con số"
    assert target_len({"blocks": [{"block": "SUMMARY", "chars": 900}]}) == {"summary": 900}
    # profile kênh lưu KHOẢNG dạng chuỗi với gạch dài — phải nhận, không thì rơi về rỗng
    assert target_len({"blocks": [{"block": "HOOK", "chars": "120–220"}]}) == {"hook": 170}
    assert target_len({"blocks": [{"block": "SUMMARY", "chars": "không rõ"}]}) == {}
    assert target_len({"blocks": [{"block": "CTA", "chars": 80}]}) == {}, "chỉ HOOK/SUMMARY"

    seen3 = []
    llm.set_hook(lambda sy, u: (seen3.append((sy, u)), json.dumps({"variants": [
        {"hook": "h1", "summary": "s1"}, {"hook": "h2", "summary": "s2"}]}))[1])
    gen_blocks("kb", "kw", srt, n=2, channels=[{"name": "A", "format": "F1", "len": {"summary": 900}},
                                               {"name": "B", "format": "F2", "len": {"summary": 200}}])
    llm.set_hook(None)
    sy3, us3 = seen3[-1]
    # ra lệnh bằng SỐ CÂU: 900/110 ≈ 8 câu, 200/110 ≈ 2 câu
    assert "bản 1: ĐÚNG 8 câu" in sy3 and "bản 2: ĐÚNG 2 câu" in sy3, sy3[:400]
    assert "ĐẾM SỐ CÂU" in sy3 and "KHÔNG viết mọi bản dài xấp xỉ nhau" in sy3, sy3[:400]
    assert "không bản nào vượt 1170 ký tự" in sy3, sy3[:400]      # trần cứng = max×1.3
    # không kênh nào đo được → BỎ luôn luật độ dài khỏi prompt, đừng nhồi câu thừa
    seen4 = []
    llm.set_hook(lambda sy, u: (seen4.append(sy), json.dumps({"variants": [{"hook": "h", "summary": "s"}]}))[1])
    gen_blocks("kb", "kw", srt, n=1, channels=[{"name": "A", "format": "F1"}])
    llm.set_hook(None)
    assert "ĐỘ DÀI SUMMARY LÀ YÊU CẦU" not in seen4[-1], "không có số đo mà vẫn dặn độ dài"

    # ── hook user viết: 1 kênh giữ NGUYÊN VĂN · nhiều kênh thì máy XÀO riêng từng kênh ──
    seen2 = []
    llm.set_hook(lambda sy, u: (seen2.append((sy, u)), json.dumps({"variants": [
        {"hook": "Ban A cua hook", "summary": "s1"},
        {"hook": "Ban B cua hook", "summary": "s2"}]}))[1])
    b4, _ = gen_blocks("kb", "kw", srt, n=2, user_hook="HOOK GOC CUA TOI",
                       channels=[{"name": "K1", "format": "F1"}, {"name": "K2", "format": "F2"}])
    llm.set_hook(None)
    sy2, us2 = seen2[-1]
    assert "XÀO LẠI" in sy2 and "CẤM thêm dữ kiện mới" in sy2, sy2[:200]
    assert "hook_goc_cua_user" in us2 and "HOOK GOC CUA TOI" in us2, us2[:200]
    assert "hoc_format" in us2 and "F2" in us2, us2[:200]        # kênh nào học format nào
    assert [x["hook"] for x in b4] == ["Ban A cua hook", "Ban B cua hook"], b4
    # LLM xào hỏng (trả rỗng) → rơi về hook gốc, KHÔNG để trống
    llm.set_hook(lambda sy, u: json.dumps({"variants": [{"hook": "", "summary": "s"},
                                                        {"hook": "", "summary": "s"}]}))
    b5, _ = gen_blocks("kb", "kw", srt, n=2, user_hook="HOOK GOC")
    llm.set_hook(None)
    assert [x["hook"] for x in b5] == ["HOOK GOC", "HOOK GOC"], b5

    # chỉ đưa chapter, hook vẫn để máy viết
    llm.set_hook(lambda sy, u: json.dumps({"hook": "máy viết", "summary": "s"}))
    b3, c3 = gen_blocks("kb", "finland", srt, user_chapters="Mở đầu\nKết")
    llm.set_hook(None)
    assert b3[0]["hook"] == "máy viết" and len(c3) == 2, (b3, c3)

    d1 = compose({"skeleton": ["HOOK", "SUMMARY"], "code": "CL-01"}, blocks[0], chaps, "Sagittarius A*")
    d2 = compose({"skeleton": ["HOOK", "CHAPTERS"], "code": "O-01"}, blocks[1], chaps, "Sagittarius A*")
    # 04/08: skeleton thiếu CHAPTERS mà CÓ chaps → NỐI vào CUỐI (thay luật cũ "không có là bỏ").
    # Hai bản vẫn phải KHÁC nhau (hook khác + vị trí chapter khác: d1 cuối, d2 theo skeleton).
    assert d1["text"] != d2["text"] and "⏱ CHAPTERS" in d2["text"], (d1, d2)
    assert "⏱ CHAPTERS" in d1["text"] and d1["text"].index("Sum A") < d1["text"].index("⏱ CHAPTERS"), d1
    # ── độ dài: ra lệnh theo ngưỡng + chốt cắt đúng biên câu ──
    assert _sent_plan(900)[1] == 0, "bản DÀI không được ra lệnh số từ (đo: kéo tụt 20%)"
    assert _sent_plan(200)[1] > 0, "bản NGẮN phải có lệnh số từ (không thì vượt +36%)"
    assert _sent_plan(200)[0] >= 1 and _sent_plan(0)[0] >= 1, "số câu luôn ≥ 1"
    r200 = _len_rule([{"len": {"summary": 200}}])
    r900 = _len_rule([{"len": {"summary": 900}}])
    assert "từ" in r200 and "mỗi câu" in r200, r200
    assert "mỗi câu" not in r900, "bản dài không được dính lệnh số từ"
    assert _len_rule([]) == "" and _len_rule(None) == "", "chưa đo được thì KHÔNG bịa con số"

    LONG = ("One sentence here. " * 6).strip()             # 6 câu × 19 = 113 ký tự
    cut, did = fit_len(LONG, 40)
    assert did and cut.endswith(".") and len(cut) <= 40 * LEN_TOL, (cut, len(cut))
    assert fit_len(LONG, 999)[1] is False, "chưa vượt thì đừng đụng"
    # Cắt phải kéo GẦN mục tiêu hơn, không thì thà để nguyên (cắn LIVE: 200 → cắt còn 139 = -30%
    # trong khi để nguyên chỉ +25%). Ở đây bỏ 1 câu là tụt từ 113 xuống 95, xa 80 hơn → giữ nguyên.
    two = "A" * 59 + ". " + "B" * 68 + "."                 # 60 + 70 = 130 ký tự, mục tiêu 100
    keep_txt, keep_did = fit_len(two, 100)                 # cắt → 60 (lệch 40) · giữ → 130 (lệch 30)
    assert keep_did is False and keep_txt == two, (len(two), len(keep_txt))
    far = "A" * 59 + ". " + "B" * 300 + "."                # giữ → lệch 262, cắt → lệch 40 ⇒ PHẢI cắt
    assert fit_len(far, 100)[1] is True, len(fit_len(far, 100)[0])
    assert fit_len("A" * 400 + ".", 100)[1] is False, "1 câu quá dài → thà giữ nguyên còn hơn cụt"
    assert fit_len("", 100) == ("", False) and fit_len(LONG, 0)[1] is False

    # Số kênh được tick KHÔNG được đổi luật viết: `build` (1 kênh) phải áp cùng mục tiêu độ dài
    # như `gen_blocks(channels=…)` (nhiều kênh), và số đo phải đi được tới result.json.
    seen = {}
    llm.set_hook(lambda sysmsg, user, **kw: seen.setdefault("sys", sysmsg) and None or
                 '{"hook":"H","summary":"S1. S2. S3.","chapters":["a","b"]}')
    EFF = {"skeleton": ["HOOK", "SUMMARY"], "blocks": [{"block": "SUMMARY", "chars": 900}]}
    dz = build(EFF, "kb", "kw", srt)
    llm.set_hook(None)
    assert "ĐÚNG 8 câu" in seen["sys"], seen["sys"][:400]      # 900/110 → 8 câu, không ép số từ
    assert dz.get("summary_target") == 900 and dz.get("summary_len") == len("S1. S2. S3."), dz
    for tgt in (40, 60, 100):                              # không ca nào được cắt giữa câu
        c, _ = fit_len(LONG, tgt)
        assert not c or c[-1] in ".!?", (tgt, c)

    # ══ MIRROR (06/08): viết theo khuôn description đối thủ chính ══
    COMP = ("Look up at the night sky tonight.\n\n"
            "In this documentary we explore the monster at the center.\n\n"
            "Subscribe here: https://youtube.com/@doithu\n"
            "0:00 Intro\n"
            "#Space #BlackHole")
    seen_m = []
    llm.set_hook(lambda sy, u: (seen_m.append((sy, u)), json.dumps({
        "text": "Sagittarius A* hook mở đầu.\n\nĐoạn tóm tắt bám kịch bản.\n\n"
                "Ghé kênh họ: https://youtube.com/@doithu\n0:00 Mở đầu\n#Space #Копия",
        "chapters": ["a", "b", "c"]}))[1])
    bm, cm = gen_mirror(COMP, brief, "Sagittarius A*", srt, opening="Look up.",
                        phrases=["black hole", "event horizon"])
    dm = compose({"skeleton": ["HOOK", "SUMMARY"], "code": "CL-01"}, bm[0], cm, "Sagittarius A*")
    llm.set_hook(None)
    sym, usm = seen_m[-1]
    assert "description_doi_thu" in usm and "related_phrases" in usm, usm[:300]
    assert "PHÂN TÍCH cấu trúc" in sym and "không vượt 5000" in sym, sym[:400]
    # Lưới scrub: link/hashtag/timestamp LLM bê từ khuôn phải bị GỠ; chapter THẬT (SRT) nối cuối
    assert "youtube.com" not in dm["text"] and "#Space" not in dm["text"], dm["text"]
    assert "0:00 Mở đầu" not in dm["text"] and "⏱ CHAPTERS" in dm["text"], dm["text"]
    assert dm["template"] == "doi_thu" and dm["sigs"]["kw_in_125"], dm
    assert len(cm) == 3, cm
    # Trần cứng 5000: khuôn dài + LLM viết tràn → text cuối không vượt DESC_MAX
    llm.set_hook(lambda sy, u: json.dumps({"text": ("Câu dài chống trôi. " * 400).strip()}))
    bo, co = gen_mirror("x" * 4000, brief, "kw", "")
    do = compose(None, bo[0], co, "kw")
    llm.set_hook(None)
    assert do["chars"] <= DESC_MAX, do["chars"]
    # Hook user 1 bản = NGUYÊN VĂN — LLM quên thì Python chèn lên đầu
    llm.set_hook(lambda sy, u: json.dumps({"text": "Thân bài không có hook."}))
    bh, _ = gen_mirror(COMP, brief, "kw", "", user_hook="HOOK GOC CUA TOI")
    llm.set_hook(None)
    assert bh[0]["mirror_text"].startswith("HOOK GOC CUA TOI"), bh
    # N bản: variants → N mirror_text; thiếu thì lặp bản đầu
    llm.set_hook(lambda sy, u: json.dumps({"variants": [{"text": "Bản A"}, {"text": "Bản B"}]}))
    bv, _ = gen_mirror(COMP, brief, "kw", "", n=3)
    llm.set_hook(None)
    assert [b["mirror_text"] for b in bv] == ["Bản A", "Bản B", "Bản A"], bv
    # mirror_text RỖNG (LLM hỏng) → compose rơi về skeleton cũ, không nổ
    dz2 = compose({"skeleton": ["HOOK", "SUMMARY"]}, {"mirror_text": ""}, [], "kw")
    assert "template" not in dz2, dz2

    # ══ NGÔN NGỮ ĐÍCH CỦA KÊNH (06/08) — bug thật: kịch bản tiếng Anh + kênh thị trường Tây
    # Ban Nha → description ra tiếng Anh, tái hiện + xác nhận sửa bằng GLM THẬT (ghi ở commit) ══
    assert _lang_rule(None) == "" and _lang_rule([]) == "", "không kênh nào khai lang → im lặng"
    assert _lang_rule([{"name": "A"}]) == "", "kênh chưa khai lang → không được bịa luật"
    r1 = _lang_rule([{"lang": "Spanish"}])
    assert "SPANISH" in r1 and "ưu tiên HƠN" in r1, r1
    r2 = _lang_rule([{"lang": "Spanish"}, {"lang": "Vietnamese"}])
    assert "bản 1: BẮT BUỘC Spanish" in r2 and "bản 2: BẮT BUỘC Vietnamese" in r2, r2
    r3 = _lang_rule([{"lang": "Spanish"}, {}])
    assert "bản 1: BẮT BUỘC Spanish" in r3 and "bản 2" not in r3, r3   # kênh 2 chưa khai → bỏ qua riêng nó

    # gen_blocks (skeleton) — channel có `lang` → luật vào prompt + nhắc lại cuối; không có → prompt
    # y hệt cũ (test hồi quy: không kênh nào chưa khai lang bị đổi hành vi)
    seen_l = []
    llm.set_hook(lambda sy, u: (seen_l.append(sy), '{"hook":"h","summary":"s"}')[1])
    gen_blocks(brief, "kw", srt, channels=[{"lang": "Vietnamese"}])
    llm.set_hook(None)
    assert "NGÔN NGỮ BẮT BUỘC CỦA KÊNH NÀY LÀ VIETNAMESE" in seen_l[-1], seen_l[-1][:300]
    # NHẮC LẠI phải đứng NGAY TRƯỚC "Trả JSON" (recency) — không chỉ có mặt đâu đó trong prompt
    assert "NHẮC LẠI" in seen_l[-1] and seen_l[-1].index("NHẮC LẠI") < seen_l[-1].rindex("Trả JSON") \
        and seen_l[-1].rindex("Trả JSON") - seen_l[-1].index("NHẮC LẠI") < 120, seen_l[-1][-300:]
    seen_l.clear()
    llm.set_hook(lambda sy, u: (seen_l.append(sy), '{"hook":"h","summary":"s"}')[1])
    gen_blocks(brief, "kw", srt, channels=[{"len": {"summary": 300}}])   # không lang
    llm.set_hook(None)
    assert "NGÔN NGỮ BẮT BUỘC" not in seen_l[-1] and "NHẮC LẠI" not in seen_l[-1], seen_l[-1][:300]

    # gen_mirror — cùng luật, và ĐỨNG TRƯỚC _MIRROR_RULE để không bị khuôn đối thủ (ngôn ngữ khác)
    # lấn át; _MIRROR_RULE cũng tự nhắc "CHỈ HỌC CẤU TRÚC, KHÔNG copy ngôn ngữ của khuôn"
    seen_lm = []
    llm.set_hook(lambda sy, u: (seen_lm.append(sy), '{"text":"t"}')[1])
    gen_mirror(COMP, brief, "kw", srt, channels=[{"lang": "Spanish"}])
    llm.set_hook(None)
    assert "NGÔN NGỮ BẮT BUỘC CỦA KÊNH NÀY LÀ SPANISH" in seen_lm[-1], seen_lm[-1][:300]
    assert seen_lm[-1].index("NGÔN NGỮ BẮT BUỘC") < seen_lm[-1].index("CHỈ HỌC CẤU TRÚC"), \
        "luật ngôn ngữ phải đứng TRƯỚC khuôn đối thủ trong prompt"
    assert "NHẮC LẠI" in seen_lm[-1], "phải nhắc lại ngay trước khi xin JSON"

    # build/build_mirror (đường 1 kênh) tự lấy `lang` từ `profile` (chính là `eff` đã resolve)
    seen_b = []
    llm.set_hook(lambda sy, u: (seen_b.append(sy), '{"hook":"h","summary":"s"}')[1])
    build({"skeleton": ["HOOK", "SUMMARY"], "lang": "Vietnamese"}, brief, "kw", srt)
    llm.set_hook(None)
    assert "NGÔN NGỮ BẮT BUỘC CỦA KÊNH NÀY LÀ VIETNAMESE" in seen_b[-1], seen_b[-1][:300]
    seen_bm = []
    llm.set_hook(lambda sy, u: (seen_bm.append(sy), '{"text":"t"}')[1])
    build_mirror({"lang": "Spanish"}, COMP, brief, "kw", srt)
    llm.set_hook(None)
    assert "NGÔN NGỮ BẮT BUỘC CỦA KÊNH NÀY LÀ SPANISH" in seen_bm[-1], seen_bm[-1][:300]

    print("describe.py self-test OK - 1 call gop chapter, N ban cho N kenh, rap theo skeleton rieng"
          " · do dai theo nguong + cat dung bien cau · mirror theo khuon doi thu + luoi scrub + tran 5000"
          " · ngon ngu kenh bat buoc (uu tien hon kich ban/khuon doi thu)")
