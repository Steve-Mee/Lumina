# LUMINA — Cursor Prompt: First Boot Training (Real Data Only + Dynamic Tooltip)

**Doel:** Implementeer First Boot Training met **voorkeur voor echte historische data** (zo min mogelijk synthetisch). De tooltip moet **dynamisch** tonen hoeveel dagen historische data nodig zijn bij de gekozen trade count.

**Huidige implementatie (repo-sync):** Het aantal `first_boot.training_trades` bepaalt **de gebruiker** via Launcher (`lumina_launcher/ui/tabs/first_boot`) en/of `config.yaml`. Normalisatie staat centraal in `lumina_core/first_boot_ui.py`: alleen clamp naar **`FIRST_BOOT_TRAINING_TRADES_MIN` (500)** … **`MAX` (2.000.000)**; het opgeslagen getal wordt **niet** overschreven door een grove vloer (zoals ±100k) of snap-stappen. Als de sleutel ontbreekt, geldt **`FIRST_BOOT_DEFAULT_TRADES` (5.000)** als fallback (expliciete YAML heeft altijd voorrang).

---

## Cursor Prompt (kopieer dit volledig)

```
You are implementing a "First Boot Training" feature for Lumina with strong preference for REAL historical data only.

Your ONLY task is to add this feature without changing any existing trading, evolution, or simulation logic.

### Core Requirements:

1. **New config parameters** (add to config.yaml)
   ```yaml
   first_boot:
     training_trades: 300000          # Example volume; user may set launcher or YAML freely (see bounds below)
     prefer_real_data_only: true      # If true, avoid or minimize synthetic data
     max_real_days: 365               # Maximum days of history to load
   ```

2. **First boot detection & forced training**
   - Detect first start (no PPO policy file or missing first_boot_completed.flag).
   - If first boot:
     - Show clear message: "Eerste keer starten gedetecteerd. Lumina laadt echte historische data en voert initiële training uit..."
     - Run InfiniteSimulator with the **user-configured** `training_trades` (launcher + YAML), after normalizing/clamping only within safe bounds (`lumina_core/first_boot_ui.normalize_first_boot_training_trades`).
     - Respect `prefer_real_data_only`: load as much real data as possible (up to `max_real_days`).
     - Only generate synthetic data if absolutely necessary (and log a warning).
     - After completion, create the flag and continue to normal mode.

3. **Dynamic Slider + Tooltip in lumina_launcher.py**
   Add a slider in the first-boot / evolution section:
   - Label: "Aantal trades bij eerste training"
   - Range must match normalization: **500 – 2.000.000** (UI step suggestion: **500**)
   - **Do not coerce** saved values onto a large minimum or 100k steps; stored value equals user intent within `[min,max]`.
   - Default when reading config: explicit YAML value first; code fallback **5.000** only if unset.

   **The tooltip must be dynamic** and update live when the user moves the slider.

   Tooltip logic (must be implemented in the UI):
   - Calculate approximate real historical days needed:
     - Rough formula: trades_needed / ~2500 (trades per day of real data is a reasonable estimate based on current simulation behavior).
     - Examples:
       - 100.000 trades → ~40-50 dagen historische data
       - 300.000 trades → ~120 dagen historische data
       - 500.000 trades → ~200 dagen historische data
       - 1.000.000 trades → ~400 dagen historische data (waarschuwing: mogelijk lichte synthetische aanvulling nodig)
       - 2.000.000 trades → ~800+ dagen (sterke waarschuwing: synthetische data zal gebruikt worden tenzij max_real_days extreem hoog staat)

   **Tooltip text template** (must be shown next to the slider):
   ```
   Bij deze instelling heeft Lumina ongeveer {X} dagen echte historische data nodig.

   - Hoe lager het aantal, hoe sneller de eerste training klaar is.
   - Hoe hoger het aantal, hoe sterker de initiële policy, maar hoe langer het duurt en hoe meer historische data er geladen moet worden.

   Bij voorkeur gebruikt Lumina enkel echte data. 
   Als je een zeer hoog aantal kiest, kan er toch wat synthetische data nodig zijn (tenzij je max_real_days extreem hoog zet).
   ```

   The tooltip must clearly communicate the trade-off between training quality, duration, and data requirements.

4. **Smart handling in InfiniteSimulator**
   - Add support for a parameter `target_trades` and `prefer_real_data_only`.
   - When `prefer_real_data_only=True`:
     - Load up to `max_real_days` of real data.
     - If the target cannot be reached with real data only, either:
       a) Cap the actual trades to what is realistically possible with real data, or
       b) Clearly log a warning and proceed with minimal synthetic data.
   - Make this behavior transparent in the logs.

5. **User feedback during first boot**
   - Show progress: "Laden van {X} dagen echte historische data..."
   - After training: "Eerste training voltooid met {Y} trades op basis van echte data. Policy opgeslagen."

6. **Logging**
   - Log clearly when real data is used vs when synthetic data is generated (with percentage).
   - Log the estimated real days needed vs actual loaded.

### Output instructions:
- First show the exact additions to `config.yaml`.
- Then provide the full modified code for:
  - `lumina_launcher.py` (slider + dynamic tooltip logic)
  - `runtime_entrypoint.py` (first boot detection + training trigger)
  - `lumina_core/infinite_simulator.py` (new parameters + real-data preference logic)
- Add clear comments at every place where new code was added.
- Keep 100% backwards compatibility with existing nightly runs.
```

---

## Waarom deze aanpak goed is

- De gebruiker krijgt **volledige controle** en ziet direct de consequenties (via de dynamische tooltip); opgeslagen volumes volgen de keuze (**500–2M**), niet een verborgen minimum in normalisatie.
- Lumina respecteert de voorkeur voor **echte data** zoveel mogelijk.
- Bij hoge trade counts wordt de gebruiker gewaarschuwd dat synthetische data waarschijnlijk toch nodig zal zijn.
- Het blijft flexibel: gevorderde gebruikers kunnen nog steeds kiezen voor maximale training met wat synthetische data.

Dit is een sterke, eerlijke en gebruiksvriendelijke oplossing.

---

**Klaar.**  
Je kunt deze prompt nu direct in Cursor plakken. Wil je dat ik daarna ook een prompt maak om de **nightly training** automatisch te schedulen (bijv. via cron of interne scheduler)? Of wil je eerst deze implementeren?