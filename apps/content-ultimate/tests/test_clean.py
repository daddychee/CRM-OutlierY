from voiceprofile.clean import clean_and_segment, is_prose


def test_is_prose_accepts_real_prose():
    text = (
        "In ancient times, the most mundane happenings were connected with the "
        "grandest cosmic events. We looked up at the sky and wondered what it meant, "
        "and whether the stars cared for us at all."
    )
    assert is_prose(text)


def test_is_prose_rejects_number_table():
    junk = "Affrighted . 445 1 628 Jaundies . 11 43 8 Ague . 43 Impostume . 74"
    assert not is_prose(junk)


def test_is_prose_rejects_too_short():
    assert not is_prose("Too short.")


def test_clean_and_segment_filters_and_chunks():
    raw = (
        "We are made of star-stuff, the iron in our blood forged in the heart of an "
        "ancient star. And yet here we are, on this small world, asking questions of "
        "the dark. The universe is not required to be in harmony with human ambition.\n\n"
        "445\n\n"
        "Affrighted . 445 1 628 Jaundies . 11 43 8 Ague . 43\n\n"
        "It is worth pausing to feel the scale of it. We have begun to understand a "
        "little, not because the cosmos owes us an answer, but because we kept asking "
        "and looking and wondering at the vastness above our small blue home."
    )
    passages = clean_and_segment([raw], min_words=20, max_words=200)
    assert len(passages) >= 1
    joined = " ".join(p.text for p in passages)
    assert "Affrighted" not in joined
    assert "star-stuff" in joined
