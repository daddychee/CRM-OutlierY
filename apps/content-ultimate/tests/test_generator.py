from voiceprofile.generator import (
    CHAPTER_WARN_CHARS,
    HOOK_CHARS,
    YOUTUBE_RULES,
    allocate_section_chars,
    build_section_prompt,
    build_voice_block,
    generate_script,
    min_chapters_for,
    parse_outline,
)

OUTLINE = """Title: What Is At The Edge Of The Universe?
Hook: You wake at midnight and wonder — where does the universe end?
Chapter 1: The observable horizon and 13.8 billion years of light
Chapter 2: Space expanding faster than light
End: Zoom back to Earth — we are how the cosmos asks about itself
"""

PROFILE = {
    "author": "Carl Sagan",
    "exemplars": ["We are made of star-stuff, looking back at the stars."],
    "signature_moves": [
        {"move": "Inclusive 'we' across cosmic scale", "evidence": [], "occurrences": 3},
        {"move": "Zoom-out then return to the human", "evidence": [], "occurrences": 4},
    ],
    "reproduction_targets": {},
}


def test_parse_outline_recognizes_all_section_kinds():
    secs = parse_outline(OUTLINE)
    kinds = [s.kind for s in secs]
    assert kinds == ["title", "hook", "chapter", "chapter", "end"]
    assert secs[0].brief.startswith("What Is At The Edge")
    assert "Title:" not in secs[0].brief  # nhan 'Title:' bi strip
    assert secs[2].heading == "Chapter 1"


def test_parse_outline_user_format_no_colon_markdown_emdash():
    # Format nguoi dung thuc te: # title, HOOK, CHAPTER N —, ENDING (khong dau ':')
    o = ("# The Terrifying Truth of Sagittarius A*\n"
         "HOOK Introduce the monster at the center.\n"
         "CHAPTER 1 — Discovery & The S-Stars explain the center.\n"
         "CHAPTER 2 — The Mass reveal the staggering mass.\n"
         "ENDING Bring the narrative back to the viewer.")
    secs = parse_outline(o)
    assert [s.kind for s in secs] == ["title", "hook", "chapter", "chapter", "end"]
    assert secs[0].brief == "The Terrifying Truth of Sagittarius A*"
    assert secs[1].brief.startswith("Introduce the monster")
    assert secs[2].heading == "Chapter 1"
    assert secs[2].brief.startswith("Discovery & The S-Stars")


def test_parse_outline_single_block_no_newlines():
    o = "HOOK the monster. CHAPTER 1 — Discovery the center. ENDING back to viewer."
    secs = parse_outline(o)
    assert [s.kind for s in secs] == ["hook", "chapter", "end"]


def test_parse_outline_empty_when_no_sections():
    assert parse_outline("Just random text, no section markers here.") == []
    assert parse_outline("") == []


def test_build_voice_block_includes_exemplars_and_moves():
    vb = build_voice_block(PROFILE)
    assert "Carl Sagan" in vb
    assert "star-stuff" in vb
    assert "Inclusive 'we'" in vb


def test_chapter_prompt_carries_voice_and_prev_tail():
    secs = parse_outline(OUTLINE)
    chapter = next(s for s in secs if s.kind == "chapter")
    system, user = build_section_prompt(chapter, PROFILE, "outline here",
                                        "…prior ending text", 2000, title="T")
    assert YOUTUBE_RULES["chapter"][:20] in user      # luat chuong
    assert "prior ending text" in user                # noi mach tu phan truoc
    assert "DEPTH PLAN" in user                       # Tang 2: phan tang do sau
    assert "Carl Sagan" in system                     # giong tac gia o system


def test_hook_prompt_is_platform_not_author_voice():
    secs = parse_outline(OUTLINE)
    hook = next(s for s in secs if s.kind == "hook")
    system, user = build_section_prompt(hook, PROFILE, "o", "", 2000, title="Edge Of The Universe")
    # hook KHONG dung giong tac gia
    assert "Carl Sagan" not in system and "Carl Sagan" not in user
    assert "star-stuff" not in system                 # khong co exemplar author
    # hook la YouTube thuan: title, rat ngan (250-500 ky tu), punchy
    assert "Edge Of The Universe" in user             # bao quat title
    assert "punchy" in user
    assert "250-500 characters" in user


