# LUMINA — Cursor Prompt: First Boot Training + Configurable Trade Volume

**Doel:** Voeg een slimme "First Boot Training" functionaliteit toe zodat Lumina bij de allereerste start direct een leer-cyclus uitvoert voordat ze gaat traden. Maak het aantal trades configureerbaar en voeg een goede tooltip toe.

**Belangrijke instructies voor Cursor:**
- Wijzig **geen bestaande trading of evolutie logica**.
- Voeg **alleen nieuwe functionaliteit** toe voor first-boot detectie en training.
- Maak alles **fail-safe** en backwards compatible.
- Gebruik de bestaande `InfiniteSimulator` class.

**Huidige implementatie (repo-sync):** `training_trades` is **door de gebruiker** te zetten (Launcher-tab + YAML). Canonical bounds en fallback staan in `lumina_core/first_boot_ui.py`: **clamp 500 … 2.000.000**, geen verplichte grove snap of 100k-vloer; ontbrekende waarde ⇒ default **5.000** (expliciete config wint altijd).

---

## Cursor Prompt (kopieer dit volledig)

```
You are implementing a high-quality "First Boot Training" feature for Lumina.

Your task is to add logic so that on the very first startup, Lumina automatically runs a training cycle (using the existing InfiniteSimulator) before entering normal trading mode. The user must be able to configure how many trades are executed during this first training run.

### Critical Context (from code review):

Current situation in `lumina_core/infinite_simulator.py`:
- It loads 45 days of real historical ticks (limit=150000).
- Then generates synthetic ticks if needed.
- Default target = 1_000_000 trades per night.
- It can run 1M trades by cycling through the loaded ticks + synthetic data.

Critical observation:
- 150k real ticks is relatively limited for 1M trades.
- The system compensates with synthetic data and cycling.
- For a high-quality first bootstrap, more real data would be better, but we should make the trade count configurable so the user can choose between speed and quality.

### Requirements (implement exactly):

1. **Config parameter**
   Add to `config.yaml` (under a new section or under `training`):
   ```yaml
   first_boot:
     training_trades: 500000          # Example deployment volume; adjustable by user via launcher/YAML (see bounds)
     max_real_days: 90                # How many days of history to load on first boot
   ```
   Add a sensible default **in code only when missing** (`FIRST_BOOT_DEFAULT_TRADES` = 5000 — not a clamp that wipes user input).

2. **First boot detection**
   Detect the very first start (e.g. absence of `lumina_agents/ppo/lumina_ppo_policy.zip` or a dedicated `state/first_boot_completed.flag`).
   This detection must happen early in `lumina_launcher.py` or `runtime_entrypoint.py`.

3. **Force training on first boot**
   - If first boot is detected:
     - Show clear user feedback (in launcher + console):
       "Eerste keer starten gedetecteerd. Lumina voert nu haar initiële leer-cyclus uit..."
     - Run `InfiniteSimulator` with the **user-normalized** `training_trades` (from launcher + YAML; use `normalize_first_boot_training_trades` — clamp only `[500, 2_000_000]`).
     - Use the new `max_real_days` parameter to load more historical data on first boot (e.g. 90 days instead of 45).
     - After training completes successfully, create the `first_boot_completed.flag`.
   - Then continue to normal runtime mode.

4. **Configurable trade volume + Tooltip (in launcher)**
   In `lumina_launcher.py` (Streamlit UI), add a new setting under the evolution/startup section:
   - Slider or number input: "Aantal trades bij eerste training"
   - Range: **500 – 2_000_000**, UI step **500** (align with launcher + `lumina_core/first_boot_ui`)
   - **Do not snap** stored values onto 100k multiples or raise every small input to a high minimum — preserve user intent within `[min,max]`.

   **Tooltip text (must be added next to the setting):**
   ```
   Bij de allereerste start heeft Lumina nog geen ervaring. 
   Hoe meer trades je kiest, hoe sterker haar initiële PPO-policy en kennisbasis wordt.
   
   - 200.000 trades  → Snelle start (± 5-10 min), redelijke basis
   - 500.000 trades  → Goede balans (aanbevolen)
   - 1.000.000+ trades → Zeer sterke start, maar duurt langer (± 20-40 min)
   
   Na deze eerste training draait Lumina veel effectiever en met hogere confidence.
   ```

5. **Update InfiniteSimulator (optional but recommended)**
   Add support for a `target_trades` parameter in `run_nightly()` or create a new method `run_bootstrap_training(target_trades: int, max_real_days: int = 90)` so the first-boot run can be customized without affecting the normal nightly run.

6. **Logging**
   Add clear INFO and WARNING logs during first-boot training (using the new logging system if available, or standard logging).

7. **User experience**
   - The launcher should clearly show progress during the first training run.
   - After training, show a summary: "Eerste training voltooid. X trades uitgevoerd. Policy opgeslagen."
   - Make sure the user cannot accidentally skip this (but allow advanced users to disable via config: `first_boot.force_training: false`).

### Output instructions:
- First, show the changes needed in `config.yaml`.
- Then provide the complete modified code for:
  - `lumina_launcher.py` (UI + tooltip + first boot detection)
  - `runtime_entrypoint.py` (trigger logic)
  - `lumina_core/infinite_simulator.py` (new method or parameter support)
- Add clear comments where new code was added.
- Keep all existing functionality 100% intact.
```

---

## Extra aanbevelingen (niet in de prompt, maar voor jou)

**Kritische review van de huidige training (samengevat):**

- **Data volume:** 45 dagen (~150k ticks) is aan de lage kant voor 1M trades. Het systeem compenseert met synthetische data en cycling, maar meer echte historische data (90–180 dagen) zou de kwaliteit significant verbeteren.
- **Voorstel (productie):** vaak wordt in `config.yaml` een hoger volume gekozen (bijv. **500k** trades met **90** dagen) voor een krachtige eerste training; dit is géén verplichte default — gebruikers/Launcher zetten **`training_trades`** zelf, binnen **500 … 2.000.000** (zie `lumina_core/first_boot_ui.py`).
- **Gebruikerscontrole:** Tooltip + Launcher laten voorkeuren zien zonder ze te overschrijven door een extra vaste vloer in code.

Dit maakt de eerste ervaring veel professioneler en voorkomt de "wit blad" frustratie die je terecht signaleerde.

---

**Klaar voor gebruik.**  
Kopieer de prompt hierboven en plak hem in Cursor. Wil je dat ik ook een tweede, kortere versie maak voor alleen de config + tooltip (als je de training logica later wilt toevoegen)? Of wil je direct starten met implementatie?