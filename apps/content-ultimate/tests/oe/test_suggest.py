"""Test gợi ý outline (offline, callback giả) — xác minh tên cluster + gap → ✍."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from oe.suggest import build_candidates, parse_suggestion, suggest_outline

CL = [
    {"name": "Big Bang everywhere", "brief": "It happened everywhere.", "role": "hook",
     "coverage_k": 4, "coverage_n": 6, "peak_score": 4.5, "pos": 0.1, "questions_n": 2,
     "questions": ["where did it happen?"]},
    {"name": "Singularity paradox", "brief": "The math breaks down.", "role": "chapters",
     "coverage_k": 3, "coverage_n": 6, "peak_score": 5.0, "pos": 0.5, "questions_n": 1,
     "questions": ["is the singularity real?"]},
    {"name": "Back to the viewer", "brief": "We are the cosmos.", "role": "ending",
     "coverage_k": 2, "coverage_n": 6, "peak_score": 1.0, "pos": 0.9, "questions_n": 0,
     "questions": []},
    {"name": "Rare peak single", "brief": "A niche retained moment.", "role": "chapters",
     "coverage_k": 1, "coverage_n": 6, "peak_score": 9.9, "pos": 0.3, "questions_n": 0,
     "questions": []},
]
GAPS = [{"text": "Why won't teachers admit uncertainty?", "likes": 1212}]


def test_build_candidates_gom_du_3_nhom():
    cands = build_candidates(CL)
    names = {c["name"] for c in cands}
    assert "Big Bang everywhere" in names          # xương sống coverage>=2
    assert "Rare peak single" in names             # single peak cao vẫn vào (giữ chân)


def test_parse_xac_minh_ten_va_gap_thanh_custom():
    raw = json.dumps({
        "title": "The Truth of the Big Bang",
        "hook": "Big Bang everywhere",
        "chapters": ["Singularity paradox",
                     "Cluster KHÔNG tồn tại",              # tên ma → phải bị loại
                     {"gap": "Why won't teachers admit uncertainty?"}],
        "ending": "Back to the viewer",
    })
    picks = parse_suggestion(raw, CL)
    assert picks["title"] == "The Truth of the Big Bang"
    assert picks["hook"] == "Big Bang everywhere"
    assert picks["ending"] == "Back to the viewer"
    assert "Singularity paradox" in picks["chapters"]
    assert "Cluster KHÔNG tồn tại" not in picks["chapters"]   # tên bịa bị loại
    gap_ch = [c for c in picks["chapters"] if c.startswith("✍ ")]
    assert len(gap_ch) == 1                                    # gap → 1 chương ✍
    assert picks["custom"][gap_ch[0]].startswith("Answer the viewers' unanswered question:")


def test_parse_chong_trung_va_json_boc_fence():
    raw = "```json\n" + json.dumps({
        "hook": "Big Bang everywhere",
        "chapters": ["Big Bang everywhere", "Singularity paradox"],  # hook lặp ở chapter
        "ending": "Back to the viewer",
    }) + "\n```"
    picks = parse_suggestion(raw, CL)
    assert picks["hook"] == "Big Bang everywhere"
    assert "Big Bang everywhere" not in picks["chapters"]      # đã dùng ở hook → không lặp
    assert picks["chapters"] == ["Singularity paradox"]


def test_suggest_outline_wire_callback():
    seen = {}
    def fake(system, user):
        seen["system"], seen["user"] = system, user
        return json.dumps({"hook": "Big Bang everywhere", "chapters": ["Singularity paradox"],
                           "ending": "Back to the viewer", "title": "X"})
    picks = suggest_outline(CL, GAPS, "My Title", fake)
    assert picks["hook"] == "Big Bang everywhere"
    assert "EVIDENCE CLUSTERS" in seen["user"] and "My Title" in seen["user"]
    assert "UNANSWERED AUDIENCE QUESTIONS" in seen["user"]


def test_suggest_cat_cung_so_chuong():
    # yêu cầu user 2026-07-10: LLM trả dư chương → cắt cứng về n_chapters, dọn gap thừa
    def fake(system, user):
        assert "EXACTLY 2 chapters" in user            # số chương vào đúng prompt
        return json.dumps({"hook": "Big Bang everywhere",
                           "chapters": ["Singularity paradox", "Back to the viewer",
                                        {"gap": "extra gap that must be dropped"}],
                           "ending": None})
    picks = suggest_outline(CL, GAPS, "", fake, n_chapters=2)
    assert len(picks["chapters"]) == 2                 # cắt còn đúng 2
    assert not any(c.startswith("✍") for c in picks["chapters"])  # gap dư đã bị cắt
    assert picks["custom"] == {}                       # custom của gap thừa đã dọn


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn(); print(f"PASS {fn.__name__}")
    print(f"\n{len(fns)}/{len(fns)} test xanh.")
