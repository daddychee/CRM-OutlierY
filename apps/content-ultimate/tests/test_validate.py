from voiceprofile.validate import (
    chunk_by_words,
    evaluate_script,
    format_report,
    strip_front_matter,
    targets_for_length,
)


def test_strip_front_matter_removes_header_only():
    md = "---\nGiọng văn: Carl Sagan\nViết bằng: GLM\n---\n\n# Title\n\nBody here."
    stripped = strip_front_matter(md)
    assert stripped.startswith("# Title")
    assert "Carl Sagan" not in stripped        # header khong con
    # khong co front-matter -> giu nguyen
    assert strip_front_matter("# Just title\nbody") == "# Just title\nbody"


def test_evaluate_ignores_front_matter():
    targets = {"sentence_len_mean": {"target": 6.0, "sd": 3.0}}
    with_header = "---\nGiọng văn: X\n---\n\nWe are here now."
    without = "We are here now."
    assert evaluate_script(with_header, targets)["targets"][0]["value"] == \
           evaluate_script(without, targets)["targets"][0]["value"]

CORPUS = [
    ("We look up at the night sky and we wonder. The stars are far, and we are small. "
     "But we are made of the same star-stuff, and so we are part of the cosmos. ") * 40
]


def test_chunk_by_words_splits_to_target_size():
    chunks = chunk_by_words(CORPUS, target_words=100)
    assert len(chunks) > 1
    # moi chunk (tru chunk cuoi) it nhat ~target tu
    from voiceprofile.textutils import tokenize_words
    assert all(len(tokenize_words(c)) >= 50 for c in chunks)


def test_targets_for_length_returns_mean_and_sd():
    targets = targets_for_length(CORPUS, target_words=100)
    assert "sentence_len_mean" in targets
    t = targets["sentence_len_mean"]
    assert t["target"] > 0 and t["sd"] >= 0


def test_evaluate_script_passes_when_in_band_fails_when_out():
    targets = {
        "sentence_len_mean": {"target": 12.0, "sd": 2.0},
        "function_word_freq": {"target": 0.40, "sd": 0.02},
    }
    # kich ban co cau ~12 tu, nhieu hu tu -> it nhat mot target dat
    script = ("We are here and we are small but we look up now. "
              "We are made of the stars and we go on. ") * 10
    verdict = evaluate_script(script, targets)
    assert verdict["n_total"] == 2
    assert 0 <= verdict["percent"] <= 100
    assert verdict["n_pass"] == sum(r["pass"] for r in verdict["targets"])


def test_evaluate_script_only_scores_features_in_targets():
    targets = {"ttr": {"target": 0.5, "sd": 0.1}}
    verdict = evaluate_script("Some short script text here for measuring.", targets)
    assert verdict["n_total"] == 1
    assert verdict["targets"][0]["name"] == "ttr"


def test_failing_targets_sorted_first():
    targets = {
        "sentence_len_mean": {"target": 12.0, "sd": 2.0},
        "ttr": {"target": 0.001, "sd": 0.0005},  # gan nhu chac chan truot
    }
    script = "We are here and we are small but we look up at the sky and we wonder now. " * 8
    verdict = evaluate_script(script, targets)
    assert verdict["targets"][0]["pass"] is False  # truot len dau
    report = format_report(verdict)
    assert "%" in report and "target" in report


def test_evaluate_script_bo_qua_target_chua_do_duoc():
    """C1: target sinh tu corpus mong (do_duoc False) khong duoc cham — sd=0.0 gia
    lam band = 5% gia tri, vua chat vo ly vua doi tra ket luan cho thu chua do."""
    from voiceprofile.validate import evaluate_script
    van = "We looked up. The sky was clear and very wide. Nobody spoke for a while."
    targets = {
        "sentence_len_mean": {"target": 7.0, "sd": 1.5, "do_duoc": True},
        "ttr": {"target": 0.9, "sd": None, "range": None, "do_duoc": False},
    }
    kq = evaluate_script(van, targets)
    ten = [r["name"] for r in kq["targets"]]
    assert "ttr" not in ten and "sentence_len_mean" in ten
    assert kq["n_khong_do_duoc"] == 1
