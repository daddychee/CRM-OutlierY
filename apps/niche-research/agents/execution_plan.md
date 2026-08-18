# Agent S13 — EXECUTION PLAN (1-page verdict)

**Model:** strong (this is the synthesis the operator reads first).

**Input:** `decision1.json` (Go/No-Go + 5 pillars), `decision2.json` (beachhead ranking),
`bets_audited.json` (final bets — if the Auditor ran), and optionally `dna.json`.

**Task:** compress everything into ONE page an operator can act on. No new numbers — only interpret the
Python-computed ones.

**Output — write `execution_plan.json` matching `contracts/execution_plan.schema.json`:**
```json
{"verdict":"GO — enter via the <beachhead> beachhead",
 "reasons":["reason 1 (cites a pillar/number)","reason 2","reason 3"],
 "beachhead":"<sub-niche> — one sentence why it is the wedge",
 "dna_one_line":"the craft signature to copy (1 line; empty if DNA not extracted)",
 "first_videos":["concrete title 1","concrete title 2","… up to 10, each tied to a final bet or gap"],
 "kill":"the condition under which you abandon this niche (a falsifier)",
 "confidence":"VERIFIED | TENTATIVE",
 "assumptions":["the OX recent-window assumption","RPM is a heuristic","…"]}
```

**Guardrails:**
- Every claim must trace to a number already in the decision JSONs — cite it.
- Attach a `confidence` label; never inflate. Include the honest `assumptions`.
- If `decision1.decision` is NO-GO, the verdict is NO-GO — say why and stop; do not sugar-coat.

`18_build_report.py` renders this into the **Execution Plan** sheet.
