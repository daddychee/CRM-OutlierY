"""Test lab do DO DAI: hieu chinh so ky tu/brief cho TUNG cap (tac gia x model).

VI SAO CAN (do that 2026-07-15, khong phai suy luan):
- `CHARS_PER_IDEA = 1250` la so KHOP TU MOT thi nghiem (Norway, n=1) roi dem ap cho MOI
  tac gia va MOI model. Do lai: Ventures = 1408, Investigate Lewis = 1720 (lech 22%).
  Mot hang so chung la SAI cho ca hai.
- Hang so ON DINH qua chu de (cung tac gia, chu de khac han: lech +2%) => do MOT LAN cho
  moi tac gia la du. Nhung PHU THUOC tac gia (cung chu de, tac gia khac: lech +19%)
  => bat buoc do rieng tung nguoi.
- He qua thuc te: Ventures chiu 2-3 brief/chuong, Lewis chi chiu 2 (3 brief = 5160 ky tu,
  vuot tran troi giong 4000). So "2-3 brief" khong phai truc giac — no SUY RA tu hang so
  cua chinh tac gia do.

LAB DO DUOC GI:
- DO DAI: co. Python dem ky tu that, tat dinh (luat A1).
- CHAT LUONG: KHONG. Lab khong do duoc "van hay". Chat luong den tu CAU TRUC — so brief
  giu chuong trong vung ngot CHAPTER_MIN_QUALITY..CHAPTER_WARN_CHARS. Lab chi cho biet
  vung ngot cua TAC GIA NAY nam o dau.

GIOI HAN PHAI NOI VOI USER:
- Lab cho TRUNG BINH dung; tung chuong le van dao dong ~15% (do that: 2754-3715 tren cung
  cau hinh) => van can vong sua ty le cua Tang 3 lam luoi an toan.
- Hang so gan voi CAP (tac gia x model). Doi GLM -> Claude la phai do lai.
"""
from __future__ import annotations

import json
import time
import os
from pathlib import Path
from statistics import fmean

ROOT = Path(os.environ.get("CU_DATA_DIR") or Path(__file__).resolve().parents[2])  # V3: CU_DATA_DIR tro kho du lieu ra data/content-ultimate (Luat 6); mac dinh giu canh repo nhu V2
RUNS = ROOT / "runs"

# NGUON LIEU LAB = CLUSTER THAT trong runs/ (khong phai fixture tu viet).
#
# Fixture hu cau ("ngon hai dang") da that bai that 2026-07-15: cung tac gia/model/cau hinh
# nhung chu de HU CAU cho 1994 ky tu con chu de CO THAT (Kellogg) cho 3531 — lech 77%.
# Khong phai do do dai brief (fixture 148 ky tu ~ trung vi cluster that 147, do tren 515
# cluster) ma do KIEN THUC NEN: chu de model khong biet thi no viet ~2500 BAT KE cau hinh
# => hai o do gan bang nhau => khop 2 an ra so rac (211 ky tu/brief, 501 ky tu/add-on).
#
# Noi dung PRODUCTION luon la cluster that tu board => do tren cluster that moi dai dien.
LAB_TITLE_FALLBACK = "The Story Behind It"
MIN_BRIEF_CHARS = 90        # brief qua ngan khong du de khai trien -> lech phep do

# Luoi do: 2-3 brief (che do user chot 2026-07-15) x 0/4 add-on. 4 diem cho phep khop
# binh phuong toi thieu thay vi giai 2 an tu 2 diem (giai 2 an khuech dai nhieu).
LAB_CONFIGS: list[tuple[int, int]] = [(2, 0), (2, 4), (3, 0), (3, 4)]

LAB_TARGET = 3000          # muc tieu danh nghia truyen vao prompt; chi de prompt co ngu canh
DEFAULT_SAMPLES = 5        # user chot 5-10; 5 -> sai so trung binh ~7% voi dao dong 15%


