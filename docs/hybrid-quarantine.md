# Hybrid Quarantine Inventory

Known stub / heuristic paths that remain **default-on** for backwards compatibility.
Enable strict flags to fail-closed. Every active path logs `hybrid_quarantine.<id>`.

| ID | Config (either path) | Default | Strict behavior |
|----|----------------------|---------|-----------------|
| `multi_day_sim` | `hybrid_quarantine.require_true_backtest` / `evolution.multi_day_sim.require_true_backtest` | `false` | RNG / tick-proxy fitness returns `-inf` unless true backtest succeeds |
| `shadow_trace_verdict` | `hybrid_quarantine.require_trace_verdict` / `risk.shadow.require_trace_verdict` | `false` | Shadow `evaluate_risk_decision` returns `fail` instead of silent `pass` |
| `arch_patch_apply` | `hybrid_quarantine.require_real_patch_apply` / `architecture_meta.require_real_patch_apply` | `false` | Architecture meta sandbox refuses optimistic pretend deltas |
| `kill_switch_auth` | `hybrid_quarantine.require_reset_authorization` / `risk.kill_switch.require_reset_authorization` | `false` | `reset_kill_switch` rejects empty `authorization_code` |
| `plateau_terminal_passthrough` | `hybrid_quarantine.handler_terminal_passthrough` / `birth.plateau.handler_terminal_passthrough` | `true` | When `false`, plateau handler does not claim `handled: True` |
| `vllm_lifecycle` | `hybrid_quarantine.manage_lifecycle` / `vllm.manage_lifecycle` | `false` | `start_vllm_server` returns false when external host unhealthy |

Source: `lumina_core/hybrid_quarantine/__init__.py` (`inventory()`).

## SIM/PAPER strict profile (opt-in)

Committed defaults stay fail-soft. To enable all six gates in one shot **only** when `mode` is `sim` or `paper`:

- env: `LUMINA_HYBRID_STRICT=1` (also `true` / `yes` / `on`), or
- config: `hybrid_quarantine.apply_strict_in_sim: true`

REAL (and other modes) **ignore** this opt-in and log a warning. Per-gate keys above still work independently when the bulk profile is off.

Strict profile forces: true_backtest, trace_verdict, real_patch_apply, reset_auth, terminal_passthrough=false, vllm manage_lifecycle=true.
