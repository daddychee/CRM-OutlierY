"""Module 4 — 1 TẬP → N KÊNH: sinh mỗi kênh 1 bộ metadata, khác nhau đủ để né trùng.

Bối cảnh: cùng 1 tập được đăng lên nhiều kênh trong mạng lưới. Nếu metadata giống nhau thì
YouTube coi là nội dung trùng lặp → phải khác thật, nhưng vẫn phải đúng phong cách từng kênh.

Chi phí: mọi thứ dùng chung được thì dùng chung — harvest đối thủ 1 lần, brief kịch bản 1 lần,
phân vai tag 1 lần, sinh title 1 call/nhóm-format, sinh description 1 call cho cả N kênh.
→ chọn 5 kênh gần như KHÔNG đắt hơn 1 kênh (~4 call, khác biệt duy nhất là output dài hơn).

Phân công khác biệt (theo lựa chọn của user):
- **Title**: mỗi kênh 1 title KHÁC HẲN (khác desire + công thức) — Python ép unique.
- **Description**: mỗi kênh 1 hook/summary khác, rồi ráp vào skeleton RIÊNG của kênh đó.
- **Tag**: được phép chồng lấn (đòn bẩy yếu nhất, cùng chủ đề thì tag giống nhau là tự nhiên) —
  vẫn xoay vòng 3 bộ sẵn có để các kênh không giống hệt nhau.
- Ngôn ngữ: TẤT CẢ theo ngôn ngữ kịch bản (không dịch) — `llm.OUTPUT_LANG_RULE` lo phần này.
"""
from __future__ import annotations

import os

from . import (common, describe, digest, harvest, library, llm, niche_format, niches, tags,
               thumbtext, titles)

# Trên ngưỡng này thì công tắc kho title bị ÉP BẬT, user không tắt được. Lý do đo được:
# `titles.N_ASK = 8` nên nhóm format đông hơn 8 kênh là mọi kênh dư nhận CHUNG một title —
# lúc đó nguyên liệu rộng là thứ duy nhất còn cứu được độ khác biệt.
BANK_FORCE_N = 8

# Số kênh tối đa cho MỘT call description. `gen_blocks` xin `1200 + 500*n` token trong một
# JSON; 10 kênh = 6.200, còn an toàn. Đây là trần TOKEN, không phải trần chất lượng.
DESC_LOT = 10


def _niche_of(profs: list[dict]) -> str:
    """Niche của tập = niche của kênh đầu tiên có khai. Kho title gắn theo niche."""
    for p in profs:
        n = (p.get("niche") or "").strip()
        if n:
            return n
    return ""


def format_for(prof: dict, explicit: dict | None, all_fmts: list[dict]) -> dict | None:
    """Format cho 1 kênh, theo thứ tự ưu tiên:

    1. **Format ĐÃ GẮN vào kênh** (`profile.format`) — kênh nào học đối thủ nào là cố định.
    2. Format user chọn tay cho run này (nếu có), khi kênh chưa gắn gì.
    3. Suy theo niche của kênh (dự phòng cho profile cũ chưa gắn).
    """
    bound = (prof.get("format") or "").strip()
    if bound:
        hit = next((f for f in all_fmts if f.get("slug") == bound), None)
        if hit:
            return hit
    if explicit:
        return explicit
    niche = (prof.get("niche") or "").strip()
    return next((f for f in all_fmts if (f.get("niche") or "").strip() == niche), None) if niche else None


def _overlap(a: str, b: str) -> float:
    """Tỉ lệ từ chung / độ dài bản dài hơn. Thô nhưng đủ để CẢNH BÁO, không tự sửa."""
    wa = set((a or "").lower().split())
    wb = set((b or "").lower().split())
    return len(wa & wb) / max(len(wa), len(wb)) if wa and wb else 0.0


def _similar(a: str, b: str) -> bool:
    return _overlap(a, b) >= 0.8


NEAR_IDENTICAL = 0.95     # gần như y hệt — mức ĐÁNG LO thật, kể cả với biến thể


