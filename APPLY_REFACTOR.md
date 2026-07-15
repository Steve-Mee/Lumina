> **HISTORICAL SNAPSHOT — not living SSOT.**
> Captured for audit. Current direction: `docs/roadmap.md`, Twin: ADR-0032. Prefer living docs under `docs/` and `project-dna/lumina/`.
# Hoe pas je de Grok-Code Refactor toe op je bestaande Lumina project?

Dit document bevat **stapsgewijze instructies** om de volledige refactor toe te passen op je huidige `Lumina` repository.

## Overzicht van de refactor

- Oude `lumina_launcher.py` (3475+ regels) → nieuwe modulaire structuur
- 6 Core modules + 2 Services + BackendClient
- 8 UI Tabs op hoog niveau
- Echte backend integratie (`/leaderboard` + `/global_wisdom`)
- Unit tests toegevoegd
- Hoge codekwaliteit en documentatie

---

## Stap 1: Maak een backup (BELANGRIJK!)

```bash
cd /pad/naar/je/Lumina

# Maak een backup van de oude launcher
cp lumina_launcher.py lumina_launcher_old_backup.py

# Of maak een volledige backup van de huidige staat
git checkout -b backup-before-refactor
git add .
git commit -m "Backup before applying grok-code refactor"
```

---

## Stap 2: Maak de nieuwe mappenstructuur aan

Voer de volgende commando's uit in de root van je Lumina project:

```bash
mkdir -p core
mkdir -p services
mkdir -p ui/components
mkdir -p ui/tabs
mkdir -p tests
```

---

## Stap 3: Plaats de nieuwe bestanden

Kopieer de volgende bestanden uit de `Lumina_new` map naar je bestaande project:

### Core modules (plaats in `core/`)

| Bestand                        | Doel                                      |
|--------------------------------|-------------------------------------------|
| `core/process_manager.py`      | Start/stop/kill + PID handling            |
| `core/config_manager.py`       | .env + config.yaml handling               |
| `core/admin_auth.py`           | Password hashing & verificatie            |
| `core/first_boot.py`           | First-boot training & progress            |
| `core/__init__.py`             | Package initialisatie                     |

### Services (plaats in `services/`)

| Bestand                        | Doel                                      |
|--------------------------------|-------------------------------------------|
| `services/hardware_service.py` | Hardware inspectie & aanbevelingen        |
| `services/model_service.py`    | Model catalog & upgrades                  |
| `services/backend_client.py`   | Communicatie met lumina_os backend        |
| `services/__init__.py`         | Package initialisatie                     |

### UI Components (plaats in `ui/components/`)

| Bestand                        | Doel                                      |
|--------------------------------|-------------------------------------------|
| `ui/components/status_badge.py`| Herbruikbare status badges                |
| `ui/components/kv_section.py`  | Key-Value renderer met tooltips           |
| `ui/components/presence_strip.py` | Live heartbeat / presence strip        |

### UI Tabs (plaats in `ui/tabs/`)

| Bestand                              | Doel                                      |
|--------------------------------------|-------------------------------------------|
| `ui/tabs/live_activity.py`           | Live Activity & Heartbeat                 |
| `ui/tabs/first_boot.py`              | First Boot wizard                         |
| `ui/tabs/live_trader.py`             | Live Dream + Runtime State                |
| `ui/tabs/hardware_tab.py`            | Hardware & Model Alignment                |
| `ui/tabs/model_management_tab.py`    | Model Management                          |
| `ui/tabs/trader_league.py`           | Trader League Leaderboard                 |
| `ui/tabs/sim_evolution.py`           | SIM Evolution Dashboard                   |
| `ui/tabs/community_bibles.py`        | Community Bibles & Global Wisdom          |

### Tests (plaats in `tests/`)

| Bestand                        | Doel                                      |
|--------------------------------|-------------------------------------------|
| `tests/test_process_manager.py` | Tests voor ProcessManager                |
| `tests/test_first_boot.py`      | Tests voor FirstBootManager              |

### Overige bestanden (plaats in root)

| Bestand                        | Doel                                      |
|--------------------------------|-------------------------------------------|
| `lumina_launcher.py`           | **Vervang** je oude launcher hiermee      |
| `pyproject.toml`               | Pytest configuratie                       |
| `MIGRATION.md`                 | Migratiegids (optioneel)                  |
| `README_REFACTOR.md`           | Documentatie van de refactor              |

---

## Stap 4: Wat moet je nog aanpassen?

### 1. Environment variabele (aanbevolen)

Maak een `.env` bestand (of voeg toe aan je bestaande `.env`):

```env
LUMINA_BACKEND_URL=http://localhost:8000
LUMINA_PYTHON=python
```

### 2. Start de backend (indien nodig)

De backend draait normaal op poort 8000. Start hem met:

```bash
cd lumina_os
python -m backend.app
# of
uvicorn backend.app:app --host 0.0.0.0 --port 8000
```

### 3. Test de nieuwe launcher

```bash
streamlit run lumina_launcher.py
```

Controleer of de volgende tabs werken:
- Live Activity
- First Boot
- Trader League (vereist backend)
- Community Bibles (vereist backend)

---

## Stap 5: Oude code opruimen (optioneel)

Na succesvolle test kun je de oude bestanden verwijderen of hernoemen:

```bash
mv lumina_launcher_old_backup.py archive/
# of
git rm lumina_launcher_old.py
```

---

## Belangrijke aandachtspunten

- De nieuwe `lumina_launcher.py` is **veel kleiner** (~140 regels) omdat alle logica is uitbesteed aan modules.
- De `BackendClient` communiceert met je bestaande `lumina_os` backend.
- Als je backend niet draait, zullen Trader League en Community Bibles een duidelijke foutmelding geven.
- De Admin methodes (`delete_all_trades`, `delete_demo_data`) zijn voorbereid maar vereisen een API key (nog niet volledig geïmplementeerd in de UI).

---

## Volgende stappen na migratie

1. Test alle tabs grondig
2. Maak eventueel een Pull Request van deze refactor
3. Bouw verder op de nieuwe modulaire structuur (bijv. meer tests, betere admin UI, etc.)

---

**Gemaakt met de grok-code skill – 12 mei 2026**

Als je ergens vastloopt, laat het weten!