def test_generate_script_sequential_calls_and_assembly():
    calls = []

    def fake_llm(system, user, max_tokens):
        # tra ve noi dung phu thuoc heading de kiem thu tu tu
        calls.append(user)
        head = "HOOKBODY" if "Hook" in user else ("ENDBODY" if "End" in user else "CHBODY")
        return f"{head} generated prose."

    script = generate_script(OUTLINE, PROFILE, fake_llm, total_chars=8000)
    assert script.title.startswith("What Is At The Edge")
    # 4 phan noi dung (hook + 2 chapter + end), title khong goi LLM
    assert len(script.sections) == 4
    assert len(calls) == 4
    md = script.to_markdown()
    assert md.startswith("# What Is At The Edge")
    assert "## Hook" in md and "## End" in md
    assert "HOOKBODY" in md


def test_allocate_section_chars_hook_fixed_end_clamped_body_even():
    secs = parse_outline(OUTLINE)  # hook + 2 chapter + end
    content = [s for s in secs if s.kind != "title"]
    allocs = allocate_section_chars(content, total_chars=10000)
    by_kind = {s.kind: a for s, a in zip(content, allocs)}
    assert by_kind["hook"] == HOOK_CHARS          # hook co dinh
    assert 500 <= by_kind["end"] <= 1200          # end clamp
    # body = 10000 - 425 - end, chia deu cho 2 chuong
    chapters = [a for s, a in zip(content, allocs) if s.kind == "chapter"]
    assert len(set(chapters)) == 1                # cac chuong deu nhau
    assert chapters[0] > by_kind["hook"]          # chuong dai hon hook


def test_allocate_hook_does_not_scale_with_total():
    secs = parse_outline(OUTLINE)
    content = [s for s in secs if s.kind != "title"]
    a10k = allocate_section_chars(content, 10000)
    a30k = allocate_section_chars(content, 30000)
    hook10 = next(a for s, a in zip(content, a10k) if s.kind == "hook")
    hook30 = next(a for s, a in zip(content, a30k) if s.kind == "hook")
    assert hook10 == hook30 == HOOK_CHARS         # hook KHONG scale theo tong
    # nhung chuong thi scale
    ch10 = next(a for s, a in zip(content, a10k) if s.kind == "chapter")
    ch30 = next(a for s, a in zip(content, a30k) if s.kind == "chapter")
    assert ch30 > ch10


def test_warning_when_chapters_too_long():
    # 20000 ky tu, 2 chuong -> moi chuong ~9k > 4000 -> canh bao vuot nguong
    assert min_chapters_for(20000, has_hook=True, has_end=True) >= 5
    warnings = []
    two_ch = "Hook: h\nChapter 1: a\nChapter 2: b\nEnd: e"
    generate_script(two_ch, PROFILE, lambda s, u, mx: "body", total_chars=20000,
                    on_progress=warnings.append)
    assert any("vuot nguong" in w for w in warnings)


def test_warning_when_chapters_too_short_flattens():
    # 6500 ky tu, 3 chuong -> moi chuong ~1858 < 2500 -> canh bao lam phang
    warnings = []
    three_ch = "Hook: h\nChapter 1: a\nChapter 2: b\nChapter 3: c\nEnd: e"
    generate_script(three_ch, PROFILE, lambda s, u, mx: "body", total_chars=6500,
                    on_progress=warnings.append)
    assert any("phang" in w or "chat luong" in w for w in warnings)


def test_tang2_prompt_ngan_sach_y_khong_nhac_ky_tu():
    # Chot 2026-07-09: chapter/end KHONG nhac con so ky tu — chi giao ngan sach Y.
    secs = parse_outline(OUTLINE)
    chapter = next(s for s in secs if s.kind == "chapter")
    _, u = build_section_prompt(chapter, PROFILE, "o", "", 3000, title="T")
    assert "DEPTH PLAN" in u and "AT MOST 2" in u     # 3000/1250 ~ 2 y khai trien day du
    assert "characters" not in u                       # khong nhac ky tu
    _, u2 = build_section_prompt(chapter, PROFILE, "o", "", 3800, title="T")
    assert "AT MOST 3" in u2                           # 3800/1250 ~ 3 y


