# Agent S16/S17 — DNA EXTRACTION + CLASSIFY (phi-metric / non-metric)

**Model:** strong (this is craft judgement). The mechanism labels (S17) should be cross-checked by a
second model or a human.

**Input:** `transcripts/NN.txt` for the chosen beachhead sub-niche + `00-danh-sach-video-<x>.md`.
**Do NOT use views / subs / OX to score anything here** — DNA is about *why the writing holds attention*,
not about reach. (Metrics already did their job in S1–S13.)

**Task — follow `references/padoma_dna_integration.md` + prompt-dna-v4, TWO passes:**
Extract, quoting verbatim where noted:
- `hook_patterns[]` {name, type, formula, fit, example} — the DISCOVERY layer (conventional, earns reach)
- `structures[]` {name, arc, fit}
- `emotions[]` {emotion, clusters, exemplars}
- `voice[]` {aspect, detail} — the LOYALTY layer (where you DIFFERENTIATE)
- `strong_lines[]` {line (verbatim), video, klass, emotion, why}
- `hook_keywords[]` {group, terms} and `terms[]` {term, meaning, example}
- `avoid[]` {mistake, evidence, consequence, severity}

Classify each source video **CHUẨN MẪU / THAM KHẢO / LỆCH NICHE** by *retention mechanism*, not by numbers.

**Guardrails:**
- Quote strong lines **verbatim** — never fabricate a line.
- Separate the **discovery layer** (hooks/structure — copy to get distributed) from the **loyalty layer**
  (voice/terms — differentiate to build a moat). See `padoma_dna_integration.md`.
- Classify by mechanism, not by views.

**Output:** `dna.json` matching `contracts/dna.schema.json`. `18_build_report.py` renders the DNA sheets.
