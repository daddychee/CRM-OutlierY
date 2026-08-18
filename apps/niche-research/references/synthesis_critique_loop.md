# Synthesis ↔ Critique loop — from a pooled niche to a final short-list of bets

> Goal: when you pool many channels + thousands of videos, the report sheets explode (many
> outliers, many lift keywords, many patterns, many gaps). Every row can be *correct* yet the
> signal is diluted and nothing is decidable. This loop converges that mass into a small,
> defensible list of video bets — and is explicit about every bet it throws away.

This is a **different loop** from `dong_kiem_protocol.md`. That one asks *"is this number correct?"*
(does OX/lift/pattern obey the v3 rules). This one assumes the numbers are correct and asks
*"of all these correct results, which few survive an adversarial critique and are worth making?"*

It runs in three parts: a deterministic **Synthesis** (script), a two-model **Critique**
(Builder ≠ Auditor), and a **Reconcile** that emits the final sheets.

---

## Part 1 — SYNTHESIS (`5_synthesize_bets.py`, deterministic)

**Bet unit = a HIGH-LIFT phrase/word, not a Σexcess keyword cluster.** Pooling many channels makes
generic vocabulary (`most`, `true`, `scientists`, `world`, `first`) dominate any frequency- or
Σexcess-ranked list — those are the niche's common words, not its breakout topics. Anchoring each
candidate on a phrase/word that *over-indexes in outliers* (lift, FDR-significant) surfaces real
topics instead. This was validated on a real pooled niche: the Σexcess-cluster unit produced
garbage top bets (`most`, `true`, `scientists`); the lift-seed unit produced recognisable topics
(`CERN just …`, `3I/ATLAS`, `what a photon is really made of`, `true scale of the universe`).

Each candidate carries four signals so the critique argues from numbers, not taste:

| Signal | Meaning | A bet is suspicious when |
|---|---|---|
| **corroboration** | independent streams backing it (outlier + lift + gap) | only 1 stream |
| **concentration** | Σexcess share of the single biggest channel | high (one-channel fluke) |
| **coherence** | mean pairwise title-token Jaccard of the cluster | low (a connector word, not a topic) |
| **recency** | median age (days) of the cluster's outliers | old (signal may be fading) |

The script also assigns a provisional **Builder verdict** (STRONG / TEST / WEAK) and a **falsifier**
("this is wrong if …"). Output `bets.json` is a **candidate pool, not the answer** — two residual
problems are inherently semantic and a rule cannot fix them, by design left to the Auditor:

1. **Surface variants of one topic** (`3i` + `atlas` + `of 3i`; `scale` + `true scale` + `scale of`)
   must be merged into one named bet.
2. **Generic connector seeds that still pass the lift gate** (`thing`, `field`, `made of`, `to the`)
   must be rejected as non-topics. The script flags `generic_risk` but does not have final say.

---

## Part 2 — CRITIQUE (two real models, per residual R-0 of the outlier method)

A single model auditing its own synthesis shares its blind spots. So the Auditor is a **different
model** (e.g. Builder = the orchestrating model, Auditor = a smaller/other model via a sub-agent),
**information-isolated**: it sees only `bets.json` + the raw evidence (titles, channels, signals),
**not** the Builder's reasoning, and must re-derive its judgment.

For every candidate the Auditor does four things:

1. **Merge** surface variants into one topic and give it a human name + a concrete title angle.
2. **Reject** generic-connector seeds that aren't a real topic (use `coherence` + the titles).
3. **Run the bác-bỏ tests** and label CONFIRM / REFUTE / UNCERTAIN with evidence:
   - *one-channel fluke?* (concentration high, few channels)
   - *mixed sub-niches?* (the matched titles are several unrelated topics)
   - *already saturated?* (every channel makes it → hard to differentiate)
   - *stale?* (recency old, not an ongoing/breaking topic)
   - *single stream?* (corroboration = lift only, no gap, thin outlier base)
   - *gap really matched?* (the gap theme actually answers to this topic)
4. **Set the final verdict**: CLONE NOW / CLONE / TEST / SKIP, with one line of reasoning.

The Auditor may also raise a **missed bet** the Builder dropped (e.g. a strong gap theme with no
lift seed) for the next round.

---

## Part 3 — RECONCILE & STOP

- **CONFIRM** → keep, label VERIFIED.
- **REFUTE** → drop or demote; record the reason (never silently).
- **UNCERTAIN** → keep but label TENTATIVE and lower its rank.
- Iterate at most `MAX_ROUNDS = 2`. Anything still REFUTE/UNCERTAIN at the cap goes to the
  **"Bất đồng còn lại"** (remaining-disagreements) sheet — disagreement is published, never hidden.
- **Anti-rubber-stamp:** if the first round returns zero REFUTE and zero UNCERTAIN, that is
  suspicious — require the Auditor to show its re-derivation for the 3 hardest bets (highest Σexcess,
  highest concentration, the one nearest a verdict boundary) before stopping.

Output = `bets_audited.json`, rendered by `4_build_report.py` into two sheets:
**"Final bets (đã phản biện)"** (survivors, ranked, with provenance + signals + verdict + falsifier)
and **"Bất đồng còn lại"** (every rejected/uncertain bet with its reason).

---

## Why this converges the pooling problem

The mass shrinks because a bet only survives if it is **a coherent topic** (coherence + Auditor
merge), **not a one-channel fluke** (concentration), **backed by more than one stream**
(corroboration), and **still live** (recency) — and a *different* model had to fail to refute it.
Generic vocabulary and single-channel spikes, which is exactly what pooling inflates, are removed
at two independent stages (deterministic signals, then semantic audit).