def test_tang2_khong_bao_gio_bo_y_cua_user():
    # Chot 2026-07-14: phan tang do sau THAY cho cat y — y ngoai ngan sach FULL van
    # phai xuat hien o muc nhac-luot. Truoc day prompt bao "leave the rest out entirely".
    secs = parse_outline(OUTLINE)
    chapter = next(s for s in secs if s.kind == "chapter")
    _, u = build_section_prompt(chapter, PROFILE, "o", "", 3000, title="T")
    assert "leave the rest out" not in u               # KHONG con vut y cua user
    assert "MUST STILL APPEAR" in u                    # y con lai van co mat
    assert "NEVER drop an idea" in u
    assert "Never compress the prose" in u             # luat cu ve chat van giu nguyen


def test_tang3_ha_tang_thay_vi_xoa_y():
    from voiceprofile.generator import build_scope_cut_prompt
    secs = parse_outline(OUTLINE)
    chapter = next(s for s in secs if s.kind == "chapter")
    _, u = build_scope_cut_prompt(chapter, PROFILE, "draft qua dai…", 3000)
    assert "DROP every other idea" not in u            # khong xoa y nua
    assert "do NOT delete any idea" in u
    assert "demoted to ONE single sentence" in u       # chi ha muc khai trien


def test_depth_plan_khong_bo_y_va_kiem_soat_do_dai():
    from voiceprofile.generator import depth_plan
    p = depth_plan(4, 3000)                            # 4 y, muc tieu 3000
    assert p["full"] == 2 and p["mention"] == 2        # 2 FULL + 2 nhac luot
    assert p["full"] + p["mention"] == 4               # KHONG y nao bi bo
    p2 = depth_plan(4, 5000)                           # ngan sach rong hon -> tat ca FULL
    assert p2["full"] == 4 and p2["mention"] == 0
    p3 = depth_plan(2, 6000)                           # it y hon ngan sach -> khong bia them
    assert p3["full"] == 2 and p3["mention"] == 0


def test_tang1_uoc_y_va_bao_cao_pham_vi():
    from voiceprofile.generator import estimate_ideas, idea_budget, outline_scope_report

    brief_3y = ("The unofficial rule of 'Janteloven' prevents showing off, channeling "
                "wealth into public welfare, electric vehicles, and environmental "
                "protection rather than superficial luxury.")
    assert 2 <= estimate_ideas(brief_3y) <= 4          # hieu chinh tu thi nghiem Norway
    assert estimate_ideas("") == 0
    assert idea_budget(2000) == 2 and idea_budget(3350) == 3 and idea_budget(9000) == 4
    assert idea_budget(1200, min_k=1) == 1             # End ngan: cho phep 1 y

    dense = OUTLINE.replace(
        "Chapter 1: The observable horizon and 13.8 billion years of light",
        "Chapter 1: " + brief_3y + " " + brief_3y)     # brief ram y gap doi
    rep = outline_scope_report(dense, 10000)
    assert rep["summary"].startswith("Outline: 2 chương")
    assert any("Chapter 1" in w for w in rep["scope_warnings"])
    assert rep["warnings"]                             # gop ca scope + structure


def test_tang3_mot_vong_cat_y_khi_vuot_tran():
    calls = []

    def fake_llm(system, user, mx):
        calls.append(user)
        if "It runs long" in user:
            return "y" * 3000                          # ban cat y: vao vung ngot
        if 'section "Chapter' in user:
            return "x" * 6000                          # chuong 1 luot: vuot tran 4000
        return "short body"

    logs = []
    script = generate_script(OUTLINE, PROFILE, fake_llm, total_chars=8000,
                             on_progress=logs.append)
    bodies = dict(script.sections)
    assert bodies["Chapter 1"] == "y" * 3000           # da thay bang ban cat y
    assert bodies["Chapter 2"] == "y" * 3000
    assert sum("It runs long" in c for c in calls) == 2  # moi chuong dung 1 vong, khong lap
    assert any("cat y" in ln for ln in logs)
    assert bodies["Hook"] == "short body"              # hook khong qua Tang 3


