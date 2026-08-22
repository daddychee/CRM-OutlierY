"""So dang ky thu vien tac gia (registry) — nam TRONG folder tool.

Vi corpus va output do user chon tu do (khong con ep o mot AUTHOR_ROOT co dinh),
Writer khong the "quet thu muc" de biet co tac gia nao. So dang ky nay la index:
moi tac gia mot ma (A001, A002...) + duong dan profile/corpus. Extractor ghi vao;
Writer doc ra de hien dropdown.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
import os
from pathlib import Path

_REPO_ROOT = Path(os.environ.get("CU_DATA_DIR") or Path(__file__).resolve().parents[2])  # V3: CU_DATA_DIR tro kho du lieu ra data/content-ultimate (Luat 6); mac dinh giu canh repo nhu V2
_REGISTRY = _REPO_ROOT / "library" / "index.json"


def registry_path() -> Path:
    return _REGISTRY


def duong_that(duong: str | Path | None) -> Path | None:
    """Duong dan trong so -> duong dan THAT tren may nay.

    So luu TUONG DOI theo kho du lieu (CU_DATA_DIR) de con di duoc khi doi may.
    Ban ghi cu luu TUYET DOI van doc duoc: neu con ton tai thi dung nguyen, neu
    khong thi thu tim lai theo DUOI duong dan trong kho hien tai (VPS /opt/...
    va C:\\OutlierY\\... deu ket thuc bang uploads/<ma>_<slug>/profile.json).
    """
    if not duong:
        return None
    p = Path(duong)
    if not p.is_absolute() and not str(duong)[:1] in ("/", "\\") and ":" not in str(duong)[:3]:
        thu = _REPO_ROOT / p
        if thu.exists():
            return thu
    # KHO HIEN TAI LA NGUON SU THAT: thu ghep duoi duong dan vao kho truoc, ke ca
    # khi duong cu con song. Ban ghi A011-A013 tro C:\OutlierY (he V2 da tat, xoa
    # ~22/09) trong khi ban giong het da nam san trong kho V3 — bam duong cu la
    # hen gio mat ho so. Duoi 3 doan: uploads/<ma>_<slug>/profile.json.
    phan = [x for x in p.parts if x not in ("/", "\\")]
    for n in (3, 2):
        if len(phan) >= n:
            thu = _REPO_ROOT.joinpath(*phan[-n:])
            if thu.exists():
                return thu
    return p


def duong_luu(duong: str | Path | None) -> str:
    """Duong dan THAT -> dang luu vao so (tuong doi khi nam trong kho du lieu)."""
    if not duong:
        return ""
    p = Path(duong)
    try:
        return p.resolve().relative_to(_REPO_ROOT.resolve()).as_posix()
    except (ValueError, OSError):
        return str(p)


def slugify(name: str) -> str:
    """Ten tac gia -> slug an toan cho ten folder: giu chu/so, space -> '-'."""
    s = re.sub(r"[^\w\s-]", "", name, flags=re.UNICODE).strip()
    s = re.sub(r"[\s_]+", "-", s)
    return s or "author"


def load_registry(path: str | Path | None = None) -> dict:
    p = Path(path) if path else _REGISTRY
    if not p.is_file():
        return {"authors": []}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"authors": []}
    data.setdefault("authors", [])
    return data


def save_registry(data: dict, path: str | Path | None = None) -> None:
    p = Path(path) if path else _REGISTRY
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def next_code(authors: list[dict]) -> str:
    """Ma tuan tu A001, A002... (max hien co + 1)."""
    nums = []
    for a in authors:
        m = re.match(r"A(\d+)$", a.get("code", ""))
        if m:
            nums.append(int(m.group(1)))
    return f"A{(max(nums) + 1 if nums else 1):03d}"


def ensure_author(name: str, path: str | Path | None = None,
                  created_by: str = "") -> dict:
    """Lay entry theo ten (khong phan biet hoa/thuong); tao moi voi ma neu chua co.

    Luu ngay. Tra ve entry {code, name, slug, profile, corpus, created, created_by}.
    created_by = thanh vien team chay extract (X-Remote-User/CU_USER) — entry cu
    khong co field nay, GUI hien trong.
    """
    data = load_registry(path)
    for a in data["authors"]:
        if a["name"].strip().lower() == name.strip().lower():
            return a
    entry = {
        "code": next_code(data["authors"]),
        "name": name.strip(),
        "slug": slugify(name),
        "profile": None,
        "corpus": None,
        "created": datetime.now().isoformat(timespec="seconds"),
        "created_by": created_by.strip(),
    }
    data["authors"].append(entry)
    save_registry(data, path)
    return entry


def update_author(code: str, profile: str | None = None, corpus: str | None = None,
                  path: str | Path | None = None, created_by: str = "") -> dict | None:
    """Cap nhat duong dan profile/corpus cho tac gia theo ma. Tra ve entry (hoac None)."""
    data = load_registry(path)
    for a in data["authors"]:
        if a["code"] == code:
            if profile is not None:
                a["profile"] = str(Path(profile).resolve())
            if corpus is not None:
                a["corpus"] = str(Path(corpus).resolve())
            if created_by.strip():                      # nguoi extract SAU CUNG dung ten
                a["created_by"] = created_by.strip()
            save_registry(data, path)
            return a
    return None


def register_profile(name: str, profile: str, corpus: str | None = None,
                     path: str | Path | None = None, created_by: str = "") -> dict:
    """Tien ich cho Extractor: dam bao co entry + gan profile/corpus. Tra ve entry."""
    entry = ensure_author(name, path, created_by=created_by)
    return update_author(entry["code"], profile=profile, corpus=corpus, path=path,
                         created_by=created_by) or entry


def list_authors(path: str | Path | None = None, existing_only: bool = True) -> list[dict]:
    """Danh sach tac gia. existing_only=True chi giu entry co profile.json ton tai."""
    data = load_registry(path)
    out = []
    for a in data["authors"]:
        a = dict(a)
        for khoa in ("profile", "corpus"):
            that = duong_that(a.get(khoa))
            if that is not None:
                a[khoa] = str(that)
        if existing_only:
            if not a.get("profile") or not Path(a["profile"]).is_file():
                continue
        out.append(a)
    return out


def author_folder_name(entry: dict) -> str:
    """Ten folder profile theo quy uoc: 'A001_Carl-Sagan'."""
    return f"{entry['code']}_{entry.get('slug') or slugify(entry['name'])}"
