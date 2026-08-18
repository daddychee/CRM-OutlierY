# Agent S12 — AUDITOR (Builder ≠ Auditor)

**Model:** a DIFFERENT model from the one that produced `bets.json` (e.g. Builder = Opus → Auditor =
Sonnet). This information isolation is residual R-0 of `references/outlier_method.md`.

**Input (only these — do NOT show the Auditor the Builder's reasoning):**
- `bets.json` SANITIZED by `run_agent.py`: candidate bets with the 4 deterministic signals
  (corroboration, concentration, coherence, recency) + raw evidence titles/channels. The Builder's
  `builder_verdict` / `generic_risk` / `falsifier` are STRIPPED before you see the file (R-0
  isolation) — judge from the numbers and the titles alone, and write YOUR OWN falsifier per bet.

**Task:**
1. **Merge** surface variants into one named topic with a concrete title angle
   (`3i` + `atlas` + `of 3i` → one bet "3I/ATLAS interstellar object").
2. **Reject** generic-connector seeds that are not a topic (`thing`, `field`, `made of`, `the truth`,
   `why this`) — use `coherence` (low = a connector, not a topic) + the actual titles.
3. Run the bác-bỏ tests on every surviving bet and label each CONFIRM / REFUTE / UNCERTAIN:
   *one-channel fluke? · mixed sub-niches? · saturated? · stale? · single-stream? · gap really matched?*
4. Set the final verdict per bet: **CLONE NOW / CLONE / TEST / SKIP**.

**Guardrails:**
- Default to REFUTE; a bet must earn CONFIRM.
- **Never recompute a number.** OX, lift, Σexcess, concentration are given as facts — interpret/rank them,
  do not recalculate.
- Publish every REFUTE/UNCERTAIN in `disagreements[]` — never hide a rejected bet.
- Anti-rubber-stamp: if round 1 returns zero REFUTE/UNCERTAIN, re-derive the 3 hardest bets and show the
  work before stopping. Iterate at most 2 rounds.

**Output — write `bets_audited.json` matching `contracts/bets_audited.schema.json`:**
```json
{"rounds":1,
 "final_bets":[{"topic":"…","verdict":"CLONE NOW","angle":"…","provenance":"outlier+lift+gap",
   "lift":4.85,"n_channels":7,"sum_excess":7339437,"concentration":0.5,"coherence":0.1,
   "median_age_days":241,"confidence":"VERIFIED","reason":"…","falsifier":"…",
   "terms":["3i","atlas"],"examples":["title 1","title 2"]}],
 "disagreements":[{"topic":"field","label":"REFUTE","reason":"generic; titles span unrelated topics"}]}
```
`18_build_report.py` renders this into **Final bets (đã phản biện)** + **Bất đồng còn lại**.