def test_write_partial_script_tu_checkpoint(tmp_path):
    # yêu cầu user 2026-07-11: lỗi/huỷ giữa chừng vẫn ghi script.md từ chương đã xong
    from voiceprofile.generator import (save_checkpoint, write_partial_script)
    out = tmp_path / "script.md"
    # mới viết xong Hook + Chapter 1 (chưa có Chapter 2 / End)
    save_checkpoint(out, OUTLINE, 8000,
                    {"Hook": "HOOK body.", "Chapter 1": "CH1 body."},
                    provider="glm", model="glm-5")
    info = write_partial_script(out, OUTLINE, PROFILE)
    assert info["sections"] == 2
    md = out.read_text(encoding="utf-8")
    assert "## Hook" in md and "## Chapter 1" in md
    assert "## Chapter 2" not in md and "## End" not in md   # chưa xong thì chưa có
    assert "HOOK body." in md
    # chưa chương nào xong → None, không ghi file rác
    assert write_partial_script(tmp_path / "empty.md", OUTLINE, PROFILE) is None
    assert not (tmp_path / "empty.md").exists()


def test_generate_script_stops_midway():
    def fake_llm(system, user, max_tokens):
        return "body"

    state = {"n": 0}
    def should_stop():
        state["n"] += 1
        return state["n"] > 2  # dung sau vai phan

    script = generate_script(OUTLINE, PROFILE, fake_llm, total_chars=8000, should_stop=should_stop)
    assert 0 < len(script.sections) < 4  # da viet mot phan, khong het


# --- Vuot ky tu + hook phinh (user bao 2026-07-15) -----------------------------------

def test_nhac_luot_phai_an_vao_ngan_sach_khong_cong_them():
    """Loi that: k = round(target/1250) => k y FULL an het target MOT MINH, roi moi y
    nhac luot cong them 110 len tren => cang nhieu y cang vuot (do duoc +35%)."""
    from voiceprofile.generator import depth_plan

    # Ca dung nhat user gap: chuong 3500 ky tu, brief 10 y
    p = depth_plan(10, 3500)
    assert p["est_chars"] <= 3500 * 1.05, f"van vuot: {p['est_chars']}"
    assert p["full"] + p["mention"] == 10          # khong y nao bi bo

    # Cang nhieu y KHONG duoc lam uoc luong phinh mai
    ests = [depth_plan(n, 3500)["est_chars"] for n in (3, 6, 10, 14)]
    assert max(ests) <= 3500 * 1.15, f"co ca vuot qua dung sai: {ests}"


def test_khong_bao_gio_bo_y_du_o_ngan_sach_nao():
    from voiceprofile.generator import depth_plan
    for target in range(2000, 6001, 500):
        for n in range(1, 21):
            p = depth_plan(n, target)
            assert p["full"] + p["mention"] == n, (n, target)
            assert p["full"] >= min(2, n) or n < 2      # san chat luong


def test_depth_plan_khong_co_y_thi_khong_hoang():
    from voiceprofile.generator import depth_plan
    assert depth_plan(0, 3500) == {"full": 0, "mention": 0, "est_chars": 0}


def test_hook_brief_la_nguyen_lieu_khong_phai_bang_kiem():
    """Tu 2026-07-14 brief HOOK keo theo dong Angle:/CTA: (compose.py). Goi chung la
    'points to hit' = bat LLM phu kin => hook phinh, pha quy uoc 250-500."""
    from voiceprofile.generator import build_hook_prompt

    brief = "Ho den nuot anh sang.\nAngle: Chan troi su kien nhin tu Trai Dat.\nCTA: Sub di."
    _, u = build_hook_prompt("Sagittarius A*", brief)
    assert "Points to hit" not in u
    assert "NOT a checklist" in u
    assert "LEAVE OUT everything else" in u
    assert "250-500 characters" in u


def test_hook_qua_dai_bi_cat_MOT_vong():
    """Truoc 2026-07-15 hook bi loai khoi chot Tang 3 (`kind in ("chapter","end")`)
    => hook viet dai bao nhieu cung khong ai chan."""
    from voiceprofile.generator import HOOK_CHARS_MAX, generate_script

    calls = []

    def fake_llm(system, user, max_tokens=None):
        calls.append(user)
        if "TOO LONG" in user:                       # vong cat hook
            return "Hook ngan gon." * 5
        if "HOOK" in user and "Material" in user:
            return "x" * 2000                        # hook phinh gap 4 lan tran
        return "short body"

    script = generate_script(OUTLINE, PROFILE, fake_llm, total_chars=8000)
    hook = dict(script.sections)["Hook"]
    assert len(hook) < 2000, "hook qua dai khong bi cat"
    assert len(hook) <= HOOK_CHARS_MAX * 1.15
    assert sum("TOO LONG" in c for c in calls) == 1   # dung MOT vong, khong lap vo han


