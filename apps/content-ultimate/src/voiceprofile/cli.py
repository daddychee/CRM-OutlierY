"""CLI cho voiceprofile (xem Muc 7 BUILD-BRIEF): build / dataset / clonekit / rhetoric."""
from __future__ import annotations

import json
import os
from pathlib import Path

import typer

from .clonekit import build_clonekit_markdown
from .corpus import build_corpus, load_corpus_dir
from .dataset import build_dataset, write_jsonl
from .generator import generate_script, parse_outline
from .llm import available_providers, llm_json, llm_text, provider_config
from .profile import MIN_STABLE_UNITS, build_profile
from .rhetoric import ground_moves, propose_moves
from .validate import evaluate_script, format_report, targets_for_length

app = typer.Typer(help="Author Extract — tool tai tao giong van tac gia")


def _pick_provider(provider: str | None, model: str | None) -> dict:
    """Chon provider tu kho key .env. provider=None -> lay cai dau tien co key.

    Nem RuntimeError (thong diep huong dan) neu khong co provider nao / provider chi dinh thieu key.
    """
    if provider:
        cfg = provider_config(provider)
    else:
        avail = available_providers()
        if not avail:
            raise RuntimeError(
                "Chua co provider nao trong .env. Dien it nhat mot key "
                "(ANTHROPIC_API_KEY / GLM_API_KEY / OPENAI_API_KEY / GEMINI_API_KEY)."
            )
        cfg = next(iter(avail.values()))
    if model:
        cfg = {**cfg, "model": model}
    return cfg


