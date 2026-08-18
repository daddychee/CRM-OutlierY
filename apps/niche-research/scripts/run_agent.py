"""AGENT RUNNER — executes one of the LLM judgement stages (S9b namer / S12 auditor / S13 plan /
S16-17 dna / S19 summary) using whichever provider is configured in .env (see llm_provider.py:
Claude / ChatGPT / GLM / Grok / any custom OpenAI-compatible endpoint).

Usage: python3 run_agent.py <niche-data dir> <namer|auditor|plan|dna|summary>

This is what turns the tool into a REAL Python+LLM hybrid. Without it, S9b/S12/S13/S16-17 are
unexecuted specs (agents/*.md) and every "verdict" in the report (crackability OPEN/CLOSED,
candidate-bet STRONG/WEAK, etc.) is a Python threshold rule, not a model's judgement.

The exact input/output contract for each agent lives in agents/*.md — that file IS the system
prompt fed to the model (single source of truth, no duplicated instructions to drift out of sync).
"""
import sys, os, re, glob, json
from llm_provider import call_role, extract_json, validate_json, LLMError
from _common import get_env

WORK  = sys.argv[1] if len(sys.argv) > 1 else "."
AGENT = sys.argv[2] if len(sys.argv) > 2 else None
TOOL_ROOT  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AGENTS_DIR = os.path.join(TOOL_ROOT, "agents")