def _dup_warnings(items: list[dict]) -> None:
    """Gắn cờ cặp kênh có title/description na ná nhau → user thấy mà xử lý, không giấu.

    Title giữa các kênh CÙNG TẬP vốn là **biến thể 80/20 của chung một pool title đối thủ**
    (user nhắc 2026-07-30) nên chồng lấn 80% là BÌNH THƯỜNG, không phải lỗi. Cảnh báo ở mức đó mà
    không nói gì thêm chỉ tạo báo động giả rồi user bỏ qua luôn cả cảnh báo thật. Nên tách 2 mức:
      · ≥ 0.80  — "gần giống", kèm ghi chú đây là mức bình thường của biến thể
      · ≥ 0.95  — "GẦN NHƯ Y HỆT", đây mới là mức nên sửa tay

    Đoạn HOOK: nếu MỌI kênh có chung một câu mở đầu thì đó là hook user tự viết (hoặc LLM xào
    hỏng nên Python rơi về bản gốc) — lúc đó so 200 ký tự đầu là cặp nào cũng trùng, báo động giả.
    Tự nhận ra bằng cách so chính dữ liệu, KHÔNG nhận cờ từ ngoài: caller có thể truyền sai, còn
    dữ liệu thì không nói dối.
    """
    def _hook_of(x):
        return (x.get("description", {}).get("text", "") or "").split("\n\n", 1)[0].strip()

    hooks = [_hook_of(x) for x in items]
    shared_hook = len(items) > 1 and len(set(hooks)) == 1 and bool(hooks[0])
    if shared_hook:
        for x in items:
            x.setdefault("warnings", []).append(
                "Câu mở đầu Description GIỐNG HỆT mọi kênh — hook do bạn tự viết chưa được xào riêng")
    for i, a in enumerate(items):
        for b in items[i + 1:]:
            ov = _overlap(a["title"]["text"], b["title"]["text"])
            if ov >= NEAR_IDENTICAL:
                for x, y in ((a, b), (b, a)):
                    x.setdefault("warnings", []).append(
                        f"Title GẦN NHƯ Y HỆT kênh {y['channel']} — nên sửa tay 1 trong 2")
            elif ov >= 0.8:
                for x, y in ((a, b), (b, a)):
                    x.setdefault("warnings", []).append(
                        f"Title trùng {round(ov * 100)}% từ với kênh {y['channel']} — "
                        "mức này bình thường với biến thể 80/20, chỉ sửa nếu bạn thấy quá giống")
            # Hook chung cả tập thì đã báo riêng ở trên → bỏ hook ra, chỉ so phần summary.
            da, db = a["description"]["text"], b["description"]["text"]
            if shared_hook:
                da, db = da.split("\n\n", 1)[-1], db.split("\n\n", 1)[-1]
            if _similar(da[:200], db[:200]):
                for x, y in ((a, b), (b, a)):
                    x.setdefault("warnings", []).append(
                        f"Mở đầu Description gần giống kênh {y['channel']}")


def compose_txt(result: dict) -> str:
    """1 file gộp, mỗi kênh 1 section (lựa chọn của user)."""
    out = [f"TẬP: {result.get('_main_title') or result.get('run', '')}",
           f"{len(result['channels'])} kênh · sinh lúc {result.get('created', '')}", ""]
    for c in result["channels"]:
        yt = ", ".join(c["tags"]["tags"])
        meta = ";".join(c["tags"]["tags"])
        des = c["description"]["text"] + (("\n\n" + c["links"]) if c.get("links") else "")
        wr = list(dict.fromkeys(c.get("warnings") or []))
        out += ["=" * 68,
                f"KÊNH: {c['channel']}  [{c['code']}]" + (f"  · {c['lang']}" if c.get("lang") else ""),
                "=" * 68, ""]
        # CẢNH BÁO ĐẶT NGAY ĐẦU SECTION, không dồn xuống cuối. Đo trên file thật (3.353 ký
        # tự): dòng "KHÔNG SINH ĐƯỢC TITLE" nằm ở vị trí 3.227 — tức SAU cả description. Ai
        # copy `TITLE:` ở đầu thì thấy một dòng trống rồi đi dán lên YouTube, không bao giờ
        # cuộn xuống đáy để đọc. Luật "title rỗng phải KÊU TO" mà đặt tiếng kêu ở chỗ không
        # ai nghe thì cũng như không có.
        if wr:
            out += ["⚠ CẢNH BÁO: " + " · ".join(wr), ""]
        # Và nhắc LẠI ngay tại chỗ trống, vì đây mới là dòng người ta bôi đen để copy.
        # THỨ TỰ MỤC (user chốt 06/08): TIÊU ĐỀ → DESCRIPTION → TAG — đúng thứ tự dán lên
        # YouTube Studio, thay khuôn cũ title→tags→description.
        tt = (c["title"]["text"] or "").strip()
        out += ["TITLE:", tt or "⚠ (TRỐNG — chưa sinh được title, ĐỪNG đăng khi chưa điền)",
                "", "DESCRIPTION:", des, "", "YOUTUBE TAGS:", yt, "", "METADATA TAGS:", meta, ""]
    return "\n".join(out)


