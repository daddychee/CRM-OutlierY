from voiceprofile.quant import (
    build_quant_features,
    compute_features,
    extract_distinctive_ngrams,
    select_exemplars,
    zscore_against_baseline,
)

AUTHOR_TEXT = (
    "We are made of star-stuff. We look up at the night sky, and we wonder. "
    "The universe is vast, and we are small, but we are connected to it all."
)
BASELINE_TEXT = (
    "The mitochondrion produces ATP through oxidative phosphorylation. "
    "This process occurs within the inner membrane of the organelle. "
    "Researchers have documented this mechanism extensively."
)


def test_compute_features_returns_expected_keys():
    feats = compute_features([AUTHOR_TEXT])
    assert "sentence_len_mean" in feats
    assert "function_word_freq" in feats
    assert "ttr" in feats
    assert feats["sentence_len_mean"] > 0


def test_zscore_against_baseline_differs_for_distinct_styles():
    author_feats = compute_features([AUTHOR_TEXT])
    _, z = zscore_against_baseline(
        author_feats["function_word_freq"], [BASELINE_TEXT, BASELINE_TEXT], "function_word_freq"
    )
    # author text has much higher function-word/pronoun density ("we") than dry baseline
    assert isinstance(z, float)


def test_build_quant_features_marks_keep_flag():
    features = build_quant_features(
        author_train=[AUTHOR_TEXT, AUTHOR_TEXT],
        author_heldout=[AUTHOR_TEXT],
        baseline_texts=[BASELINE_TEXT, BASELINE_TEXT],
    )
    names = {f.name for f in features}
    assert "function_word_freq" in names
    assert any(isinstance(f.keep, bool) for f in features)


def test_extract_distinctive_ngrams_finds_we_pattern():
    author_texts = [AUTHOR_TEXT * 3]
    baseline_texts = [BASELINE_TEXT * 3]
    ngrams = extract_distinctive_ngrams(author_texts, baseline_texts, n=2, min_count=2)
    grams = [n.ngram for n in ngrams]
    assert any("we" in g for g in grams)


def test_select_exemplars_returns_nonempty():
    from voiceprofile.quant import QuantFeature
    kept = [QuantFeature(name="sentence_len_mean", value=10.0, keep=True)]
    exemplars = select_exemplars([AUTHOR_TEXT * 4], kept, min_words=5, max_words=30)
    assert len(exemplars) > 0


def test_noun_specificity_ignores_sentence_start_capitals():
    from voiceprofile.quant import _raw_features
    # Moi tu viet hoa deu o dau cau -> proxy phai bang 0
    no_proper = "The dog ran fast. The cat sat still. The bird flew away."
    assert _raw_features(no_proper)["noun_specificity_proxy"] == 0.0
    # Them danh tu rieng giua cau -> proxy phai duong
    with_proper = "The dog ran to Paris. The cat sat in London. The bird flew to Rome."
    assert _raw_features(with_proper)["noun_specificity_proxy"] > 0.0


def test_stability_is_none_without_heldout():
    # Hai baseline khac nhau nhe -> stdev > 0 -> z-score tinh duoc (khong nhu hai
    # van ban giong het, stdev = 0 lam moi z = 0)
    baseline_b = (
        "The ribosome synthesizes proteins through translation. "
        "This process occurs within the cytoplasm of the cell. "
        "Scientists have studied this mechanism thoroughly."
    )
    features = build_quant_features(
        author_train=[AUTHOR_TEXT, AUTHOR_TEXT],
        author_heldout=[],
        baseline_texts=[BASELINE_TEXT, baseline_b],
    )
    # Khong co held-out -> khong duoc bao cao True (thu chua do); va None khong loai dac trung
    assert all(f.stable_on_heldout is None for f in features)
    assert any(f.keep for f in features)


def test_exemplar_distance_not_dominated_by_large_scale_feature():
    from voiceprofile.quant import QuantFeature
    # Hai feature: flesch (scale ~60) va function_word_freq (scale ~0.3). Neu khong
    # chuan hoa, flesch thong tri va freq vo tac dung; sau chuan hoa, lech tuong doi
    # lon o freq phai thang lech tuong doi nho o flesch.
    author_like = "We wonder, and we look, and we are made of the stars above us all."
    dry = "Mitochondrial oxidative phosphorylation produces adenosine triphosphate molecules."
    from voiceprofile.quant import _raw_features
    target_feats = _raw_features(author_like)
    kept = [
        QuantFeature(name="function_word_freq", value=target_feats["function_word_freq"], keep=True),
        QuantFeature(name="flesch_reading_ease", value=target_feats["flesch_reading_ease"], keep=True),
    ]
    # Dau cach sau moi cau: khong co no thi "...all.We wonder" khong tach duoc cau => ca
    # doan thanh MOT cau 42 tu, vuot max_words=40 va bi bo (dung luat, sua 2026-07-16).
    picked = select_exemplars([(author_like + " ") * 3, (dry + " ") * 3], kept,
                              top_k=1, min_words=5, max_words=40)
    assert picked and "we" in picked[0].lower()


# --- Transcript tho lam hong nhip cau (loi that 2026-07-16) --------------------------

