from voiceprofile.clonekit import build_clonekit_markdown, select_diverse_exemplars

PASSAGE = (
    "We are made of star-stuff, the iron in our blood forged in the heart of an ancient, "
    "exploded star. And yet here we are, on this small blue world, asking questions of the "
    "dark. The universe is not required to be in harmony with human ambition, and it does "
    "not care whether we understand it. And yet, against all odds, we have begun to "
    "understand a little, not because the cosmos owes us an answer, but because we kept "
    "asking, again and again, looking up into the night and wondering at the scale of it all."
)


def test_select_diverse_exemplars_returns_complete_passages():
    exemplars = select_diverse_exemplars([PASSAGE], n=3, min_words=40, max_words=200)
    assert len(exemplars) >= 1
    assert exemplars[0].rstrip().endswith((".", "!", "?", '"'))


def test_build_clonekit_markdown_has_sections():
    md = build_clonekit_markdown([PASSAGE], author="Carl Sagan", n_exemplars=2)
    assert "Carl Sagan" in md
    assert "SYSTEM" in md
    assert "exemplars" in md.lower() or "Đoạn mẫu" in md
    assert "[CHỦ ĐỀ]" in md
