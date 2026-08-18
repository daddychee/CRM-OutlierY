"""Module 2 orchestrator — harvest → tag/title/description → result.json.

Gọi các stage theo thứ tự, cập nhật status (poll GUI). Mỗi stage tự verify được riêng;
đây chỉ nối chúng lại + ghi hợp đồng result.json cho board.
"""
import os

from . import (common, describe, digest, episode, harvest, library, llm, niche_format, niches,
               tags, thumbtext, titles)


def _load_profile(slug: str | None) -> dict | None:
    if not slug:
        return None
    f = common.profiles_dir() / f"{common.slug(slug)}.json"
    return common.read_json(f) if f.exists() else None


def _mark_rules(result: dict, eff: dict) -> None:
    """Soi luật 'avoid' của Format niche trên nội dung vừa sinh → cảnh báo, KHÔNG loại bỏ."""
    rules = eff.get("rules") or {}
    for t in result.get("titles", []):
        t["rule_hits"] = niche_format.check_rules(t.get("text", ""), rules)
    des = result.get("description") or {}
    if des:
        des.setdefault("sigs", {})["rule_hits"] = niche_format.check_rules(des.get("text", ""), rules)


def generate(run: str, body: dict, status: dict) -> dict:
    common.load_env()
    if body.get("model"):                                  # override model cho run này (tool local, 1 job/lúc)
        os.environ["LLM_MODEL"] = body["model"]
    script, srt = body.get("script", ""), body.get("srt", "")
    # User tự đưa hook mở đầu + tên chapter → Python dùng nguyên văn, không hỏi LLM
    u_hook, u_chaps = body.get("hook", ""), body.get("chapters", "")
    profile = _load_profile(body.get("profile"))
    # Format lấy theo thứ tự: đã GẮN vào kênh → chọn tay cho run này → suy theo niche (episode.format_for)
    fmt = episode.format_for(profile or {},
                             niche_format.load(body["format"]) if body.get("format") else None,
                             niche_format.all_formats()) if (profile or body.get("format")) else None
    eff = niche_format.resolve(profile, fmt)                  # KÊNH ĐÈ NICHE
    rd = common.run_dir(run, create=True)
    only = body.get("only")
    prior = common.read_json(rd / "result.json") if (rd / "result.json").exists() else {}
    llm.usage_reset()                                         # đếm token cho RIÊNG lần chạy này

    # Brief kịch bản: nén 1 lần, 3 stage dùng chung. Regen tái dùng brief đã lưu trong result.json
    # (không phụ thuộc cache đĩa → restart server vẫn 0 token), giống cách _pool được tái dùng.
    brief = prior.get("_brief") if only else None
    if not brief:
        if len(script) >= digest.MIN_CHARS:
            status["step"] = "nén brief kịch bản…"
        brief = digest.build(script)
    # brief rỗng (kịch bản ngắn/không có) → truyền thẳng kịch bản; stage nhận cả dict lẫn str.
    content = brief or script
    opening = digest.opening(script)

    # ── regen 1 phần (Sinh lại) — tái dùng pool/comp_titles đã lưu, KHÔNG re-harvest ──
    if only and prior:
        if only == "description":
            status["step"] = "sinh lại description…"
            # Khuôn đối thủ đã lưu trong result (06/08) → sinh lại vẫn theo khuôn, không re-harvest.
            # Run cũ (trước khi có _main_desc) không lưu khuôn → đường skeleton cũ như trước.
            _comp = (prior.get("_main_desc") or "").strip()
            if _comp:
                prior["description"] = describe.build_mirror(
                    eff, _comp, content, prior.get("keyword", ""), srt, opening, u_hook, u_chaps,
                    phrases=(prior.get("_desc_meta") or {}).get("phrases"))
            else:
                prior["description"] = describe.build(eff, content, prior.get("keyword", ""), srt,
                                                      opening, u_hook, u_chaps)
        elif only == "titles":
            status["step"] = "sinh lại title…"
            trep = {}
            prior["titles"] = titles.generate(content, prior.get("_comp_titles", []),
                                              fmt=eff, report=trep,
                                              ref_titles=prior.get("_ref_titles") or [],
                                              ref_patterns=prior.get("_ref_forms") or [])
            prior["titles_dropped"] = trep.get("dropped") or []
        elif only == "tags":
            status["step"] = "sinh lại tag…"
            # PHẢI dùng lại _desc_meta đã lưu: thiếu nó thì bộ ứng viên khác lần chạy đầu
            # ⇒ prompt khác ⇒ trượt cache, tốn token mà kết quả lệch vô cớ.
            sets = tags.select(prior.get("_pool", []), prior.get("_main_title", ""), content,
                               prior.get("n_videos", 0), base_tags=eff["base_tags"],
                               desc_meta=prior.get("_desc_meta"))
            prior["tags"] = sets
            if sets and sets[0]["tags"]:
                prior["keyword"] = sets[0]["tags"][0]
        if body.get("profile"):
            prior["profile"] = common.slug(body["profile"])   # đổi Profile lúc sinh lại Description
        prior["format"] = (fmt or {}).get("slug", "")
        prior["skeleton_source"] = eff["source"]
        if brief:
            prior["_brief"] = brief
        _mark_rules(prior, eff)
        prior["updated"] = library.now_iso()
        prior["usage"] = status["usage"] = llm.usage_snapshot()
        common.write_json(rd / "result.json", prior)
        return prior

    # ── full pipeline ──
    keys = common.load_keys()
    status["step"] = "harvest tag đối thủ…"
    h = harvest.harvest(body.get("main_url", ""), body.get("sub_urls", ""), keys)
    videos, pool, n = h["videos"], h["pool"], h["n_videos"]
    main = next((v for v in videos if v.get("is_main")), videos[0] if videos else {})
    comp_titles = [v.get("title", "") for v in videos]

    status["step"] = "chọn tag (3 bộ)…"
    tsets = tags.select(pool, main.get("title", ""), content, n, base_tags=eff["base_tags"],
                        desc_meta=h.get("desc_meta"))   # hashtag/cụm khoá trong description đối thủ
    keyword = tsets[0]["tags"][0] if tsets and tsets[0]["tags"] else main.get("title", "")
    status["usage"] = llm.usage_snapshot()

    status["step"] = "sinh title (3)…"
    trep: dict = {}
    # Kho THAM KHẢO song song: outlier THẬT của Format đã gắn + báo cáo title user dán.
    # Chỉ góp Ô lắp vào; KHUNG vẫn bám video đối thủ của tập (titles.score canh chốt đó).
    use_bank = bool(body.get("use_bank", True))
    # KHÔNG TRỘN NICHE (user chốt 2026-08-02): outlier của Format chỉ là chất liệu hợp lệ khi
    # Format cùng niche với kênh. Format chưa khai niche thì CHO QUA ("chưa khai" ≠ "khác");
    # khai mà lệch thì BỎ và nói rõ — im lặng dùng là chất liệu sai niche đi thẳng lên YouTube.
    _nn = ((profile or {}).get("niche") or "").strip()
    _fn = ((fmt or {}).get("niche") or "").strip()
    mixw: list[str] = []
    cross = bool(_nn and _fn and _fn.lower() != _nn.lower())
    if cross:
        mixw.append(f"Format thuộc niche '{_fn}' nhưng kênh khai niche '{_nn}' — KHÔNG lấy "
                    f"outlier của format này làm chất liệu")
    ref_titles = ([e.get("title", "") for e in ((fmt or {}).get("evidence") or []) if e.get("title")]
                  if (use_bank and not cross) else [])
    ref_forms = []
    if use_bank and _nn:
        ref_titles += niches.titles_for(_nn)
        ref_forms = niches.patterns_for(_nn)     # công thức: chỉ vào prompt, không vào kho truy nguyên
    ref_titles += niches.parse_bank(body.get("title_bank") or "")
    tits = titles.generate(content, comp_titles, fmt=eff, report=trep, ref_titles=ref_titles,
                           ref_patterns=ref_forms)
    status["usage"] = llm.usage_snapshot()

    status["step"] = "sinh description…"
    # KHUÔN ĐỐI THỦ (user chốt 06/08): video chính (link đầu tiên) có description → viết theo
    # ĐÚNG cấu trúc bản đó; không có → đường skeleton cũ giữ nguyên.
    comp_desc = (main.get("description") or "").strip()
    if comp_desc:
        des = describe.build_mirror(eff, comp_desc, content, keyword, srt, opening, u_hook, u_chaps,
                                    phrases=(h.get("desc_meta") or {}).get("phrases"))
    else:
        des = describe.build(eff, content, keyword, srt, opening, u_hook, u_chaps)

    # TEXT ON THUMB: nguồn DUY NHẤT là kho niche (ô dán-theo-tập đã GỠ — xem episode.py).
    # Python đo + xếp hạng, 0 LLM, 0 quota.
    tt_niche = niches.thumbs_for((profile or {}).get("niche", ""))
    tt = thumbtext.analyze("\n".join(tt_niche), comp_titles) if tt_niche else {}
    thumb = {"analysis": tt, "rules": thumbtext.rules(tt),
             "suggest": thumbtext.suggest(tt, (tits[0] or {}).get("text", "") if tits else "",
                                          keyword, bank=tt_niche)} if tt else {}

    result = {"titles": tits, "titles_dropped": trep.get("dropped") or [],
              "tags": tsets, "description": des,
              "n_videos": n, "keyword": keyword,
              "desc_meta": h.get("desc_meta") or {},   # meta trong description đối thủ (Python đo)
              "thumb": thumb,
              # gắn run vào KÊNH → lịch sử theo kênh (library.runs), tránh trùng title khi re-up
              "profile": common.slug(body.get("profile") or "") if body.get("profile") else "",
              "format": (fmt or {}).get("slug", ""),   # format THỰC SỰ dùng (ưu tiên cái gắn vào kênh)
              "skeleton_source": eff["source"],
              "created": library.now_iso(), "main_url": body.get("main_url", ""),
              "usage": llm.usage_snapshot(),
              # `_ref_titles` lưu lại như `_pool`/`_comp_titles`: "↻ Sinh lại Title" phải dùng
              # ĐÚNG kho tham khảo của lần chạy đầu, không thì bản sinh lại chơi bằng luật khác.
              "_pool": pool, "_comp_titles": comp_titles, "_ref_titles": ref_titles,
              "_ref_forms": ref_forms, "niche_mix": mixw,
              "_main_title": main.get("title", ""),
              "_desc_meta": h.get("desc_meta") or {},     # regen tag dùng lại → cùng ứng viên, giữ cache
              "_main_desc": comp_desc,                     # khuôn đối thủ — regen description theo khuôn
              "_brief": brief}                             # regen dùng lại → không nén kịch bản 2 lần
    _mark_rules(result, eff)
    status["usage"] = result["usage"]
    common.write_json(rd / "result.json", result)
    return result


