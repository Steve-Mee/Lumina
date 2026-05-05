# LUMINA — Cursor Prompt: First Boot Training + Configurable Trade Volume

**Doel:** Voeg een slimme "First Boot Training" functionaliteit toe zodat Lumina bij de allereerste start direct een leer-cyclus uitvoert voordat ze gaat traden. Maak het aantal trades configureerbaar en voeg een goede tooltip toe.

**Belangrijke instructies voor Cursor:**
- Wijzig **geen bestaande trading of evolutie logica**.
- Voeg **alleen nieuwe functionaliteit** toe voor first-boot detectie en training.
- Maak alles **fail-safe** en backwards compatible.
- Gebruik de bestaande `InfiniteSimulator` class.

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
     training_trades: 500000          # Default for first boot
     max_real_days: 90                # How many days of history to load on first boot
   ```
   Also add a sensible default in code if config is missing.

2. **First boot detection**
   Detect the very first start (e.g. absence of `lumina_agents/ppo/lumina_ppo_policy.zip` or a dedicated `state/first_boot_completed.flag`).
   This detection must happen early in `lumina_launcher.py` or `runtime_entrypoint.py`.

3. **Force training on first boot**
   - If first boot is detected:
     - Show clear user feedback (in launcher + console):
       "Eerste keer starten gedetecteerd. Lumina voert nu haar initiële leer-cyclus uit..."
     - Run `InfiniteSimulator` with the configured `training_trades` (from config).
     - Use the new `max_real_days` parameter to load more historical data on first boot (e.g. 90 days instead of 45).
     - After training completes successfully, create the `first_boot_completed.flag`.
   - Then continue to normal runtime mode.

4. **Configurable trade volume + Tooltip (in launcher)**
   In `lumina_launcher.py` (Streamlit UI), add a new setting under the evolution/startup section:
   - Slider or number input: "Aantal trades bij eerste training"
   - Range: 100.000 – 2.000.000 (in stappen van 100.000)
   - Default: 500.000

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
- **Voorstel:** In de first-boot optie standaard **500.000 trades** met **90 dagen** geschiedenis laden. Dit geeft een sterke maar niet té lange eerste training.
- **Gebruikerscontrole:** Door de slider + tooltip geef je de gebruiker volledige controle + educatie over de trade-off tussen snelheid en kwaliteit.

Dit maakt de eerste ervaring veel professioneler en voorkomt de "wit blad" frustratie die je terecht signaleerde.

---

**Klaar voor gebruik.**  
Kopieer de prompt hierboven en plak hem in Cursor. Wil je dat ik ook een tweede, kortere versie maak voor alleen de config + tooltip (als je de training logica later wilt toevoegen)? Of wil je direct starten met implementatie?