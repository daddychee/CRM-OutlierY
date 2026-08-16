from voiceprofile.corpus import Corpus
from voiceprofile.profile import build_profile
from voiceprofile.quant import build_self_features, extract_recurring_ngrams

# Cac "chuong" cung phong cach: cau ngan deu dan -> dac trung on dinh
STABLE_WORKS = [
    "We look at the stars. We wonder about the sky. We ask what it means for us. "
    "The night is deep and the stars are far, but we keep asking about the stars.",
    "We walk under the stars. We think about the sky. We ask how it began for us. "
    "The dark is wide and the stars are old, but we keep looking at the stars.",
    "We dream about the stars. We talk about the sky. We ask why it calls to us. "
    "The night is long and the stars are cold, but we keep dreaming of the stars.",
]
# Mot "chuong" phong cach khac han: cau rat dai, tu dai -> pha vo do on dinh
DIVERGENT_WORK = (
    "Notwithstanding extraordinarily complicated methodological considerations "
    "characteristic of contemporary astrophysical instrumentation development, "
    "interdisciplinary collaboration methodologies fundamentally revolutionized "
    "observational cosmology throughout innumerable multigenerational research initiatives."
)


def test_build_self_features_keeps_stable_and_reports_spread():
    feats = build_self_features(STABLE_WORKS, author_heldout=[])
    by_name = {f.name: f for f in feats}
    slm = by_name["sentence_len_mean"]
    assert slm.keep is True          # do dai cau gan nhu giong het qua 3 "chuong"
    assert slm.spread is not None and slm.spread < slm.value * 0.3
    assert slm.baseline is None and slm.zscore is None  # khong co baseline nao trong self mode


def test_build_self_features_drops_unstable_feature():
    feats = build_self_features(STABLE_WORKS + [DIVERGENT_WORK * 2], author_heldout=[])
    by_name = {f.name: f for f in feats}
    # chuong lech pha lam sentence_len/word_len dao dong manh -> it nhat mot cai bi loai
    assert not by_name["avg_word_len_chars"].keep or not by_name["sentence_len_mean"].keep


def test_extract_recurring_ngrams_requires_presence_across_works():
    grams = extract_recurring_ngrams(STABLE_WORKS, n=2, top_k=10, min_count=3)
    names = [g.ngram for g in grams]
    assert "the stars" in names       # xuat hien o ca 3 van ban, nhieu lan
    top = grams[0]
    assert top.n_works >= 2 and top.count >= 3


def test_build_profile_self_mode_has_reproduction_targets():
    corpus = Corpus(name="A", works=STABLE_WORKS, train=STABLE_WORKS, heldout=[])
    p = build_profile("A", "en", "en", corpus, baseline_corpus=None)
    assert p["profile_mode"] == "self_profile"
    assert p["reproduction_targets"], "phai co target tai tao"
    t = p["reproduction_targets"]["sentence_len_mean"]
    assert t["range"][0] <= t["target"] <= t["range"][1]
    assert p["exemplars"]


def test_build_profile_contrast_mode_still_works():
    corpus = Corpus(name="A", works=STABLE_WORKS, train=STABLE_WORKS, heldout=[])
    base_texts = [DIVERGENT_WORK, DIVERGENT_WORK + " Additional divergent scientific text here."]
    baseline = Corpus(name="B", works=base_texts, train=base_texts, heldout=[])
    p = build_profile("A", "en", "en", corpus, baseline_corpus=baseline)
    assert p["profile_mode"] == "contrast"
    assert any(f["zscore"] is not None for f in p["quant_features"])