@app.command(name="build")
def build(
    author_dir: str = typer.Option(..., "--author-dir", help="Thu muc corpus tac gia"),
    baseline_dir: str = typer.Option(None, "--baseline-dir",
                                     help="(Tuy chon) corpus baseline de tuong phan; bo trong -> self-profile mode"),
    out: str = typer.Option("profile.json", "--out", help="Duong dan file profile.json dau ra"),
    author: str = typer.Option("Unknown Author", "--author", help="Ten tac gia"),
    source_language: str = typer.Option("en", "--source-language"),
    output_language: str = typer.Option("en", "--output-language"),
    z_threshold: float = typer.Option(1.0, "--z-threshold", help="Nguong z-score (contrast mode)"),
    stability_cv: float = typer.Option(0.30, "--stability-cv",
                                       help="Nguong he so bien thien de giu dac trung (self-profile mode)"),
    register: bool = typer.Option(True, "--register/--no-register",
                                  help="Dang ky tac gia vao so thu vien (de Writer thay)"),
):
    """Module 1-2: nap corpus, tinh dac trung, xuat profile.json.

    Khong co --baseline-dir: self-profile mode — giu dac trung ON DINH qua cac van ban
    tac gia, target tai tao +-1 SD. Co --baseline-dir: contrast mode (z-score) nhu cu.
    """
    author_corpus = build_corpus(author_dir, name=author)
    typer.echo(f"Corpus tac gia: {author_corpus.n_works} file, {author_corpus.n_tokens} tu.")
    if author_corpus.file_bo:
        # Noi RO da bo gi — nguoi dung phai biet ho so duoc dung tren nhung file nao.
        typer.echo(f"  DA BO {len(author_corpus.file_bo)} file thieu dau cau (transcript "
                   "chua cham cau): " + "; ".join(author_corpus.file_bo))

    baseline_corpus = None
    if baseline_dir:
        baseline_corpus = build_corpus(baseline_dir, name="baseline")
        if len(baseline_corpus.train) < 5:
            typer.echo(f"CANH BAO: corpus BASELINE ({baseline_dir}) chi co "
                       f"{len(baseline_corpus.train)} van ban train — z-score se rat nhieu. "
                       "Nen dung >=5 van ban, hoac bo --baseline-dir de dung self-profile mode.")

    profile = build_profile(
        author=author,
        source_language=source_language,
        output_language=output_language,
        author_corpus=author_corpus,
        baseline_corpus=baseline_corpus,
        z_keep_threshold=z_threshold,
        stability_cv=stability_cv,
    )

    # Nho DUONG DAN corpus trong chinh ho so: bao cao kho can doc lai van goc de dung
    # bang Delta, va khong co cho nao khac luu duong dan nay ngoai so dang ky thu vien.
    profile.setdefault("corpus_stats", {})["corpus_dir"] = str(Path(author_dir).resolve())

    # Giu lai signature_moves da co (ket qua lenh `rhetoric` ton kem LLM, khong nen
    # mat khi do lai dac trung) — chay lai `rhetoric` neu muon lam moi.
    out_path = Path(out)
    if out_path.is_file():
        try:
            old = json.loads(out_path.read_text(encoding="utf-8"))
            if old.get("signature_moves"):
                profile["signature_moves"] = old["signature_moves"]
                typer.echo(f"Giu lai {len(old['signature_moves'])} signature_moves tu profile cu.")
        except (json.JSONDecodeError, OSError):
            pass

    with open(out, "w", encoding="utf-8") as f:
        json.dump(profile, f, ensure_ascii=False, indent=2)

    n_kept = sum(1 for q in profile["quant_features"] if q["keep"])
    typer.echo(f"Da ghi {out} [{profile['profile_mode']}] — {n_kept}/{len(profile['quant_features'])} "
               f"dac trung dat nguong, {len(profile['distinctive_ngrams'])} n-gram, "
               f"{len(profile['reproduction_targets'])} target tai tao, {len(profile['exemplars'])} exemplar.")

    # BAO CAO EXTRACT (24/08): ghi ngay canh profile.json. Truoc day muon biet ho so
    # co dung khong thi phai mo profile.json doc tay — va khong ai doc, do la ly do ba
    # ho so dung tren corpus transcript tho van duoc dung de viet suot ba tuan.
    try:
        from .bao_cao import bao_cao_extract, ghi_bao_cao
        duong_bc = ghi_bao_cao(bao_cao_extract(profile, corpus_dir=author_dir),
                               Path(out).parent / "bao-cao-extract.md")
        typer.echo(f"Bao cao extract: {duong_bc}")
    except Exception as e:  # noqa: BLE001 — bao cao hong KHONG duoc lam hong extract
        typer.echo(f"(Khong dung duoc bao cao extract: {e})")

    # Chi canh bao khi corpus THAT SU ngan (it doan do) — 1 sach day da tu du doan.
    n_units = profile["corpus_stats"].get("n_stability_units", author_corpus.n_works)
    if profile["profile_mode"] == "self_profile" and n_units < MIN_STABLE_UNITS:
        typer.echo(f"CANH BAO: corpus hoi ngan ({author_corpus.n_tokens} tu, {n_units} doan do) "
                   "— do on dinh kem tin cay hon. Bo sung ban thao de tang do tin cay.")

    if register and author and author != "Unknown Author":
        from .library import register_profile, registry_path
        # CU_USER do server job dat khi spawn subprocess (2026-07-15) — thanh vien team
        # nao chay extract thi thu vien ghi ten nguoi do ("nguoi viet" tren GUI).
        entry = register_profile(author, profile=out, corpus=author_dir,
                                 created_by=os.environ.get("CU_USER", ""))
        typer.echo(f"Da dang ky vao thu vien: {entry['code']} · {entry['name']} ({registry_path()}).")


@app.command(name="dataset")
def dataset(
    author_dir: str = typer.Option(..., "--author-dir", help="Thu muc corpus tac gia"),
    out: str = typer.Option("dataset.jsonl", "--out", help="File JSONL dau ra"),
    author: str = typer.Option("the author", "--author", help="Ten tac gia (cho system prompt)"),
    mode: str = typer.Option("continuation", "--mode", help="continuation | instruction"),
    seed_sentences: int = typer.Option(2, "--seed-sentences", help="So cau lam seed (mode continuation)"),
    min_words: int = typer.Option(60, "--min-words"),
    max_words: int = typer.Option(350, "--max-words"),
):
    """Dung dataset JSONL fine-tune tu corpus tac gia (lam sach OCR + cat doan)."""
    texts = load_corpus_dir(author_dir)

    llm_summarize = None
    if mode == "instruction":
        typer.echo("LUU Y: mode 'instruction' can callback LLM (chua cau hinh API key trong CLI). "
                   "Tam thoi dung 'continuation', hoac noi voi Claude Code de cam API.")
        raise typer.Exit(code=1)

    pairs, report = build_dataset(
        texts, author=author, mode=mode, seed_sentences=seed_sentences,
        llm_summarize=llm_summarize, min_words=min_words, max_words=max_words,
    )
    write_jsonl(pairs, out)
    typer.echo(f"Da ghi {out} — {report['n_pairs']} cap.")
    typer.echo(f"  Trung lap nguyen van: {report['exact_duplicate_completions']} | "
               f"5-gram lap >=3 lan: {report['repeated_5grams_ge3']}")
    typer.echo(f"  Do dai completion (tu): min {report['completion_words_min']}, "
               f"mean {report['completion_words_mean']}, max {report['completion_words_max']}")


