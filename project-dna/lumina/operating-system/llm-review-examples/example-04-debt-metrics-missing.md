# Few-shot Example 04 — Excellent at Spotting Missing Metrics

**File reviewed**: current-reality/evolutionary-debt.md (pre-improvement)

**Heuristic score**: 7.0

**LLM output**:

```json
{
  "refined_score": 6,
  "additional_findings": [
    "Claims are often aspirational without clear metrics or benchmarks.",
    "Argumentation sometimes lacks hard substantiation and relies on general statements.",
    "Descriptions are too vague (e.g. 'recently introduced' without specific dates).",
    "Implicit or complex boundaries may hinder future evolvability."
  ],
  "evolvability_impact": "The absence of dated, measurable targets makes it nearly impossible to track whether debt is actually being reduced over time.",
  "top_actionable_improvement": "For every debt item, add: (1) current measurable state, (2) hypothesis for resolution, (3) concrete success signal, (4) target review date.",
  "missing_precision_areas": [
    "No success criteria or KPIs per debt item",
    "No timeline or review cadence mentioned"
  ],
  "confidence": 0.8,
  "one_sentence_summary": "Good high-level overview of problems, but not yet engineered as a living, prioritizable improvement backlog."
}
```

**Human evaluation**:
- Actionability: 9.5/10 (very concrete template suggested)
- Depth: 8/10
- Quality: One of the best examples of turning criticism into a clear improvement template.