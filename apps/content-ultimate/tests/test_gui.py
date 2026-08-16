from pathlib import Path

from voiceprofile.dirsuggest import (
    default_author_name,
    default_output_dir,
    detect_corpus_dirs,
)


def test_detect_corpus_dirs_finds_nested_text_folders(tmp_path):
    (tmp_path / "Cosmos").mkdir()
    (tmp_path / "Cosmos" / "ch1.txt").write_text("x", encoding="utf-8")
    (tmp_path / "Notes").mkdir()
    (tmp_path / "Notes" / "draft.md").write_text("y", encoding="utf-8")
    (tmp_path / "Images").mkdir()  # khong co van ban -> khong duoc liet ke
    dirs = detect_corpus_dirs(tmp_path)
    assert str(tmp_path / "Cosmos") in dirs
    assert str(tmp_path / "Notes") in dirs
    assert str(tmp_path / "Images") not in dirs


def test_detect_corpus_dirs_empty_for_missing_or_textless(tmp_path):
    assert detect_corpus_dirs(tmp_path / "khong-ton-tai") == []
    assert detect_corpus_dirs(tmp_path) == []


def test_default_author_name_is_basename():
    assert default_author_name("/tmp/somewhere/Carl Sagan") == "Carl Sagan"
    assert default_author_name("/tmp/x/Haruki Murakami") == "Haruki Murakami"


def test_default_output_dir_sits_next_to_source():
    # ket qua nam canh folder ban thao, ten = folder_name truyen vao (vd ma thu vien)
    out = default_output_dir("/tmp/somewhere/Carl Sagan", "A001_Carl-Sagan")
    assert out == str(Path("/tmp/somewhere").resolve() / "A001_Carl-Sagan")