@app.command(name="clonekit")
def clonekit(
    author_dir: str = typer.Option(..., "--author-dir", help="Thu muc corpus tac gia"),
    out: str = typer.Option("clonekit.md", "--out", help="File markdown dau ra"),
    author: str = typer.Option("the author", "--author", help="Ten tac gia"),
    n_exemplars: int = typer.Option(5, "--n-exemplars", help="So doan mau nhung vao kit"),
):
    """Tao clone-kit (markdown) de clone giong van bang prompt few-shot — dan thang vao LLM."""
    texts = load_corpus_dir(author_dir)
    md = build_clonekit_markdown(texts, author=author, n_exemplars=n_exemplars)
    with open(out, "w", encoding="utf-8") as f:
        f.write(md)
    typer.echo(f"Da ghi {out} — clone-kit voi {n_exemplars} exemplar. Dan vao LLM va viet thu.")


@app.command(name="rhetoric")
def rhetoric(
    author_dir: str = typer.Option(..., "--author-dir", help="Thu muc corpus tac gia"),
    profile_path: str = typer.Option(..., "--profile", help="profile.json da tao boi `build` — se duoc ghi them signature_moves"),
    author: str = typer.Option("the author", "--author", help="Ten tac gia"),
    min_evidence: int = typer.Option(3, "--min-evidence", help="So trich dan xac minh toi thieu de giu 1 move (N cua brief)"),
    n_passages: int = typer.Option(12, "--n-passages", help="So doan mau dua vao LLM"),
    n_moves: int = typer.Option(8, "--n-moves", help="So move toi da LLM de xuat"),
    provider: str = typer.Option(None, "--provider", help="Provider LLM (anthropic/glm/openai/gemini); mac dinh: cai dau tien co key"),
    model: str = typer.Option(None, "--model", help="Ghi de model cua provider"),
):
    """Module 3 + 3b: LLM de xuat signature moves, Python kiem chung tung trich dan voi corpus."""
    if not Path(profile_path).is_file():
        typer.echo(f"Khong tim thay {profile_path} — chay `voiceprofile build` truoc de tao profile.json.")
        raise typer.Exit(code=1)
    with open(profile_path, encoding="utf-8") as f:
        profile = json.load(f)

    try:
        cfg = _pick_provider(provider, model)
    except RuntimeError as e:
        typer.echo(f"LOI: {e}")
        raise typer.Exit(code=1)
    typer.echo(f"Provider: {cfg['provider']} | model: {cfg['model']}")

    texts = load_corpus_dir(author_dir)
    try:
        proposed = propose_moves(
            texts, author=author,
            llm_json=lambda prompt, schema: llm_json(prompt, schema, cfg),
            n_passages=n_passages, n_moves=n_moves, min_evidence=min_evidence,
        )
    except (RuntimeError, ValueError) as e:
        typer.echo(f"LOI: {e}")
        raise typer.Exit(code=1)

    grounded = ground_moves(proposed, texts, min_evidence=min_evidence)
    profile["signature_moves"] = grounded
    with open(profile_path, "w", encoding="utf-8") as f:
        json.dump(profile, f, ensure_ascii=False, indent=2)

    dropped = len(proposed) - len(grounded)
    typer.echo(f"Da ghi {profile_path} — {len(grounded)}/{len(proposed)} move dat chung cu "
               f"(>= {min_evidence} trich dan xac minh duoc); loai {dropped} move thieu chung cu.")
    for m in grounded:
        typer.echo(f"  [{m['type']}] {m['move']} — {m['occurrences']} trich dan")


