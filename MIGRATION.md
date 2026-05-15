# Migratiegids: Van oude naar nieuwe lumina_launcher.py

Deze gids beschrijft hoe je migreert van de oude monolithische `lumina_launcher.py` naar de nieuwe modulaire structuur.

## Waarom deze refactor?

- De originele file was **3475+ regels** → extreem moeilijk te onderhouden.
- Alle logica zat in één bestand (God Object anti-pattern).
- Moeilijk te testen, debuggen en uit te breiden.

De nieuwe structuur is:
- **Modulair** (Core / Services / UI)
- **Testbaar**
- **Onderhoudbaar**
- **Schaalbaar**

## Nieuwe structuur

```
Lumina_new/
├── lumina_launcher.py          # Minimale entrypoint (~140 regels)
├── core/
│   ├── process_manager.py
│   ├── config_manager.py
│   ├── admin_auth.py
│   └── first_boot.py
├── services/
│   ├── hardware_service.py
│   └── model_service.py
├── ui/
│   ├── components/
│   │   ├── status_badge.py
│   │   ├── kv_section.py
│   │   └── presence_strip.py
│   └── tabs/
│       ├── live_activity.py
│       ├── first_boot.py
│       ├── live_trader.py
│       ├── hardware_tab.py
│       ├── model_management_tab.py
│       ├── trader_league.py
│       └── sim_evolution.py
├── state/                      # Runtime state (lumina_sim_state.json, etc.)
├── logs/                       # Logs
└── README_REFACTOR.md
```

## Belangrijkste veranderingen

| Oude code                          | Nieuwe locatie                          | Opmerking |
|------------------------------------|-----------------------------------------|---------|
| Process start/stop/kill            | `core/process_manager.py`               | Volledig geïsoleerd |
| Config & .env handling             | `core/config_manager.py`                | Centraal beheerd |
| Admin password hashing             | `core/admin_auth.py`                    | Veilig en herbruikbaar |
| First Boot logica                  | `core/first_boot.py` + `ui/tabs/first_boot.py` | Duidelijke scheiding |
| Hardware inspectie                 | `services/hardware_service.py`          | Wrapper rond HardwareInspector |
| Model catalog & upgrades           | `services/model_service.py`             | Centrale model logica |
| Live Activity / Heartbeat          | `ui/tabs/live_activity.py`              | Hersteld en verbeterd |
| UI Tabs                            | `ui/tabs/`                              | Elk tab in eigen bestand |

## Hoe migreer je?

### 1. Backup
Maak altijd eerst een backup van je huidige `lumina_launcher.py`.

### 2. Vervang de launcher
- Gebruik de nieuwe `lumina_launcher.py` uit deze map.
- Zorg dat de mappen `core/`, `services/` en `ui/` aanwezig zijn.

### 3. Staat & Logs
Zorg dat de volgende mappen bestaan:
- `state/`
- `logs/`

De launcher laadt automatisch `state/lumina_sim_state.json`.

### 4. Testen
```bash
cd Lumina_new
streamlit run lumina_launcher.py
```

Controleer of:
- Live Activity werkt
- First Boot instellingen opslaan
- Hardware scan werkt
- Start/Stop bot functioneert

### 5. Oude code verwijderen (optioneel)
Na succesvolle migratie kun je de oude `lumina_launcher.py` verwijderen of hernoemen naar `lumina_launcher_old.py`.

## Bekende verschillen

- Sommige zeer specifieke UI fragments (zoals complexe auto-refresh logic) zijn vereenvoudigd of gemoderniseerd.
- Backend calls zijn nog deels placeholder (worden in latere fase verder geïntegreerd).
- De architectuur is nu veel cleaner → toekomstige features zijn makkelijker toe te voegen.

## Ondersteuning

Bij vragen of problemen:
- Open een issue in de repo
- Of neem contact op met de maintainer

---

**Deze refactor is gemaakt met de `grok-code` skill.**
