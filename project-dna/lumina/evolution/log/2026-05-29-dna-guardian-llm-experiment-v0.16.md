# 2026-05-29 — DNA Guardian v0.16-experimental — First Narrow Slice of LLM-Assisted Review (Increment 4)

**Increment of**: DNA Validation & Scoring Tool

## What was implemented
- Added minimal, stdlib-only Ollama client (`_call_ollama_chat` + `run_llm_review_on_file`).
- New CLI flag `--llm-review` (only meaningful together with `--create-entry`).
- When enabled: after normal heuristic scoring, the Guardian attempts a targeted LLM second-opinion **only on the single current weakest file**.
- Strict requirements:
  - Heuristic scoring remains the source of truth for Health Score and recommendations.
  - Hard 8-second timeout + complete silent fallback on any error (Ollama unavailable, bad JSON, timeout, etc.).
  - LLM output (when successful) is always presented under clearly labeled "LLM Review (EXPERIMENTAL)" sections.
- Results are propagated to:
  - Evolution log entries
  - Human `--report` output
  - `dna_health_latest.json`
- Zero impact on normal Guardian runs.

## Why this narrow scope
This is the smallest possible responsible first experiment for Increment 4, exactly as planned:
- Local model only (Ollama qwen3.5:9b preferred by the project).
- Attacks the real persistent pain point (evolutionary-debt.md).
- Full reversibility and zero risk to the existing reliable heuristic baseline.
- Forces us to confront prompt quality, model capability, and evaluation early, before any wider adoption.

## Current status of the experiment (as of this entry)
- The plumbing, fallback logic, and surface areas are implemented and tested.
- In the current development environment, Ollama was not available → clean fallback path was exercised and verified.
- Real LLM output has not yet been observed in this session (will be done on a machine with Ollama running).

**Honest assessment so far**: The engineering safety (fallback, labeling, narrow target) is good. The actual value of the LLM layer is still unproven and will be evaluated on the next runs that have a live model.

## Hypothesis (re-stated from plan)
A narrow, opt-in local LLM second opinion on the current weakest DNA file can surface falsifiability, reasoning quality, and evolvability issues that the keyword heuristic misses, leading to higher-quality self-improvement actions.

## Next immediate actions for this experiment
1. Run on a machine with Ollama + qwen3.5:9b (or equivalent meta model) using `--create-entry --llm-review`.
2. Capture real LLM output on `current-reality/evolutionary-debt.md`.
3. Honestly evaluate signal quality in a follow-up evolution entry.
4. Decide: improve prompt, switch model, widen scope slightly, or pause the direction.

## Risks observed during implementation
- Prompt length and model instruction-following will be critical.
- Even with low temperature, non-determinism remains.
- Local 9B-class models may struggle with nuanced meta-analysis.

These will be documented with real data in the next entry.

---
*This entry follows the Recursive Self-Improvement Protocol v2.0. First experimental slice of Increment 4.*