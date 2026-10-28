# `lumina_research/risk_core`

Independent **research-time** Risk Core. Agents may only *propose*. This module decides `Approved | Rejected | Scaled`.

## Relation to the live KEEP Risk Core

| Layer | Path | Role |
|-------|------|------|
| Live KEEP Risk Core | `lumina_core/risk/` (`HardRiskController`, Admission Chain, Final Arbitration) | Untouchable. Sits on the live order path before the broker. Charter: agents may never modify or bypass it. **This package does not import or patch it.** |
| Research Risk Core | `lumina_research/risk_core/` (this package) | Additional filter inside the propose-only research loop. Frozen config, sticky kill switch, no evolution/agent imports. Survivors still face the live Risk Core + `PromotionGate`. |

Defense in depth: a research `Approved` is **not** a live fill. Promotion remains a KEEP-fabric decision.

## Hard rules (config-driven, code-enforced)

- max position % of equity
- max daily loss % of equity
- max total drawdown % (kill switch, sticky)
- leverage cap
- correlation-cluster notional limit
- kill switch on heartbeat loss **or** a drawdown / daily-loss breach

Config is a frozen dataclass loaded from `limits.toml`. No setters. Subclassing `RiskCore`, `RiskConfig`, `Decision`, and `OrderProposal` is refused. Public module names are sealed against monkeypatch.

## Isolation

This package imports only the Python stdlib and itself. CI AST-tests that it never imports `lumina_core`, `lumina_research.validation`, evolution, or agents.
