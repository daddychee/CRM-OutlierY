from voiceprofile.rhetoric import (
    RHETORIC_SCHEMA,
    build_rhetoric_prompt,
    ground_moves,
    propose_moves,
)

# Corpus gia lap du dai de clean_and_segment giu lai (van xuoi, nhieu hu tu)
CORPUS_TEXT = (
    "We looked up at the night sky and we wondered what it all meant for us. "
    "The stars were distant fires, and we were small beneath them, but we were "
    "part of the same story that they were telling across the dark. "
    "Every atom in our bodies was forged in the heart of a dying star, and so "
    "we are, in the most literal sense, made of the ashes of ancient suns. "
    "When we consider the ocean of night above us, we begin to understand that "
    "the universe is not a stranger to us but a home we have barely explored. "
    "It is a story that begins before we existed and will continue after we are gone."
)


def _quote(text: str) -> str:
    return text


def test_ground_moves_keeps_verified_and_drops_fabricated():
    moves = [
        {
            "move": "inclusive we sweeping to cosmic scale",
            "type": "signature",
            "transferable": True,
            "evidence": [
                "We looked up at the night sky and we wondered what it all meant",
                "we are, in the most literal sense, made of the ashes of ancient suns",
                "the universe is not a stranger to us but a home we have barely explored",
            ],
        },
        {
            "move": "fabricated move",
            "type": "signature",
            "transferable": True,
            "evidence": [
                "This sentence does not appear anywhere in the corpus at all, truly",
                "Another completely invented quotation that sounds quite plausible here",
                "A third fabricated line about the majesty of the swirling cosmos",
            ],
        },
    ]
    grounded = ground_moves(moves, [CORPUS_TEXT], min_evidence=3)
    assert len(grounded) == 1
    assert grounded[0]["move"] == "inclusive we sweeping to cosmic scale"
    assert grounded[0]["occurrences"] == 3


def test_ground_moves_normalizes_punctuation_case_and_ocr_hyphenation():
    corpus = "The great oblate¬ ness of the spinning star was, in truth, remarkable to behold."
    moves = [{
        "move": "m", "type": "signature", "transferable": True,
        "evidence": [
            # khac hoa/thuong, khac dau cau, khac ngat tu OCR — van phai khop
            "the great OBLATENESS of the spinning star was in truth remarkable",
        ],
    }]
    grounded = ground_moves(moves, [corpus], min_evidence=1)
    assert len(grounded) == 1


def test_ground_moves_rejects_short_and_duplicate_quotes():
    moves = [{
        "move": "m", "type": "signature", "transferable": True,
        "evidence": [
            "the night sky",  # qua ngan -> khong tinh
            "We looked up at the night sky and we wondered what it all meant",
            "We looked up at the night sky and we wondered what it all meant",  # trung -> dem 1 lan
        ],
    }]
    grounded = ground_moves(moves, [CORPUS_TEXT], min_evidence=2)
    assert grounded == []  # chi 1 trich dan hop le duy nhat < 2


def test_propose_moves_passes_passages_to_llm_and_returns_moves():
    captured = {}

    def fake_llm(prompt: str, schema: dict) -> dict:
        captured["prompt"] = prompt
        captured["schema"] = schema
        return {"moves": [{"move": "x", "type": "signature", "transferable": True, "evidence": []}]}

    texts = [CORPUS_TEXT * 3]
    moves = propose_moves(texts, author="Test Author", llm_json=fake_llm,
                          n_passages=3, n_moves=5, min_evidence=2)
    assert moves == [{"move": "x", "type": "signature", "transferable": True, "evidence": []}]
    assert captured["schema"] is RHETORIC_SCHEMA
    assert "Test Author" in captured["prompt"]
    assert "[PASSAGE 1]" in captured["prompt"]
    assert "VERBATIM" in captured["prompt"]


def test_build_rhetoric_prompt_states_evidence_rules():
    prompt = build_rhetoric_prompt(["some passage"], "A", n_moves=4, min_evidence=3)
    assert "at least 3" in prompt
    assert "checked mechanically" in prompt