@app.command(name="lab")
def lab(
    profile_path: str = typer.Option(..., "--profile", help="profile.json cua tac gia (tu `build`)"),
    samples: int = typer.Option(5, "--samples", min=3, max=10,
                                help="So mau moi o do (5-10). Cang nhieu cang chinh, cang ton."),
    provider: str = typer.Option(None, "--provider", help="Provider LLM (anthropic/glm/openai/gemini)"),
    model: str = typer.Option(None, "--model", help="Ghi de model"),
):
    """Test lab do DO DAI: do so ky tu/brief RIENG cua tac gia nay -> ghi vao profile.json.

    Vi sao: CHARS_PER_IDEA=1250 la so khop tu MOT thi nghiem roi ap cho MOI tac gia. Do
    that 2026-07-15: Ventures 1408 / Investigate Lewis 1720 (lech 22%) — mot hang so chung
    sai cho ca hai. Hang so ON DINH qua chu de (+2%) nen do MOT LAN moi tac gia la du,
    nhung PHU THUOC tac gia (+19%) nen bat buoc do rieng.

    TON TIEN: samples x 4 o = so chuong phai viet (mac dinh 5 -> 20 luot LLM).
    """
    from .lengthlab import LAB_CONFIGS, render_guide, run_lab

    if not Path(profile_path).is_file():
        typer.echo(f"Khong tim thay {profile_path} — chay `voiceprofile build` truoc.")
        raise typer.Exit(code=1)
    with open(profile_path, encoding="utf-8") as f:
        profile = json.load(f)
    try:
        cfg = _pick_provider(provider, model)
    except RuntimeError as e:
        typer.echo(f"LOI: {e}")
        raise typer.Exit(code=1)

    tag = f"{cfg['provider']}:{cfg['model']}"
    n = samples * len(LAB_CONFIGS)
    typer.echo(f"Lab do do dai — tac gia '{profile.get('author')}' x model {tag}")
    typer.echo(f"  {len(LAB_CONFIGS)} o x {samples} mau = {n} chuong thu (ton {n} luot LLM)")

    out = run_lab(profile, lambda s, u: llm_text(s, u, cfg, max_tokens=8000),
                  samples=samples, model=tag, on_progress=typer.echo)
    if not out:
        typer.echo("LOI: lab khong do duoc o nao — khong ghi gi vao profile.")
        raise typer.Exit(code=1)

    profile["length_lab"] = out
    with open(profile_path, "w", encoding="utf-8") as f:
        json.dump(profile, f, ensure_ascii=False, indent=2)
    typer.echo(f"\nDa ghi length_lab vao {profile_path}:")
    for line in render_guide(out):
        typer.echo(line)


