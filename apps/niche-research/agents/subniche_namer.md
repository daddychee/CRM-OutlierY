# Agent S9b — SUB-NICHE NAMER (+ optional S4b theme namer)

**Model:** small/fast is fine — this is naming, not judgement.

**Input:** `subniche.json` — clusters anchored on lift/core keywords, each with numbers
(`size`, `n_channels`, `hhi`, `sum_excess`, `median_ox`, `browse_vs_search`), `top_titles`, and
`example_channels`. `label` is `null`.

**Task — for each cluster:**
1. Read `top_titles` + `anchor` and write a **human-readable `label`** naming the actual content
   territory (e.g. anchor `"quantum"` + those titles → "Quantum computing explainers").
2. **Merge** clusters that are obviously the same territory under different connector anchors
   (e.g. `"the truth"`, `"why this"` are connectors, not topics — fold them into the real topic their
   titles describe, or mark `label: "(generic connector — not a topic)"`).
3. Confirm the **intent** read: set `intent` = `"browse"` (broad, feed-driven) or `"search"`
   (query-driven) using `browse_vs_search` + the titles.

**Guardrails:**
- Name by the shared CONTENT, never by a single generic word.
- **Do not touch any number.** Only add `label` and `intent`.
- If a cluster's titles are incoherent, say so in the label rather than inventing a theme.

**Output:** rewrite `subniche.json` with each `clusters[i].label` filled and `clusters[i].intent` added.
(Optional S4b: the same idea over `gaps.json.themes[]` — add a readable `label` to each auto-theme.)
