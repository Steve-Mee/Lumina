# LUMINA Research Charter — Non-negotiable Agent Rules
Version: 1.0 (2026-10-28)
Binding for every agent (Cursor, Grok, multi-agent, birth, evolution, research).

This file is the **root SSOT**. The DNA copy at `project-dna/lumina/RESEARCH_CHARTER.md` is a pointer.

## Absolute Priorities (in order)
1. Capital Preservation (independent Risk Core can always reject)
2. Truth-seeking / Intellectual Honesty (no optimistic backtests)
3. Adaptation rate > Edge decay rate
4. Maximal autonomy *within* the gates above

## Mandatory Validation Gate (before any promotion or live exposure)
No strategy, signal, parameter set or evolutionary mutant may be promoted without ALL of the following:

- Walk-forward analysis: minimum 5–8 non-overlapping OOS windows (rolling preferred).
- Combinatorial Purged Cross-Validation (CPCV) with purge + embargo. Report the *distribution* of OOS results, not one lucky path.
- Deflated Sharpe Ratio (DSR) after correcting for the number of trials performed.
- Probability of Backtest Overfitting (PBO) < 0.25 preferred, hard reject above 0.50.
- Realistic costs from day 1: commissions + half-spread + dynamic slippage + simple market impact.
- Regime robustness check (at least volatility and trend regimes).

Only the survivors of this gate enter the live portfolio. Everything else is research waste and must be killed.

The live enforcement point is `PromotionGate` (`lumina_core/evolution/promotion_gate.py`). Any remaining mutation, promotion or birth path that would skip this gate must hard-fail.

## Phase 1 freeze (mandatory)
Every task starts with the Validation Gate. Agents **may not write new signals**, strategy mutants, birth curricula, or fitness search until Phase 1 of `lumina_research/` (Validation Gate implementation) exists and is tested.

Phase 1 lives in `lumina_research/validation/` (`walk_forward`, `cpcv`, `dsr`, `cost_model`, `gate`) plus `lumina_research/fitness.py` and the additional research-time `lumina_research/risk_core/`. The live Risk Core in `lumina_core/risk/` remains untouchable.

- Do not build further on `archive/birth-v1/` or the old birth/evolution search logic.
- Propose-only research lives in `lumina_research/`. It may never modify or bypass the Risk Core.
- Archived Birth-v1 code is experimental: insufficient Validation Gate rigor.

Phase 3 (`lumina_research/evolution/`): birth may open new windows and tune parameters. Every mutation is a `TrialRegistry` trial and must pass the Phase 1 gate via the Phase 2 event flow. Regime detection may size or throttle, never hard-switch strategy. Risk Core and gate thresholds cannot be changed by evolution without an ADR plus a signed human review, and even then the evolutionary path does not apply the write.

Phase 4 (`lumina_research/monitoring/`): live paper/shadow performance is compared to the promotion-time OOS distribution. Significant decay de-weights, then suspends, then retires (exposure only falls). Capacity caps scale back over-concentration. A scheduled guardian scan checks this charter. Replenishment requests new hypotheses through the Phase 2 factory; new signals still require the Validation Gate, PromotionAgent, and Risk Core. Monitoring must not import into `risk_core` or mutate it.

Phase 5 (`lumina_research/proof/`, `cycles/`, `ports/`): independent empirical proof of the Phase 1 gate and Phase 4 floors; 12 economic templates on real ES/NQ/MES/MNQ data or a documented stop; first P2 cycle is 10–15 pre-registered variants of the 24-variant pre-filter, chosen before seeing bars, with the last 6–12 months of NT8 1m MES/MNQ locked (fail-closed). Primary high-vol FAR is a between-window regime switch; `high_vol_mixture` is stress-only. Guardian/weekly metrics including mutation kill ≥ 0.80 and capital-preservation violations = 0. Research stays a separate layer, integrated only via Event Bus ports (`SignalIntent` / `ResearchOrderIntent` / `ResearchFillEvent`). Shadow mode may log signals and CostModel hypothetical fills. No NT8/gRPC coupling, no SIM/live orders. LIVE_RELEASE requires a dedicated ADR and a logged human action; research agents cannot mutate that config. Fail-closed: stale/lost → no new orders; monitor alarm → de-weight/reduce; full close only on a hard Risk Core limit. Do not build on `archive/birth-v1/`.

## Independent Risk Core (untouchable)
- Position sizing, max drawdown limits, leverage caps, correlation exposure, kill switches and Dead Man’s Switch live outside the evolutionary path.
- Agents may only *propose*. The Risk Core decides and can always reject.
- Self-evolution, birth phase and any agent may never modify or bypass the Risk Core.

## Anti-Overfitting Discipline
- Prefer parameter plateaus over peaks.
- Limit free parameters relative to independent observations.
- Features need economic/physical rationale or proven cross-regime stability.
- Prefer ensembles of weakly correlated signals over single models.
- Fitness function for any RL/evolution = composite OOS metrics + risk (never pure in-sample PnL).

## Continuous Research Loop
Generate many hypotheses → filter ruthlessly with the Validation Gate → promote only survivors → monitor live vs expected → deweight or retire immediately on decay.
The research loop itself is the product. A static strategy is temporary by definition.

## Forbidden
- Promoting anything based on a single beautiful backtest.
- Optimizing for in-sample beauty.
- Letting evolution or agents touch the Risk Core.
- Ignoring costs, slippage or regime shifts.
- Claiming an edge without the distribution of OOS results.
- Writing new signals before Phase 1 is complete.
- Reusing archived Birth-v1 search as a live path.

If a proposed change violates any of the above → reject it and propose a compliant alternative.
