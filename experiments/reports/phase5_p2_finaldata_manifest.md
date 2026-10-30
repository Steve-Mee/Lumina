# Lumina final research cycle — pre-holdout data (finaldata)
Created: 2026-10-30 (Europe/Brussels). Holdout start: **2026-01-28T23:00:00Z**. All files end strictly before it.

| File | sha256 | Range | Rows |
|---|---|---|---|
| NQ_pre_holdout.csv.gz | decompressed: `d60dd0c203ef31382def4278f4524a671bc7b4a050ab1334948ba693e269eed8` / gz: `4f5f7d4ef94e5dbecf3afea5021ad6d693eb7050ade439dd74d076d114e5c855` | 2023-10-01T22:01:00Z → 2026-01-28T22:00:00Z | 821,334 bars (+header) |
| VIX_daily_pre_holdout.csv | `481dc031c6d2b51b9150718c21c01b7f3706c99678ebf12b0edba19d0c8d2d1d` | 1990-01-02 → 2026-01-28 | 9,110 |
| macro_events_pre_holdout.csv | `104018d21552544a6c60ef52de0bbb6c82447c6afcb685e3059a14edd1c19aa7` | 2023-10-06 → 2026-01-28 14:00 ET | 73 (27 CPI, 27 NFP, 19 FOMC) |

## NQ 1-minute
- Source (box): /workspace/lumina-data/NQ/1m/NQ_continuous_unadj_1m_2023-10-01_2026-10-29.csv (sha256 9d41f2202cb2a638653f2502752f21daa17beb5d1b4848a227c79a8036024dc4; identical to /workspace/lumina-data/NQ_continuous.csv.gz). Built 2026-10-29 from NT8 per-contract exports (NQ_MANIFEST.json, unadjusted, NT8 roll dates). PC_Home not used.
- Filter: timestamp < 2026-01-28T23:00:00Z. Same columns as ES_pre_holdout: timestamp,open,high,low,close,volume (UTC, bar-end ISO Z). Sorted, no duplicate timestamps.
- Byte-identical (same sha d60dd0c2…) to the existing /workspace/p2report/nullval/NQ_pre_holdout.csv.gz. ES reference: nullval/ES_pre_holdout.csv.gz, decompressed sha 6100588d2f3e519bd815b8f952dc15f01d434cc2a2b70e6453d0c3a7477bbca6, same first/last bar.

## VIX daily
- Source: https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv (downloaded 2026-10-30; raw file sha256 50c16d5033bbe65dfd8724bec51d535cdb3114d6492615ccf5e42a773df4e3e2).
- Date reformatted to ISO (YYYY-MM-DD); columns date,open,high,low,close. Kept only days whose 16:15 ET close < holdout (last = 2026-01-28, close 21:15Z).

## Macro calendar (columns date,time_et,event,source_url)
- CPI and NFP (Employment Situation): BLS archived releases, from https://www.bls.gov/bls/news-release/cpi.htm and .../empsit.htm. Each release page was fetched; all 54 state "8:30 a.m. (ET)". Shutdown 2025: no Oct-2025 CPI; Sep-2025 CPI on 2025-10-24; NFP for Sep on 2025-11-20, Oct+Nov combined on 2025-12-16; Dec-2025 CPI on 2025-12-18.
- FOMC: statement dates from https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm. Each statement page was fetched; all say "For release at 2:00 p.m." ET. Excluded: 2025-08-22 notation vote (Statement on Longer-Run Goals, not a policy statement).
- Range filter: 2023-10-01 ≤ date and ET timestamp < holdout (last = FOMC 2026-01-28 14:00 ET = 19:00Z).

## S&P 500 cash index 1-minute
No free official source. Cboe (Global Indices Feed / DataShop) and S&P DJI sell intraday SPX history; free official data is daily only. Per the researchers' decision, **LH-04 is dropped**.

## Confirmation
No row in any file reaches or passes 2026-01-28T23:00:00Z (checked max timestamps: NQ 2026-01-28T22:00:00Z, VIX 2026-01-28, macro 2026-01-28 14:00 ET). No holdout/EXAM/SEAL/CUT/quarantine/zz- files were read. No PC_Home access. All files chmod 444.