def test_vong_cat_dung_chung_ngan_sach_voi_tang_2():
    """Tang 3 goi thang idea_budget => doi lai dung cai k gay vuot; phai dung depth_plan."""
    from voiceprofile.generator import (build_scope_cut_prompt, build_section_prompt,
                                        parse_outline)
    import re

    ch = next(s for s in parse_outline(OUTLINE) if s.kind == "chapter")
    _, u2 = build_section_prompt(ch, PROFILE, "o", "", 3500, title="T")
    _, u3 = build_scope_cut_prompt(ch, PROFILE, "ban nhap dai", 3500)
    k2 = re.search(r"AT MOST (\d+)", u2).group(1)
    k3 = re.search(r"ONLY the (\d+) most central", u3).group(1)
    assert k2 == k3, f"Tang 2 giao {k2} y nhung Tang 3 doi {k3} y"


def test_CTA_chua_tu_khoa_moc_khong_duoc_xe_outline():
    """Loi that 2026-07-15 (do chinh dong CTA/Angle compose.py them vao tu 2026-07-14):
    parse_outline san tu khoa moc o BAT KY dau, nen CTA doi thuong ("Watch till the
    end!") bi hieu la moc phan => outline vo thanh cac phan MA => sai phan bo do dai
    => kich ban vuot ky tu."""
    for phrase in ("Stay to the end for a surprise.",
                   "Comment below your intro song.",
                   "Chapter 2 of this story is on our channel.",
                   "Watch till the end!",
                   "Subscribe — the ending will shock you."):
        o = f"HOOK\nMot cau mo dau.\nCTA: {phrase}\n\nCHAPTER 1 — A\nnoi dung\n\nENDING\nket"
        assert [s.kind for s in parse_outline(o)] == ["hook", "chapter", "end"], phrase


def test_che_metadata_nhung_KHONG_lam_mat_noi_dung_cua_no():
    """Che de tim moc, nhung brief van phai cat tu text GOC — Angle la thu user doi
    phai giu bang duoc ('phat hien chi mang' 2026-07-14)."""
    o = ("Title: London\nHOOK\nThe city hides its scars.\n"
         "Angle: The Tube opened in 1863 while cholera ran the streets.\n"
         "CTA: Watch till the end!\n\nCHAPTER 1 — A\nnoi dung\n\nENDING\nket")
    hook = next(s for s in parse_outline(o) if s.kind == "hook")
    assert "Angle: The Tube opened in 1863" in hook.brief
    assert "CTA: Watch till the end!" in hook.brief


def test_moc_that_van_nhan_dien_binh_thuong():
    # Khong duoc vi che metadata ma pha nhan dien moc linh hoat da co.
    assert [s.kind for s in parse_outline(
        "HOOK the monster. CHAPTER 1 — Discovery the center. ENDING back to viewer."
    )] == ["hook", "chapter", "end"]
    o = "Angle: mot dong angle khong co moc nao\nCTA: cung vay"
    assert parse_outline(o) == []          # chi co metadata -> khong co phan nao


# --- Tran Tang 3 = nguong CHAT LUONG 4000, KHONG phai muc tieu chuong -----------------
#
# Luat user (2026-07-16): "viet hay la toi thuong, CO THE DAI HON, nhung vuot 4000 la
# truot khoi diem ngot -> van chan". Muc tieu ky tu MEM; 4000 la tran CUNG.
# 2026-07-15 tung doi tran thanh max(target, MIN_QUALITY) -> chuong muc tieu 3000 bi cat o
# 3450, trong khi prompt that viet 2965-3433 (tb 3289) => qua nua so chuong bi CAT OAN.

def _llm_chi_chuong_dai(chapter_len, cut_len=3000):
    """LLM gia: CHI chuong viet dai; hook/end viet ngan de khong lam nhieu phep do."""
    calls = []

    def f(system, user, max_tokens=None):
        calls.append(user)
        if "It runs long" in user:
            return "y" * cut_len                       # ban da cat y
        if 'write ONLY the section "Chapter' in user:
            return "x" * chapter_len
        return "ngan"                                  # hook / end
    return f, calls