@app.command(name="write")
def write(
    outline_path: str = typer.Option(..., "--outline", help="File outline (Title/Hook/Chapter 1..n/End)"),
    profile_path: str = typer.Option(..., "--profile", help="profile.json cua tac gia (tu `build`+`rhetoric`)"),
    author_dir: str = typer.Option(None, "--author-dir", help="Corpus tac gia (de do target cong bang do dai khi validate)"),
    out: str = typer.Option("script.md", "--out", help="File kich ban dau ra"),
    chars: int = typer.Option(18000, "--chars", help="Do dai muc tieu (ky tu)"),
    provider: str = typer.Option(None, "--provider", help="Provider LLM (anthropic/glm/openai/gemini)"),
    model: str = typer.Option(None, "--model", help="Ghi de model"),
    resume: bool = typer.Option(False, "--continue/--fresh",
                                help="Tiep tuc tu checkpoint (bo qua cac phan da viet) thay vi viet lai tu dau"),
    no_validate: bool = typer.Option(False, "--no-validate", help="Bo qua buoc do sau khi viet"),
    chi_phan: str = typer.Option(None, "--chi-phan", help="Chi viet DUNG phan nay (vd 'Chapter 2')"),
    gop_y: str = typer.Option("", "--gop-y", help="Gop y cua nguoi viet, dung khi viet lai mot phan"),
):
    """Module 5: sinh kich ban YouTube theo giong tac gia (sinh theo chuong -> ghep 1 file).

    --continue: chay tiep tu checkpoint (khi bi ngat: het token/mat mang). --fresh
    (mac dinh): viet lai tu dau, xoa checkpoint cu.
    """
    from .generator import (clear_checkpoint, load_checkpoint, save_checkpoint,
                            write_partial_script)
    if not Path(profile_path).is_file():
        typer.echo(f"Khong tim thay {profile_path} — chay `build` (+`rhetoric`) truoc.")
        raise typer.Exit(code=1)
    if not Path(outline_path).is_file():
        typer.echo(f"Khong tim thay file outline: {outline_path}")
        raise typer.Exit(code=1)
    profile = json.loads(Path(profile_path).read_text(encoding="utf-8"))
    outline = Path(outline_path).read_text(encoding="utf-8")

    # NEO DAY (C3b 22/08): thay 3 exemplar ~200 tu bang tap chon tu corpus that,
    # day ~1.800 tu VA khop nhip corpus. Chi doi bien trong bo nho — KHONG ghi de
    # profile.json (bai hoc 16/07: dung lai ho so tu transcript da bi user bac).
    # Corpus thieu dau cau -> giu nguyen neo cu, noi ro ly do.
    if author_dir:
        from .chon_neo import neo_day
        _r = neo_day(author_dir)
        if _r["neo"]:
            _cu = len(" ".join(str(e) for e in profile.get("exemplars") or []).split())
            profile = {**profile, "exemplars": _r["neo"]}
            typer.echo(f"Neo giong: {_r['tong_tu']} tu tu corpus ({len(_r['neo'])} khoi) "
                       f"thay cho {_cu} tu — nhip neo {_r['nhip_neo']['tu_moi_cau']} tu/cau "
                       f"vs corpus {_r['nhip_corpus']['tu_moi_cau']}"
                       + (f", bo qua {_r['file_bo_qua']} file thieu dau cau" if _r.get("file_bo_qua") else ""))
        else:
            typer.echo(f"Neo giong: giu 3 mau cu — {_r['ly_do']}")

    try:
        cfg = _pick_provider(provider, model)
    except RuntimeError as e:
        typer.echo(f"LOI: {e}")
        raise typer.Exit(code=1)
    typer.echo(f"Provider: {cfg['provider']} | model: {cfg['model']} | muc tieu ~{chars} ky tu")

    # Khoi VOICE TARGETS tu bat/tat theo model (generator.MODEL_BAM_NEO) — chi gan
    # bien trong bo nho, KHONG ghi de profile.json.
    profile = {**profile, "_model": cfg["model"]}
    from .generator import build_nhip_block
    if build_nhip_block(profile):
        typer.echo(f"Nhip: gui kem so do cua tac gia vao prompt ({cfg['model']} bam neo).")

    if resume:
        done = load_checkpoint(out, outline)
        if done:
            typer.echo(f"Tiep tuc tu checkpoint: {len(done)} phan da co ({', '.join(done)}).")
        else:
            typer.echo("Khong co checkpoint khop (hoac outline da doi) — viet tu dau.")
    else:
        clear_checkpoint(out)
        done = {}
    accumulated = dict(done)

    def on_done(heading: str, body: str) -> None:
        accumulated[heading] = body
        save_checkpoint(out, outline, chars, accumulated, cfg["provider"], cfg["model"])
        # VIET TUNG PHAN: cap nhat script.md ngay sau moi chuong (yeu cau user 2026-07-11)
        # → tai ve duoc bat cu luc nao; loi/huy giua chung van con phan da viet.
        write_partial_script(out, outline, profile)

    try:
        script = generate_script(
            outline, profile,
            llm_text=lambda system, user, mx: llm_text(system, user, cfg, mx),
            total_chars=chars,
            on_progress=lambda msg: typer.echo(msg),
            done_sections=done,
            on_section_done=on_done,
            chi_phan=chi_phan,
            gop_y=gop_y,
        )
    except (RuntimeError, ValueError) as e:
        from .generator import write_partial_script
        info = write_partial_script(out, outline, profile)
        if info:
            typer.echo(f"LOI: {e} — da luu {info['sections']} phan da viet vao {out} "
                       "(tai ve duoc / bam Tiep tuc de viet not).")
        else:
            typer.echo(f"LOI: {e} (chua phan nao xong — bam Tiep tuc de thu lai)")
        raise typer.Exit(code=1)

    from .generator import render_header
    from .llm import PROVIDERS
    actual = sum(len(b) for _, b in script.sections)
    header = render_header(
        author=profile.get("author", "the author"),
        target_chars=chars, actual_chars=actual,
        provider_label=PROVIDERS.get(cfg["provider"], {}).get("label", cfg["provider"]),
        model=cfg["model"],
    )
    script_md = header + script.to_markdown()
    Path(out).write_text(script_md, encoding="utf-8")
    n_content = sum(1 for s in parse_outline(outline) if s.kind != "title")
    if len(script.sections) >= n_content:
        clear_checkpoint(out)  # hoan tat -> xoa checkpoint
        typer.echo(f"Da ghi {out} — {len(script.sections)} phan, {len(script_md)} ky tu (hoan tat).")
    else:
        typer.echo(f"Da ghi {out} — {len(script.sections)}/{n_content} phan (chua xong, giu checkpoint). "
                   "Bam Tiep tuc de viet not.")

    if not no_validate and len(script.sections) >= n_content:
        _run_validate(script_md, profile, author_dir)


