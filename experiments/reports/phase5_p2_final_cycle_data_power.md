# P2 final-cycle data availability + power (2026-10-30 09:13)

Binding: `docs/research/ONDERZOEKERS-PREREG-FINALE-CYCLUS-20261030T0913.md`
content sha256 `106af5b23d2eeb24454a2174e8c59ae24fb69e78c9729bb6e2accf3452aedade`.
Operational lock: `phase5_p2_search_space_preregister_2026-10-30.md`.

**No trials.** DSR/PBO N stays 0. Holdout pin `2026-01-28T23:00:00Z` unopened.
No SIM/promotion. Risk Core untouched.

## Data availability

| source | present | path / note |
|---|---|---|
| ES pre-holdout | yes | `/tmp/lumina-es/ES_pre_holdout.csv` sha256 `6100588d…` |
| NQ pre-holdout | **no** | searched `/tmp/lumina-nq`, `$LUMINA_RESEARCH_DATA_DIR/NQ/1m`, `data/research/NQ/1m` |
| VIX series | **no** | searched `$LUMINA_RESEARCH_DATA_DIR/VIX/1d`, `data/research/VIX/1d`, `/tmp/lumina-vix` |
| macro calendar (CPI/NFP/FOMC) | **no** | searched `macro/releases.csv` under data dir / repo / `/tmp/lumina-macro` |
| cash index | **no** | searched `SPX/1d/spx.csv` under data dir / repo / `/tmp/lumina-cash` |

## Locked single values (no grid)

- LH-01 NR7 target = **1.5×** NR7 range (not 2.0×)
- RV-02 sizing = **dollar-neutral** (1 ES vs notional-matched NQ, min 1 NQ)

## Trade counts (pre-holdout power, entries only)

| research | config_id | status | n_trades | missing |
|---|---|---|---|---|
| RV-01 | `p2s-rv-01` | blocked_missing_data | — | NQ, VIX |
| RV-02 | `p2s-rv-02` | blocked_missing_data | — | NQ |
| LH-01 | `p2s-lh-01` | ready | **102** | |
| LH-02 | `p2s-lh-02` | ready | **5** | |
| LH-03 | `p2s-lh-03` | blocked_missing_data | — | macro calendar |
| LH-04 | `p2s-lh-04` | blocked_missing_data | — | cash index |

Kill still: DSR ≥ 0.95 AND ≥7/8 OOS+ AND net > 0. Not evaluated; no trial.

JSON: `phase5_p2_final_cycle_data_power.json`.