def p(f): return os.path.join(WORK, f)
def spec(name): return open(os.path.join(AGENTS_DIR, f"{name}.md"), encoding="utf-8").read()
def load(f): return json.load(open(p(f), encoding="utf-8"))
def save(f, obj): json.dump(obj, open(p(f), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

def call_with_json_retry(role, system, user, *, work, max_tokens, cache_prefix=None, label="agent"):
    """Call LLM and parse JSON. If parse fails, retry ONCE with a corrective prompt that shows
    the error and asks the model to return valid JSON. This catches truncation (model self-trims
    on retry) and syntax errors (model fixes its own formatting)."""
    text, prov = call_role(role, system, user, work=work, max_tokens=max_tokens, cache_prefix=cache_prefix)
    try:
        return extract_json(text), prov
    except LLMError as e:
        # Retry: tell the model what went wrong and ask for valid JSON
        retry_prompt = (
            f"Output trước đó của bạn KHÔNG parse được JSON: {e}\n\n"
            f"Hãy trả lại JSON hợp lệ, đảm bảo:\n"
            f"- Mọi string đều được bọc bởi dấu ngoặc kép \" \"\n"
            f"- Không có dấu phẩy thừa hoặc thiếu\n"
            f"- Không có ký tự điều khiển (newline thô) trong string — dùng \\n thay thế\n"
            f"- Nếu output quá dài, rút gọn nội dung nhưng GIỮ cấu trúc JSON\n\n"
            f"Output gốc (có thể bị cắt):\n{text[-3000:]}"
        )
        text2, prov2 = call_role(role, system + "\n\n⚠ LƯU Ý: output trước bị lỗi JSON, hãy cẩn thận.",
                                 retry_prompt, work=work, max_tokens=max_tokens, cache_prefix=cache_prefix)
        out = extract_json(text2)  # if this fails, it raises — caller catches LLMError
        print(f"  ℹ {label}: JSON repaired on retry (1st attempt failed: {str(e)[:80]})")
        return out, prov2


def run_namer():
    d = load("subniche.json")
    system = spec("subniche_namer") + ("\n\nReturn ONLY a JSON object "
             '{"clusters":[{"anchor":"...","label":"...","intent":"browse|search"}, ...]} '
             "— one entry per input cluster (match by 'anchor'), no commentary outside the JSON.")
    user = json.dumps({"clusters": d.get("clusters", [])}, ensure_ascii=False)
    out, provider = call_with_json_retry("default", system, user,
                               work=WORK, max_tokens=8192, label="namer")
    validate_json(out, ["clusters"], "namer")
    by_anchor = {c.get("anchor"): c for c in out.get("clusters", []) if isinstance(c, dict)}
    n = 0
    for c in d.get("clusters", []):
        m = by_anchor.get(c.get("anchor"))
        if m:
            c["label"] = m.get("label", c.get("label")); c["intent"] = m.get("intent"); n += 1
    save("subniche.json", d)
    open(p("_s9b_namer.done"), "w").write(provider)   # marker: this exact subniche.json has been labeled
    print(f"namer ({provider}) — labeled {n}/{len(d.get('clusters', []))} clusters -> subniche.json")


def run_auditor():
    bets = load("bets.json")
    # R-0 INFORMATION ISOLATION (audit V16): strip the Builder's CONCLUSIONS before the Auditor sees
    # the file — architecture §5: "do NOT show the Auditor the Builder's reasoning". The Auditor must
    # judge from the deterministic signals + raw titles alone and write its OWN falsifiers; feeding it
    # builder_verdict/generic_risk/falsifier anchors it into a rubber stamp.
    STRIP = ("builder_verdict", "generic_risk", "falsifier", "topic_group")
    iso = {k: v for k, v in bets.items() if k != "note"}
    iso["bets"] = [{k: v for k, v in b.items() if k not in STRIP} for b in bets.get("bets", [])]
    system = spec("auditor") + ('\n\nReturn ONLY a JSON object '
             '{"rounds":1,"final_bets":[...],"disagreements":[...]} matching the shape shown above '
             "— no commentary outside the JSON.")
    user = json.dumps(iso, ensure_ascii=False)
    out, provider = call_with_json_retry("auditor", system, user,
                               work=WORK, max_tokens=16000, label="auditor")
    validate_json(out, ["final_bets"], "auditor")
    # provenance for the report's honesty label (V17b): 1-model = "design-only verify", 2 = real leg
    out["_meta"] = {"auditor_provider": provider,
                    "default_provider": get_env("LLM_PROVIDER", WORK, "anthropic"),
                    "builder_fields_stripped": list(STRIP)}
    save("bets_audited.json", out)
    print(f"auditor ({provider}) — {len(out.get('final_bets', []))} final bets, "
          f"{len(out.get('disagreements', []))} disagreements -> bets_audited.json "
          f"(builder verdict/falsifier stripped from input — R-0)")


def run_plan():
    d1 = load("decision1.json"); d2 = load("decision2.json")
    bets = load("bets_audited.json") if os.path.exists(p("bets_audited.json")) else (
           load("bets.json") if os.path.exists(p("bets.json")) else {})
    dna = load("dna.json") if os.path.exists(p("dna.json")) else None
    system = spec("execution_plan") + "\n\nReturn ONLY the JSON object described above — no commentary."
    user = json.dumps({"decision1": d1, "decision2": d2, "bets": bets, "dna": dna}, ensure_ascii=False)
    out, provider = call_with_json_retry("default", system, user,
                               work=WORK, max_tokens=4096, label="plan")
    validate_json(out, ["verdict"], "execution_plan")
    save("execution_plan.json", out)
    print(f"plan ({provider}) — verdict: {out.get('verdict', '?')!r} -> execution_plan.json")


def run_dna():
    tdir = os.environ.get("NICHE_TRANSCRIPTS_DIR") or p("transcripts")
    files = sorted(glob.glob(os.path.join(tdir, "*.txt")))
    if not files:
        raise SystemExit(f"no transcripts found in {tdir} — run the deep-dive (--deepdive) first.")
    def sample_transcript(txt, head=3500, mid=1500, tail=1500):
        """Head + middle + tail instead of the old first-6000-chars cut (audit V20): the DNA spec
        analyses full-video STRUCTURE/arc, which the opening third alone cannot show."""
        if len(txt) <= head + mid + tail: return txt
        m0 = (len(txt) - mid) // 2
        return (txt[:head] + "\n[... GIỮA BÀI ...]\n" + txt[m0:m0+mid]
                + "\n[... CUỐI BÀI ...]\n" + txt[-tail:])
    chunks = []
    for f in files[:30]:
        txt = sample_transcript(open(f, encoding="utf-8").read())
        chunks.append(f"### {os.path.basename(f)}\n{txt}")
    system = spec("dna_extractor") + "\n\nReturn ONLY the JSON object matching contracts/dna.schema.json — no commentary."
    user = "\n\n".join(chunks)
    out, provider = call_with_json_retry("default", system, user,
                               work=WORK, max_tokens=16000, label="dna")
    validate_json(out, ["hook_patterns"], "dna")
    save("dna.json", out)
    print(f"dna ({provider}) — extracted from {len(chunks)} transcripts -> dna.json")


def _evidence_pack():
    """COMPREHENSIVE evidence for the summary — reads EVERY artifact in the research so no signal is
    left out (the user's explicit requirement). Bounded per-list so the payload stays token-sane, but
    it spans: all 5 decision files, the FULL keyword analysis, the FULL comment gaps, sub-niches, bets,
    the top outliers by absolute reach, cross-channel PATTERNS, format/length mix, and channel coverage."""
    import re, statistics
    from collections import Counter, defaultdict
    from _common import compute_outliers, winners, get_scan_time, tokenize

    def opt(f):
        try: return load(f)
        except Exception: return None

    an = opt("analysis.json") or {}
    gaps = opt("gaps.json") or {}
    pack = {
        # --- decision layer (verbatim, small) ---
        "decision1": opt("decision1.json"), "crackability": opt("crackability.json"),
        "monetization": opt("monetization.json"), "demand": opt("demand.json"),
        "decision2": opt("decision2.json"), "subniche": opt("subniche.json"),
        "bets_audited": opt("bets_audited.json"),
        "bets": opt("bets.json") if not os.path.exists(p("bets_audited.json")) else None,
        "execution_plan": opt("execution_plan.json"),
        "dna": opt("dna.json"),
        # --- keyword / title analysis (§5 winning formula) — top signal, long tail trimmed for tokens ---
        "lift_unigrams": an.get("lift_unigrams", [])[:25],
        "lift_bigrams": an.get("lift_bigrams", [])[:18],
        "core_keywords": an.get("unigrams", [])[:22],
        "phrases_bigrams": an.get("bigrams", [])[:15],
        "phrases_trigrams": an.get("trigrams", [])[:12],
        "title_templates": an.get("templates", [])[:20],
        "openers": an.get("openers", [])[:15],
        "emphasis_words": an.get("emphasis", [])[:20],
        # tags the competitors themselves set (+ which over-index in winners) — §Winning-Format: tags
        "top_tags": an.get("tags", [])[:25],
        "lift_tags": an.get("lift_tags", [])[:20],
        "analysis_counts": {"total_videos": an.get("total_videos"), "total_channels": an.get("total_channels"),
                            "n_winners": an.get("n_winners"), "n_normal": an.get("n_normal")},
        # --- FULL comment gaps (§6 question goldmine) ---
        "gap_themes": (gaps.get("themes") or [])[:20],
        "top_questions": (gaps.get("top_questions") or [])[:20],
        "gap_totals": {"total_questions": gaps.get("total_questions"), "total_comments": gaps.get("total_comments")},
    }

    # --- videos.json: outliers by ABSOLUTE reach + patterns + WINNING-FORMAT stats ---
    try:
        from _common import normals
        vids = load("videos.json"); _n_raw = len(vids)
        compute_outliers(vids, get_scan_time(WORK))
        pack["shorts_blocked"] = _n_raw - len(vids)   # shorts gate (0 on new scans — S1 filters)
        valid = winners(vids)          # shared winner rule + pinned time (V7/V12)
        norm = normals(vids)
        strong = sorted(valid, key=lambda x: -x.get("excess", 0))
        pack["top_outliers"] = [{"title": x["title"], "channel": x.get("channelTitle"), "ox": x.get("ox"),
                                 "excess": x.get("excess"), "views": x.get("viewCount"), "fmt": x.get("fmt"),
                                 "duration_s": x.get("dur_s"), "age_days": round(x.get("age") or 0)}
                                for x in strong[:22]]
        pack["n_valid_outliers"] = len(valid); pack["n_videos"] = len(vids)
        # cross-channel PATTERNS (keyword clusters of outliers across >=3 channels, ranked by Σexcess)
        toks = tokenize                # shared stop-list (V5)
        kw_ch = defaultdict(set); kw_ex = defaultdict(int); kw_n = defaultdict(int)
        for x in valid:
            for w in set(toks(x["title"])):
                kw_ch[w].add(x["channelId"]); kw_ex[w] += max(x.get("excess", 0), 0); kw_n[w] += 1
        pats = [{"keyword": w, "n_outliers": kw_n[w], "n_channels": len(kw_ch[w]), "sum_excess": kw_ex[w]}
                for w in kw_ch if len(kw_ch[w]) >= 3 and kw_n[w] >= 3]
        pack["patterns"] = sorted(pats, key=lambda r: -r["sum_excess"])[:20]
        # ---- WINNING-FORMAT numbers (Python MEASURES the correlations; the LLM only interprets) ----
        # format & length mix: winners vs normals per format, with share % and p25/median/p75 duration
        def _q(vals, q):
            s = sorted(vals); return s[min(len(s) - 1, int(q * len(s)))] if s else None
        fmt_c = Counter(x.get("fmt") for x in valid); fmt_n = Counter(x.get("fmt") for x in norm)
        durs = defaultdict(list)
        for x in valid:
            if x.get("dur_s"): durs[x.get("fmt")].append(x["dur_s"])
        nw = max(len(valid), 1)
        pack["format_mix"] = {f: {"n_outliers": fmt_c.get(f, 0),
                                  "share_of_outliers_pct": round(100 * fmt_c.get(f, 0) / nw, 1),
                                  "n_normals": fmt_n.get(f, 0),
                                  "median_len_s": round(statistics.median(durs[f])) if durs.get(f) else None,
                                  "p25_len_s": _q(durs.get(f, []), 0.25), "p75_len_s": _q(durs.get(f, []), 0.75)}
                              for f in ("Short", "Mid", "Long")}
        # title-structure features: share of winner titles vs normal titles carrying each feature.
        # ratio >> 1 = the feature CO-OCCURS with winning (correlation, not causation — R-3).
        def _tf(xs):
            n = max(len(xs), 1)
            def share(rx): return round(100 * sum(1 for x in xs if re.search(rx, x.get("title") or "")) / n, 1)
            wl = [len((x.get("title") or "").split()) for x in xs]
            return {"n": len(xs),
                    "pct_caps_word": share(r"\b[A-Z]{3,}\b"),      # INSANE / SHOCKING ...
                    "pct_number": share(r"\d"),
                    "pct_year": share(r"\b(19|20)\d{2}\b"),
                    "pct_question_mark": share(r"\?"),
                    "median_title_words": int(statistics.median(wl)) if wl else None}
        pack["title_features"] = {"winners": _tf(valid), "normals": _tf(norm),
                                  "note": "so % winners vs normals: chênh lệch lớn = đặc điểm ĐI KÈM video thắng (liên hệ, không nhân quả)"}
        # cadence: uploads in the last 90 days per channel -> median uploads/month of ACTIVE channels
        up90 = defaultdict(int)
        for x in vids:
            if x.get("age") is not None and x["age"] <= 90: up90[x["channelId"]] += 1
        if up90:
            pack["cadence"] = {"median_uploads_per_month_per_channel": round(statistics.median(list(up90.values())) / 3.0, 1),
                               "n_active_channels_90d": len(up90)}
    except Exception as e:
        pack["top_outliers"] = []; pack["patterns"] = []; pack["_videos_error"] = str(e)

    # global browse-vs-search share, size-weighted over sub-niche clusters (numbers S9 already computed)
    try:
        cl = [c for c in (pack.get("subniche") or {}).get("clusters", []) if c.get("browse_vs_search") is not None]
        tot = sum(c.get("size", 0) for c in cl)
        if tot:
            pack["browse_share_weighted"] = round(sum(c["browse_vs_search"] * c.get("size", 0) for c in cl) / tot, 2)
    except Exception:
        pass

    # --- channels.json: coverage + who the big players are (§2 white space, §7 cadence) ---
    try:
        ch = load("channels.json")
        rows = []
        for cid, i in ch.items():
            rows.append({"channel": i.get("title"), "subs": int(i.get("subs") or 0),
                         "videoCount": int(i.get("videoCount") or 0)})
        pack["channels"] = sorted(rows, key=lambda r: -r["subs"])[:25]
        pack["n_channels_scanned"] = len(ch)
    except Exception:
        pack["channels"] = []
    return pack


def run_summary():
    """S19 — turn ALL the research numbers into a concrete expert action-guide via a rigorous 3-pass
    SELF-critique loop (draft -> adversarial critique -> refine) on the single configured model. The
    discipline of the loop, not swapping models, is what keeps the guide practical and defensible."""
    method = spec("summary")
    pack = _evidence_pack()
    if not pack.get("decision1"):
        raise SystemExit("summary needs decision1.json (run the deterministic pipeline first).")
    ev = json.dumps(pack, ensure_ascii=False)
    # TOKEN GUARD: estimate tokens (~4 chars/token for mixed JSON) and trim if the evidence pack
    # is too large to leave room for the method prompt + 3 LLM outputs within a typical 200K context.
    est_tokens = len(ev) // 4
    if est_tokens > 100000:
        # aggressive trim: cut long lists in half
        for key in ("top_outliers", "patterns", "channels", "lift_unigrams", "lift_bigrams",
                     "core_keywords", "gap_themes", "top_questions", "title_templates",
                     "top_tags", "lift_tags"):
            if isinstance(pack.get(key), list) and len(pack[key]) > 10:
                pack[key] = pack[key][:len(pack[key])//2]
        ev = json.dumps(pack, ensure_ascii=False)
        est_tokens = len(ev) // 4
        print(f"  ⚠ evidence pack trimmed to ~{est_tokens:,} tokens (was >100K)")
    # TOKEN SAVER: method + evidence are STATIC across all 3 passes -> send them ONCE as a cached
    # prefix (Anthropic explicit cache_control; OpenAI/GLM automatic prefix cache). Passes 2 & 3
    # reuse it at ~10% cost and never re-send the evidence in their user message.
    base_prefix = method + "\n\n=== EVIDENCE PACK (đọc HẾT — dùng cho cả 3 lượt) ===\n" + ev

    # ---- PASS 1: DRAFT A SKELETON (small JSON, robust) — the full 10-section content is written as
    # raw markdown in PASS 3 from the same evidence; the draft only needs the strategic spine. ----
    draft_sys = ("=== LƯỢT 1 — SOẠN KHUNG CHIẾN LƯỢC ===\nĐọc HẾT evidence pack (format_mix, title_features, "
                 "patterns, lift_tags, cadence, browse_share_weighted, gap_themes, channels — đừng bỏ nguồn "
                 "nào). CHƯA cần viết đầy đủ 10 mục; chỉ chốt bộ khung để lượt sau phản biện. Trả về CHỈ JSON "
                 "NGẮN GỌN: {\"verdict\":\"GO|CÂN NHẮC|NO-GO\",\"confidence\":\"VERIFIED|TENTATIVE\","
                 "\"thesis\":\"luận điểm 1 câu\",\"beachhead\":\"...\","
                 "\"winning_format\":{\"duration\":\"kết luận thời lượng + số dẫn chứng\",\"topics\":\"3-5 "
                 "sub-format có tên + Σexcess\",\"title\":\"công thức tiêu đề + số title_features\","
                 "\"thumbnail\":\"suy luận từ browse share + emphasis (ghi rõ là suy luận)\",\"tags\":\"bộ tag "
                 "nên đặt\",\"cadence\":\"nhịp đăng khuyến nghị + số\"},"
                 "\"key_points\":[\"nhận định chính, MỖI cái gắn 1 con số + nguồn (tối đa ~10 gạch, phủ: cầu, "
                 "kiếm tiền, khả phá, cạnh tranh, đầu cầu, 3-5 ý tưởng video cụ thể, gap câu hỏi)\"],"
                 "\"risks\":[\"...\"],\"kill\":\"điều kiện dừng đo được bằng số\"}. Mỗi giá trị là CÂU NGẮN. "
                 "Không văn xuôi ngoài JSON.")
    draft, prov = call_with_json_retry("default", draft_sys, "Soạn khung chiến lược từ EVIDENCE PACK ở trên.",
                               work=WORK, max_tokens=6000, cache_prefix=base_prefix, label="summary-P1")

    # ---- PASS 2: SELF-CRITIQUE (adversarial reviewer persona) — evidence reused from cached prefix ----
    crit_sys = ("=== LƯỢT 2 — TỰ PHẢN BIỆN GAY GẮT ===\nGiờ bạn là GIÁM ĐỐC NỘI DUNG hoài "
                "nghi, soi lại chính bản nháp này (đối chiếu EVIDENCE PACK ở trên). Với từng khuyến nghị "
                "hỏi: NGƯỜI THƯỜNG đọc có hiểu không (câu nào cần biết thống kê mới hiểu ⇒ SỬA theo công "
                "thức SỐ→NGHĨA→LÀM)? có số chống lưng không? winning_format có đủ 6 thành phần (thời lượng/"
                "chủ đề/tiêu đề/thumbnail/tags/nhịp đăng) không? thumbnail có bịa không (phải là suy luận có "
                "nhãn)? có bị OX-số-nhỏ đánh lừa không (ưu tiên Σexcess)? kèo concentration cao có bị hạ bậc "
                "chưa? có nhầm liên hệ thành nhân quả / heuristic (RPM) thành sự thật? phán quyết có khớp số? "
                "Trả về CHỈ JSON: {\"issues\":[{\"target\":\"mục/tiêu đề\",\"verdict\":\"GIỮ|SỬA|BỎ\","
                "\"reason\":\"...\",\"fix\":\"cách viết lại cụ thể hơn\"}],\"missing\":[...],"
                "\"final\":{\"verdict\":\"GO|CÂN NHẮC|NO-GO\",\"confidence\":\"VERIFIED|TENTATIVE\","
                "\"beachhead\":\"...\"}} — 'final' là giá trị SAU phản biện (bằng bản nháp nếu giữ nguyên; "
                "nếu phản biện lật verdict thì ghi giá trị MỚI). Nếu không thấy "
                "gì để sửa, buộc mổ lại 3 khuyến nghị yếu nhất và trưng số.")
    crit_user = "Bản nháp cần phản biện:\n" + json.dumps(draft, ensure_ascii=False)
    critique, _ = call_with_json_retry("default", crit_sys, crit_user,
                               work=WORK, max_tokens=8000, cache_prefix=base_prefix, label="summary-P2")

    # ---- PASS 3: REFINE -> final guide. Return RAW MARKDOWN (not JSON) so a long guide can't get
    # truncated into "unbalanced JSON". Structured fields come from the draft/critique we already have. ----
    recon_sys = ("=== LƯỢT 3 — HOÀN THIỆN & KẾT XUẤT (10 mục §0–§9) ===\nÁp kết quả phản "
                 "biện: GIỮ→giữ; SỬA→viết lại cụ thể hơn (dùng 'fix'); BỎ→loại + ghi vào §9 Nhật ký. Bổ "
                 "sung 'missing'. Viết bản PHÂN TÍCH cuối ĐẦY ĐỦ 10 mục §0–§9 đúng cấu trúc đã mô tả — "
                 "TRỌNG TÂM là §1 WINNING FORMAT đủ 6 tiểu mục (1.1 thời lượng · 1.2 chủ đề/sub-format có "
                 "bảng ví dụ thật + Σexcess · 1.3 công thức tiêu đề từ title_features · 1.4 thumbnail SUY "
                 "LUẬN có nhãn · 1.5 tags · 1.6 nhịp đăng) + khung 1 câu 'Winning formula = …'; kèm §3 Bảng "
                 "bằng chứng, §4 Lộ trình 30/60/90, §5 Mỏ vàng câu hỏi, §6 Giá trị chưng cất (insight xâu "
                 "chuỗi), §7 Kill switch bằng số. Văn phong: SỐ đứng trước → nghĩa là gì → làm gì; giải "
                 "nghĩa thuật ngữ trong ngoặc lần đầu dùng; kết luận IN ĐẬM cuối mỗi mục — lấy số từ "
                 "EVIDENCE PACK ở trên. TRẢ VỀ TRỰC TIẾP văn bản Markdown tiếng Việt (KHÔNG phải JSON, "
                 "KHÔNG bọc trong ```), bắt đầu ngay bằng '# '. Trực quan: bảng + thanh điểm ████░░ + danh "
                 "sách video đánh số.")
    recon_user = ("Bản nháp:\n" + json.dumps(draft, ensure_ascii=False) +
                  "\n\nKết quả phản biện:\n" + json.dumps(critique, ensure_ascii=False) +
                  "\n\nHoàn thiện thành bản hướng dẫn Markdown đầy đủ 10 mục.")
    md_raw, _ = call_role("default", recon_sys, recon_user, work=WORK, max_tokens=16000, cache_prefix=base_prefix)
    # strip an accidental ``` fence if the model added one
    md = re.sub(r"^```(?:markdown)?\s*|\s*```$", "", (md_raw or "").strip()).strip()

    # structured fields (for the Excel sheet) taken from what we already have — no fragile JSON-in-JSON
    rejected = [{"item": i.get("target"), "reason": i.get("reason")}
                for i in (critique.get("issues") or [])
                if "BỎ" in str(i.get("verdict", "")).upper() or "BO" == str(i.get("verdict", "")).upper()]
    d1 = pack.get("decision1") or {}
    # structured fields come from the POST-critique 'final' block (audit V17a): the old code froze
    # the PASS-1 draft verdict, so a critique that flipped it left the sheet contradicting the markdown.
    fin = critique.get("final") if isinstance(critique.get("final"), dict) else {}
    final = {"verdict": fin.get("verdict") or draft.get("verdict"),
             "confidence": fin.get("confidence") or draft.get("confidence"),
             "beachhead": fin.get("beachhead") or draft.get("beachhead"),
             "attractiveness": d1.get("attractiveness"),
             "markdown": md, "rejected": rejected,
             "_meta": {"model": prov, "passes": 3, "cached_prefix": True, "n_rejected": len(rejected),
                       "verdict_source": "post-critique" if fin.get("verdict") else "draft"}}
    save("summary.json", final)

    if md:
        report_dir = os.path.join(os.path.dirname(WORK), "Report")   # WORK = <project>/niche-data
        os.makedirs(report_dir, exist_ok=True)
        open(os.path.join(report_dir, "SUMMARY.md"), "w", encoding="utf-8").write(md + "\n")
    print(f"summary — model={prov} · vòng lặp 3 lượt (soạn→tự phản biện→hoàn thiện) · evidence cache dùng "
          f"chung (lượt 2–3 ~10% chi phí) · {len(rejected)} khuyến nghị bị loại · markdown {len(md):,} ký tự "
          f"-> summary.json + Report/SUMMARY.md")


AGENTS = {"namer": run_namer, "auditor": run_auditor, "plan": run_plan, "dna": run_dna, "summary": run_summary}

if AGENT not in AGENTS:
    print(f"usage: run_agent.py <niche-data dir> <{'|'.join(AGENTS)}>"); sys.exit(2)
try:
    AGENTS[AGENT]()
except LLMError as e:
    print(f"LLM ERROR ({AGENT}): {e}"); sys.exit(1)
except FileNotFoundError as e:
    print(f"MISSING INPUT for {AGENT}: {e}"); sys.exit(1)
