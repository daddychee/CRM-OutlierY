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


# --- C1 (24/08): corpus mong khong duoc TU KHAI la chac chan ---------------------
# Do that 24/08 tren kho: A013 Derek Muller (1 file / 3.726 tu) cat ra DUNG MOT don
# vi do -> spread = 0.0 cho moi dac trung -> cv = 0 -> giu 17/17 va sd = 0.0, trong
# khi A014 (6 file / 25.392 tu) chi giu 7/17 vi co phuong sai that de do. Ho so mong
# nhat kho lai khai la chac chan nhat. "Khong co phuong sai" bi doc thanh "phuong sai
# bang 0" = chac chan tuyet doi.

_MOT_DOAN = ("The signal came at night. We listened. It repeated twice, then stopped. "
             "Nobody could explain it. The next morning we tried again and heard nothing. ") * 4


def test_corpus_mong_khong_khai_on_dinh():
    """Duoi MIN_DON_VI_DO doan do: khong dac trung nao duoc khai keep/sd."""
    from voiceprofile.profile import MIN_DON_VI_DO  # noqa: F401
    corpus = Corpus(name="A", works=[_MOT_DOAN], train=[_MOT_DOAN], heldout=[])
    p = build_profile("A", "en", "en", corpus, baseline_corpus=None)
    assert p["corpus_stats"]["n_stability_units"] < 3
    assert all(f["keep"] is False for f in p["quant_features"]), "chua do duoc thi khong duoc keep"
    assert all(f["do_duoc"] is False for f in p["quant_features"])
    assert all(f["spread"] is None for f in p["quant_features"])
    t = p["reproduction_targets"]["sentence_len_mean"]
    assert t["do_duoc"] is False and t["sd"] is None and t["range"] is None
    assert p["exemplars"], "van phai chon duoc exemplar (chon bang moi chieu do duoc)"


def test_don_vi_do_co_gian_theo_corpus():
    """Corpus nho cat nho de co >=3 diem do; corpus lon giu nguyen 4.000 tu."""
    from voiceprofile.profile import CHUNK_WORDS, DON_VI_MIN_TU, co_don_vi_do
    assert co_don_vi_do(3726) == 3726 // 4          # A013: 1 don vi gia -> 4 don vi that
                                                   # (3 diem do + 1 held-out)
    assert co_don_vi_do(120_000) == CHUNK_WORDS     # sach day: khong doi mot ly
    assert co_don_vi_do(500) == DON_VI_MIN_TU       # qua ngan: khong cat vun hon nua


def test_don_vi_do_de_du_diem_do_sau_khi_tru_heldout():
    """Cat xong phai con >= MIN_DON_VI_DO diem tren TAP TRAIN, khong phai tong."""
    from voiceprofile.profile import MIN_DON_VI_DO, _split_units, co_don_vi_do
    from voiceprofile.validate import chunk_by_words
    van = _MOT_DOAN * 40
    chunks = chunk_by_words([van], co_don_vi_do(len(van.split())))
    train, heldout = _split_units(chunks)
    assert len(train) >= MIN_DON_VI_DO and len(heldout) >= 1


def test_corpus_mong_cat_du_ba_don_vi_do():
    van = _MOT_DOAN * 40  # ~4.000 tu, mot "file" duy nhat nhu A013
    corpus = Corpus(name="A", works=[van], train=[van], heldout=[])
    p = build_profile("A", "en", "en", corpus, baseline_corpus=None)
    assert p["corpus_stats"]["n_stability_units"] >= 3
    sds = [t["sd"] for t in p["reproduction_targets"].values()]
    assert any(s is not None for s in sds), "co diem do that thi phai co sd that"