def generate(run: str, body: dict, status: dict) -> dict:
    """body: {main_url, sub_urls, script, srt, channels:[slug], format?, model?}"""
    common.load_env()
    if body.get("model"):
        os.environ["LLM_MODEL"] = body["model"]
    llm.usage_reset()

    slugs = [common.slug(s) for s in (body.get("channels") or []) if s]
    loaded = [(s, library.load(s)) for s in slugs]
    profs = [p for _, p in loaded if p]
    # Kênh bị xoá sau khi tập đã tick nó → hồ sơ không còn, phải BÁO chứ không bỏ im lặng:
    # user tick 2 kênh mà nhận 1 bộ metadata thì tưởng tool chạy thiếu.
    gone = [s for s, p in loaded if not p]
    if not profs:
        raise RuntimeError("Không nạp được kênh nào — "
                           + (f"kênh đã bị xoá: {', '.join(gone)}" if gone
                              else "tick ít nhất 1 kênh trong danh sách"))
    script, srt = body.get("script", ""), body.get("srt", "")
    n = len(profs)

    all_fmts = niche_format.all_formats()
    explicit = niche_format.load(body["format"]) if body.get("format") else None
    fmts = [format_for(p, explicit, all_fmts) for p in profs]
    effs = [niche_format.resolve(p, f) for p, f in zip(profs, fmts)]

    # ── dùng chung: harvest 1 lần cho cả N kênh (tiết kiệm quota YouTube) ──
    status["step"] = "harvest tag đối thủ…"
    h = harvest.harvest(body.get("main_url", ""), body.get("sub_urls", ""), common.load_keys())
    videos, pool = h["videos"], h["pool"]
    main = next((v for v in videos if v.get("is_main")), videos[0] if videos else {})
    comp_titles = [v.get("title", "") for v in videos]

    if len(script) >= digest.MIN_CHARS:
        status["step"] = "nén brief kịch bản…"
    brief = digest.build(script)
    content = brief or script
    opening = digest.opening(script)

    # ── tag: 1 LẦN gọi LLM phân vai (tốn tiền), rồi ráp bộ RIÊNG cho từng kênh bằng Python
    #    với tag nền của ĐÚNG format kênh đó — kênh A không được dính tag nền của kênh B ──
    status["step"] = "chọn tag…"
    # 1 call annotate dùng chung cho mọi kênh — kèm ứng viên từ description đối thủ như
    # chế độ 1 kênh, nếu không thì cùng 1 tập lại ra bộ tag khác nhau giữa 2 chế độ.
    ann = tags.annotate(pool, main.get("title", ""), content, h.get("desc_meta"))
    tsets_by_ch = [tags.assemble_sets(pool, ann, h["n_videos"], base_tags=e["base_tags"]) for e in effs]
    keyword = ann.get("primary") or (tsets_by_ch[0][0]["tags"][0] if tsets_by_ch[0] and tsets_by_ch[0][0]["tags"]
                                     else main.get("title", ""))
    status["usage"] = llm.usage_snapshot()

    # ── title: 1 call cho mỗi NHÓM cùng format (khác format thì pattern khác nhau) ──
    groups: dict[str, list[int]] = {}
    for i, e in enumerate(effs):
        groups.setdefault(e.get("format_name") or "", []).append(i)
    status["step"] = f"sinh title cho {n} kênh…"
    picked: dict[int, dict] = {}
    dropped: list = []                   # GOM của mọi nhóm — dùng chung 1 dict là nhóm sau xoá nhóm trước
    # KHO THAM KHẢO chạy SONG SONG (user chốt 2026-07-31): outlier THẬT của Format kênh đó học
    # + báo cáo title user tự dán. Chỉ góp Ô để tháo lắp → nhiều biến thể hơn khi 1 tập ra N kênh.
    # KHUNG GỐC vẫn bám `comp_titles` (video đối thủ của tập) — `titles.score` loại thẳng bản nào
    # lấy khung từ kho này, nên đây KHÔNG phải cửa sau làm loãng luật 80/20.
    # CÔNG TẮC: user bật/tắt kho. >BANK_FORCE_N kênh thì ÉP BẬT — quá ngưỡng đó mà chỉ có
    # 3 title của tập làm nguyên liệu thì chắc chắn ra title trùng nhau (đo được: nhóm >8 kênh
    # là mọi kênh dư dùng chung một bản).
    use_bank = body.get("use_bank", True) or n > BANK_FORCE_N
    user_bank = niches.parse_bank(body.get("title_bank") or "")
    ep_niche = _niche_of(profs)
    short: list[str] = []                # nhóm nào KHÔNG xin đủ title — phải nói ra, xem dưới
    mixw: list[str] = []                 # chỗ suýt trộn niche — phải nói ra, xem `niche_mix`
    for key, idxs in groups.items():
        fmt_raw = fmts[idxs[0]] or {}
        # ── KHÔNG TRỘN NICHE (user chốt 2026-08-02) ────────────────────────────────────
        # Kho title/công thức phải lấy theo niche của CHÍNH nhóm kênh này, KHÔNG theo một
        # `ep_niche` chung cho cả tập. Bản cũ lấy niche của KÊNH ĐẦU TIÊN có khai rồi phát
        # cho mọi nhóm ⇒ tick Hidden Globe (Life In) + SpaceX (Space) vào một tập là SpaceX
        # nhận kho của **Life In**. Chất liệu sai niche đi thẳng vào title đăng lên YouTube.
        gn = {(profs[i].get("niche") or "").strip() for i in idxs}
        gn = {x for x in gn if x}
        if len(gn) > 1:
            # Nhóm có kênh khác niche nhau (dùng chung format nhưng khai niche khác) —
            # KHÔNG có kho nào đúng cho cả nhóm, nên thà không dùng kho còn hơn dùng nhầm.
            g_niche = ""
            mixw.append(f"{key or '(chưa gắn format)'}: các kênh trong nhóm khai niche khác "
                        f"nhau ({', '.join(sorted(gn))}) — KHÔNG dùng kho niche cho nhóm này")
        else:
            g_niche = next(iter(gn), "")
        niche_bank = niches.titles_for(g_niche) if (use_bank and g_niche) else []
        # CÔNG THỨC đi đường RIÊNG (prompt), không nhập vào ref_titles — xem chú thích đầu niches.py
        niche_forms = niches.patterns_for(g_niche) if (use_bank and g_niche) else []
        # Outlier của FORMAT chỉ dùng khi format cùng niche với kênh. Format chưa khai niche
        # thì CHO QUA ("chưa khai" ≠ "khác"); khai mà lệch thì bỏ + nói rõ, đừng im lặng dùng.
        f_niche = (fmt_raw.get("niche") or "").strip()
        cross = bool(g_niche and f_niche and f_niche.lower() != g_niche.lower())
        if cross:
            mixw.append(f"{key}: format thuộc niche '{f_niche}' nhưng kênh khai niche "
                        f"'{g_niche}' — KHÔNG lấy outlier của format này làm chất liệu")
        ref = ([e.get("title", "") for e in (fmt_raw.get("evidence") or []) if e.get("title")]
               if (use_bank and not cross) else [])
        # CHIA LÔ ≤ N_ASK. Trước đây gọi MỘT lần cho cả nhóm rồi thiếu thì `cand[-1]` phát lại
        # cho mọi kênh dư — đo được: 12 kênh cùng format ⇒ MỘT title dùng cho 5 kênh, mà cảnh
        # báo lại ghi "nên sửa tay 1 trong 2" (đổ lỗi cho user) chứ không nói tool hết ứng viên.
        # Không nâng `N_ASK` lên bằng số kênh được: cả nhóm nằm trong MỘT JSON, xin 100 phần tử
        # là chạm trần token rồi JSON đứt (đúng lỗi đã cắn ở `_SYS_PACKAGE`).
        # ĐÁNH ĐỔI phải nói trước: từ đây chi phí title hết phẳng, thành tuyến tính — mỗi 8 kênh
        # trong CÙNG một format là thêm một call. Nhóm ≤ 8 kênh (mọi tập hiện tại) không đổi gì.
        cand: list = []
        for s in range(0, len(idxs), titles.N_ASK):
            lot = idxs[s:s + titles.N_ASK]
            trep: dict = {}
            cand += titles.generate(content, comp_titles, n=len(lot), fmt=effs[idxs[0]],
                                    spread=len(idxs) > 1, report=trep,
                                    ref_titles=ref + niche_bank + user_bank,
                                    ref_patterns=niche_forms)
            dropped += [{**d, "format": key} for d in (trep.get("dropped") or [])]
        # Chia lô rồi vẫn có thể thiếu (bản bị chốt chống bịa loại). Lúc đó THÀ ĐỂ TRỐNG còn hơn
        # phát lại bản của kênh khác: title rỗng đã có sẵn đường kêu to (`_warn_no_title`), còn
        # title trùng thì trôi thẳng lên YouTube thành metadata trùng lặp giữa các kênh.
        for j, i in enumerate(idxs):
            picked[i] = cand[j] if j < len(cand) else {"text": "", "score": 0, "chars": 0}
        if len(cand) < len(idxs):
            short.append(f"{key or '(kênh chưa gắn format)'}: xin {len(idxs)} title, chỉ {len(cand)} bản qua được chốt")
    status["usage"] = llm.usage_snapshot()

    # ── description: 1 call ra N bản hook/summary, Python ráp vào skeleton riêng từng kênh ──
    status["step"] = f"sinh description cho {n} kênh…"
    # Truyền tên kênh + Format từng kênh: hook do user viết sẽ được XÀO LẠI theo giọng của kênh
    # tương ứng, thay vì copy y nguyên cho cả tập (user chốt 2026-07-30).
    # `len` = độ dài HOOK+SUMMARY đo được từ chính đối thủ mà kênh đó học (blocks[].chars).
    # Kênh nào học đối thủ viết dài thì viết dài, học đối thủ viết ngắn thì viết ngắn — thay cho
    # một câu "2-4 câu" dùng chung cho mọi kênh.
    # `lang` (06/08): ngôn ngữ THỊ TRƯỜNG kênh nhắm tới (kênh thắng, thiếu thì lấy của niche —
    # xem niche_format.resolve) — bắt buộc description viết đúng ngôn ngữ đó, không rơi về
    # ngôn ngữ kịch bản/khuôn đối thủ khi chúng khác nhau (xem describe._lang_rule).
    ch_desc = [{"name": p.get("channel", ""), "format": (f or {}).get("name", ""),
                "len": describe.target_len(e), "lang": e.get("lang") or p.get("lang", "")}
               for p, f, e in zip(profs, fmts, effs)]
    # CHIA LÔ ≤ DESC_LOT. `gen_blocks` xin `max_tokens = 1200 + 500*n` trong MỘT call, nên n
    # lớn là vượt trần model rồi JSON đứt giữa chừng — đo được: 12 kênh đã là 7.200 token, 100
    # kênh là 51.200. Cắt lô giữ trần ở 6.200 bất kể bao nhiêu kênh.
    # `chaps` lấy của lô ĐẦU: chapter neo từ SRT nên mọi kênh dùng chung, xin lại mỗi lô là trả
    # tiền cho cùng một kết quả.
    # KHUÔN ĐỐI THỦ (user chốt 06/08): video đối thủ CHÍNH (link đầu tiên) có description →
    # viết theo ĐÚNG cấu trúc bản đó, đan cụm khóa đo từ chính các link đối thủ (desc_meta).
    # Video chính không có description → giữ nguyên đường skeleton cũ, không đổi hành vi.
    comp_desc = (main.get("description") or "").strip()
    blocks, chaps = [], []
    for s in range(0, n, DESC_LOT):
        lot = ch_desc[s:s + DESC_LOT]
        if comp_desc:
            b, c = describe.gen_mirror(comp_desc, content, keyword, srt, opening, n=len(lot),
                                       user_hook=body.get("hook", ""),
                                       user_chapters=body.get("chapters", ""),
                                       channels=lot,
                                       phrases=(h.get("desc_meta") or {}).get("phrases"))
        else:
            b, c = describe.gen_blocks(content, keyword, srt, opening, n=len(lot),
                                       user_hook=body.get("hook", ""),
                                       user_chapters=body.get("chapters", ""),
                                       channels=lot)
        blocks += b
        chaps = chaps or c
    # `compose` đọc `blocks[i]` cho mọi i < n — thiếu là IndexError giết cả lần chạy sau khi đã
    # tiêu quota + mọi call LLM. Bù bản rỗng rồi để `_warn_no_desc` kêu, đừng để nổ.
    while len(blocks) < n:
        blocks.append({})

    out = []
    for i, (p, e) in enumerate(zip(profs, effs)):
        des = describe.compose(e, blocks[i], chaps, keyword)
        des["sigs"]["rule_hits"] = niche_format.check_rules(des["text"], e.get("rules") or {})
        # Mang theo SỐ ĐO ĐỘ DÀI summary. `compose` chỉ trả text đã ráp nên nếu không chép sang
        # đây thì `result.json` mất hẳn — mà đó đúng là thứ cho biết bản này có bám được độ dài
        # của Format kênh không. Trượt mục tiêu phải THẤY ĐƯỢC, không lặng lẽ trôi qua.
        for k in ("summary_target", "summary_len", "summary_trimmed"):
            if k in blocks[i]:
                des[k] = blocks[i][k]
        t = dict(picked[i])
        t["rule_hits"] = niche_format.check_rules(t.get("text", ""), e.get("rules") or {})
        out.append({"slug": p["slug"], "channel": p.get("channel", ""), "code": p.get("code", ""),
                    "lang": p.get("lang", ""), "niche": p.get("niche", ""),
                    "links": p.get("links", ""), "format": (fmts[i] or {}).get("name", ""),
                    "skeleton_source": e["source"], "title": t,
                    # xoay vòng 3 bộ để các kênh không trùng bộ tag y hệt nhau
                    "tags": tsets_by_ch[i][i % len(tsets_by_ch[i])] if tsets_by_ch[i] else {"tags": [], "name": ""},
                    "description": des})
    # n>1 thì hook đã được xào riêng từng kênh nên so được như thường; chỉ khi n==1 mới dùng
    # nguyên văn (mà 1 kênh thì chẳng có cặp nào để so).
    # Kênh không sinh được title nào (mọi ứng viên bị loại) → phải KÊU TO. Trước đây lặng lẽ ghi
    # title rỗng vào metadata.txt, user chỉ phát hiện khi dán lên YouTube. Cắn LIVE 2026-07-30.
    for i, c in enumerate(out):
        if not (c.get("title") or {}).get("text", "").strip():
            c.setdefault("warnings", []).insert(
                0, "KHÔNG SINH ĐƯỢC TITLE cho kênh này — mọi ứng viên đều bị loại "
                   "(xem mục 'Đã loại' để biết lý do). Bấm ↻ Sinh lại hoặc sửa tay.")
        # NGÔN NGỮ LỆCH — đặt NGAY SAU cảnh báo title rỗng vì nó thường là NGUYÊN NHÂN của
        # cảnh báo đó. Không có nó thì user đọc "mọi ứng viên đều bị loại" rồi đi bấm Sinh lại
        # mãi, trong khi lỗi nằm ở chỗ gắn format khác thứ tiếng — bấm bao nhiêu lần cũng vậy.
        warn = niche_format.lang_mismatch(profs[i], fmts[i])
        if warn:
            c.setdefault("warnings", []).insert(
                1 if c.get("warnings") else 0, "NGÔN NGỮ LỆCH: " + warn)
    _dup_warnings(out)

    # Chế độ nhiều kênh cũng phải có bằng chứng đối thủ như chế độ 1 kênh — trước đây nuốt im
    # lặng: user dán chữ thumb, tool đã đo desc_meta, nhưng result không mang gì nên board hiện
    # số liệu của RUN TRƯỚC, đọc nhầm là của tập này.
    # TEXT ON THUMB: nguồn DUY NHẤT là kho niche (user chốt 2026-07-31 — "tôi sẽ cập nhật cho
    # bạn vào kho và bạn sẽ gợi ý bằng cách lấy từ kho ra thôi"). Ô dán-theo-từng-tập đã GỠ:
    # nó buộc user gõ lại cho mỗi tập đúng thứ tự URL, mà kho niche đã giữ sẵn thứ tốt hơn.
    tt_niche = niches.thumbs_for(ep_niche)
    tt = thumbtext.analyze("\n".join(tt_niche), comp_titles) if tt_niche else {}
    result = {"mode": "episode", "channels": out, "keyword": keyword,
              "n_videos": h["n_videos"], "created": library.now_iso(),
              "main_url": body.get("main_url", ""), "_main_title": main.get("title", ""),
              "desc_meta": h.get("desc_meta") or {},
              "thumb": {"analysis": tt, "rules": thumbtext.rules(tt),
                        # Gợi ý CHỈ lấy từ kho, xếp theo độ liên quan với video này.
                        "suggest": thumbtext.suggest(tt, (out[0].get("title") or {}).get("text", "")
                                                     if out else "", keyword,
                                                     bank=tt_niche)} if tt else {},
              "usage": llm.usage_snapshot(), "gone_channels": gone,
              # `niche_mix`: chỗ tool CHỦ ĐỘNG không dùng kho vì sẽ trộn niche. Im lặng bỏ thì
              # user thấy ít biến thể hơn mà không hiểu vì sao, rồi đi dán thêm title vào kho
              # — đúng thứ không giúp được gì.
              "titles_dropped": dropped, "titles_short": short, "niche_mix": mixw,
              "_pool": pool, "_comp_titles": comp_titles, "_brief": brief,
              "_main_desc": comp_desc}                     # khuôn đối thủ — sinh lại không re-harvest
    rd = common.run_dir(run, create=True)
    common.write_json(rd / "result.json", result)
    (rd / "metadata.txt").write_text(compose_txt({**result, "run": run}), encoding="utf-8")
    status["usage"] = result["usage"]
    return result


