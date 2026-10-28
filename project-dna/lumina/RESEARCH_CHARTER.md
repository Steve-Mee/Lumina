# LUMINA Research Charter — Non-negotiable Agent Rules
Version: 1.0 (2026-10-28)
Binding for every agent (Cursor, Grok, multi-agent, birth, evolution, research).

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

If a proposed change violates any of the above → reject it and propose a compliant alternative.