def pick_lab_material(runs_dir: Path | None = None) -> dict:
    """Chon nguyen lieu lab tu CLUSTER THAT trong runs/, THEO DUNG mo hinh user chot:
    MOT cluster chinh (brief cua no = 2-3 NHIP) + thong tin lien quan dinh kem.

    - briefs = cac NHIP trong brief cua MOT cluster ("Introduce X. Explain Y. Reveal Z.")
      — KHONG phai 3 cluster khac nhau. Do la cach do da cho hang so hop ly (1408).
    - addons = CAU DAU cua cac cluster khac (mot su kien ngan de nhac luot), khong phai
      ca cluster brief nhieu nhip.

    Chon TAT DINH (run nhieu cluster nhat; cluster coverage cao nhat co du nhip) de moi
    tac gia duoc do bang CUNG mot thuoc do => hang so so sanh duoc, chay lai on dinh.
    {} neu chua co run nao du lieu.
    """
    from .textutils import split_sentences

    runs_dir = runs_dir or RUNS
    if not runs_dir.is_dir():
        return {}
    n_b = max(n for n, _ in LAB_CONFIGS)
    n_a = max(n for _, n in LAB_CONFIGS)
    best: tuple | None = None
    for cj in sorted(runs_dir.glob("*/clusters.json")):
        try:
            cl = json.loads(cj.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        ch = [c for c in cl if isinstance(c, dict) and c.get("role") == "chapters"
              and len(str(c.get("brief") or "")) >= MIN_BRIEF_CHARS]
        if len(ch) < 1 + n_a:
            continue
        if best is None or len(ch) > len(best[1]):
            best = (cj.parent.name, ch)
    if not best:
        return {}
    run, ch = best
    ch.sort(key=lambda c: (-float(c.get("coverage_k") or 0), str(c.get("name") or "")))

    # Cluster chinh = cluster dau tien co DU nhip (>= n_b cau).
    main = next((c for c in ch if len(split_sentences(str(c["brief"]))) >= n_b), None)
    if main is None:
        return {}
    briefs = [s.strip() for s in split_sentences(str(main["brief"]))][:n_b]
    # Add-on = CAU DAU cua cac cluster khac (mot su kien, khong phai ca mach ke).
    addons = []
    for c in ch:
        if c is main:
            continue
        first = next((s.strip() for s in split_sentences(str(c["brief"])) if s.strip()), "")
        if first:
            addons.append(first)
        if len(addons) >= n_a:
            break
    if len(briefs) < n_b or len(addons) < n_a:
        return {}
    return {"run": run, "title": str(main.get("name") or LAB_TITLE_FALLBACK),
            "briefs": briefs, "addons": addons}


def build_lab_brief(material: dict, n_brief: int, n_addon: int) -> str:
    """Brief cua mot o do — ghep y het cach compose.py ghep brief + y them."""
    parts = material["briefs"][:n_brief] + material["addons"][:n_addon]
    return " ".join(p if p.endswith((".", "!", "?")) else p + "." for p in parts)


# Cong chan so vo ly. Lab chay THAT 2026-07-15 tren fixture hu cau da tra ve
# "211 ky tu/brief · 501 ky tu/add-on" — mot add-on la MOT CAU, khong the dai gap 2.4 lan
# mot brief khai trien day du. Nguyen nhan: tren noi dung LLM khong biet, no viet ~2500
# BAT KE cau hinh => hai o do gan bang nhau => giai 2 an ra so rac. Neu khong chan, so rac
# nay chui vao profile va Writer dung ngay -> te hon ca hang so cung.
MIN_CHARS_PER_BRIEF = 400        # mot y "khai trien day du" khong the ngan hon the
MAX_ADDON_RATIO = 0.5            # add-on (1 cau) phai nho hon HAN mot brief


def _sane(a: float, b: float) -> bool:
    return a >= MIN_CHARS_PER_BRIEF and b >= 0 and b <= a * MAX_ADDON_RATIO


def fit_constants(rows: dict[tuple[int, int], list[int]]) -> dict:
    """Khop `chapter = a*n_brief + b*n_addon` bang binh phuong toi thieu (2 an).

    Chi dung cac o co add-on: do that cho thay cong thuc khop < 1 ky tu o day, nhung
    truot 20% o cac o KHONG add-on (brief qua ngheo -> LLM tu don chu cho day chuong).

    Tra {} khi khong khop duoc HOAC khop ra so vo ly (xem cong chan tren) — tha KHONG CO
    hang so (Writer roi ve mac dinh chung) con hon co hang so SAI.
    """
    pts = [(nb, na, fmean(v)) for (nb, na), v in rows.items() if v and na > 0]
    if len(pts) < 2:
        return {}
    # Chuan phuong trinh cho he 2 an: sum over points of (a*nb + b*na - y)^2
    s11 = sum(nb * nb for nb, _, _ in pts)
    s12 = sum(nb * na for nb, na, _ in pts)
    s22 = sum(na * na for _, na, _ in pts)
    t1 = sum(nb * y for nb, _, y in pts)
    t2 = sum(na * y for _, na, y in pts)
    det = s11 * s22 - s12 * s12
    if not det:
        return {}
    a = (t1 * s22 - t2 * s12) / det
    b = (s11 * t2 - s12 * t1) / det
    if not _sane(a, b):
        return {}
    return {"chars_per_brief": round(a), "chars_per_addon": round(b)}


def sweet_spot_briefs(chars_per_brief: int, lo: int, hi: int) -> list[int]:
    """So brief giu chuong trong vung ngot [lo, hi] — SUY RA tu hang so cua tac gia.

    Day la guide that su cua lab: Ventures (1408) chiu 2; Lewis (1720) cung chi chiu 2
    nhung chat hon; mot tac gia viet gon (vd 900) se chiu 3-4.
    """
    return [n for n in range(1, 7) if lo <= n * chars_per_brief <= hi]


def guide_table(rows: dict[tuple[int, int], list[int]], author: str, model: str) -> list[dict]:
    """Bang tra theo dung dinh dang user chot: Tac gia - Chapter - Brief - Add on.

    `chapter` la SO DO THAT (trung binh cac mau), khong phai so tu cong thuc — bang tra
    khong chiu nhieu khuech dai cua phep khop.
    """
    out = []
    for (nb, na), v in sorted(rows.items()):
        if not v:
            continue
        m = fmean(v)
        spread = (max(v) - min(v)) / m * 100 if m else 0.0
        out.append({"author": author, "model": model, "chapter": round(m),
                    "brief": nb, "addon": na,
                    "spread_pct": round(spread), "samples": len(v),
                    "min": min(v), "max": max(v)})
    out.sort(key=lambda r: r["chapter"])
    return out


def config_for_target(table: list[dict], target_chars: int) -> dict | None:
    """O do gan muc tieu nhat — tra loi 'chuong 3000 thi dung may brief, may add-on'.

    Hoa nhau thi uu tien o ON DINH hon (spread nho): do that cho thay o nhieu add-on
    dao dong +-3% con o ngheo add-on +-22% — brief giau thi LLM bam theo, khong ung tac.
    """
    if not table:
        return None
    return min(table, key=lambda r: (abs(r["chapter"] - target_chars), r["spread_pct"]))


def run_lab(profile: dict, llm_text_fn, *, samples: int = DEFAULT_SAMPLES,
            model: str = "", on_progress=None, should_stop=None,
            material: dict | None = None) -> dict:
    """Chay lab: viet `samples` chuong thu cho moi o, do, khop hang so.

    `llm_text_fn(system, user) -> str` do nguoi goi tiem (test offline khong dot credit,
    luat C3). `material` tu pick_lab_material() — tiem duoc de test. Tra ve khoi
    `length_lab` de nhet vao profile.json; {} neu chua co cluster that de do.
    """
    from .generator import (CHAPTER_MIN_QUALITY, CHAPTER_WARN_CHARS, OutlineSection,
                            build_section_prompt)
    from . import generator as G

    material = material if material is not None else pick_lab_material()
    if not material:
        if on_progress:
            on_progress("LOI: chua co run nao trong runs/ co du cluster that de do lab.")
            on_progress("     Chay pipeline board Outline it nhat 1 lan roi chay lai lab.")
        return {}

    author = str(profile.get("author") or "?")
    rows: dict[tuple[int, int], list[int]] = {}
    total = len(LAB_CONFIGS) * samples
    i = 0
    if on_progress:
        on_progress(f"  nguồn liệu: cluster thật từ run '{material['run']}'")
    for nb, na in LAB_CONFIGS:
        sec = OutlineSection(kind="chapter", heading="Chapter 1",
                             brief=build_lab_brief(material, nb, na))
        # k = SO BRIEF KHAI BAO (khong phai doan tu estimate_ideas) — day la dieu lab do.
        # Chu ky phai khop depth_plan that (ke ca chars_per_idea): lab do de TIM hang so
        # do, nen khong duoc de no anh huong nguoc lai phep do.
        real = G.depth_plan
        G.depth_plan = lambda n, t, min_k=2, chars_per_idea=0, _k=nb: {
            "full": _k, "mention": max(0, n - _k), "est_chars": 0}
        try:
            system, user = build_section_prompt(sec, profile, "outline", "", LAB_TARGET,
                                                title=material["title"])
        finally:
            G.depth_plan = real
        got: list[int] = []
        for _ in range(samples):
            if should_stop and should_stop():
                if on_progress:
                    on_progress("(Da dung lab — huy, khong ghi vao profile)")
                return {}
            i += 1
            if on_progress:
                on_progress(f"  lab {i}/{total}: {nb} brief + {na} add-on…")
            try:
                got.append(len(llm_text_fn(system, user).strip()))
            except Exception as e:  # noqa: BLE001 — mot mau hong khong duoc giet ca lab
                if on_progress:
                    on_progress(f"    (mau hong, bo qua: {str(e)[:80]})")
        if got:
            rows[(nb, na)] = got
            if on_progress:
                on_progress(f"  {nb} brief + {na} add-on: {got} -> tb {fmean(got):.0f} ky tu")

    if not rows:
        return {}
    table = guide_table(rows, author, model)
    fit = fit_constants(rows)
    # `source_run` de truy nguoc: hang so gan voi (tac gia x model x DO QUEN THUOC cua chu de).
    # Doi nguon lieu la so co the doi — phai biet no do tren cai gi.
    lab = {"author": author, "model": model, "measured_at": time.time(),
           "samples": samples, "source_run": material["run"], "table": table, **fit}
    if fit:
        lab["sweet_spot_briefs"] = sweet_spot_briefs(
            fit["chars_per_brief"], CHAPTER_MIN_QUALITY, CHAPTER_WARN_CHARS)
    else:
        # Do duoc nhung khop ra so vo ly: giu BANG TRA (van doc duoc) nhung KHONG dat
        # hang so => Writer roi ve mac dinh chung thay vi dung so rac.
        lab["unreliable"] = ("khớp ra hằng số vô lý — thường vì nội dung lab quá lạ với "
                            "model nên nó viết gần như nhau ở mọi cấu hình")
        if on_progress:
            on_progress("  ⚠ Lab KHÔNG tin được: " + lab["unreliable"])
            on_progress("    → profile KHÔNG được đặt hằng số; Writer dùng mặc định chung.")
    return lab


def chars_per_brief_of(profile: dict, default: int) -> int:
    """Hang so cua tac gia neu da chay lab; khong co thi dung mac dinh chung.

    Profile cu (chua co lab) van chay binh thuong — khong pha gi.
    """
    lab = (profile or {}).get("length_lab") or {}
    a = lab.get("chars_per_brief")
    return int(a) if isinstance(a, (int, float)) and a > 0 else default


def render_guide(lab: dict) -> list[str]:
    """Bang tra cho nguoi doc: Tac gia - Chapter - Brief - Add on (dinh dang user chot)."""
    if not lab or not lab.get("table"):
        return ["(chua chay lab)"]
    out = [f"{lab['author']} · model {lab.get('model') or '?'} · {lab.get('samples')} mẫu/ô",
           "  Chapter | Brief | Add-on | dao động"]
    for r in lab["table"]:
        out.append(f"  {r['chapter']:7d} | {r['brief']:5d} | {r['addon']:6d} | ±{r['spread_pct']}%")
    if lab.get("chars_per_brief"):
        out.append(f"  → {lab['chars_per_brief']} ký tự/brief · "
                   f"{lab.get('chars_per_addon', 0)} ký tự/add-on")
    if lab.get("sweet_spot_briefs"):
        out.append(f"  → vùng ngọt: {lab['sweet_spot_briefs']} brief/chương")
    return out
