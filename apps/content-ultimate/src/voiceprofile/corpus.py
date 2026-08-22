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
    file_bo: list[str] = field(default_factory=list)   # file bi loai vi thieu dau cau

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
MIN_CHARS_KIEM_DAU = 500      # duoi nguong nay khong du mau de ket luan thieu dau cau


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


def load_corpus_dir(path: str | Path, name: str | None = None,
                    bao_file_bo: bool = False):
    """Doc file .txt/.md trong thu muc, TU LOAI file thieu dau cau (23/08).

    Vi sao tu loai chu khong canh bao: canh bao suong co tu 16/07 nhung bi bo qua
    100%, va cua chan 21/08 lai cho tick di tiep — da co nguoi tick, nen sinh ra 3
    ho so dung tren corpus khong dau cau (sentence_len_mean = 1085) va duoc dung de
    viet suot 3 tuan. Bat nguoi chon giua "bo het" va "nham mat di tiep" la lua
    chon sai; may loc duoc thi may loc, roi noi ro da loc gi.

    bao_file_bo=True -> tra (works, [ten file bi bo]). Mac dinh tra works nhu cu.
    """
    p = Path(path)
    if not p.is_dir():
        raise FileNotFoundError(f"Khong tim thay thu muc corpus: {p}")
    works, bo = [], []
    for f in sorted(p.iterdir()):
        if f.suffix.lower() in TEXT_EXTENSIONS:
            text = read_text_any(f).strip()
            if not text:
                continue
            if len(text) >= MIN_CHARS_KIEM_DAU and punctuation_density(text) < MIN_ENDERS_PER_1K:
                bo.append(f"{f.name} ({punctuation_density(text):.1f} dau ket/1000 ky tu)")
                continue
            works.append(text)
    if not works and bo:
        raise ValueError(
            f"Moi file trong {p} deu thieu dau cau (transcript chua cham cau): "
            + "; ".join(bo) + ". Cham cau lai roi nap lai — dung ho so tren van "
            "khong dau cau thi moi so do giong deu la rac.")
    if not works:
        raise ValueError(f"Thu muc {p} khong co file .txt/.md nao co noi dung")
    if bao_file_bo:
        return works, bo
    return works


def build_corpus(path: str | Path, name: str, heldout_ratio: float = 0.2, seed: int = 42) -> Corpus:
    """Nap corpus va chia train/held-out theo file (khong tron lan trong cung 1 tac pham).

    File thieu dau cau bi TU LOAI o load_corpus_dir; ten chung nam trong
    Corpus.file_bo de nguoi dung hoi doi hoc thay may da bo gi.
    """
    works, bo = load_corpus_dir(path, name, bao_file_bo=True)
    rng = random.Random(seed)
    indices = list(range(len(works)))
    rng.shuffle(indices)
    n_heldout = max(1, round(len(works) * heldout_ratio)) if len(works) > 1 else 0
    heldout_idx = set(indices[:n_heldout])
    train = [w for i, w in enumerate(works) if i not in heldout_idx]
    heldout = [w for i, w in enumerate(works) if i in heldout_idx]
    return Corpus(name=name, works=works, train=train or works, heldout=heldout, file_bo=bo)
