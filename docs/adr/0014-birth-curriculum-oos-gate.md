# ADR-0014: Birth Curriculum + OOS Gate

> **Supersession (2026-08-14):** Intra-Birth stage count and pass law are defined by [ADR-0046](./0046-birth-foundation-evolvable-plant.md) (five Foundation stages, process-R / occupancy / first-touch). This ADR remains historical for the purged-holdout + certificate OOS idea. Do not treat stage4_polish or WR-as-pass as current Birth law.

**Status**: Accepted

**Date**: 2026-06-11

## Context

Birth v1 optimized for configurable trade count (500–2M) as a proxy for quality. Cycling ticks and 98% near-complete grace allowed incomplete training to pass. More trades on repeated data does not equal more knowledge.

## Decision

Birth v2 uses a four-stage curriculum on purged train data:

1. **stage1_trend** — TREND regimes only
2. **stage2_range** — NEUTRAL/RANGING patience
3. **stage3_mixed** — full train split with constitution checks
4. **stage4_polish** — PPO buffer polish

Last 20% calendar days are hold-out (embargo aligned with ADR-0004). Certificate issuance requires OOS metrics on hold-out only. Trade count is a budget cap for progress display, not completion criteria. Near-complete grace is removed.

## Consequences

- Positief: Higher signal per compute minute; honest completion.
- Positief: Curriculum teaches patience before mixed regimes.
- Negatief: Operators must understand certificate metrics vs trade slider.
- Risico's: Strict thresholds may fail on thin history — thresholds configurable in `birth_v2.certificate_thresholds`.

## Alternatives Considered

- **Optie A:** Keep trade count gate with better sim — rejected; wrong metric.
- **Optie B:** Single flat training run — rejected; wastes compute on unstructured data.

## Related ADRs

- ADR-0004: Purged CV
- ADR-0012: Single simulator SSOT
- ADR-0013: Birth Certificate v2
