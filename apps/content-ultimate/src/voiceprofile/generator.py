"""Module 5 — Generator: sinh kich ban YouTube theo giong tac gia.

Doc profile.json (exemplars + signature_moves) lam neo giong, nhan outline theo
khung co dinh Title / Hook / Chapter 1..n / End, sinh TUAN TU tung phan (chong troi
giong tren van ban dai) roi ghep MOT file script.md.

Phan vai (Muc 4 brief): giong CAU do profile quyet (exemplar + moves), lop luat
YouTube chi cham vao CAU TRUC (hook mo loop, chuong giu nhip, end dong loop) — hai
lop khong giam chan nhau. Logic nhan callback `llm_text(system, user) -> str` nen
test duoc offline.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .textutils import split_sentences, tokenize_words

# Mo hinh thoi luong YouTube (chot 2026-07-03): Hook ngan co dinh, End clamp, Body
# chia deu cho cac chuong. Chuong la DON VI BAO TOAN — khong tu chia; canh bao neu dai.
# Hook = tang PLATFORM thuan (KHONG dung giong tac gia): nhiem vu hook YouTube — ngan,
# truc dien, cau ngan nhip nhanh manh, bao quat title. Do dai 250-500 KY TU (~15-25 giay).
HOOK_CHARS_MIN, HOOK_CHARS_MAX = 250, 500
HOOK_CHARS = 375                 # giua khoang, dung cho allocate (tru khoi tong)
END_RATIO, END_MIN, END_MAX = 0.07, 500, 1200
CHAPTER_MIN_CHARS = 600
# Vung ngot chat luong cho 1 chuong: ~2500-4000 ky tu. Ngoai vung nay giong hong:
#  - < QUALITY: chuong qua ngan -> LLM nen -> van phang.
#  - > WARN:    chuong qua dai  -> troi giong nua sau.
CHAPTER_MIN_QUALITY = 2500
CHAPTER_WARN_CHARS = 4000

# --- Phuong phap 3 tang kiem soat do dai (chot 2026-07-09, xem DEVLOG) --------------
# LLM khong dem duoc ky tu khi viet nhung dem Y rat tot -> do dai = so y x do khai
# trien. Do that (thi nghiem Norway, glm-5): 1 y khai trien day du ~1.100-1.350 ky tu
# (3 y -> 3.735). Prompt giao NGAN SACH Y (Tang 2) thay cho con so ky tu.
CHARS_PER_IDEA = 1250
# Tang 3 (MOT vong ha-tang-y) chi chay khi vuot tran kem dung sai — khong dot them luot
# goi LLM chi vi vuot vai phan tram.
REVISE_OVER_RATIO = 1.15

# --- PHAN TANG DO SAU thay cho CAT Y (chot 2026-07-14) -------------------------------
# Sua sai lam cua ban 3-tang cu: no coi DO SAU la hang so (moi y ~1250 ky tu) nen chi
# con 2 can gat — bo y hoac nen van — ma nen van thi bi cam => buoc phai BO Y cua user.
# Cong thuc dung: do dai = TONG(do sau tung y), khong phai (so y x do sau co dinh).
# Moi y nhan mot MUC khai trien; y yeu nhat van xuat hien o muc MENTION => KHONG BO SOT.
# "Nhac luot" (mot cau gon, co y, long vao mach) KHAC "nen van" (ep khai trien day du
# thanh doan dac nghet) — luat "never compress the prose" giu nguyen cho cac y FULL.
CHARS_PER_MENTION = 110          # mot cau nhac luot


def depth_plan(n_ideas: int, target_chars: int, min_k: int = 2,
               chars_per_idea: int = 0) -> dict:
    """Phan bo do sau cho n_ideas trong ngan sach target_chars — Python tinh, tat dinh.

    Tra {full, mention, est_chars}. full = so y khai trien day du (kiem soat do dai);
    mention = phan con lai, moi y MOT cau. Khong bao gio bo y nao.

    Chon k = so y FULL sao cho uoc luong GAN target NHAT. Ban dau (2026-07-14) lay thang
    k = idea_budget(target) roi cong mention len tren => VUOT co he thong: idea_budget
    chon k sao cho k y FULL an HET target mot minh, nen moi y nhac-luot (+110) la phan
    doi ra. Do that: target 3500 + 10 y => 4520 ky tu (+29%); 12 y => +35%. Cang nhieu y
    cua user cang vuot nang — dung cai user bao "over ky tu qua nhieu" (2026-07-15).
    Nhac luot phai an vao ngan sach, khong duoc cong them.

    `chars_per_idea`: hang so RIENG cua tac gia (test lab). Bo trong -> hang so chung.
    """
    if not n_ideas:
        return {"full": 0, "mention": 0, "est_chars": 0}

    a = chars_per_idea or CHARS_PER_IDEA

    def est(k: int) -> int:
        return k * a + (n_ideas - k) * CHARS_PER_MENTION

    cap = min(idea_budget(target_chars, min_k=min_k, chars_per_idea=a), n_ideas)
    floor = min(min_k, n_ideas)      # san chat luong: it hon min_k y FULL thi chuong thanh danh sach
    k = min(range(floor, cap + 1), key=lambda x: abs(est(x) - target_chars))
    return {"full": k, "mention": n_ideas - k, "est_chars": est(k)}

# Lop luat nen tang YouTube cho CHAPTER/END — cham vao CAU TRUC (loop, nhip chuong),
# KHONG ep cau ngan. Ưu tien giong tac gia (cau dai, tu phong phu). Hook co prompt
# rieng (build_hook_prompt) — hook YouTube thuan, khong dung giong tac gia.
YOUTUBE_RULES = {
    # KHONG khang dinh mot phong cach cau cu the o day. Truoc 2026-07-16 dong nay hard-code
    # "long, clause-rich sentences that sweep and accumulate ... the author's LONG sentences
    # ARE the voice" cho MOI tac gia — trong khi Ventures that su viet 78-92 ky tu/cau (do
    # tren 86.000 ky tu corpus sach). Tool ep viet dai => LLM ra 271-307 ky tu/cau => user
    # bao "cau van phang va qua dai". Nhip cau phai den tu EXEMPLAR that (show, dung tell);
    # luat nen tang chi noi ve CAU TRUC (loop, nhip chuong), khong ve do dai cau.
    "chapter": (
        "PLATFORM (YouTube retention): carry ONE idea through this chapter and end on a "
        "small open loop that pulls the viewer into the next. It is voiceover, so it must "
        "read well aloud. Match the AUTHOR'S rhythm as shown in the examples above, "
        "including how long their sentences run and how that length rises and falls. "
        "Do not smooth every sentence to the same length: that flatness is what kills a "
        "voice."
    ),
    "end": (
        "PLATFORM (YouTube ending): close the curiosity loop opened in the hook and land "
        "the emotional beat. NO 'thanks for watching / like and subscribe'. Hold the "
        "author's voice to the final line: end on resonance, not a sign-off."
    ),
    "title": (
        "PLATFORM (YouTube title): one line, high-curiosity, no quotes around it."
    ),
}

# Moc phan trong outline. Nhan dien LINH HOAT: co/khong dau ':' , em-dash '—', markdown
# '#', viet hoa/thuong, va ca khi outline khong xuong dong (finditer tren toan text).
_SECTION_MARK = re.compile(
    r"(?im)(?:^|(?<=\s))#*\s*"
    r"\b(hook|chapters?\s*\d+|chapters?|end|ending|outro|conclusion|intro|introduction)\b"
    r"\s*[:.\-–—)]*\s+"
)

# Dong metadata do compose.py (board Outline) tu ghi: `Angle:` = goc goc tai peak,
# `CTA:` = cau keu goi hanh dong; V2 (2026-07-26) them `Question:` = cau hoi vien
# NGUYEN VAN tu comment, `Misconception:` = niem tin sai M cua hook. Chung la VAN XUOI,
# khong phai cau truc — nhung lai chua dung nhung tu _SECTION_MARK san lung
# (vd Question: "Watch till the end?" — chinh lop loi CTA 2026-07-15).
_META_LINE = re.compile(r"(?im)^[ \t]*(?:angle|cta|question|misconception)[ \t]*:.*$")

# V2 (2026-07-26): 2 dong meta cua cong thuc V = (M + (Q->E)) x (A + B).
# Question: cau hoi vien NGUYEN VAN (khong duoc sua chu — verify duoc trong comment
# that); Misconception: niem tin sai M ma hook be gay. Writer TACH chung khoi brief
# roi tiem lai thanh khoi luat rieng (_v2_meta / _v2_section_block).
_Q_LINE = re.compile(r"(?im)^[ \t]*question[ \t]*:[ \t]*(.*\S)[ \t]*$")
_MIS_LINE = re.compile(r"(?im)^[ \t]*misconception[ \t]*:[ \t]*(.*\S)[ \t]*$")


def _v2_meta(brief: str) -> tuple[str, str, str]:
    """Tach meta V2 khoi brief -> (question, mis_line, brief-sach).

    Brief sach de dua vao prompt: dong Question:/Misconception: da duoc tiem lai
    thanh khoi luat, de nguyen trong brief la lap doi. Angle:/CTA: GIU NGUYEN
    (hanh vi cu)."""
    q = _Q_LINE.search(brief or "")
    m = _MIS_LINE.search(brief or "")
    clean = _Q_LINE.sub("", _MIS_LINE.sub("", brief or ""))
    clean = re.sub(r"\n{3,}", "\n\n", clean).strip()
    return (q.group(1).strip() if q else "", m.group(1).strip() if m else "", clean)


def _v2_section_block(question: str, mis_line: str) -> str:
    """Khoi luat Writer V2 cho chapter/end — ban chot 2026-07-26 sau 2 thi nghiem tay
    (Jupiter deep-dive + Moscow toplist, user duyet tung chuong). RONG khi outline
    khong phai V2 (gate: khong co Question/Misconception -> hanh vi cu nguyen ven).

    Tung khoi deu tra gia moi co (xem CONTENT-ULTIMATE-V2-MASTER.md PHAN V):
    OPENING = Q->E long chuong; PACING = 2 luat HEP (metronome hoi-dap per-doan da
    thu va BI LOAI — tai pham lop loi luat-hoa-nhip 07-16); LOOP DISCIPLINE = vet ro
    reveal C1 Jupiter; BREAK STANDS = ban (b) viet 'Jupiter is a gas giant' phan hook."""
    if not question and not mis_line:
        return ""
    blocks = []
    if question:
        blocks.append(
            "OPENING (Question-first): begin this section by RAISING this real viewer "
            f"question:\n\"{question}\"\n"
            "Rephrase it naturally in the author's voice: or quote the viewer's wording "
            "if it lands harder. Your FIRST sentence must not answer it. Let the section "
            "build to the answer: the explanation is the reward, not the greeting."
        )
    blocks.append(
        "PACING: only two rules; the author's examples above set everything else:\n"
        "- Rhetorical questions inside the section: at most one or two, and only at a "
        "true turn in the argument. Do not open consecutive paragraphs with a question "
        "or an imperative ('Consider...', 'Think...'). Paragraphs connect through their "
        "content, each flowing out of the last, not by restarting.\n"
        "- ONE idea per sentence. A long sentence is welcome when a single idea gathers "
        "momentum; never lengthen one by packing in a list or a second aside. At most "
        "one em-dash insertion per paragraph, if a sentence needs two, split it."
    )
    blocks.append(
        "LOOP DISCIPLINE: the outline above assigns each reveal to its own chapter. Do "
        "NOT pay off another chapter's reveal here. If your material builds toward "
        "something a LATER chapter owns, gesture toward it and leave it unopened: "
        "tension you hand to the next chapter is a gift, not a debt."
    )
    if mis_line:
        blocks.append(
            "THE HOOK'S BREAK STANDS: the hook has already told the viewer this belief "
            f"is FALSE: \"{mis_line}\". Never re-assert that belief as fact, not even "
            "in passing. Every chapter lives downstream of that break."
        )
    return "\n\n".join(blocks)


# Ky tu lap cho: khong phai khoang trang, khong tao tu khoa nao. KHONG duoc che bang
# dau cach — _SECTION_MARK co `\s*` truoc tu khoa nen no NUOT het khoang trang vua che
# vao moc ke tiep, keo theo ca dong Angle:/CTA: ra khoi brief (do that 2026-07-15).
_MASK_CH = "x"


def _mask_meta(text: str) -> str:
    """Che noi dung dong Angle:/CTA: — GIU NGUYEN do dai va so dong de moi offset cua
    _SECTION_MARK van tro dung vi tri trong text GOC (brief van cat tu text goc).

    Vi sao can (loi that 2026-07-15): CTA doi thuong nhu "Watch till the end!",
    "Comment below your intro song", "Chapter 2 is on our channel" chua tu khoa moc =>
    parse_outline cat outline thanh cac phan MA (hook bi xe doi, chuong bi gan nhan end)
    => sai so phan => sai phan bo do dai => kich ban vuot ky tu. Cai gia cua viec nhan
    dien moc "linh hoat o bat ky dau" (de chiu outline lien mot khoi).
    """
    return _META_LINE.sub(lambda m: _MASK_CH * len(m.group(0)), text)


@dataclass
class OutlineSection:
    kind: str          # "title" | "hook" | "chapter" | "end"
    heading: str       # nhan hien thi, vd "Chapter 2"
    brief: str         # noi dung outline nguoi dung viet cho phan nay


@dataclass
class Script:
    title: str = ""
    sections: list[tuple[str, str]] = field(default_factory=list)  # (heading, body)

    def to_markdown(self) -> str:
        lines = [f"# {self.title}"] if self.title else []
        for heading, body in self.sections:
            lines += ["", f"## {heading}", "", body]
        return "\n".join(lines).strip() + "\n"


def parse_outline(text: str) -> list[OutlineSection]:
    """Parse outline khung Title/Hook/Chapter N/End thanh cac OutlineSection.

    Tim cac moc tu-khoa (hook/chapter N/end...) trong toan van ban — chiu duoc ca khi
    outline viet lien mot khoi khong xuong dong. Phan TRUOC moc dau tien = Title (bo
    dau markdown '#'). Moi moc -> section, brief = van ban tu sau moc den moc ke tiep.

    Dong Angle:/CTA:/Question:/Misconception: bi CHE khi tim moc (xem _mask_meta) —
    noi dung cua chung van nam nguyen trong brief, chi khong duoc coi la moc phan.

    2 pass (B1 V2, 2026-07-26): brief V2 CO CHU DICH nhac ten phan khac ("Chapter 2's
    reveal", "belongs to the ENDING", "the hook's break") — luat loop discipline. Neu
    ban che co it nhat MOT dong bat dau bang moc chuong (template compose/V2 luon the)
    thi CHI nhan moc dau dong; outline dan lien mot khoi khong co dong chuong -> roi
    ve san-moi-noi nhu cu.
    """
    text = text.strip()
    if not text:
        return []
    masked = _mask_meta(text)
    marks = list(_SECTION_MARK.finditer(masked))             # tim tren ban CHE
    line_marks = []
    for m in marks:
        # Đi lùi từ TỪ KHOÁ (start(1)), KHÔNG từ đầu match — `\s*` trước từ khoá ngoạm
        # được cả '\n' nên m.start() có thể đứng ở CUỐI DÒNG TRƯỚC (lỗi thật 2026-07-27:
        # 'Title: ' trống → match HOOK bắt đầu sau dấu cách của Title → bị coi là giữa
        # dòng → HOOK văng khỏi mốc → cả khối hook bị nuốt vào title, Writer bỏ qua hook).
        i = m.start(1)
        while i > 0 and masked[i - 1] in " \t#":
            i -= 1
        if i == 0 or masked[i - 1] == "\n":
            line_marks.append(m)
    if any(re.match(r"(?i)chapter|intro", m.group(1)) for m in line_marks):
        marks = line_marks
    if not marks:
        return []

    sections: list[OutlineSection] = []
    head = text[:marks[0].start()].strip().lstrip("#").strip()
    head = re.sub(r"^title\s*[:.\-–—]*\s*", "", head, flags=re.I).strip()  # bo nhan 'Title:' neu co
    if head:
        sections.append(OutlineSection(kind="title", heading="Title", brief=head))

    for i, m in enumerate(marks):
        label = re.sub(r"\s+", " ", m.group(1).strip()).lower()
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        brief = text[m.end():end].strip()
        if label == "hook":
            kind, heading = "hook", "Hook"
        elif label in ("end", "ending", "outro", "conclusion"):
            kind, heading = "end", "End"
        elif label in ("intro", "introduction"):
            kind, heading = "chapter", "Intro"
        else:  # chapter N / chapter
            kind = "chapter"
            heading = re.sub(r"\s+", " ", m.group(1).strip()).title()
        sections.append(OutlineSection(kind=kind, heading=heading, brief=brief))
    return sections


def _end_chars(total_chars: int) -> int:
    return max(END_MIN, min(END_MAX, round(END_RATIO * total_chars)))


def allocate_section_chars(content_sections: list[OutlineSection], total_chars: int) -> list[int]:
    """So ky tu muc tieu cho tung phan noi dung (song song content_sections).

    Hook co dinh HOOK_CHARS; End clamp 7% (500..1200); Body = phan con lai chia DEU
    cho cac chuong (chuong tuong dong).
    """
    n_ch = sum(1 for s in content_sections if s.kind == "chapter")
    reserved = 0
    for s in content_sections:
        if s.kind == "hook":
            reserved += HOOK_CHARS
        elif s.kind == "end":
            reserved += _end_chars(total_chars)
    per_ch = max(CHAPTER_MIN_CHARS, round((total_chars - reserved) / n_ch)) if n_ch else 0
    out = []
    for s in content_sections:
        if s.kind == "hook":
            out.append(HOOK_CHARS)
        elif s.kind == "end":
            out.append(_end_chars(total_chars))
        else:
            out.append(per_ch)
    return out


def _chars_per_idea(profile: dict) -> int:
    """Hang so ky tu/brief RIENG cua tac gia (do bang test lab), 0 neu chua chay lab.

    Import cuc bo: lengthlab import nguoc lai generator (build_section_prompt) — de o dau
    file la vong tron.
    """
    from .lengthlab import chars_per_brief_of
    return chars_per_brief_of(profile or {}, 0)


def idea_budget(target_chars: int, min_k: int = 2, chars_per_idea: int = 0) -> int:
    """So Y toi da cho mot phan dai target_chars (Tang 1/2) — Python tinh, tat dinh.

    `chars_per_idea`: hang so RIENG cua tac gia do bang test lab (lengthlab.py). Bo trong
    -> dung CHARS_PER_IDEA chung. Do that 2026-07-15: Ventures 1408 / Lewis 1720 — mot
    hang so chung la sai cho ca hai.
    """
    return max(min_k, min(4, round(target_chars / (chars_per_idea or CHARS_PER_IDEA))))


_IDEA_SEG = re.compile(r"[.;!?•\n]+|\s—\s")


def estimate_ideas(brief: str) -> int:
    """Uoc luong so Y trong brief — heuristic co chu dich (hieu chinh 2026-07-09 tren
    brief board Outline: ~55-60 ky tu/y). CHI dung de canh bao Tang 1, khong dieu khien.

    Dong meta (Angle:/CTA:/Question:/Misconception:) bi LOAI truoc khi dem — chung la
    chi dan cho Writer, khong phai Y noi dung; de nguyen thi thanh y ma (benh Pillar:
    dem phong -> depth_plan ha nham y that xuong nhac luot)."""
    brief = _META_LINE.sub("", brief or "").strip()
    if not brief:
        return 0
    segs = [s for s in _IDEA_SEG.split(brief) if s.strip()]
    return max(len(segs), round(len(brief) / 58))


def outline_scope_report(outline: str, total_chars: int) -> dict:
    """Tang 1 — bao cao pham vi outline TRUOC khi viet (Python do, khong ton LLM).

    scope_warnings: brief cua chuong nao ram y hon ngan sach -> nen bot/gop trong
    outline. structure_warnings: so chuong lech voi tong ky tu (trung logic canh bao
    trong generate_script — de UI hien truoc khi bam WRITE).
    """
    sections = parse_outline(outline)
    content = [s for s in sections if s.kind != "title"]
    if not content:
        return {"summary": "", "chapters": [], "scope_warnings": [],
                "structure_warnings": [], "warnings": ["Outline chưa nhận diện được phần nào."]}
    allocs = allocate_section_chars(content, total_chars)
    chapters, scope_warnings, structure_warnings, scope_plans = [], [], [], []
    for s, a in zip(content, allocs):
        if s.kind != "chapter":
            continue
        est = estimate_ideas(s.brief)
        plan = depth_plan(est, a)
        k = plan["full"]
        chapters.append({"heading": s.heading, "alloc": a, "idea_budget": k,
                         "est_ideas": est, "full": k, "mention": plan["mention"],
                         "est_chars": plan["est_chars"]})
        # Bao KE HOACH (khong phai canh bao): moi y deu co mat, chi khac muc khai trien.
        if plan["mention"]:
            scope_plans.append(
                f"{s.heading}: ~{est} ý → {k} khai triển đầy đủ + {plan['mention']} nhắc "
                f"lướt (~{plan['est_chars']} ký tự / mục tiêu {a}). Không ý nào bị bỏ.")
        # Chi CANH BAO khi ngay ca muc toi thieu cung vuot — luc do user phai quyet
        # (nang muc tieu hay bot y), tool khong duoc am tham cat (luat A3).
        if plan["est_chars"] > a * REVISE_OVER_RATIO:
            scope_warnings.append(
                f"{s.heading}: ~{est} ý — kể cả khi chỉ khai triển đầy đủ {k} ý và nhắc "
                f"lướt phần còn lại vẫn cần ~{plan['est_chars']} ký tự, vượt mục tiêu {a}. "
                "Nâng mục tiêu độ dài, hoặc tự bớt/gộp ý trong outline.")
    per = chapters[0]["alloc"] if chapters else 0
    if per > CHAPTER_WARN_CHARS:
        need = min_chapters_for(total_chars,
                                any(s.kind == "hook" for s in content),
                                any(s.kind == "end" for s in content))
        structure_warnings.append(
            f"Mỗi chương ~{per} ký tự, vượt trần {CHAPTER_WARN_CHARS} — nên chia outline "
            f"thành ít nhất {need} chương.")
    elif chapters and per < CHAPTER_MIN_QUALITY:
        structure_warnings.append(
            f"Mỗi chương chỉ ~{per} ký tự (< ngưỡng chất lượng {CHAPTER_MIN_QUALITY}) — "
            "nên giảm số chương hoặc tăng tổng ký tự.")
    summary = (f"Outline: {len(chapters)} chương · ~{per} ký tự/chương · {idea_budget(per)} ý "
               f"khai triển đầy đủ/chương, ý còn lại nhắc lướt — không bỏ ý nào "
               f"(mục tiêu tổng {total_chars}).") if chapters else ""
    return {"summary": summary, "chapters": chapters, "scope_warnings": scope_warnings,
            "structure_warnings": structure_warnings, "scope_plans": scope_plans,
            "warnings": scope_warnings + structure_warnings}


def min_chapters_for(total_chars: int, has_hook: bool, has_end: bool) -> int:
    """So chuong toi thieu de moi chuong <= CHAPTER_WARN_CHARS (dung cho canh bao)."""
    reserved = (HOOK_CHARS if has_hook else 0) + (_end_chars(total_chars) if has_end else 0)
    body = max(0, total_chars - reserved)
    return max(1, math.ceil(body / CHAPTER_WARN_CHARS))


def build_voice_block(profile: dict) -> str:
    """Khoi huong dan giong dung chung cho moi phan: exemplar + signature moves."""
    author = profile.get("author", "the author")
    parts = [
        f"You are ghost-writing in the exact prose voice of {author}. The exemplar "
        "passages below are the ground truth for this voice: match their rhythm, "
        "sentence-length variation, imagery, and stance toward the reader. Do NOT copy "
        "their sentences.",
    ]
    exemplars = profile.get("exemplars", [])[:3]
    if exemplars:
        parts.append("\nEXEMPLARS (voice ground truth):")
        for i, ex in enumerate(exemplars, 1):
            parts.append(f"[{i}] {ex}")
    moves = profile.get("signature_moves", [])
    if moves:
        parts.append("\nSIGNATURE MOVES (use these deliberately, they are verified in the author's real work):")
        for m in moves:
            parts.append(f"- {m['move']}")
    return "\n".join(parts)


def build_hook_prompt(title: str, brief: str) -> tuple[str, str]:
    """Hook YouTube thuan — KHONG dung giong tac gia. Ngan, truc dien, cau ngan nhip nhanh.

    V2: brief co dong Misconception: -> khoi THE FALSE BELIEF (3 luat, chot sau 2 ban
    hook bi user loai: ban 1 warm-up truoc khi be, ban 2 lo payoff cua video)."""
    _q, mis_line, brief = _v2_meta(brief)
    system = (
        "You are an elite YouTube scriptwriter. Your only job here is to write HOOKS that "
        "stop the scroll and make viewers unable to look away. You write hooks, not "
        "literary prose, punchy, direct, propulsive."
    )
    user_parts = []
    if title:
        user_parts.append(f'Write ONLY the HOOK for a YouTube video titled:\n"{title}"\n')
    else:
        user_parts.append("Write ONLY the HOOK for a YouTube video.\n")
    user_parts.append(
        "The hook must:\n"
        "- Grab attention in the very first line: open on the single most gripping idea.\n"
        "- Use short, direct, punchy sentences with fast, strong rhythm (vary length, but "
        "lean SHORT, this is the opposite of long literary prose).\n"
        "- Deliver on the promise of the TITLE above; make the viewer feel its stakes.\n"
        "- Open a curiosity loop the rest of the video will pay off.\n"
        "- NO channel intro, NO 'hello everyone', NO 'in this video'.\n"
        f"- VERY SHORT: about {HOOK_CHARS_MIN}-{HOOK_CHARS_MAX} characters "
        "(~15-25 seconds of narration). A few tight, hard-hitting sentences, no more.\n"
    )
    if brief:
        # KHONG goi la "Points to hit": hook mo DUNG MOT vong to mo, khong phai bang kiem
        # moi y. Tu 2026-07-14 brief cua HOOK con keo theo dong `Angle:`/`CTA:` (compose.py)
        # => "points to hit" bat LLM noi het ca chung, hook phinh vuot xa 250-500 (user bao
        # 2026-07-15). Day la NGUYEN LIEU de chon, khong phai danh sach phai phu kin.
        user_parts.append(
            f"\nMaterial you may draw from, NOT a checklist:\n{brief}\n"
            "\nTake ONLY the single most gripping thread from that material and open the "
            "loop with it. Deliberately LEAVE OUT everything else: the video itself pays "
            "the rest off, and a hook that covers every point is not a hook. Ignore any "
            "'Angle:' or 'CTA:' line except as background for choosing that one thread.\n")
    if mis_line:
        user_parts.append(
            "\nTHE FALSE BELIEF (top priority). The audience believes this:\n"
            f'"{mis_line}"\n'
            "Build the hook around BREAKING it:\n"
            "1. Your FIRST sentence must BE the break: open on the negation itself "
            "(the \"my life is a lie\" moment hits at second zero). Do NOT warm up by "
            "restating or explaining the belief first: the viewer already holds it, "
            "hearing it again reads as something they already know.\n"
            "2. Immediately after, in one short breath, name the belief being broken, "
            "so the viewer knows exactly which rug was pulled.\n"
            "3. That break creates ONE question. Open that question and leave it open. "
            "Do NOT reveal the answer: that reveal is the video's payoff; saying it "
            "here kills the loop.\n"
            "Break ONLY this one belief, do not claim everything they know is wrong.\n"
            + ("4. The material above is BACKGROUND ONLY, never a second opening. If it "
               "suggests starting another way (asking the audience a warm-up question, "
               "introducing the topic, setting a scene), IGNORE that start: the break "
               "is the only opening. You are NOT covering the material's ideas: one "
               "belief broken, one question opened, done.\n" if brief else ""))
    user_parts.append("\nOutput prose only: no heading, no markdown, no notes.")
    return system, "".join(user_parts)


def build_hook_cut_prompt(title: str, draft: str, keep_break: bool = False) -> tuple[str, str]:
    """MOT vong cat khi hook viet ra vuot HOOK_CHARS_MAX.

    Hook KHONG dung build_scope_cut_prompt (do la giong tac gia + ha tang y). Hook la
    tang platform: cat = bo bot moi truong, giu don mot cu moc. Truoc 2026-07-15 hook
    KHONG he co chot do dai nao — viet dai bao nhieu cung loft qua.
    """
    system = (
        "You are an elite YouTube scriptwriter. You cut hooks down to their sharpest form."
    )
    user = (
        f'Here is a draft HOOK{f" for the video titled: \"{title}\"" if title else ""}:'
        f"\n\n{draft}\n\n"
        f"It is TOO LONG. Cut it to about {HOOK_CHARS_MIN}-{HOOK_CHARS_MAX} characters "
        ", a few tight, hard-hitting sentences.\n"
        "- Keep the single strongest opening line and the curiosity loop; cut everything "
        "that merely explains, sets up, or covers extra points.\n"
        "- Do not summarise the video. Do not add anything new.\n"
        "- Keep the punchy, short-sentence rhythm.\n"
        + ("- Keep the false-belief break AND the unanswered question intact.\n"
           if keep_break else "")
        + "Output prose only: no heading, no markdown, no notes."
    )
    return system, user


def build_section_prompt(
    section: OutlineSection,
    profile: dict,
    outline_summary: str,
    prev_tail: str,
    target_chars: int,
    title: str = "",
    mis_line: str = "",
) -> tuple[str, str]:
    """Tra ve (system, user) cho mot phan.

    Hook: prompt YouTube thuan (khong giong tac gia). Chapter/End: giong tac gia + luat YouTube.
    V2: `mis_line` = Misconception cua HOOK (generate_script tach mot lan, truyen xuong
    moi chuong — luat BREAK STANDS); Question: cua chinh phan nay tach tu brief.
    """
    if section.kind == "hook":
        return build_hook_prompt(title, section.brief)
    question, _own_mis, clean_brief = _v2_meta(section.brief)

    system = build_voice_block(profile)
    rule = YOUTUBE_RULES.get(section.kind, YOUTUBE_RULES["chapter"])
    parts = [
        f"FULL SCRIPT OUTLINE (for context, do not rewrite other parts):\n{outline_summary}",
        "",
        rule,
    ]
    if prev_tail:
        parts += ["", f"The previous section ended with:\n…{prev_tail}\n"
                  "Continue naturally from there, do not repeat it, keep the thread unbroken."]
    # Tang 2 — NGAN SACH Y thay cho so ky tu (chot 2026-07-09): LLM khong dem duoc
    # ky tu nhung dem y rat tot; do dai la he qua cua so y x khai trien day du.
    # k lay tu depth_plan (KHONG phai idea_budget tho): nhac luot phai an vao ngan sach,
    # neu khong cang nhieu y cang vuot (do that +35%, sua 2026-07-15).
    min_k = 1 if section.kind == "end" else 2
    k = depth_plan(estimate_ideas(section.brief), target_chars, min_k=min_k,
                   chars_per_idea=_chars_per_idea(profile))["full"]
    # Tang 2 — PHAN TANG DO SAU (2026-07-14): k y FULL kiem soat do dai, nhung MOI y con
    # lai VAN PHAI XUAT HIEN o muc nhac-luot. Truoc day cau nay bao "leave the rest out
    # entirely" -> vut y cua user; do dai van kiem soat duoc ma khong can bo y nao.
    scope_rule = (
        f"DEPTH PLAN: develop AT MOST {k} distinct idea{'s' if k > 1 else ''} from the "
        f"brief FULLY: choose the {k} most central. EVERY OTHER idea in the brief MUST "
        "STILL APPEAR: condense each of them into ONE clear sentence woven into the flow "
        ", a passing mention, not a full treatment. NEVER drop an idea from the brief, "
        "and never add ideas beyond it. Develop each chosen idea FULLY in the author's "
        "voice, vivid, concrete, unhurried. Never compress the prose flat or drop the "
        "long sweeping sentences and concrete imagery of the FULL ideas: that richness "
        "IS the voice (a one-sentence mention is a deliberate short form, not compressed "
        "prose). When the last idea has landed, close the section as the platform rule "
        "above describes, then STOP."
    )
    parts += [
        "",
        f"Now write ONLY the section \"{section.heading}\".",
        "This is the outline brief for it: a SKELETON of bullet points to expand, NOT "
        f"text to copy. Write full flowing prose that develops these points:\n{clean_brief}",
    ]
    v2 = _v2_section_block(question, mis_line)
    if v2:
        parts += ["", v2]
    parts += [
        "",
        scope_rule,
        "Do NOT restate the brief or list its points: turn them into narrated writing. "
        "Output prose only: no heading, no markdown, no bullet points, no notes, no "
        "stage directions.",
    ]
    return system, "\n".join(parts)


def build_scope_cut_prompt(section: OutlineSection, profile: dict, draft: str,
                           target_chars: int, mis_line: str = "") -> tuple[str, str]:
    """Tang 3 — MOT vong HA TANG Y khi phan viet ra vuot tran: FULL -> nhac luot.

    2026-07-14: truoc day vong nay XOA HAN y (mat y cua user). Gio chi HA MUC khai trien
    — y van con mat o mot cau. Van giu luat "khong nen van" cho cac y FULL.
    Khac Module 6 auto-revise (chua build): khong toi uu theo diem %, chi giu cam ket
    thoi luong bang cach ha do sau; chat van cac doan FULL giu nguyen.

    Dung CHUNG depth_plan voi Tang 2 (sua 2026-07-15): truoc day goi thang idea_budget
    nen vong cat lai doi dung cai k gay vuot => cat xong van vuot.
    """
    min_k = 1 if section.kind == "end" else 2
    k = depth_plan(estimate_ideas(section.brief), target_chars, min_k=min_k,
                   chars_per_idea=_chars_per_idea(profile))["full"]
    system = build_voice_block(profile)
    user = (
        f'Here is a draft of the section "{section.heading}" you wrote:\n\n{draft}\n\n'
        f"It runs long because too many ideas are developed at full length. Rewrite it "
        f"keeping ONLY the {k} most central idea{'s' if k > 1 else ''} at FULL "
        "development. Every OTHER idea must STILL APPEAR, each demoted to ONE single "
        "sentence woven into the flow: do NOT delete any idea, only shorten its form. "
        "Do NOT compress or flatten the ideas that stay at full development: keep the "
        "author's voice, rhythm and the strongest passages intact. "
        "Keep the section's closing (the open loop or landing) intact.\n"
        "Output prose only: no heading, no markdown, no notes."
    )
    # V2: vong sua chay MU la nguon ro payoff chuong khac (do that: lieu 2 Jupiter
    # 2392->4736 lo reveal C3) — luat V2 phai song ca trong vong cat/no.
    question, _m, _b = _v2_meta(section.brief)
    v2 = _v2_section_block(question, mis_line)
    if v2:
        user += ("\nKeep the section's opening (the raised viewer question) intact.\n\n"
                 + v2)
    return system, user


# --- Vong NO (Tang 3 chieu nguoc, cai 2026-07-17 sau vong phan bien co so lieu) --------
# Chuong viet ra HUT so khung (ho so giong viet ngan — do that: A008 exemplar 1.164 ky tu
# -> hut deu -34%). Lech la benh toan he, ca 2 chieu, ke ca tac gia tot (A003: -9..+113%)
# => can bo dieu toc 2 chieu theo TUNG BAI, khong chi sua ho so.
# Don bay TY LE (do: -46% -> +5%, giu 89-100% van cu); lenh dem so y bi loai (pha 57% van).
EXPAND_FLOOR = 0.8        # <80% khung = hut (tac gia khoe thap nhat -9% — khong bao gio cham)
EXPAND_KEPT_MIN = 0.7     # phai giu >=70% cau cu (do that 89-100%; duoi nguong = viet lai trom)
EXPAND_MAX_ROUNDS = 2     # 1 luot thuong du (do that ve -1%); luot 2 la bao hiem phuong sai
EXPAND_STARVING = 10      # gian brief >10x = doi nguyen lieu -> NO = ep LLM bia -> KHONG no


def build_expand_prompt(section: OutlineSection, profile: dict, draft: str,
                        pct: int, mis_line: str = "") -> tuple[str, str]:
    """MOT luot NO khi chuong hut: nang cac y dang nhac-luot len khai trien day du.

    Chi hop le khi brief CON y chua khai trien — chieu sau that, nam trong outline user
    da duyet. Nguoc voi build_scope_cut_prompt; cung don bay ty le."""
    question, _m, clean_brief = _v2_meta(section.brief)
    system = build_voice_block(profile)
    user = (
        f'Here is a draft of a chapter you wrote:\n\n{draft}\n\n'
        f"It runs about {pct}% SHORTER than needed. Expand it by about {pct}%, by "
        "developing MORE ideas from the brief below into FULL passages. Choose the ideas "
        "currently covered in only one passing line and develop each fully in the "
        "author's voice: vivid, concrete, unhurried. Do NOT pad or inflate existing "
        "sentences; do NOT repeat anything; keep every existing passage intact (smoothing "
        "transitions is fine). Never compress the prose flat.\n\n"
        f"The chapter's brief:\n{clean_brief}\n\n"
        "Output the FULL expanded chapter, prose only: no heading, no markdown, no notes."
    )
    # V2: ban no chay mu = nguon ro payoff + van kham (bai hoc lieu 2, 2026-07-26).
    v2 = _v2_section_block(question, mis_line)
    if v2:
        user += "\n\n" + v2
    return system, user


def kept_ratio(old: str, new: str) -> float:
    """Phan van cu SONG SOT trong ban no — chong 'no' bang cach viet lai tu dau.

    Do theo cau dai >40 ky tu, khop 60 ky tu dau. Khong co cau do duoc -> 1.0
    (khong the mat thu khong do duoc)."""
    olds = [s.strip() for s in split_sentences(old) if len(s.strip()) > 40]
    if not olds:
        return 1.0
    return sum(1 for s in olds if s[:60] in new) / len(olds)


def _tail(text: str, n_words: int = 60) -> str:
    words = tokenize_words(text)
    if len(words) <= n_words:
        return text.strip()
    # cat theo ranh gioi cau gan cuoi cho muot
    sents = split_sentences(text)
    tail, count = [], 0
    for s in reversed(sents):
        tail.insert(0, s)
        count += len(tokenize_words(s))
        if count >= n_words:
            break
    return " ".join(tail).strip()


def _vn_int(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def render_header(author: str, target_chars: int, actual_chars: int,
                  provider_label: str, model: str) -> str:
    """Front-matter thong tin o dau file kich ban (validate se bo qua khi do)."""
    return (
        "---\n"
        f"Giọng văn: {author}\n"
        f"Độ dài yêu cầu: {_vn_int(target_chars)} ký tự\n"
        f"Độ dài thực tế: {_vn_int(actual_chars)} ký tự\n"
        f"Viết bằng: {provider_label} ({model})\n"
        "---\n\n"
    )


def _outline_hash(outline: str) -> str:
    return hashlib.sha1(outline.strip().encode("utf-8")).hexdigest()[:16]


def checkpoint_path(out: str | Path) -> Path:
    """File luu tien do canh output: '{out}.progress.json'."""
    return Path(str(out) + ".progress.json")


def load_checkpoint(out: str | Path, outline: str) -> dict[str, str]:
    """Cac phan da viet xong tu checkpoint — CHI khi outline khop (khong doi giua chung).

    Tra ve {heading: body}; rong neu khong co checkpoint hoac outline da doi.
    """
    p = checkpoint_path(out)
    if not p.is_file():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    if data.get("outline_hash") != _outline_hash(outline):
        return {}
    return data.get("sections", {})


def save_checkpoint(out: str | Path, outline: str, total_chars: int,
                    sections: dict[str, str], provider: str = "", model: str = "") -> None:
    checkpoint_path(out).write_text(json.dumps({
        "outline_hash": _outline_hash(outline),
        "provider": provider, "model": model, "total_chars": total_chars,
        "sections": sections,
    }, ensure_ascii=False, indent=2), encoding="utf-8")


def clear_checkpoint(out: str | Path) -> None:
    p = checkpoint_path(out)
    if p.is_file():
        p.unlink()


def write_partial_script(out: str | Path, outline: str, profile: dict) -> dict | None:
    """Ghép script.md từ các chương ĐÃ XONG trong checkpoint — dùng khi lỗi/huỷ giữa
    chừng để luôn có file tải về được (bài học 2026-07-11: lỗi giữa chừng → không ghi
    script → không tải được). Trả {sections, chars} hoặc None nếu chưa chương nào xong."""
    done = load_checkpoint(out, outline)
    if not done:
        return None
    secs = parse_outline(outline)
    title_sec = next((s for s in secs if s.kind == "title"), None)
    script = Script(title=title_sec.brief if title_sec else "")
    for s in secs:
        if s.kind != "title" and s.heading in done:
            script.sections.append((s.heading, done[s.heading]))
    try:
        cp = json.loads(checkpoint_path(out).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        cp = {}
    actual = sum(len(b) for _, b in script.sections)
    header = render_header(profile.get("author", "the author"),
                           cp.get("total_chars", 0), actual,
                           cp.get("provider", ""), cp.get("model", ""))
    Path(out).write_text(header + script.to_markdown(), encoding="utf-8")
    return {"sections": len(script.sections), "chars": actual}


def generate_script(
    outline: str,
    profile: dict,
    llm_text: Callable[[str, str, int], str],
    total_chars: int = 18000,
    on_progress: Callable[[str], None] | None = None,
    should_stop: Callable[[], bool] | None = None,
    done_sections: dict[str, str] | None = None,
    on_section_done: Callable[[str, str], None] | None = None,
) -> Script:
    """Sinh kich ban tuan tu theo cac phan cua outline. Ghep vao mot Script.

    Phan bo do dai theo mo hinh YouTube (hook ngan, body chia deu, end clamp).
    llm_text(system, user, max_tokens) -> str; on_progress(msg) de log; should_stop()
    de dung giua chung. done_sections {heading: body} = cac phan da co (resume) -> bo qua.
    on_section_done(heading, body) goi sau MOI phan viet xong (de luu checkpoint).
    """
    done_sections = done_sections or {}
    sections = parse_outline(outline)
    content_check = [s for s in sections if s.kind != "title"]
    if not content_check:
        raise ValueError(
            "Khong nhan dien duoc phan nao trong outline. Can cac moc Hook / Chapter 1 / "
            "Chapter 2 / ... / End (co the co hoac khong dau ':'). Vi du:\n"
            "  Title: ...\n  Hook: ...\n  Chapter 1: ...\n  End: ..."
        )

    outline_summary = "\n".join(f"{s.heading}: {s.brief}" for s in sections)
    content_sections = [s for s in sections if s.kind != "title"]
    allocs = allocate_section_chars(content_sections, total_chars)

    # Canh bao neu chuong ra ngoai vung ngot chat luong (2500-4000 ky tu/chuong).
    per_ch = next((a for s, a in zip(content_sections, allocs) if s.kind == "chapter"), 0)
    n_ch = sum(1 for s in content_sections if s.kind == "chapter")
    if on_progress and per_ch > CHAPTER_WARN_CHARS:
        need = min_chapters_for(total_chars,
                                any(s.kind == "hook" for s in content_sections),
                                any(s.kind == "end" for s in content_sections))
        on_progress(f"CANH BAO: moi chuong ~{per_ch} ky tu, vuot nguong {CHAPTER_WARN_CHARS} — "
                    f"nen chia outline thanh it nhat {need} chuong de giu giong on dinh.")
    elif on_progress and n_ch and per_ch < CHAPTER_MIN_QUALITY:
        on_progress(f"CANH BAO: moi chuong chi ~{per_ch} ky tu, duoi nguong chat luong "
                    f"~{CHAPTER_MIN_QUALITY} — chuong qua ngan de LLM se NEN lai lam van "
                    "phang, mat chat. Nen GIAM so chuong hoac TANG tong ky tu de giong co "
                    "khong gian phat trien.")
    if on_progress:
        # Tang 1: brief chuong nao ram y hon ngan sach -> bao truoc khi ton token.
        for w in outline_scope_report(outline, total_chars)["scope_warnings"]:
            on_progress(f"CANH BAO: {w}")

    script = Script()
    title_sec = next((s for s in sections if s.kind == "title"), None)
    if title_sec:
        script.title = title_sec.brief

    # V2: Misconception cua HOOK -> luat BREAK STANDS cho MOI chuong phia sau
    # (khong co dong nay = outline cu = mis_line rong = moi khoi V2 tat).
    hook_sec = next((s for s in content_sections if s.kind == "hook"), None)
    mis_line = _v2_meta(hook_sec.brief)[1] if hook_sec else ""

    n_total = len(content_sections)
    written = 0
    prev_tail = ""
    n_expand = 0                                  # so chuong HUT phai keo (canh bao goc re)
    n_ch = sum(1 for s in content_sections if s.kind == "chapter")
    for i, (sec, target) in enumerate(zip(content_sections, allocs), 1):
        # Resume: phan da co trong checkpoint -> dung lai, khong goi LLM
        if sec.heading in done_sections:
            body = done_sections[sec.heading]
            script.sections.append((sec.heading, body))
            written += len(body)
            prev_tail = _tail(body)
            if on_progress:
                on_progress(f"  {sec.heading} ({i}/{n_total}): da co tu checkpoint ({len(body)} ky tu)")
            continue
        if should_stop and should_stop():
            if on_progress:
                on_progress("(Da dung — giu lai cac phan da viet, bam Tiep tuc de chay tiep)")
            break
        if on_progress:
            on_progress(f"Dang viet {sec.heading} ({i}/{n_total}, ~{target} ky tu) · "
                        f"da {written}/{total_chars} ky tu…")
        system, user = build_section_prompt(sec, profile, outline_summary, prev_tail, target,
                                            title=script.title, mis_line=mis_line)
        # rong rai cho model thinking (vd GLM) + phan output
        body = llm_text(system, user, max(4096, target * 3)).strip()
        # Tang 3: Python do sau khi viet; vuot tran (kem dung sai) -> MOT vong cat.
        # HOOK cung co tran tu 2026-07-15: truoc day no bi loai khoi cho nay nen viet
        # dai bao nhieu cung khong ai chan (user bao hook phinh, pha quy uoc 250-500).
        if sec.kind == "hook":
            ceiling = HOOK_CHARS_MAX
        elif sec.kind == "chapter":
            # Trần = CHAPTER_WARN_CHARS (ngưỡng CHẤT LƯỢNG), KHÔNG phải mục tiêu của chương.
            #
            # Luật user (2026-07-16): "viết hay là tối thượng, CÓ THỂ DÀI HƠN, nhưng vượt
            # 4000 là trượt khỏi điểm ngọt → văn chán". Tức mục tiêu ký tự MỀM, 4000 là
            # trần cứng.
            #
            # 2026-07-15 tôi đổi thành max(target, MIN_QUALITY) vì tưởng user cần siết ký
            # tự → chương mục tiêu 3000 bị cắt ở 3450. Nhưng đo thật prompt hiện tại viết
            # 2965-3433 (tb 3289, ±7%) ⇒ QUÁ NỬA số chương bị cắt oan: tốn thêm 1 lượt LLM
            # và hạ ý của user xuống một câu, trong khi chương đó vốn đã hay và vẫn trong
            # vùng ngọt. Cắt = mất nội dung; đó là cái giá đắt hơn vài trăm ký tự thừa.
            ceiling = CHAPTER_WARN_CHARS
        else:
            ceiling = _end_chars(total_chars)      # end: vốn đã đo theo mục tiêu của nó
        if len(body) > ceiling * REVISE_OVER_RATIO:
            how = ("cat gon hook ve 250-500" if sec.kind == "hook"
                   else "cat y (ha tang y, khong nen van, khong bo y)")
            if on_progress:
                on_progress(f"  {sec.heading}: {len(body)} ky tu — vuot tran {ceiling}, "
                            f"chay MOT vong {how}…")
            if sec.kind == "hook":
                rs, ru = build_hook_cut_prompt(script.title, body, keep_break=bool(mis_line))
            else:
                rs, ru = build_scope_cut_prompt(sec, profile, body, target, mis_line=mis_line)
            revised = llm_text(rs, ru, max(4096, target * 3)).strip()
            if revised and len(revised) < len(body):
                body = revised
        # Vong NO: chuong HUT so khung -> keo len bang y con trong brief (nguoc vong cat).
        if sec.kind == "chapter" and len(body) < target * EXPAND_FLOOR:
            n_expand += 1                       # dem de canh bao ho so viet ngan he thong
            mat = len(sec.brief.strip())
            if not mat or target / mat > EXPAND_STARVING:
                # Doi nguyen lieu: no = ep LLM bia noi dung user chua duyet -> KHONG no.
                if on_progress:
                    on_progress(f"  {sec.heading}: {len(body)} ky tu — HUT nhung brief chi "
                                f"{mat} ky tu (thieu nguyen lieu). Khong no; them add-on "
                                "tren board roi viet lai chuong nay.")
            else:
                for _ in range(EXPAND_MAX_ROUNDS):
                    pct = round((target - len(body)) / target * 100)
                    if pct < round((1 - EXPAND_FLOOR) * 100):
                        break                                    # da vao dung sai
                    if on_progress:
                        on_progress(f"  {sec.heading}: {len(body)} ky tu — hut {pct}% so "
                                    f"khung {target}, chay MOT luot no (nang y nhac luot "
                                    "len day du, khong don chu)…")
                    es, eu = build_expand_prompt(sec, profile, body, pct, mis_line=mis_line)
                    grown = llm_text(es, eu, max(4096, target * 3)).strip()
                    ok = (grown and len(grown) > len(body)
                          and kept_ratio(body, grown) >= EXPAND_KEPT_MIN
                          and len(grown) <= CHAPTER_WARN_CHARS * REVISE_OVER_RATIO)
                    if not ok:
                        if on_progress:
                            on_progress(f"  {sec.heading}: luot no bi TU CHOI (ngan hon / "
                                        "mat van cu / vuot tran) — giu ban truoc.")
                        break
                    body = grown
        script.sections.append((sec.heading, body))
        written += len(body)
        prev_tail = _tail(body)
        if on_section_done:
            on_section_done(sec.heading, body)   # luu checkpoint ngay
        if on_progress:
            on_progress(f"  {sec.heading}: {len(body)} ky tu (tong {written}/{total_chars})")
    # >= nua so chuong phai no => khong phai ngau nhien tung chuong ma la HO SO GIONG viet
    # ngan (goc re: exemplar ngan — vd A008 1.164 ky tu). Bao de user sua goc, het tra phi no.
    if on_progress and n_ch and n_expand * 2 >= n_ch:
        on_progress(f"CANH BAO: {n_expand}/{n_ch} chuong hut phai keo len — ho so giong nay "
                    "viet NGAN he thong (exemplar ngan). Nen dung lai ho so voi ban thao "
                    "dai hon de het ton luot no moi bai.")
    return script
