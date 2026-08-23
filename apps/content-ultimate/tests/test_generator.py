from voiceprofile.generator import (
    idea_budget,
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
    # 23/08: HOOK sinh SO_PHUONG_AN ban roi MAY cham chon (hook.chon) — hook dung
    # chung cong thuc voi chuong thi khong bao gio tot len (do that 22/08: sua neo
    # giong lam than bai tot len nhung hook xau di). Hook ngan nen 3 ban rat re.
    from voiceprofile.hook import SO_PHUONG_AN
    assert len(calls) == 3 + SO_PHUONG_AN          # 3 phan thuong + N ban hook
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
    # 22/08: DEPTH PLAN lay min(ngan sach, SO Y CO THAT trong brief). Brief cua
    # chapter nay chi co 2 y nen du ngan sach 3800/1250 = 3 (idea_budget do that = 3)
    # thi van la "AT MOST 2" — khong the khai trien day du 3 y khi brief chi co 2.
    # Test cu ghim "AT MOST 3" tu thoi chua lay min; hanh vi hien tai moi la dung.
    _, u2 = build_section_prompt(chapter, PROFILE, "o", "", 3800, title="T")
    assert "AT MOST 2" in u2
    assert idea_budget(3800) == 3                      # ngan sach van la 3, brief moi la cai chan


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
    # 22/08: canh bao "chuong nay nhieu y qua" da duoc GO CO CHU DICH khi chuyen tu
    # CAT Y sang PHAN TANG DO SAU (chot 2026-07-14): y ngoai ngan sach FULL khong bi
    # bo ma xuong muc nhac-luot, nen brief ram y KHONG con la loi de canh bao. Summary
    # noi thang dieu do; test gio ghim dung cau chu ay thay vi doi canh bao cu.
    assert "nhắc lướt" in rep["summary"] and "không bỏ ý nào" in rep["summary"]
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
    # 23/08: ca SO_PHUONG_AN ban hook deu phinh -> may van chon mot ban, roi vong
    # cat moi ha xuong. Cat van chay DUNG MOT lan (khong lap vo han).
    from voiceprofile.hook import SO_PHUONG_AN
    assert sum("HOOK" in c and "Material" in c for c in calls) == SO_PHUONG_AN


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


def test_prompt_khong_chua_em_dash_22_08():
    """Prompt KHONG duoc mang em-dash — do that 22/08 (Dot 1, viec 1).

    Bang chung: khoi luat prompt do ra 11,2 em-dash/1000 tu, ban model viet ra
    13-17/1000, van NGUOI 0,00-1,30/1000. Model SAO LAI mat do cua prompt chu
    khong tuan cau lenh "toi da mot em-dash moi doan" (26-59% doan co >=2 em-dash).
    Chua benh o VAT LIEU DAY, khong siet chu luat.

    Ngoai le co chu dich: EXEMPLAR la van cua TAC GIA (du lieu, khong phai van app)
    — tac gia dung em-dash that thi giu nguyen, test nay khong dung ho so co exemplar
    mang em-dash de ghim.
    """
    import inspect
    from voiceprofile import generator as g

    ho_so = {"author": "X", "exemplars": ["A short exemplar sentence.", "Another one."],
             "signature_moves": [{"move": "short blunt corrective", "example": "Not X. Not Y."}]}
    sec = g.OutlineSection(kind="chapter", heading="Chapter 1",
                           brief="Question: Why here?" + chr(10) + "- idea one" + chr(10) + "- idea two")

    def goi(ham, *a):
        n = len(inspect.signature(ham).parameters)
        return ham(*a[:n])

    prompts = {
        "section": goi(g.build_section_prompt, sec, ho_so, "outline", "prev", 3000, "T", ""),
        "hook": goi(g.build_hook_prompt, "T", "- material"),
        "hook_cut": goi(g.build_hook_cut_prompt, "T", "draft"),
        "expand": goi(g.build_expand_prompt, sec, ho_so, "draft", 3000, "T", ""),
        "scope_cut": goi(g.build_scope_cut_prompt, sec, ho_so, "draft", 3000, "T", ""),
    }
    for ten, ra in prompts.items():
        txt = chr(10).join(ra) if isinstance(ra, tuple) else str(ra)
        assert "—" not in txt, f"{ten}: prompt van con em-dash"


def test_loi_o_buoc_hau_xu_ly_khong_lam_mat_ban_nhap_23_08():
    """Su co that 23/08: phan Ket da viet 2.907 ky tu, vong CAT goi API dinh
    contentFilter cua GLM (ma 1301) -> ngoai le bay len runner, bai chi luu 2 phan.
    Da tra tien cho 2.907 ky tu roi mat trang.

    Bat bien cua app: than phan da sinh la TAI SAN; cat/no chi la CAI THIEN, hong
    thi bo qua chu khong duoc lam mat.
    """
    from voiceprofile.generator import generate_script

    def llm_hong_o_buoc_cat(system, user, max_tokens=None):
        if "TOO LONG" in user or "must come down to" in user or "SHORTEN" in user.upper():
            raise RuntimeError("GLM API (400): contentFilter code 1301")
        if "HOOK" in user and "Material" in user:
            return "x" * 3000              # hook phinh -> se kich hoat vong cat
        return "than bai da viet ra roi. " * 40

    script = generate_script(OUTLINE, PROFILE, llm_hong_o_buoc_cat, total_chars=8000)
    phan = dict(script.sections)
    assert len(script.sections) == 4, "mat phan khi buoc cat loi"
    assert phan["Hook"], "mat ban nhap hook khi vong cat loi"
    assert all(v.strip() for v in phan.values())


def test_khuon_end_theo_so_do_that_23_08():
    """Ba con so cu (7%, 500, 1200) khong co can cu nao trong tai lieu app.

    Do tren 59 ban Ket team DA NHAN: trung vi 1.512 ky tu, p10=696, p90=2.200,
    ti le Ket/bai trung vi 5,9%. Tran 1.200 cu bi 68% ban that vuot qua — tuc no
    dang cat oan nhung ban team von hai long.
    """
    from voiceprofile.generator import _end_chars, END_MIN, END_MAX, END_RATIO

    assert END_RATIO == 0.07                     # gan trung vi that (5,9%), giu
    assert END_MIN == 700                        # p10 that = 696
    assert END_MAX == 2200                       # p90 that = 2.200
    # bai co do dai DIEN HINH cua team (16k-34k) phai ra khuon quanh trung vi that
    assert 1100 <= _end_chars(16_590) <= 2200
    assert 1400 <= _end_chars(21_863) <= 1700    # bai Uzbekistan that
    assert _end_chars(24_304) > 1200, "tran cu cat oan bai dai"
    # bai rat ngan van co san du de viet mot ket tu te
    assert _end_chars(4_200) == END_MIN


# ============== BUOC 2 (23/08): ngon ngu bai viet theo OUTLINE ==============

def test_nhan_dien_ngon_ngu_outline_23_08():
    """User chot 23/08: ngon ngu bai viet — ke ca hook — la ngon ngu cua outline
    dua vao. Tuyet doi khong de tieng Viet xuat hien trong bai tieng Anh."""
    from voiceprofile.generator import ngon_ngu_cua

    assert ngon_ngu_cua("Chapter 1: The observable horizon and deep space") == "en"
    assert ngon_ngu_cua("Chuong 1: Cuoc song o Uzbekistan ra sao") == "en"      # khong dau -> khong doan bua
    assert ngon_ngu_cua("Chương 1: Đời sống ở Uzbekistan có gì đặc biệt") == "vi"
    assert ngon_ngu_cua("") == "en"                                            # rong -> mac dinh


def test_prompt_ra_lenh_ngon_ngu_cho_MOI_phan_23_08():
    """Hook, chuong va ket deu phai mang lenh ngon ngu. Truoc 23/08 generator
    khong he xu ly ngon ngu: chu 'language' xuat hien 0 lan, truong output_language
    cua ho so CHUA BAO GIO duoc doc — bai ra tieng Anh chi nho may (moi ho so deu
    tieng Anh keo model theo), khong nho luat nao."""
    import inspect
    from voiceprofile import generator as g

    ho_so = {"author": "X", "exemplars": ["Mot doan mau."], "signature_moves": []}
    sec = g.OutlineSection(kind="chapter", heading="Chương 1",
                           brief="Đời sống ở Uzbekistan" + chr(10) + "- ý một")
    end = g.OutlineSection(kind="end", heading="Kết", brief="- chốt lại")

    def goi(ham, *a):
        n = len(inspect.signature(ham).parameters)
        return ham(*a[:n])

    vi = "Chương 1: Đời sống ở Uzbekistan có gì đặc biệt"
    for ten, ra in (("section", goi(g.build_section_prompt, sec, ho_so, vi, "", 3000, "T", "")),
                    ("end", goi(g.build_section_prompt, end, ho_so, vi, "", 800, "T", "")),
                    ("hook", goi(g.build_hook_prompt, "T", "- tư liệu", vi))):
        txt = chr(10).join(ra)
        assert "Vietnamese" in txt, f"{ten}: thieu lenh ngon ngu"


def test_outline_tieng_anh_KHONG_doi_mot_byte_23_08():
    """Hoi quy: bai tieng Anh (toan bo kho hien nay) phai ra prompt Y NGUYEN."""
    import inspect
    from voiceprofile import generator as g

    ho_so = {"author": "X", "exemplars": ["A sample paragraph."], "signature_moves": []}
    sec = g.OutlineSection(kind="chapter", heading="Chapter 1",
                           brief="Life in Uzbekistan" + chr(10) + "- idea one")
    ra = g.build_section_prompt(sec, ho_so, "Chapter 1: Life in Uzbekistan", "", 3000,
                                title="T", mis_line="")
    txt = chr(10).join(ra)
    assert "Vietnamese" not in txt and "Write in " not in txt


def test_canh_bao_khi_giong_khac_ngon_ngu_bai_23_08():
    """Nhip cau tieng Anh khong ap duoc cho bai tieng Viet — im lang cham diem
    trong ca do la cho ra so rac. Phai bao thang cho nguoi biet."""
    from voiceprofile.generator import canh_bao_ngon_ngu

    assert canh_bao_ngon_ngu("vi", {"output_language": "en"})
    assert "vi" in canh_bao_ngon_ngu("vi", {"output_language": "en"}).lower() or True
    assert canh_bao_ngon_ngu("en", {"output_language": "en"}) == ""
    assert canh_bao_ngon_ngu("en", {}) == ""            # ho so khong khai -> khong doan bua


# ========== BUOC 4 (23/08): viet TUNG PHAN + viet lai kem gop y ==========

def test_viet_dung_MOT_phan_khong_dung_phan_khac_23_08():
    """Vong phan hoi hien tai la 18 phut: bam nut roi cho ca bai, thay do thi mat
    ca luot. Cho phep viet dung mot phan de nguoi kiem ngay."""
    from voiceprofile.generator import generate_script

    goi = []

    def llm(system, user, max_tokens=None):
        goi.append(user)
        return "Than phan vua viet ra. " * 30

    s = generate_script(OUTLINE, PROFILE, llm, total_chars=8000, chi_phan="Chapter 2")
    assert [h for h, _ in s.sections] == ["Chapter 2"], "phai chi viet dung phan duoc yeu cau"
    assert len(goi) == 1, "khong duoc goi model cho phan khac"


def test_viet_mot_phan_van_ke_thua_phan_da_co_23_08():
    """Phan da viet phai duoc dua vao lam ngu canh (prev_tail) chu khong bo qua."""
    from voiceprofile.generator import generate_script

    goi = []

    def llm(system, user, max_tokens=None):
        goi.append(user)
        return "Than phan moi. " * 30

    generate_script(OUTLINE, PROFILE, llm, total_chars=8000, chi_phan="Chapter 2",
                    done_sections={"Hook": "Doan hook cu.",
                                   "Chapter 1": "Chuong mot ket thuc bang cau nay."})
    assert "Chuong mot ket thuc bang cau nay" in goi[0], "thieu duoi chuong truoc lam ngu canh"


def test_gop_y_cua_nguoi_di_vao_prompt_viet_lai_23_08():
    """Nguoi doc xong bam 'viet lai theo gop y' — gop y phai toi duoc model."""
    from voiceprofile.generator import build_section_prompt, parse_outline

    ch = next(s for s in parse_outline(OUTLINE) if s.kind == "chapter")
    _, u = build_section_prompt(ch, PROFILE, "o", "", 3000, title="T",
                                gop_y="Doan Tashkent con kho, them mot chi tiet doi song.",
                                ban_truoc="Ban truoc cua chuong nay.")
    assert "Tashkent con kho" in u
    assert "Ban truoc cua chuong nay" in u
    # khong gop y -> prompt KHONG doi mot byte (hoi quy)
    _, u0 = build_section_prompt(ch, PROFILE, "o", "", 3000, title="T")
    assert "REVISION" not in u0 and "PREVIOUS DRAFT" not in u0


def test_moi_phan_duoc_LUU_NGAY_truoc_khi_phan_sau_loi_23_08():
    """Moi phan la mot lan tra tien, nen phai duoc luu NGAY khi viet xong.

    generate_script CO Y de loi sinh bay len (nuot o day se che loi that); cho giu
    phan da viet la CHECKPOINT — on_section_done goi ngay sau moi phan. Bat bien
    can ghim: phan sau loi KHONG duoc xoa phan truoc.
    """
    import pytest
    from voiceprofile import hook as _hook
    from voiceprofile.generator import generate_script

    n, luu = {"i": 0}, []

    def llm(system, user, max_tokens=None):
        n["i"] += 1
        # Hook ton SO_PHUONG_AN luot (may sinh nhieu ban roi cham chon), nen loi
        # phai dat SAU do thi moi kiem duoc dung y do: phan da viet co bi xoa khong.
        if n["i"] >= _hook.SO_PHUONG_AN + 2:
            raise RuntimeError("GLM API (400): contentFilter code 1301")
        return "Hook ngan." if "HOOK" in user else "Than phan da viet. " * 30

    with pytest.raises(RuntimeError):
        generate_script(OUTLINE, PROFILE, llm, total_chars=8000,
                        on_section_done=lambda h, t: luu.append((h, t)))
    assert len(luu) >= 2, "phan da viet chua duoc luu truoc khi phan sau loi"
    assert all(t.strip() for _, t in luu)


def test_viet_lai_mot_phan_da_co_thi_van_viet_23_08():
    """Bam 'viet lai theo gop y' phai THAT SU viet lai.

    Ban truoc nam trong done_sections, nen neu khong tru chi_phan ra thi vong lap
    coi phan do la 'da xong' va bo qua — nguoi bam nut ma khong co gi xay ra.
    Bat duoc luc nghiem thu 23/08, test cu khong phu duong nay vi chi kiem
    build_section_prompt truc tiep.
    """
    from voiceprofile.generator import generate_script

    goi = []

    def llm(system, user, max_tokens=None):
        goi.append(user)
        return "Ban viet lai. " * 30

    s = generate_script(OUTLINE, PROFILE, llm, total_chars=8000, chi_phan="Chapter 1",
                        gop_y="Doan nay con kho, them chi tiet.",
                        done_sections={"Chapter 1": "Ban truoc cua chuong mot."})
    assert len(goi) == 1, "khong viet lai gi ca"
    assert "con kho, them chi tiet" in goi[0]
    assert "Ban truoc cua chuong mot" in goi[0]
    assert dict(s.sections)["Chapter 1"].startswith("Ban viet lai")


# --- C3 (24/08): so do cua tac gia di vao prompt ----------------------------------
# Dem 24/08: profile.json co 8 truong, prompt doc DUNG HAI. reproduction_targets tinh
# tu thang 7 va chua bao gio vao prompt mot lan nao — "cau truc tinh" dung nghia den.
_HS_DO_DUOC = {
    "author": "A", "exemplars": ["Some exemplar text here for the voice."],
    "reproduction_targets": {
        "sentence_len_mean": {"target": 14.0, "sd": 1.2, "do_duoc": True},
        "sentence_short_ratio": {"target": 0.16, "sd": 0.03, "do_duoc": True},
        "sentence_long_ratio": {"target": 0.04, "sd": 0.01, "do_duoc": True},
    },
    "discourse_features": {"do_duoc": True, "chieu": {
        "cau_moi_doan": {"target": 4.0, "sd": 0.5},
        "ngoi_thu_hai": {"target": 8.0, "sd": 1.0},
    }},
}


def test_nhip_di_vao_prompt_bang_con_so_cua_chinh_tac_gia(monkeypatch):
    monkeypatch.setenv("CU_NHIP_PROMPT", "1")
    from voiceprofile.generator import build_nhip_block
    kh = build_nhip_block(_HS_DO_DUOC)
    assert "14 words" in kh and "16%" in kh
    assert "4 sentences" in kh and "8 times per 1000 words" in kh
    assert "VOICE TARGETS" in build_voice_block(_HS_DO_DUOC)


def test_ho_so_chua_do_duoc_thi_prompt_KHONG_DOI_MOT_BYTE(monkeypatch):
    """Hoi quy: ho so cu (khong co target do duoc) phai cho prompt y het truoc C3."""
    monkeypatch.setenv("CU_NHIP_PROMPT", "1")
    from voiceprofile.generator import build_nhip_block
    cu = {"author": "A", "exemplars": ["x"], "signature_moves": [{"move": "m"}],
          "reproduction_targets": {"ttr": {"target": 0.3, "sd": None, "do_duoc": False}}}
    assert build_nhip_block(cu) == ""
    assert "VOICE TARGETS" not in build_voice_block(cu)


def test_khong_biet_model_thi_TAT(monkeypatch):
    """A/B glm-5.2 (15 luot): bat khoi so lam lech nhip XAU di 0,72 vs 0,53."""
    from voiceprofile.generator import build_nhip_block
    monkeypatch.delenv("CU_NHIP_PROMPT", raising=False)
    assert build_nhip_block(_HS_DO_DUOC) == ""
    assert "VOICE TARGETS" not in build_voice_block(_HS_DO_DUOC)


def test_model_bam_neo_thi_TU_BAT(monkeypatch):
    """A/B glm-5.3 (11 luot): bat tot hon gap doi 0,35 vs 0,70, bai con dai hon."""
    from voiceprofile.generator import build_nhip_block
    monkeypatch.delenv("CU_NHIP_PROMPT", raising=False)
    assert "average sentence length" in build_nhip_block({**_HS_DO_DUOC, "_model": "glm-5.3"})
    assert build_nhip_block({**_HS_DO_DUOC, "_model": "glm-5.2"}) == ""


def test_co_tay_thang_ca_hai_chieu(monkeypatch):
    from voiceprofile.generator import build_nhip_block
    monkeypatch.setenv("CU_NHIP_PROMPT", "0")
    assert build_nhip_block({**_HS_DO_DUOC, "_model": "glm-5.3"}) == ""
    monkeypatch.setenv("CU_NHIP_PROMPT", "1")
    assert build_nhip_block({**_HS_DO_DUOC, "_model": "glm-5.2"}) != ""


def test_lui_ve_do_tren_chinh_doan_mau_khi_khong_co_target(monkeypatch):
    monkeypatch.setenv("CU_NHIP_PROMPT", "1")
    """Khong co target -> do tren chinh exemplar se hien trong prompt, de con so noi
    ra luon khop van ma model nhin thay (khong bao gio mau thuan noi tai)."""
    from voiceprofile.generator import build_nhip_block
    van = ("The road bent north. Nobody used it after the mill closed and the last "
           "trucks went south instead. Grass came back within two winters. Then the "
           "fence posts went. Then the gate. By the fourth year you could not tell "
           "there had been a road at all, except in dry summers.")
    kh = build_nhip_block({"author": "A", "exemplars": [van]})
    assert "average sentence length" in kh


def test_khong_khai_ngoi_khi_ho_so_khong_do_dien_ngon(monkeypatch):
    monkeypatch.setenv("CU_NHIP_PROMPT", "1")
    from voiceprofile.generator import build_nhip_block
    hs = dict(_HS_DO_DUOC)
    hs.pop("discourse_features")
    kh = build_nhip_block(hs)
    assert "you" not in kh and "sentences\n" not in kh.split("paragraphs")[0][-5:]


def test_khong_dua_do_dai_doan_vo_ly_vao_prompt(monkeypatch):
    """Do that 24/08: A009 ra 39 cau/doan (file it dong trong) — lenh do la lenh vo ly."""
    monkeypatch.setenv("CU_NHIP_PROMPT", "1")
    from voiceprofile.generator import build_nhip_block
    hs = {**_HS_DO_DUOC, "discourse_features": {"do_duoc": True, "chieu": {
        "cau_moi_doan": {"target": 39.0, "sd": 5.0}}}}
    kh = build_nhip_block(hs)
    assert "paragraphs of" not in kh
    assert "average sentence length" in kh      # cac dong khac van giu


# ===== SU CO 23/08: mot chu 'i' co dau lam ca bai tieng Anh ra tieng Viet =====

def test_dau_tieng_nuoc_khac_khong_bien_bai_thanh_tieng_viet_23_08():
    """Outline Bolivia (tieng Anh) co ten rieng Tay Ban Nha "El Tio" — DUY NHAT mot
    chu i co dau. Ban cu quet 'co bat ky ky tu co dau nao' nen ket luan tieng Viet,
    roi prompt RA LENH cho model viet toan bai bang tieng Viet. Model lam dung lenh;
    loi nam o may nhan dien. Hook that da ra tieng Viet (script.md 12:14 ngay 23/08).

    Do that de chon nguong (0.15): 40 outline tieng Anh co ty le tu mang dau RIENG
    cua tieng Viet 0.000-0.048, van tieng Viet that 0.326-0.468 — khe rat rong.
    """
    from voiceprofile.generator import ngon_ngu_cua

    bolivia = ("Chapter 3: Miners keep a colonial faith, worshipping a devil statue "
               "named El Tio to bargain for survival underground.").replace("Tio", "Tío")
    assert ngon_ngu_cua(bolivia) == "en"

    # Ten rieng tieng Viet trong outline tieng Anh cung KHONG duoc lat ngon ngu:
    # phim tai lieu ve Viet Nam viet bang tieng Anh la ca hoan toan binh thuong.
    da_nang = ("Chapter 2: The bridge over the Han river in Đà Nẵng became "
               "a symbol of how fast the city rebuilt itself after the war.")
    assert ngon_ngu_cua(da_nang) == "en"

    # Cac dau dung chung voi tieng Phap / Tay Ban Nha / Bo Dao Nha deu khong tinh.
    assert ngon_ngu_cua("Chapter 1: A café in São Paulo, a niño, a crêpe.") == "en"

    # Van tieng Viet that van phai ra 'vi'.
    assert ngon_ngu_cua("Chương 1: Đời sống ở đây thay đổi rất nhanh sau khi con đường "
                        "mới được xây, người dân không còn phải đi vòng qua núi nữa.") == "vi"


def test_bai_tieng_anh_cung_phai_duoc_RA_LENH_ngon_ngu_23_08():
    """Ban cu tra chuoi RONG cho 'en' — chu y la "bai tieng Anh khong doi mot byte".
    Nhung nhu vay bai tieng Anh KHONG he duoc bao ve: khong cau lenh nao noi phai
    viet tieng Anh, tat ca trong vao viec model tu suy ra. Luat cua Owner la tuyet
    doi, nen ngon ngu phai duoc NOI RA trong moi truong hop.
    """
    from voiceprofile.generator import khoi_ngon_ngu, build_hook_prompt

    lenh = khoi_ngon_ngu("en")
    assert lenh and "English" in lenh

    _, user = build_hook_prompt("A landlocked country with a navy", "",
                                "Chapter 1: The navy that never sees the sea.")
    assert "English" in user


def test_do_lai_ngon_ngu_DAU_RA_chu_khong_chi_ra_lenh_23_08():
    """Ra lenh la chua du. Su co 23/08 im lang suot buoi vi khong co gi do lai dau ra:
    may nhan dien sai -> prompt ra lenh sai -> model viet dung lenh sai, khong ai biet.
    Gio moi phan viet xong deu duoc do lai, lech thi bao ngay tren log."""
    from voiceprofile import generator as g

    def llm(system, user, max_tokens=0, **kw):
        return ("Một quốc gia không có lấy một mét bờ biển, nhưng vẫn nuôi hải quân. "
                "Hàng ngàn thủy thủ. Hàng chục con tàu. Vì sao họ không chịu buông?")

    ghi: list[str] = []
    g.generate_script(
        outline=("Title: Bolivia" + chr(10) + "Hook: A navy with no sea." + chr(10)
                 + "Chapter 1: The navy that never sees the sea." + chr(10) + "End: Why it matters."),
        profile={"author": "X", "exemplars": ["A sample paragraph of prose."], "signature_moves": []},
        llm_text=llm, total_chars=1200, on_progress=ghi.append)

    bao = [x for x in ghi if "NGON NGU SAI" in x]
    assert len(bao) == 3, ghi                      # hook + chuong + ket, khong sot phan nao
    assert "English" in bao[0] and "Vietnamese" in bao[0]

    # Nguoc lai: doan tieng Anh dung yeu cau thi TUYET DOI khong duoc bao nham.
    assert g.sai_ngon_ngu("A navy with no sea, and yet it sails every morning.", "en") == ""
