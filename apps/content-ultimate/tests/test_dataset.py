from voiceprofile.clean import Passage
from voiceprofile.dataset import (
    build_continuation_pairs,
    build_dataset,
    build_instruction_pairs,
    dedup_report,
    write_jsonl,
)

PASSAGE_TEXT = (
    "We are made of star-stuff. The iron in our blood was forged in the heart of an "
    "ancient star. And yet here we are, asking questions of the dark. The universe is "
    "vast, and we are small, but we are connected to all of it."
)


def test_build_continuation_pairs_splits_seed_and_rest():
    passages = [Passage(text=PASSAGE_TEXT, n_words=40, n_sentences=4)]
    pairs = build_continuation_pairs(passages, author="Test Author", seed_sentences=2)
    assert len(pairs) == 1
    pair = pairs[0]
    assert "star-stuff" in pair.user  # seed
    assert "connected" in pair.assistant  # rest
    assert "Test Author" in pair.system


def test_build_instruction_pairs_uses_callback():
    passages = [Passage(text=PASSAGE_TEXT, n_words=40, n_sentences=4)]
    pairs = build_instruction_pairs(
        passages, author="Test Author", llm_summarize=lambda t: "Write about cosmic scale."
    )
    assert len(pairs) == 1
    assert pairs[0].user == "Write about cosmic scale."
    assert pairs[0].assistant == PASSAGE_TEXT


def test_dedup_report_counts_exact_dups():
    passages = [Passage(text=PASSAGE_TEXT, n_words=40, n_sentences=4)] * 3
    pairs = build_continuation_pairs(passages, author="X")
    report = dedup_report(pairs)
    assert report["n_pairs"] == 3
    assert report["exact_duplicate_completions"] == 2


def test_to_chat_format():
    passages = [Passage(text=PASSAGE_TEXT, n_words=40, n_sentences=4)]
    pair = build_continuation_pairs(passages, author="X")[0]
    chat = pair.to_chat()
    roles = [m["role"] for m in chat["messages"]]
    assert roles == ["system", "user", "assistant"]


def test_write_jsonl_roundtrip(tmp_path):
    import json
    passages = [Passage(text=PASSAGE_TEXT, n_words=40, n_sentences=4)]
    pairs = build_continuation_pairs(passages, author="X")
    out = tmp_path / "d.jsonl"
    write_jsonl(pairs, str(out))
    lines = out.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    obj = json.loads(lines[0])
    assert obj["messages"][0]["role"] == "system"


def test_build_dataset_continuation_end_to_end():
    raw = PASSAGE_TEXT + "\n\n" + PASSAGE_TEXT.replace("star", "sun")
    pairs, report = build_dataset([raw], author="X", mode="continuation", min_words=20, max_words=200)
    assert report["n_pairs"] >= 1
