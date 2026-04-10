# NinjaTraderAI_Bot

Duidelijke projectstructuur voor de actieve Lumina runtime, deployment en research-assets.

## Snelle Navigatie

- Runtime entrypoint: lumina_v45.1.1.py
- Supervisie en health: watchdog.py
- Nightly simulator: nightly_infinite_sim.py
- Runtime core package: lumina_core/
- Bible package in app: lumina_bible/
- Public package source: lumina-bible/
- Deployment scripts: deploy/
- Testsuite: tests/

## Mappenstructuur

- deploy/
  - Install/update/smoke scripts voor productie en preprod
- docs/
  - release-workflow.md
  - production-machine-setup.md
  - history/ (gearchiveerde analyseversies)
  - notes/ (historische stap-notities)
  - requests/ (AI/ops request payloads)
- journal/
  - runtime dashboards en PDF output
- lumina_core/
  - engine, workers, trainer, simulator en runtime services
- lumina_bible/
  - runtime bible-engine integratie gebruikt door de app
- lumina-bible/
  - standalone package voor distributie naar PyPI
- lumina_agents/
  - agent-specifieke code
- lumina_vector_db/
  - lokale vector database files
- scripts/
  - utilities en cron assets
  - validation/ (losse validatie scripts)
- tests/
  - actieve tests voor runtime/core
- old/
  - lokale archiefmap, niet meer op GitHub (genegeerd via .gitignore)

## Root-bestanden met runtime rol

- config.yaml: lokale default config
- docker-compose.yml: lokale compose stack
- docker-compose.prod.yml: productie compose stack
- Dockerfile: container build
- lumina_launcher.py: startscherm met guided setup, hardwarescan en modelbeheer
- pytest.ini: pytest instellingen
- .env: lokale secrets/config (niet publiceren)

## Runtime data (gestructureerd)

- state/lumina_daytrading_bible.json: basis bible state
- state/lumina_sim_state.json: lokale sim state snapshot
- state/lumina_thought_log.jsonl: thought log (runtime generated)
- state/live_stream.jsonl: live stream data (runtime generated)
- logs/lumina_full_log.csv: runtime log output

## Werkafspraken

- Nieuwe operationele notities: docs/notes/
- Nieuwe validatie scripts: scripts/validation/
- Nieuwe tests: tests/
- Vermijd nieuwe losse root-bestanden tenzij het expliciet een entrypoint of top-level config is.

## Nieuwe machine opstarten

- Eerste bootstrap: `python scripts/bootstrap_lumina.py`
- Dit script maakt een lokale `.venv`, installeert launcher/runtime dependencies en start daarna Streamlit.
- De launcher toont bij eerste run een setup-wizard met hardwarescan, aanbevolen Qwen3.5-model en guided installatie.
- De wizard bewaart setup-status in `state/lumina_setup_complete.json` en `state/lumina_setup_status.json`.
- Model-upgrades en hardware-aanbevelingen worden gestuurd door `lumina_model_catalog.json`.
- Unsloth fine-tuning is voorbereid in de app, maar vereist nog steeds Linux of WSL2 met CUDA voordat de echte training kan draaien.
- Voor GGUF export en modelregistratie kan daarna `python scripts/setup_llama_cpp.py` de `llama.cpp` toolchain voorbereiden op Linux of WSL2.
