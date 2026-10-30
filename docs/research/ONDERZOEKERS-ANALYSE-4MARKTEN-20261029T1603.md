# Onderzoeksteam — analyse 4-markten rapport + antwoorden §8 (doorgegeven door Steve 2026-10-29 16:03 Brussel; NIET Steve's eigen mening)

Kernconclusies:
- Cost-fix 1.1.0→1.2.0 correct. Kills MES/MNQ/ES hard: negatieve bruto-PnL vóór kosten, hitrates onder kostenvrije BE 0,333, 0/8 positieve OOS. Geen kostenartefact.
- NQ-null-fail = methodologisch; eerst oplossen vóór NQ-test.
- Vaste 16/8 (stop-on-touch, target op trade-through) op 1m is dominante factor; 16/8 grotendeels afgehandeld als lab-experiment; verder testen = low-value.
- Zonder diagnostiek (exitredenen, MFE/MAE, hitrate zonder bracket) geen onderscheid signaal waardeloos vs exit te asymmetrisch.

1. NQ-null: herontwerp, mag daarna opnieuw draaien. Vooraf registreren: (b)+(c) drift-aware null (detrend sessie-rendementen of balanceer tekens per venster) + minimaal 20–50 seeds, rapporteer verdeling (aandeel seeds dat A2-drempel haalt). Optioneel (a) block-shuffle week/maand als extra check. Zelfde null op ES/MES/MNQ. Tot null betrouwbaar: NQ gesloten. Geen respec op configs zelf.
2. Geometrie: stop met vaste 16/8. Pre-registreren: mean-reversion/fade target 0,8–1,2×ATR (of 1R), stop 1,0–1,5×ATR, of symmetrisch in punten; time-stop of RTH-flatten verplicht. Breakout/momentum target 1,5–2,0×ATR, stop 0,8–1,0×ATR. Gap/opening: sessie- of dag-horizon, geen 1m-bracket. Geometrie gelijk in punten of ATR-multiples tussen micro en mini (niet ticks). Verplicht: positive control in die nieuwe geometrie met geplante edge van bekende grootte op relevante horizon; geen nieuwe templates zonder.
3. ES TRAIN-gat: optie (c) met voorkeur (b). Sessies 2025-07-13/14/15 en dunne 2025-11-28 uitsluiten voor alle vier markten (of alleen ES als instrument-specifiek). Idealiter herexport NT8 + re-seal. Tot dan uitsluiten + documenteren. Holdout-gaten apr/mei 2026: uitsluiten of herexporteren vóór ooit een survivor wordt getoetst; geen evaluatie over incomplete holdout; geen MES-bars om te vullen.
4. Hitrate: beide, geometrie dominant. Diagnostiek: verdeling exitredenen (stop/target/time-stop/gap), MFE/MAE per trade, hitrate zonder bracket (vaste N bars), hitrate onder symmetrisch 1R/1R. Volgende cyclus: stop pure 1m OHLC mean-reversion/volume-imbalance hoge turnover; prioriteit langere horizon (uren–dagen), RTH-only, macro-event, cross ES–NQ, lagere turnover. Max 8–12 configs, klein pre-registered grid.
5. Pad MES/MNQ: (a)+(c). Ontwerpen/valideren op ES/NQ; daarna survivors als aparte pre-geregistreerde stap op MES/MNQ met eigen trial-telling. Kostendrempel: bv. bruto > 6–8 ticks per RT op ES vóór micro. Normaliseer gross/net per instrument (ticks/punten).
6. CostModel 1.2.0 accepteren als basis. SIM-fill-kalibratie later, nu niet blokkerend. Documenteer residual bias (ETH-slippage), herzie banden bij SIM-data.
7. N telt over alle markten en controles (D13 telt mee); rapporteer N per markt en totaal. Holdout-pin 2026-01-28T23:00Z mag max 1–2 evaluaties; daarna spent; nieuwe cycli nieuwe pin of locked extension.

Prioritaire acties:
1. Pre-register + implementeer betere NQ-null (drift-aware + multi-seed); zelfde null op andere markten.
2. Pre-register per-familie geometrie in ATR/punten + positive control in die geometrie. Stop 16/8.
3. ES-gaten expliciet uitsluiten of re-exporten; documenteer.
4. Diagnostiek: exitredenen, MFE/MAE, hitrate zonder bracket, hitrate symmetrisch.
5. Her-run alleen ES (+ MES als controle) met nieuwe geometrie. NQ pas na null-fix.
6. Geen SIM-orders en geen nieuwe 1m high-turnover templates tot een config bruto-positief is én positive control overleeft.
Archiveer 16/8 als lab-resultaat (niet als weerlegde economische hypothesen).