@app.command(name="mo-ta")
def mo_ta_lenh(
    profile_path: str = typer.Option(..., "--profile", help="profile.json cua tac gia"),
    provider: str = typer.Option(None, "--provider", help="Provider LLM"),
    model: str = typer.Option(None, "--model", help="Ghi de model"),
):
    """Mo ta giong van + huong dan dung (dung cho noi dung gi, mood, atmosphere).

    Cho DUY NHAT trong author extract ma LLM noi thanh loi — nen no chi duoc nhin SO
    DA DO va DOAN VAN THAT; ho so chua du diem do thi khong goi model.
    """
    from .mo_ta_giong import sinh_mo_ta
    p = Path(profile_path)
    if not p.is_file():
        typer.echo(f"Khong tim thay {profile_path} — chay `build` truoc.")
        raise typer.Exit(code=1)
    profile = json.loads(p.read_text(encoding="utf-8"))
    try:
        cfg = _pick_provider(provider, model)
    except RuntimeError as e:
        typer.echo(f"LOI: {e}")
        raise typer.Exit(code=1)
    # Khuon van (cach mo / chuyen doan / ket / cum tu) do tren CORPUS THAT, 0 token —
    # day la nguyen lieu cua khoi C. Khong doc duoc corpus thi mo ta van chay, chi
    # thieu ba muc do.
    kv = None
    cd = (profile.get("corpus_stats") or {}).get("corpus_dir")
    if cd and Path(cd).is_dir():
        from .khuon_van import khuon
        from .corpus import load_corpus_dir
        try:
            kv = khuon(load_corpus_dir(cd))
        except (OSError, ValueError) as e:
            typer.echo(f"(Khong do duoc khuon van: {e})")
    r = sinh_mo_ta(profile, lambda pr, sc: llm_json(pr, sc, cfg), kv=kv)
    if not r.get("mo_ta"):
        typer.echo(f"Khong sinh duoc mo ta: {r.get('ly_do')}")
        raise typer.Exit(code=1)
    profile["mo_ta_giong"] = r["mo_ta"]
    p.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")
    typer.echo(f"Da ghi mo_ta_giong vao {p}:")
    from .mo_ta_giong import dong_markdown
    for dong in dong_markdown(r["mo_ta"]):
        typer.echo("  " + dong)
    # Bao cao .md dung lai de mang theo doan mo ta vua sinh
    try:
        from .bao_cao import bao_cao_extract, ghi_bao_cao
        cd = (profile.get("corpus_stats") or {}).get("corpus_dir")
        ghi_bao_cao(bao_cao_extract(profile, corpus_dir=cd), p.parent / "bao-cao-extract.md")
    except Exception as e:  # noqa: BLE001
        typer.echo(f"(Khong dung lai duoc bao cao: {e})")