if __name__ == "__main__":                                # self-test offline (monkeypatch API + LLM)
    import json
    from . import llm

    seed = [
        {"id": "A", "title": "The Monster at the Center of Our Galaxy", "description": "",
         "tags": ["sagittarius a*", "black hole", "event horizon"], "views": 800_000, "is_main": True},
        {"id": "B", "title": "What Is a Black Hole", "description": "",
         "tags": ["black hole", "astrophysics"], "views": 50_000, "is_main": False},
    ]
    harvest.harvest = lambda m, s, k: {"videos": seed, "pool": harvest.build_pool(seed), "n_videos": 2}

    LONG_SCRIPT = "Sagittarius A star la ho den sieu khoi tam Ngan Ha. " * 60   # > digest.MIN_CHARS
    seen_users = []

    def route(sysmsg, user):
        seen_users.append(user)
        if "BRIEF" in sysmsg:                                 # digest: nén kịch bản 1 lần
            return '{"topic":"Sagittarius A*","entities":["Sagittarius A*"],"beats":["mở"],"desires":["dread"],"keywords":["black hole"],"promise":"p"}'
        if "tag ứng viên" in sysmsg or "phân loại" in sysmsg:
            return '{"primary":"sagittarius a*","tags":[{"tag":"sagittarius a*","keep":true,"role":"primary"},{"tag":"black hole","keep":true,"role":"longtail"},{"tag":"event horizon","keep":true,"role":"longtail"},{"tag":"astrophysics","keep":true,"role":"broad"}]}'
        if "MARKETING" in sysmsg:
            return json.dumps([{"text": "There's a Monster at the Center of Our Galaxy", "desire": "dread",
                                "technique": "Personification", "awareness": "Unaware", "proof": True}])
        return '{"hook":"Sagittarius A* is the monster at our galaxy\'s core.","summary":"A dark documentary.","chapters":[]}'
    llm.set_hook(route)
    res = generate("selftest", {"main_url": "A", "sub_urls": "B", "script": LONG_SCRIPT, "srt": ""}, {})
    llm.set_hook(None)
    assert len(res["titles"]) >= 1 and len(res["tags"]) == 3 and res["description"]["text"], res
    assert res["keyword"] == "sagittarius a*", res
    assert res["skeleton_source"] == "standard", res
    out = common.run_dir("selftest") / "result.json"
    assert out.exists(), out
    # token: 4 call (digest + tag + title + description) và kịch bản KHÔNG còn gửi thô 3 lần
    assert len(seen_users) == 4, seen_users
    assert sum("content_brief" in u for u in seen_users) == 3, seen_users
    assert "usage" in res, res

    # ── có Format niche: base tag chèn vào, luật 'avoid' bị soi, kênh KHÔNG có skeleton → dùng của niche ──
    niche_format.load = lambda slug: {"slug": slug, "name": "Doc", "niche": "Space",
                                      "description": {"skeleton": ["HOOK", "SUMMARY"]},
                                      "tags": {"base": ["deep space documentary"]},
                                      "title": {"patterns": [{"pattern": "The [x] [y]"}], "note": "n"},
                                      "rules": {"must": [], "avoid": ["monster galaxy"]}}
    llm.set_hook(route)
    res2 = generate("selftest", {"main_url": "A", "sub_urls": "B", "script": LONG_SCRIPT, "srt": "",
                                 "format": "space-doc"}, {})
    llm.set_hook(None)
    assert res2["skeleton_source"] == "niche" and res2["format"] == "space-doc", res2
    assert any("deep space documentary" in s["tags"] for s in res2["tags"]), res2["tags"]
    assert res2["titles"][0]["rule_hits"] == ["monster galaxy"], res2["titles"][0]   # title chạm luật cấm

    # ── KHUÔN ĐỐI THỦ (06/08): video chính CÓ description → mirror; kết quả lưu _main_desc ──
    seed_m = [{**seed[0], "description": "Hook line here.\n\nBlock two of the template.\n#Old"},
              seed[1]]
    harvest.harvest = lambda m, s, k: {"videos": seed_m, "pool": harvest.build_pool(seed_m),
                                       "n_videos": 2, "desc_meta": harvest.desc_meta(seed_m)}

    def route_m(sysmsg, user):
        if "description_doi_thu" in user and "PHÂN TÍCH cấu trúc" in sysmsg:
            return '{"text":"Sagittarius A* mirror hook.\\n\\nMirror block two."}'
        return route(sysmsg, user)
    llm.set_hook(route_m)
    res3 = generate("selftest", {"main_url": "A", "sub_urls": "B", "script": LONG_SCRIPT, "srt": ""}, {})
    llm.set_hook(None)
    assert res3["description"]["text"].startswith("Sagittarius A* mirror hook."), res3["description"]
    assert res3["description"].get("template") == "doi_thu", res3["description"]
    assert res3["_main_desc"].startswith("Hook line here."), res3["_main_desc"]
    print("pipeline.py self-test OK - titles", len(res["titles"]), "- tag sets", len(res["tags"]),
          "- kw", res["keyword"], "- format niche: base tag + rule check OK - mirror theo khuon doi thu")
