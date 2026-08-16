"""Corpus Manager: nap van ban tu thu muc, chia train/held-out."""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from pathlib import Path

TEXT_EXTENSIONS = {".txt", ".md"}


def read_text_any(path: Path) -> str:
    """Doc file van ban voi encoding linh hoat.

    Nhieu file .txt xuat tu Word/Windows la cp1252 (byte 0x95 = bullet), khong phai
    UTF-8 — doc cung utf-8 se crash. Thu lan luot utf-8 -> utf-8-sig (BOM) -> cp1252;
    cuoi cung latin-1 (doc duoc MOI byte, khong bao gio loi).
    """
    for enc in ("utf-8", "utf-8-sig", "cp1252"):
        try:
            return path.read_text(encoding=enc)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="latin-1")


@dataclass
class Corpus:
    name: str
    works: list[str] = field(default_factory=list)  # raw text per file
    train: list[str] = field(default_factory=list)
    heldout: list[str] = field(default_factory=list)

    @property
    def n_works(self) -> int:
        return len(self.works)

    @property
    def n_tokens(self) -> int:
        return sum(len(w.split()) for w in self.works)


# Transcript YouTube tu dong KHONG co dau cham. Do that tren corpus Ventures:
#   file sach   : 11-13 dau ket cau / 1000 ky tu  (78-92 ky tu/cau)
#   transcript  : 0.1 / 1000                      (ca file = 1 "cau" 14.799 ky tu)
# Nguong 4 nam giua hai cum, cach xa ca hai.
MIN_ENDERS_PER_1K = 4.0


def punctuation_density(text: str) -> float:
    """So dau ket cau / 1000 ky tu. Thap = transcript tho, khong tach duoc cau."""
    if not text:
        return 0.0
    return sum(text.count(c) for c in ".!?") / (len(text) / 1000)


def transcript_warnings(path: str | Path) -> list[str]:
    """File nao trong corpus la transcript THO (khong dau cham) — KHONG dung duoc de hoc
    nhip cau.

    Vi sao phai bao (loi that 2026-07-16): 2/5 file corpus Ventures la transcript tho =>
    sentence_len_mean = 1085 (hu cau) => select_exemplars di tim doan khop 1085 => chon
    dung 2 cuc tho do lam "giong tac gia" => LLM viet 271-307 ky tu/cau trong khi tac gia
    that viet 78-92 => "cau van phang va qua dai".
    Tool BAO, user quyet (luat A3) — khong tu y bo file cua user.
    """
    p = Path(path)
    out = []
    if not p.is_dir():
        return out
    for f in sorted(p.iterdir()):
        if f.suffix.lower() not in TEXT_EXTENSIONS:
            continue
        text = read_text_any(f).strip()
        if len(text) < 500:
            continue
        d = punctuation_density(text)
        if d < MIN_ENDERS_PER_1K:
            out.append(f"{f.name}: {d:.1f} dấu câu/1000 ký tự — transcript thô, không tách "
                       f"được câu. File này sẽ làm hỏng nhịp câu của hồ sơ giọng "
                       f"(bỏ ra, hoặc chấm câu lại rồi nạp lại).")
    return out


def load_corpus_dir(path: str | Path, name: str | None = None) -> list[str]:
    """Doc tat ca file .txt/.md trong thu muc, tra ve danh sach noi dung (1 phan tu / file)."""
    p = Path(path)
    if not p.is_dir():
        raise FileNotFoundError(f"Khong tim thay thu muc corpus: {p}")
    works = []
    for f in sorted(p.iterdir()):
        if f.suffix.lower() in TEXT_EXTENSIONS:
            text = read_text_any(f).strip()
            if text:
                works.append(text)
    if not works:
        raise ValueError(f"Thu muc {p} khong co file .txt/.md nao co noi dung")
    return works


def build_corpus(path: str | Path, name: str, heldout_ratio: float = 0.2, seed: int = 42) -> Corpus:
    """Nap corpus va chia train/held-out theo file (khong tron lan trong cung 1 tac pham)."""
    works = load_corpus_dir(path, name)
    rng = random.Random(seed)
    indices = list(range(len(works)))
    rng.shuffle(indices)
    n_heldout = max(1, round(len(works) * heldout_ratio)) if len(works) > 1 else 0
    heldout_idx = set(indices[:n_heldout])
    train = [w for i, w in enumerate(works) if i not in heldout_idx]
    heldout = [w for i, w in enumerate(works) if i in heldout_idx]
    return Corpus(name=name, works=works, train=train or works, heldout=heldout)
