"""Test compose (offline) — outline.txt đúng format hợp đồng với Author Extract."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from oe.compose import compose_outline, compose_evidence

CL = [
    {"name": "The Everywhere Explosion", "brief": "Explain the Big Bang happened everywhere.",
     "coverage_k": 3, "coverage_n": 6, "peak_score": 4.5, "pos": 0.2, "top_video": True, "videos": ["A", "B"]},
    {"name": "The Unsolved Singularity", "brief": "Reveal the singularity paradox.",
     "coverage_k": 2, "coverage_n": 6, "peak_score": 0.0, "pos": 0.7, "top_video": False, "videos": ["C"]},
    {"name": "26,000 Years", "brief": "Bring it back to the viewer.",
     "coverage_k": 1, "coverage_n": 6, "peak_score": 2.2, "pos": 0.95, "top_video": False, "videos": ["A"]},
]
PICKS = {"title": "The Truth of the Big Bang", "hook": "The Everywhere Explosion",
         "chapters": ["The Unsolved Singularity"], "ending": "26,000 Years"}


def test_outline_format():
    out = compose_outline(PICKS, CL)
    assert out.startswith("Title: The Truth of the Big Bang\n\nHOOK\n")
    assert "CHAPTER 1 — The Unsolved Singularity" in out
    assert "ENDING\nBring it back to the viewer." in out
    assert "coverage" not in out.lower()          # bản sạch: không citation


def test_chapter_numbering():
    picks = dict(PICKS, chapters=["The Unsolved Singularity", "The Everywhere Explosion"], hook=None, ending=None)
    out = compose_outline(picks, CL)
    assert "CHAPTER 1 — The Unsolved Singularity" in out
    assert "CHAPTER 2 — The Everywhere Explosion" in out


def test_evidence_has_citation():
    ev = compose_evidence(PICKS, CL)
    assert "3/6 video" in ev and "peak z×w 4.5" in ev and "★ top-video" in ev


def test_missing_slots_warned_not_placeholdered():
    picks = {"title": "X", "hook": None, "chapters": ["The Unsolved Singularity"], "ending": None}
    out = compose_outline(picks, CL)
    ev = compose_evidence(picks, CL)
    assert "HOOK" not in out and "ENDING" not in out    # không chèn placeholder vào file sạch
    assert "Thiếu: HOOK, ENDING" in ev                  # nhưng cảnh báo trong evidence


def test_angle_preserved_in_outline():
    # angle = góc gốc tại peak, phải vào outline.txt (không để Author Extract tự sinh)
    cl = [dict(CL[0], angle="Space itself expands everywhere, not from a point.")]
    picks = {"title": "X", "hook": None, "chapters": ["The Everywhere Explosion"], "ending": None}
    out = compose_outline(picks, cl)
    assert "Angle: Space itself expands everywhere, not from a point." in out


def test_angle_skipped_when_equal_to_brief():
    cl = [dict(CL[0], angle=CL[0]["brief"])]     # angle trùng brief → không in dòng thừa
    picks = {"title": "X", "hook": None, "chapters": ["The Everywhere Explosion"], "ending": None}
    assert compose_outline(picks, cl).count("Angle:") == 0


def test_cta_line_in_outline():
    # CTA user chọn cho một chương → dòng CTA: trong outline.txt (sau brief/angle)
    picks = {"title": "X", "hook": None, "chapters": ["The Everywhere Explosion"], "ending": None,
             "ctas": {"The Everywhere Explosion": "Comment your favorite below."}}
    out = compose_outline(picks, CL)
    assert "CTA: Comment your favorite below." in out
    # không có CTA cho chương khác → không in dòng CTA thừa
    assert out.count("CTA:") == 1


def test_custom_chapter_va_y_con():
    # 2026-07-09: chương tự viết (custom) + ý con trong chương (extras) — ý con có
    # 2 loại: gõ tay (str) hoặc kéo cluster từ bảng vào ({"cluster": name}).
    picks = dict(PICKS,
                 chapters=["The Unsolved Singularity", "✍ The Stone Memory"],
                 ending=None,
                 custom={"✍ The Stone Memory": "A hand-written chapter about stone memory"},
                 extras={"The Unsolved Singularity": [
                     "Also cover the Planck wall",
                     {"cluster": "26,000 Years"},
                     {"cluster": "cluster-da-bien-mat"},      # ref mất -> bỏ qua êm
                 ]})
    out = compose_outline(picks, CL)
    assert "CHAPTER 2 — The Stone Memory" in out                 # bản sạch bỏ tiền tố ✍
    assert "A hand-written chapter about stone memory." in out   # brief toàn văn, có chấm câu
    # brief chương = brief gốc + ý gõ tay + brief của cluster-ý-con, chốt câu từng phần
    assert ("Reveal the singularity paradox. Also cover the Planck wall. "
            "Bring it back to the viewer.") in out
    ev = compose_evidence(picks, CL)
    assert "✍ tự thêm — không có bằng chứng từ video" in ev      # chương tự viết: nói rõ
    assert "✍ ý tự thêm: Also cover the Planck wall" in ev
    assert "◇ ý con (cluster): 26,000 Years — 1/6 video" in ev   # ý con cluster GIỮ citation


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn(); print(f"PASS {fn.__name__}")
    print(f"\n{len(fns)}/{len(fns)} test xanh.")