@app.command(name="bao-cao")
def bao_cao_lenh(
    profile_path: str = typer.Option(None, "--profile", help="profile.json cua MOT ho so"),
    author_dir: str = typer.Option(None, "--author-dir", help="Corpus (de do neo giong)"),
    kho: str = typer.Option(None, "--kho", help="Thu muc chua nhieu <ma>/profile.json — bao cao CA KHO"),
    out: str = typer.Option(None, "--out", help="File .md dau ra (mac dinh: canh profile)"),
):
    """Bao cao qua trinh extract — Python doc lai ho so, 0 token, khong goi model.

    Mot ho so:  --profile <duong>/profile.json [--author-dir <corpus>]
    Ca kho:     --kho <thu muc uploads>
    """
    from .bao_cao import bao_cao_extract, bao_cao_kho, ghi_bao_cao
    from . import delta as D

    if kho:
        goc = Path(kho)
        ds, kho_van = [], {}
        for p in sorted(goc.glob("*/profile.json")):
            try:
                pf = json.loads(p.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            ma = p.parent.name.split("_")[0]
            ds.append({"ma": ma, "ten": pf.get("author", ""), "profile": pf})
        if not ds:
            typer.echo(f"Khong tim thay profile.json nao trong {goc}")
            raise typer.Exit(code=1)
        # Bang Delta chi dung duoc khi doc lai duoc corpus goc; thieu thi bo qua phan do.
        bang = None
        for h in ds:
            d = (h["profile"].get("corpus_stats") or {}).get("corpus_dir")
            if d and Path(d).is_dir():
                try:
                    kho_van[h["ma"]] = load_corpus_dir(d)
                except (OSError, ValueError):
                    pass
        if len(kho_van) >= 2:
            bang = D.xay_bang(kho_van)
        md = bao_cao_kho(ds, bang)
        duong = out or str(goc / "bao-cao-kho.md")
    else:
        if not profile_path or not Path(profile_path).is_file():
            typer.echo("Can --profile <duong>/profile.json hoac --kho <thu muc>")
            raise typer.Exit(code=1)
        pf = json.loads(Path(profile_path).read_text(encoding="utf-8"))
        neo = None
        if author_dir:
            from .chon_neo import neo_day
            neo = neo_day(author_dir)
        md = bao_cao_extract(pf, corpus_dir=author_dir, neo=neo)
        duong = out or str(Path(profile_path).parent / "bao-cao-extract.md")
    typer.echo(f"Da ghi {ghi_bao_cao(md, duong)}")


@app.command(name="validate")
def validate(
    script_path: str = typer.Option(..., "--script", help="File kich ban .md/.txt de do"),
    profile_path: str = typer.Option(..., "--profile", help="profile.json cua tac gia"),
    author_dir: str = typer.Option(None, "--author-dir", help="Corpus tac gia (do target cong bang do dai)"),
):
    """Module 6 (phan do): kich ban giong tac gia bao nhieu % (X/N target trong +-1 SD)."""
    if not Path(script_path).is_file() or not Path(profile_path).is_file():
        typer.echo("Khong tim thay file script hoac profile.")
        raise typer.Exit(code=1)
    profile = json.loads(Path(profile_path).read_text(encoding="utf-8"))
    script_text = Path(script_path).read_text(encoding="utf-8")
    _run_validate(script_text, profile, author_dir)


def _run_validate(script_text: str, profile: dict, author_dir: str | None) -> None:
    """Do chung cho `write` va `validate`: chon target cong bang do dai neu co corpus."""
    from .textutils import tokenize_words
    targets = profile.get("reproduction_targets", {})
    if author_dir and Path(author_dir).is_dir():
        texts = load_corpus_dir(author_dir)
        kept_names = set(targets) or None
        fair = targets_for_length(texts, target_words=len(tokenize_words(script_text)))
        # chi giu cac dac trung von duoc keep trong profile (neu co)
        targets = {k: v for k, v in fair.items() if kept_names is None or k in kept_names}
        typer.echo("(Target do lai tren cua so corpus cung do dai kich ban — cong bang do dai)")
    elif not targets:
        typer.echo("CANH BAO: profile chua co reproduction_targets — chay `build` truoc.")
        return
    verdict = evaluate_script(script_text, targets)
    typer.echo(format_report(verdict))


if __name__ == "__main__":
    app()
