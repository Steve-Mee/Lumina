# Phase 5 P2 data spec (NT8 1m MES/MNQ)

- generated_at: `2026-10-29T11:23:56.741996+00:00`
- status: P2 cycle loads NT8 1m MES/MNQ via $LUMINA_RESEARCH_DATA_DIR; raw CSVs are not committed

- **universe_first**: MES and MNQ 1-minute bars; ES/NQ later after the micro cycle
- **period**: recent 2-3 years through the export date
- **holdout**: last 9 calendar months (allowed 6-12); P2 NT8 tapes pin 2026-01-28T23:00:00Z (Globex session boundary; legacy 2026-01-29T00:00:00Z recorded) before selection, ranking, tuning, or gate calibration; evaluation-only accessor for the locked window; holdout stays sealed and unopened
- **locations**: $LUMINA_RESEARCH_DATA_DIR/{MES,MNQ}/1m/*.csv ; {--data-dir}/{MES,MNQ}/1m/*.csv ; {repo}/data/research/{MES,MNQ}/1m/*.csv
- **filename_examples**: data/research/MES/1m/nt8_mes_1m.csv ; data/research/MNQ/1m/nt8_mnq_1m.csv
- **format**: UTF-8 CSV with header timestamp,open,high,low,close,volume
- **timestamp**: UTC ISO-8601 with offset, e.g. 2024-03-15T14:31:00+00:00 (convert NT8 CT → UTC)
- **ohlc**: float CME MES/MNQ prices; high >= max(open,close,low); low <= min(open,close,high)
- **volume**: float >= 0 (NT8 1m volume)
- **nt8_instrument**: MES continuous or front month (e.g. MES 09-26); MNQ likewise
- **nt8_bar**: 1 Minute, CME Globex session (document RTH-only if that is what is exported)
- **optional_vix**: data/research/VIX/1d/vix.csv columns timestamp,close for regime labels only
- **code**: lumina_research.cycles.data.discover_data + lumina_research.cycles.holdout.access_bars

## CSV example

```
timestamp,open,high,low,close,volume
2024-03-15T14:31:00+00:00,5212.25,5213.00,5211.75,5212.50,1842
```

## Holdout lock

Call `access_bars(tape, purpose='gate'|'selection'|'tuning'|'calibration')` for train bars.
Call `access_bars(tape, purpose='evaluation')` for the locked holdout.
Any other purpose, a missing split, or a train bar with ts_ns inside the holdout raises `HoldoutLocked`.
