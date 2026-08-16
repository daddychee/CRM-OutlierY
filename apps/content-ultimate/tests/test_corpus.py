import pytest

from voiceprofile.corpus import build_corpus, load_corpus_dir


def test_load_corpus_dir(tmp_path):
    (tmp_path / "a.txt").write_text("Hello world. This is a test.")
    (tmp_path / "b.md").write_text("Another file here.")
    (tmp_path / "ignore.csv").write_text("not,loaded")
    works = load_corpus_dir(tmp_path)
    assert len(works) == 2


def test_load_corpus_dir_missing():
    with pytest.raises(FileNotFoundError):
        load_corpus_dir("/nonexistent/path/xyz")


def test_load_corpus_dir_empty(tmp_path):
    with pytest.raises(ValueError):
        load_corpus_dir(tmp_path)


def test_build_corpus_split(tmp_path):
    for i in range(5):
        (tmp_path / f"work_{i}.txt").write_text(f"This is work number {i}. " * 10)
    corpus = build_corpus(tmp_path, name="test")
    assert corpus.n_works == 5
    assert len(corpus.train) + len(corpus.heldout) == 5
    assert corpus.n_tokens > 0


def test_read_text_any_handles_cp1252_word_files(tmp_path):
    from voiceprofile.corpus import read_text_any
    # File xuat tu Word: bullet 0x95, smart quotes 0x91/0x92 (cp1252, khong phai utf-8)
    f = tmp_path / "word.txt"
    f.write_bytes(b"Item \x95 with \x91smart\x92 quotes")  # byte tho, khong phai utf-8 hop le
    text = read_text_any(f)  # khong duoc crash
    assert "Item" in text and "smart" in text


def test_read_text_any_reads_plain_utf8(tmp_path):
    from voiceprofile.corpus import read_text_any
    f = tmp_path / "u.txt"
    f.write_text("Xin chào — vũ trụ", encoding="utf-8")
    assert read_text_any(f) == "Xin chào — vũ trụ"
