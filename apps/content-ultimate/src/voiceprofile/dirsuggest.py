"""Logic thuan goi y folder corpus/ket qua — tach khoi gui.py de server headless
(VPS khong co tkinter) import duoc; gui.py re-export lai cho tuong thich cu."""
from __future__ import annotations

from pathlib import Path


def detect_corpus_dirs(author_dir: str | Path) -> list[str]:
    """Cac thu muc (de quy) ben trong author_dir co chua file .txt/.md."""
    root = Path(author_dir)
    if not root.is_dir():
        return []
    found = {
        str(f.parent)
        for f in list(root.rglob("*.txt")) + list(root.rglob("*.md"))
        if f.is_file()
    }
    return sorted(found)


def default_author_name(author_dir: str | Path) -> str:
    """Ten tac gia mac dinh = basename cua folder duoc chon (user co the sua)."""
    return Path(author_dir).resolve().name


def default_output_dir(author_dir: str | Path, folder_name: str) -> str:
    """Folder ket qua mac dinh: '{folder_name}' nam CANH folder ban thao được chọn."""
    return str(Path(author_dir).resolve().parent / folder_name)
