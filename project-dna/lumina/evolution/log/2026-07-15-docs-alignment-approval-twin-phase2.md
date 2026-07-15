# 2026-07-15 — Living docs alignment: Approval Twin + Phase 2 Autonomy

**Classification**: Small (documentation / DNA narrative; no capital-path code change)  
**Related ADRs**: 0030, 0031, 0032

## Hypothesis

When living roadmap, project-dna, and public README explicitly state that the **Approval Twin** is the human-replacement *judgment* layer (with hard gates intact), agents and operators stop reading April–June analyses or pre-Twin “mandatory human forever” wording as current law.

## What changed

- `docs/roadmap.md` → v5.2.x wave; §6 Twin; §7 Phase 2 Autonomy; §8 secure self-code vision
- `project-dna/lumina/current-status.md` + agent-context export refreshed
- north-star, architecture §3.4, constitution invariant #1 clarification
- `lumina_core/evolution/lumina_bible.py` module docs name Twin as differentiator
- Historical banners on `docs/history/*` and versioned production snapshots
- ADR index includes 0030–0032

## What did **not** change

- No Twin thresholds, PromotionGate, sandbox, or aperture enforcement logic
- Package semver in `pyproject.toml` (still independent of roadmap wave labels)
- Body text of historical analyses (banner only)

## Falsifiable check

1. An agent with only `docs/roadmap.md` + `project-dna/lumina/current-status.md` can name Twin as differentiator **and** state Twin cannot solo-promote REAL.
2. Opening any `docs/history/lumina_analyse_*.md` shows HISTORICAL SNAPSHOT within first 5 lines.
3. `rg "HISTORICAL SNAPSHOT" docs/history` returns matches for all analyse files.

## Rollback

Revert the markdown/docstring commits for this date; constitution #1 clarification is the only DNA law wording change (restore prior bullet if needed).