def test_chuong_vuot_MUC_TIEU_nhung_con_trong_vung_ngot_thi_KHONG_bi_cat():
    """Do THAT prompt hien tai (5 mau, muc tieu 3000): 2965-3433, tb 3289, +-7%. Cac chuong
    nay VAN HAY va van duoi 4000 => cat chung la cat oan: ton them 1 luot LLM VA ha y cua
    user xuong mot cau. Mat noi dung dat hon vai tram ky tu thua."""
    from voiceprofile.generator import CHAPTER_WARN_CHARS, generate_script

    for do_that in (3289, 3433, 4092):                 # deu > muc tieu, deu < 4000*1.15
        f, calls = _llm_chi_chuong_dai(do_that)
        assert do_that < CHAPTER_WARN_CHARS * 1.15
        o = "Hook: h\nChapter 1: a\nChapter 2: b\nEnd: e"   # moi chuong muc tieu ~3532
        generate_script(o, PROFILE, f, total_chars=8000)
        assert not any("It runs long" in c for c in calls), f"cat oan chuong {do_that} ky tu"


def test_chuong_vuot_TRAN_CHAT_LUONG_4000_thi_bi_cat():
    """Tren 4000 la troi giong, van chan — luc do moi cat."""
    from voiceprofile.generator import CHAPTER_WARN_CHARS, generate_script

    dai = round(CHAPTER_WARN_CHARS * 1.3)              # 5200 — qua tran chat luong
    f, calls = _llm_chi_chuong_dai(dai)
    o = "Hook: h\nChapter 1: a\nChapter 2: b\nEnd: e"
    script = generate_script(o, PROFILE, f, total_chars=8000)
    assert dict(script.sections)["Chapter 1"] == "y" * 3000, "vuot tran chat luong ma khong cat"
    assert sum("It runs long" in c for c in calls) == 2, "moi chuong dung MOT vong cat"


def test_chuong_muc_tieu_ngan_khong_bi_cat_thanh_van_cut():
    """Chuong muc tieu ~1375: tran van la 4000 nen 2600 khong bi dung toi. Chuong qua ngan
    da co canh bao CAU TRUC rieng (chia lai outline), khong chua bang cach cat."""
    from voiceprofile.generator import generate_script

    f, calls = _llm_chi_chuong_dai(2600)
    o = "Hook: h\nChapter 1: a\nChapter 2: b\nChapter 3: c\nEnd: e"
    generate_script(o, PROFILE, f, total_chars=5000)
    assert not any("It runs long" in c for c in calls)


# --- Vong NO (Tang 3 chieu nguoc, 2026-07-17) — cai sau vong phan bien co so lieu ------

BRIEF_DAI = ("The city grew from a fishing village into a metropolis. " * 8).strip()  # ~450 ky tu

def _outline_no():
    return ("Hook: h\nChapter 1: " + BRIEF_DAI + "\nChapter 2: " + BRIEF_DAI + "\nEnd: e")


def test_chuong_hut_duoc_no_ve_khung():
    """Ho so giong viet ngan (A008 -34%) -> chuong hut 46% phai duoc keo len bang y
    trong brief. Do that: 2122 -> 4054+-, giu 100% van cu."""
    from voiceprofile.generator import generate_script

    calls = []
    def f(system, user, max_tokens=None):
        calls.append(user)
        if "SHORTER than needed" in user:
            old = user.split("you wrote:\n\n", 1)[1].split("\n\nIt runs about")[0]
            return old + " " + "More developed idea from the brief. " * 40   # no THAT: giu van cu
        if 'write ONLY the section "Chapter' in user:
            return ("Short draft sentence that is long enough to be measured properly here. " * 25).strip()  # ~1850 < 80% khung
        return "ngan"
    script = generate_script(_outline_no(), PROFILE, f, total_chars=8000)
    c1 = dict(script.sections)["Chapter 1"]
    assert len(c1) > 1900                                  # da duoc keo len
    assert "Short draft sentence" in c1                    # van cu con song
    assert sum("SHORTER than needed" in c for c in calls) >= 1