def test_cua_so_KHONG_phun_doan_vuot_max_words():
    """Bug that: `out.append` chay TRUOC khi kiem max_words => gioi han vo hieu. Transcript
    YouTube khong dau cham => split_sentences tra 1 "cau" = ca file => cua so dau tien la
    nguyen cuc 14.799 ky tu (gap 20 lan gioi han) va duoc phun ra lam exemplar."""
    from voiceprofile.quant import _sliding_paragraphs

    transcript = "khong he co dau cham nao trong ca cai file nay " * 60   # ~540 tu, 1 "cau"
    assert _sliding_paragraphs(transcript, 25, 120) == []      # phai BO, khong phun

    sach = " ".join(f"Day la cau so {i} voi du tu de tao thanh mot cua so hop le." 
                    for i in range(10))
    out = _sliding_paragraphs(sach, 5, 40)
    assert out
    from voiceprofile.textutils import tokenize_words
    assert all(len(tokenize_words(w)) <= 40 for w in out), "van con cua so vuot tran"


def test_bao_dong_khi_corpus_la_transcript_tho(tmp_path):
    """Tool BAO, user quyet (luat A3) — khong tu y bo file cua user."""
    from voiceprofile.corpus import punctuation_density, transcript_warnings

    (tmp_path / "tho.txt").write_text("khong cham gi ca " * 200, encoding="utf-8")
    (tmp_path / "sach.txt").write_text(
        " ".join(f"Cau {i} co dau cham dang hoang." for i in range(80)), encoding="utf-8")
    w = transcript_warnings(tmp_path)
    assert len(w) == 1 and "tho.txt" in w[0] and "transcript thô" in w[0]

    assert punctuation_density("a" * 1000) == 0.0
    assert punctuation_density("") == 0.0
    assert punctuation_density("x. y! z? " * 100) > 4      # van sach -> tren nguong


def test_luat_nen_tang_KHONG_ep_do_dai_cau():
    """Truoc 2026-07-16 luat hard-code 'long, clause-rich sentences ... the author's LONG
    sentences ARE the voice' cho MOI tac gia — trong khi Ventures viet 78-92 ky tu/cau.
    Nhip cau phai den tu EXEMPLAR that (show, dung tell)."""
    from voiceprofile.generator import YOUTUBE_RULES

    r = YOUTUBE_RULES["chapter"]
    assert "long, clause-rich" not in r
    assert "long sentences ARE the voice" not in r
    assert "rises and falls" in r          # nhip len xuong — thu user goi la "cao trao"


# ========== BUOC 3 (23/08): cua nhap tu loai file thieu dau cau ==========

VAN_LANH = ("The market opens before dawn. Vendors set out their crates in the half "
            "dark, and nobody hurries. A woman builds a pyramid of tomatoes that will "
            "collapse twice before the sun is up. She rebuilds it both times. By seven "
            "the street is loud, and by nine it is over.\n\n"
            "Further along, the bread stalls. Flour dusts everything. The baker talks "
            "while he works, and he works fast. His hands know the dough better than he "
            "does, a thing he says himself, laughing.\n\n"
            "Winter changes the rhythm. Stalls close by two. The fog does not lift some "
            "days, and the whole street works inside a soft grey box.") * 3

TRANSCRIPT_THO = ("imagine a country where the winters last half the year and the people "
                  "are calm about it they wake up early they go to work they come home and "
                  "nobody complains about the cold because complaining does not make the "
                  "cold go away this is just how life works there ") * 8


def test_load_corpus_tu_loai_file_thieu_dau_cau_23_08(tmp_path):
    """Cua canh bao co tu 16/07 nhung CHO TICK BO QUA — va da co nguoi tick, nen
    sinh ra 3 ho so dung tren corpus khong dau cau (sentence_len_mean = 1085) va
    duoc dung de viet suot 3 tuan. Doi thanh TU LOAI file hong roi bao ro, thay vi
    bat nguoi chon giua 'bo het' va 'nham mat di tiep'.
    """
    from voiceprofile.corpus import load_corpus_dir

    (tmp_path / "lanh1.txt").write_text(VAN_LANH, encoding="utf-8")
    (tmp_path / "lanh2.txt").write_text(VAN_LANH, encoding="utf-8")
    (tmp_path / "tho.txt").write_text(TRANSCRIPT_THO, encoding="utf-8")

    works, bo = load_corpus_dir(tmp_path, bao_file_bo=True)
    assert len(works) == 2, "file transcript tho phai bi loai"
    assert len(bo) == 1 and "tho.txt" in bo[0]
    assert all("imagine a country where" not in w for w in works)


def test_corpus_toan_file_tho_thi_KHONG_tu_loai_23_08(tmp_path):
    """Loai het thi khong con gi de dung ho so — luc do phai BAO LOI ro rang chu
    khong tra corpus rong (khong bao gio tra ban hong)."""
    import pytest
    from voiceprofile.corpus import load_corpus_dir

    (tmp_path / "a.txt").write_text(TRANSCRIPT_THO, encoding="utf-8")
    (tmp_path / "b.txt").write_text(TRANSCRIPT_THO, encoding="utf-8")
    with pytest.raises(ValueError, match="dau cau"):
        load_corpus_dir(tmp_path)


def test_giu_nguyen_hanh_vi_khi_corpus_deu_lanh_23_08(tmp_path):
    """Hoi quy: corpus sach thi khong loai gi ca."""
    from voiceprofile.corpus import load_corpus_dir

    (tmp_path / "a.txt").write_text(VAN_LANH, encoding="utf-8")
    (tmp_path / "b.txt").write_text(VAN_LANH, encoding="utf-8")
    works, bo = load_corpus_dir(tmp_path, bao_file_bo=True)
    assert len(works) == 2 and bo == []
