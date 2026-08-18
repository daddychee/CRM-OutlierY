# Niche Research

A YouTube **niche intelligence** tool. From a list of competitor channels + an API key it builds one
multi-sheet Excel workbook that answers three questions:

1. **Market map** — what titles/topics recur, which videos truly broke out (OUTLIER v3), which keywords
   over-index in winners (LIFT), which patterns repeat, which viewer questions go unanswered.
2. **Decision 1 — Go / No-Go** — is this niche worth entering? (crackability · monetization · demand ·
   competition · trend → attractiveness, with a crackability *hard gate*).
3. **Decision 2 — Beachhead** — if GO, which sub-niche to attack first, and a candidate bet list.

Built on the architecture in `NICHE-TOOL-ARCHITECTURE.md`: **Python does everything measurable, the LLM
does everything that must be understood** — the two only talk through typed JSON files.

## Run — the easy way (START button)

- **macOS:** double-click **`Start.command`**
- **Windows:** double-click **`Start.bat`**

Pick your `competitors.txt`, press **▶ START**. The log streams live; **Open report** appears when done.
Everything is written into the **same folder as the competitor file** (each project self-contained).

### Project folder layout

The tool keeps each project tidy — you only ever look at two things: your input, and `Report/`.

```
<your project>/
├─ competitors.txt              ← your input (untouched)
├─ Report/
│   └─ <name>_report.xlsx       ← THE DELIVERABLE
├─ Transcripts/                 ← readable, TITLE-named transcripts (deep-dive only)
│   ├─ 01 - What is a black hole explained.txt
│   └─ index.json
└─ niche-data/                  ← all intermediates (safe to ignore)
    ├─ videos.json, analysis.json, …   (every JSON)
    ├─ run.log                          (full log, incl. errors)
    └─ .state.json                      (remembers args for Refresh)
```

Transcripts are saved under the **video title**, not an opaque id. Older "flat" projects (everything
dumped in the root) are **migrated into this layout automatically** on the next run — without
re-scanning.