def test_no_pha_van_thi_bi_tu_choi_va_giu_ban_goc():
    """Luot no tra ban viet-lai-tu-dau (mat van cu) -> reject, khong thu tiep bang ban do."""
    from voiceprofile.generator import generate_script

    goc = ("Original sentence that must survive the expansion attempt fully intact. " * 25).strip()
    calls = []
    def f(system, user, max_tokens=None):
        calls.append(user)
        if "SHORTER than needed" in user:
            return "Completely rewritten text with none of the original sentences kept. " * 40
        if 'write ONLY the section "Chapter' in user:
            return goc
        return "ngan"
    script = generate_script(_outline_no(), PROFILE, f, total_chars=8000)
    assert dict(script.sections)["Chapter 1"] == goc       # giu nguyen ban goc
    # bi tu choi thi DUNG (break), khong dot luot 2 bang cung ban nhap
    assert sum("SHORTER than needed" in c for c in calls) == 2   # moi chuong dung 1 lan


def test_doi_nguyen_lieu_thi_KHONG_no():
    """Phan de 1 cua vong phan bien: hut + brief ngheo -> no = ep LLM bia -> cam.
    Brief 'a' 1 ky tu, gian >10x -> chi log, khong goi luot no nao."""
    from voiceprofile.generator import generate_script

    calls, logs = [], []
    def f(system, user, max_tokens=None):
        calls.append(user)
        if 'write ONLY the section "Chapter' in user:
            return "x" * 1000                              # hut nang
        return "ngan"
    generate_script("Hook: h\nChapter 1: a\nChapter 2: b\nEnd: e", PROFILE, f,
                    total_chars=8000, on_progress=logs.append)
    assert not any("SHORTER than needed" in c for c in calls)
    assert any("thieu nguyen lieu" in ln for ln in logs)


def test_trong_dung_sai_thi_khong_no():
    from voiceprofile.generator import generate_script

    calls = []
    def f(system, user, max_tokens=None):
        calls.append(user)
        if 'write ONLY the section "Chapter' in user:
            return "x" * 3300                              # ~93% khung 3532 — khong hut
        return "ngan"
    generate_script(_outline_no(), PROFILE, f, total_chars=8000)
    assert not any("SHORTER than needed" in c for c in calls)


def test_ho_sau_dung_toi_da_2_luot():
    """Do that: hut 53% co lan chi ve -26% sau luot 1 -> can luot 2; khong bao gio luot 3."""
    from voiceprofile.generator import generate_script

    calls = []
    def f(system, user, max_tokens=None):
        calls.append(user)
        if "SHORTER than needed" in user:
            old = user.split("you wrote:\n\n", 1)[1].split("\n\nIt runs about")[0]
            return old + " " + "Grow a little each round with brief ideas. " * 15  # +~640/luot
        if 'write ONLY the section "Chapter' in user:
            return ("Seed sentence long enough to register as original prose here. " * 15).strip()  # ~950
        return "ngan"
    generate_script(_outline_no(), PROFILE, f, total_chars=8000)
    per_ch = sum("SHORTER than needed" in c for c in calls) / 2
    assert per_ch == 2                                     # dung 2 luot moi chuong, khong hon


def test_canh_bao_ho_so_viet_ngan_he_thong():
    """Phan de 2: >= nua so chuong phai no -> bao goc re (exemplar ngan) de user sua ho so."""
    from voiceprofile.generator import generate_script

    logs = []
    def f(system, user, max_tokens=None):
        if "SHORTER than needed" in user:
            return ""                                       # no that bai -> van hut
        if 'write ONLY the section "Chapter' in user:
            return "x" * 1500
        return "ngan"
    generate_script(_outline_no(), PROFILE, f, total_chars=8000, on_progress=logs.append)
    assert any("viet NGAN he thong" in ln for ln in logs)


def test_kept_ratio_do_dung():
    from voiceprofile.generator import kept_ratio
    old = ("First survivor sentence that is definitely long enough to count here. "
           "Second survivor sentence that is also long enough to be counted well.")
    assert kept_ratio(old, old + " New material added after.") == 1.0
    assert kept_ratio(old, "Totally different text with nothing kept from before at all.") == 0.0
    # khoi khong dau cham van la MOT cau do duoc — mat no trong ban moi thi 0.0 (tu choi dung)
    assert kept_ratio("x" * 3000, "anything") == 0.0
    assert kept_ratio("ngan.", "anything") == 1.0           # khong co cau >40 ky tu -> 1.0