if __name__ == "__main__":                                  # self-test offline (seed giả + monkeypatch LLM)
    import json
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        common.ROOT, common.PROFILES, common.RUNS = Path(tmp), Path(tmp) / "profiles", Path(tmp) / "runs"
        for slug, ch, code, skel, links in [
                ("cosmic-lens-cl-01", "Cosmic Lens", "CL-01", ["HOOK", "SUMMARY", "CHAPTERS"], "SUB: https://a"),
                ("outland-o-01", "Outland", "O-01", ["HOOK", "SUMMARY"], "SUB: https://b"),
                ("sleep-sc-01", "Sleep Calm", "SC-01", [], "")]:
            common.write_json(common.profiles_dir(create=True) / f"{slug}.json",
                              {"channel": ch, "code": code, "skeleton": skel, "niche": "Space",
                               "lang": "English", "links": links})

        seed = [{"id": "A", "title": "The Monster at the Center", "description": "", "views": 900_000,
                 "tags": ["sagittarius a*", "black hole"], "is_main": True},
                {"id": "B", "title": "What Is a Black Hole", "description": "", "views": 40_000,
                 "tags": ["black hole"], "is_main": False}]
        harvest.harvest = lambda m, s, k: {"videos": seed, "pool": harvest.build_pool(seed), "n_videos": 2}

        calls = []
        # Phải là THÁO-LẮP (thay ô), không phải NỐI THÊM: title chứa trọn 1 title đối thủ thì
        # keep_ratio = 1.0 → bị coi là chép nguyên văn và loại thẳng, đúng ý đồ.
        MIXES = ["The Black Hole at the Center",                  # A, thay "Monster"→"Black Hole"
                 "A Black Hole at the Center of the Monster",
                 "What Is the Monster",                           # B, thay "a Black Hole"→"the Monster"
                 "The Monster at the Black Hole",
                 "What Is the Center",
                 "The Monster Black Hole"]

        def route(sysmsg, user):
            calls.append(sysmsg[:40])
            if "BRIEF" in sysmsg:
                return '{"topic":"Sgr A*","entities":["Sagittarius A*"],"beats":["b"],"desires":["dread"],"keywords":["black hole"],"promise":"p"}'
            if "tag ứng viên" in sysmsg:
                return '{"primary":"sagittarius a*","tags":[{"tag":"sagittarius a*","keep":true,"role":"primary"},{"tag":"black hole","keep":true,"role":"broad"}]}'
            if "MARKETING" in sysmsg:
                # Phải là bản KẾT HỢP thật từ 2 title trong seed: titles.score truy nguyên từng cụm,
                # title bịa chữ ngoài pool + kịch bản sẽ bị loại thẳng (luật 2026-07-29).
                return json.dumps([{"text": t, "desire": "d", "technique": "t",
                                    "awareness": "Unaware", "proof": True} for t in MIXES])
            return json.dumps({"variants": [{"hook": f"Hook {i} Sagittarius A*", "summary": f"Sum {i}"}
                                            for i in range(3)], "chapters": []})
        llm.set_hook(route)
        res = generate("ep1", {"main_url": "A", "sub_urls": "B", "script": "kb " * 900, "srt": "",
                               "channels": ["cosmic-lens-cl-01", "outland-o-01", "sleep-sc-01"]}, {})
        llm.set_hook(None)

        ch = res["channels"]
        assert len(ch) == 3, ch
        assert res["gone_channels"] == [], res["gone_channels"]
        assert len(calls) == 4, calls                       # 3 kênh vẫn chỉ 4 call (digest/tag/title/des)
        assert len({c["title"]["text"] for c in ch}) == 3, [c["title"]["text"] for c in ch]  # title khác nhau
        assert len({c["description"]["text"] for c in ch}) == 3, ch                          # description khác nhau
        assert "⏱" not in ch[1]["description"]["text"], ch[1]        # kênh O-01 skeleton không có CHAPTERS
        assert ch[2]["skeleton_source"] == "standard", ch[2]         # kênh chưa extract → standard
        assert ch[0]["links"] == "SUB: https://a", ch[0]
        txt = (common.run_dir("ep1") / "metadata.txt").read_text(encoding="utf-8")
        assert txt.count("KÊNH:") == 3 and "SUB: https://a" in txt, txt[:400]
        assert ("at the Center" in txt or "Black Hole" in txt) and "TẬP:" in txt
        # THỨ TỰ MỤC (user chốt 06/08): TITLE → DESCRIPTION → TAG — ghim để không ai đảo lại
        assert txt.index("TITLE:") < txt.index("DESCRIPTION:") < txt.index("YOUTUBE TAGS:"), txt[:600]

        # kênh đã bị xoá mà tập vẫn tick → BỎ QUA nhưng phải BÁO, không im lặng
        llm.set_hook(route)
        res2 = generate("ep2", {"main_url": "A", "sub_urls": "B", "script": "kb " * 900, "srt": "",
                                "channels": ["cosmic-lens-cl-01", "kenh-da-bi-xoa"]}, {})
        llm.set_hook(None)
        assert len(res2["channels"]) == 1 and res2["gone_channels"] == ["kenh-da-bi-xoa"], res2["gone_channels"]

        # ── thứ tự ưu tiên format: GẮN vào kênh > chọn tay > suy theo niche ──
        FS = [{"slug": "sleep-fmt", "name": "Sleep", "niche": "Sleep"},
              {"slug": "space-a", "name": "SpaceA", "niche": "Space"},
              {"slug": "space-b", "name": "SpaceB", "niche": "Space"}]
        run_pick = {"slug": "run-fmt", "name": "ChonTay", "niche": "Space"}
        # kênh đã GẮN space-b → thắng cả format chọn tay cho run này
        assert format_for({"format": "space-b", "niche": "Space"}, run_pick, FS)["slug"] == "space-b"
        assert format_for({"niche": "Space"}, run_pick, FS)["slug"] == "run-fmt"      # chưa gắn → chọn tay
        assert format_for({"niche": "Space"}, None, FS)["slug"] == "space-a"          # dự phòng: khớp niche đầu tiên
        assert format_for({"format": "da-bi-xoa", "niche": "Sleep"}, None, FS)["slug"] == "sleep-fmt"
        assert format_for({}, None, FS) is None                                       # không niche, không gắn

        # cảnh báo trùng: 2 kênh nhận title y hệt → phải gắn cờ
        dup = [{"channel": "A", "title": {"text": "Same Title Here"}, "description": {"text": "x"}},
               {"channel": "B", "title": {"text": "Same Title Here"}, "description": {"text": "y"}}]
        _dup_warnings(dup)

        # ── CẢNH BÁO TRÙNG: 2 mức, và gọi tên cặp KÊNH ANH EM (user chốt 2026-07-30) ──
        NL = chr(10) * 2
        def _w(a_txt, b_txt, **kw):
            it = [{"slug": "a", "channel": "A", "title": {"text": a_txt},
                   # hook KHÁC nhau: khối này chỉ test luật của TITLE, đừng để lẫn cảnh báo hook
                   "description": {"text": "hook rieng cua A" + NL + "Summary cua A rat rieng biet"}},
                  {"slug": "b", "channel": "B", "title": {"text": b_txt},
                   "description": {"text": "mo dau khac han ben B" + NL + "Noi dung hoan toan khac cua kenh B"}}]
            _dup_warnings(it, **kw)
            return " | ".join(it[0].get("warnings", []))

        # biến thể 80/20 chồng lấn cao là BÌNH THƯỜNG → cảnh báo nhẹ, có nói rõ
        soft = _w("Life in FINLAND HAPPIEST Country on Earth PRISTINE",     # 7/8 từ chung = 0.875
                  "Life in FINLAND HAPPIEST Country on Earth GIRLS")
        assert "bình thường với biến thể" in soft and "GẦN NHƯ Y HỆT" not in soft, soft
        # gần như y hệt mới là mức đáng sửa tay
        hard = _w("Life in FINLAND HAPPIEST Country on Earth",
                  "Life in FINLAND HAPPIEST Country on Earth")
        assert "GẦN NHƯ Y HỆT" in hard, hard
        # title khác hẳn → im lặng
        assert _w("Life in FINLAND happiest country", "Sleep music for deep rest tonight") == ""

        # hook do USER viết → mọi kênh dùng chung, phải bỏ hook ra mới so description
        same_hook = [{"slug": "a", "channel": "A", "title": {"text": "x1 y1 z1"},
                      "description": {"text": "HOOK CHUNG CUA USER" + NL + "Summary A khac hoan toan"}},
                     {"slug": "b", "channel": "B", "title": {"text": "q2 w2 e2"},
                      "description": {"text": "HOOK CHUNG CUA USER" + NL + "Noi dung B rat rieng"}}]
        _dup_warnings(same_hook)
        w = " | ".join(same_hook[0].get("warnings") or [])
        assert "GIỐNG HỆT mọi kênh" in w, w                        # tự nhận ra, không cần cờ ngoài
        assert "Mở đầu Description gần giống" not in w, w          # và KHÔNG báo động giả thêm lần nữa
        assert dup[0]["warnings"] and "B" in dup[0]["warnings"][0], dup
    print("episode.py self-test OK - 3 kenh / 4 call, title+description khac nhau, skeleton rieng, 1 file gop")