First-time notes:
- **macOS** may block the launcher: right-click `Start.command` → **Open** → confirm.
- **Windows** needs Python 3 from [python.org](https://www.python.org/downloads/) with *"Add Python to
  PATH"* ticked (tkinter is included). Missing `requests`/`openpyxl` are auto-installed on first run.

## If it stops before finishing — 🔄 Refresh

Any run can stop before producing every output: you close the window, the internet drops, an API quota
runs out, a transcript key has no credit, the app crashes. Press **🔄 Refresh (continue)** and it picks
up exactly where it left off — it never re-does work that already finished.

- Refresh uses whichever project is currently loaded; if none is loaded it falls back to the **last
  project this app touched** (remembered across restarts — reopening the app auto-fills the fields), or
  lets you pick the project folder.
- It works because every `run` is **idempotent**: each stage is skipped once its output exists and is
  newer than its inputs, so Refresh only (re)does what's missing or stale.
- Every run's config is saved to `niche-data/.state.json`, and the full log to `niche-data/run.log`
  (persists even after the GUI window is closed) — the exact reason a stage failed (e.g. an API quota
  or a "no active paid plan" error) is always readable there.
- Check what's missing without running anything:  `python3 orchestrator.py status <project folder>`

## Run — command line

```bash
python3 orchestrator.py run competitors.txt
python3 orchestrator.py run competitors.txt --work ./PROJECT --out report.xlsx --skip-comments
python3 orchestrator.py run competitors.txt --force            # rebuild every stage
python3 orchestrator.py run competitors.txt --deepdive         # + fetch transcripts of the top beachhead
python3 orchestrator.py status ./PROJECT                       # read-only checklist: done / stale / missing
python3 orchestrator.py resume ./PROJECT                       # continue a stopped run (replays the saved args)
python3 orchestrator.py run competitors.txt --deepdive quantum # + fetch transcripts for a named sub-niche
```

## Deep-dive: transcripts for DNA (S14 + S15)

With `--deepdive` (or the GUI checkbox), after the report the tool picks a sub-niche's valid outliers
(S14) and downloads their transcripts via **[transcriptapi.com](https://transcriptapi.com/docs/api/)**
into `transcripts/` (S15). This feeds the DNA agent (`agents/dna_extractor.md`, S16/17 → `dna.json`).

- Put your key in `.env`:  `TRANSCRIPT_API_KEY=sk_...`
- **Costs 1 credit per video** (capped at 30). The orchestrator prints a cost guard first.
- Resumable: it checkpoints after each video. `402 no credits` / `429 rate-limit` are handled cleanly —
  top up or wait, then re-run; already-fetched transcripts are skipped.

## LLM stages — bring your own model (Claude, ChatGPT, GLM, Grok, or any OpenAI-compatible API)

Without this, S9b/S12/S13/S16-17 are **unexecuted specs** and every "verdict" in the report (Go/No-Go,
crackability, candidate bets) is a plain Python threshold rule — no model has looked at your data yet.

Turn them on with **`--llm`** (CLI) or the **🤖 "Run LLM analysis"** checkbox (GUI). **Pick ONE provider
and use it throughout** — configure it in `.env`:

```bash
LLM_PROVIDER=anthropic        # or: glm | openai | grok | custom
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-sonnet-4-5     # optional, this is the default

# GLM instead:         LLM_PROVIDER=glm   GLM_API_KEY=...   GLM_MODEL=glm-4-plus
# ChatGPT:             OPENAI_API_KEY=...  OPENAI_MODEL=gpt-4o
# Grok:                 GROK_API_KEY=...    GROK_MODEL=grok-4
# any other provider:  CUSTOM_BASE_URL=https://.../v1  CUSTOM_API_KEY=...  CUSTOM_MODEL=...
```

`custom` accepts **any OpenAI-compatible `/chat/completions` endpoint** — so new models work without
code changes. One key, one provider, all stages.

LLM stages are always **optional** — if a call fails (bad key, quota, network), that stage is skipped
and the deterministic pipeline still produces a report.

*(Advanced, optional: set `AUDITOR_LLM_PROVIDER` to a second provider if you want the Auditor step on a
different model for an independent critique. Leave it unset to keep everything on the one model.)*

Run agents individually, or with a different provider per stage, without re-running everything:

```bash
python3 orchestrator.py llm ./PROJECT                          # run pending: namer/auditor/plan/summary
python3 orchestrator.py llm ./PROJECT --agent auditor --provider glm
python3 orchestrator.py llm ./PROJECT --agent dna               # after transcripts exist (--deepdive)
python3 orchestrator.py llm ./PROJECT --agent summary           # the final expert assessment (see below)
```

### The final SUMMARY (S19) — dry numbers → a concrete, actionable guide

The `summary` agent reads **every** decision file and turns the raw numbers into a **practical guide in
Vietnamese** that tells a creator exactly what to do this week — written by an expert-analyst persona.
Output: `Report/SUMMARY.md` (readable) and the **first sheet** of the workbook ("Đánh giá sau cùng").

Its method (`agents/summary.md`) runs a rigorous **3-pass self-critique loop on your one model**:

1. **Draft the guide** — verdict + a scorecard + **5–10 concrete video ideas** (titles built from the
   niche's real lift-keywords/title-templates) + winning formula + content gaps + what to avoid.
2. **Self-critique (adversarial)** — the model re-reads its own draft as a skeptical content director:
   *Is each item actionable Monday morning? Backed by a number? Fooled by a tiny-baseline OX (rank by
   Σexcess instead)? A heuristic (RPM) mistaken for fact? Does the verdict follow the numbers?* — each
   item labelled KEEP / REVISE / DROP.
3. **Refine** — vague, unbacked items are rewritten into concrete actions or dropped (with a published
   "critique log"); missing risks are added.

The guide ranks by **absolute reach (Σexcess)**, cites a number for every recommendation, flags
heuristics (RPM) and residuals (R-1/R-A/R-3), and never invents titles — they trace to real winning
keywords/templates in the data.

```bash
python3 orchestrator.py llm ./PROJECT --agent summary     # produce Report/SUMMARY.md
```

## Input file

One plain-text file mixing API key(s) and channels:

```
AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
https://www.youtube.com/channel/UCxxxxxxxxxxxxxxxxxxxxxx
https://www.youtube.com/@somehandle
UCyyyyyyyyyyyyyyyyyyyyyy
```

## Pipeline (the DAG)

| Stage | Kind | Script / spec | Output |
|---|---|---|---|
| S1 scan | PY | `scripts/1_scan.py` | `videos.json`, `channels.json` |
| S3 keywords + LIFT | PY | `scripts/2_keywords.py` | `analysis.json` |
| S4 comments → questions | PY | `scripts/3_comments.py` | `gaps.json` |
| S5 crackability | PY | `scripts/5_crackability.py` | `crackability.json` |
| S6 monetization | PY | `scripts/6_monetization.py` | `monetization.json` |
| S7 demand & trend | PY | `scripts/7_demand.py` | `demand.json` |
| **S8 Decision 1 (Go/No-Go)** | PY | `scripts/8_decision1.py` | `decision1.json` |
| S9 sub-niche clustering | PY | `scripts/9_subniche.py` | `subniche.json` |
| **S10 Decision 2 (beachhead)** | PY | `scripts/10_decision2.py` | `decision2.json` |
| S11 synthesize bets | PY | `scripts/11_synthesize_bets.py` | `bets.json` |
| S18 build report | PY | `scripts/18_build_report.py` | `*.xlsx` |
| S14 deep-dive (opt.) | PY | `scripts/14_deepdive.py` | `deepdive_*.json`, `00-danh-sach-video-*.md` |
| S15 fetch transcripts (opt.) | PY | `scripts/15_fetch_transcripts.py` | `transcripts/` |

The **orchestrator** runs all Python stages: idempotent (skips stages whose output is newer than input),
resumable (S1/S4 checkpoint per page and loop until `DONE`), and schema-gated against `contracts/`.

## LLM stages (not run by the tool — need a real model)

Per the architecture, judgement stages are **agent specs** in `agents/`, run with a model (ideally a
*different* model for the Auditor — information isolation). The report renders whatever exists and shows a
banner where an LLM artifact is missing:

| Stage | Spec | Produces |
|---|---|---|
| S9b name sub-niches | `agents/subniche_namer.md` | labels in `subniche.json` |
| S12 Auditor (Builder ≠ Auditor) | `agents/auditor.md` | `bets_audited.json` |
| S13 Execution Plan | `agents/execution_plan.md` | `execution_plan.json` |
| S16/17 DNA extraction | `agents/dna_extractor.md` | `dna.json` |

## Honesty

Every number lives under the OX recent-window assumption (R-1); RPM is a heuristic; crackability's
`newcomer_rate` is conservative (current subs ≠ subs-at-post, R-A); sub-niche borders are soft; DNA is
craft judgement. The report prints confidence labels and never hides disagreements. Results are
**informed bets to A/B test**, not proof. See `references/` for the full method.
