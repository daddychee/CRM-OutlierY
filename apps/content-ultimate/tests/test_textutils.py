from voiceprofile.textutils import split_sentences, tokenize_words


def test_split_sentences_basic():
    text = "This is one. This is two! Is this three?"
    assert split_sentences(text) == ["This is one.", "This is two!", "Is this three?"]


def test_split_sentences_empty():
    assert split_sentences("   ") == []


def test_tokenize_words():
    assert tokenize_words("We are made of star-stuff.") == ["We", "are", "made", "of", "star", "stuff"]


def test_tokenize_words_apostrophe():
    assert "don't" in tokenize_words("We don't know yet.")
