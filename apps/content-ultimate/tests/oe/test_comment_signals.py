"""Test phân loại comment (offline)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from oe import comment_signals as cs


def test_question_vs_statement():
    assert cs.is_question("How do they measure the mass?")
    assert cs.is_question("what came before the big bang")
    assert not cs.is_question("This was a great video.")


def test_rhetorical_excluded():
    assert not cs.is_question("Who else is here confused but watching anyway?")
    assert not cs.is_question("why did i click this and expect to understand")
    assert cs.is_rhetorical("anyone else totally lost?")


def test_request_detected():
    assert cs.is_request("Please make a video about black holes")
    assert cs.is_request("can you cover white holes next")
    assert not cs.is_request("Why is the universe expanding?")


def test_timestamp():
    assert cs.has_timestamp("at 12:34 he explains it")
    assert not cs.has_timestamp("no time here")


def test_quote_matching():
    segs = ["the universe was opaque for the first three hundred thousand years then light escaped freely"]
    sh = cs.build_transcript_shingles(segs, n=8)
    assert cs.is_quote("the universe was opaque for the first three hundred thousand years", sh, n=8)
    assert not cs.is_quote("i love this channel so much keep it up please", sh, n=8)


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn(); print(f"PASS {fn.__name__}")
    print(f"\n{len(fns)}/{len(fns)} test xanh.")
