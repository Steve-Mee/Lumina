# Lumina — Professionele codebase-analyse (herzien)

**Datum:** 1 mei 2026  
**Reikwijdte:** volledige Lumina-repository na implementatie van het stabilisatieplan (constitutie, risk/Kelly, broker/paper, governance, audit-hash-chain, CI-gates).  
**Panel:** vijf onafhankelijke experts (ieder >20 jaar ervaring): Senior Software Engineer & Architect, Code Reviewer & Static Analysis Specialist, Daytrader, Financial Advisor, AGI Developer.

---

## 1. Methodologie

- Verkenning van mappen (`lumina_core/`, `lumina_os/`, `lumina_agents/`, tests, CI, Docker, config).
- Beoordeling van canonieke paden: `lumina_core/safety/trading_constitution.py`, `constitutional_guard.py`, `sandboxed_executor.py`, `risk_controller.py`, `broker_bridge.py`, evolution/shadow, backend endpoints.
- Afweging t.o.v. eerdere analyse: **eerder als kritiek gemelde punten zijn deels opgelost** (zie per expert). Resterende risico’s zijn hier expliciet herschaald.

---

## 2. Projectstructuur en tech stack (samenvatting)

| Gebied | Locatie / technologie |
|--------|------------------------|
| Kern-engine | `lumina_core/engine/` (`lumina_engine.py`, brokers, backtest, RL) |
| Risk | `lumina_core/risk/` (HardRiskController, Dynamic Kelly, cost model, gates) |
| Safety / AGI | `lumina_core/safety/` (Trading Constitution, ConstitutionalGuard, sandbox) |
| Evolution | `lumina_core/evolution/` (orchestrator, shadow, DNA registry, neuro) |
| Agents / orchestratie | `lumina_core/agent_orchestration/`, `lumina_agents/` |
| Lumina OS | `lumina_os/backend/` (FastAPI), `lumina_os/frontend/` (Streamlit) |
| Entrypoints | `lumina_runtime.py`, `lumina_launcher.py`, `watchdog.py` |
| Config | `config.yaml`, `.env`, `EngineConfig` |
| Kwaliteit | Ruff, MyPy, Pytest (markers), GitHub Actions (`lumina-quality-gate.yml`, Python 3.13, coverage-floor) |

**Architectuurpatronen:** bounded contexts, event bus / blackboard, dependency injection (`ApplicationContainer`), fail-closed veiligheidspaden waar expliciet ontworpen.

---

## Expert 1 — Senior Software Engineer & Architect

### Sterke punten

- **Duidelijke domeingrenzen** onder `lumina_core/` met aparte packages voor risk, safety en evolution; README en ADR’s ondersteunen besluitvorming.
- **DI-container** (`lumina_core/container.py`) centraliseert services en vermindert “globale spaghetti” ten opzichte van puur script-gedreven bots.
- **Recente consolidatie:** canonieke `TRADING_CONSTITUTION`, verwijdering van legacy `constitutional_principles` / `mutation_sandbox`, hash-chain voor audit (`lumina_core/audit/hash_chain.py`).
- **CI is aangescherpt:** Python 3.13, MyPy niet meer optioneel, coverage-ondergrens — dit sluit aan bij `requires-python = ">=3.13"` in `pyproject.toml`.

### Zwaktes en verbeterpunten

| Prioriteit | Punt | Uitleg | Concrete actie |
|------------|------|--------|----------------|
| **High** | **God-file launcher** | `lumina_launcher.py` is zeer groot (~1880+ regels): UI, auth, processen en setup door elkaar — moeilijk te reviewen en te testen. | Splits in modules: setup-wizard, admin, procesbeheer, gedeelde widgets; voeg gerichte tests toe. |
| **Medium** | **Operationele heterogeniteit** | `watchdog.py` gebruikt Linux-/Docker-paden (`/app`, symlinks); op Windows of afwijkende container roots blijft dit fragiel. | Config-gestuurde paden; optioneel junctions op Windows; documenteer ondersteunde omgevingen. |
| **Medium** | **End-to-end approved hyperparams** | Goedkeuring schrijft naar `state/approved_hyperparams.json`; de volledige runtime moet dit **overal** consequent laden vóór risk sizing. | Centrale loader in bootstrap/container + één bron van waarheid in docs. |
| **Low** | **Documentatie vs. code** | ADR’s verwijzen soms nog naar oude bestandsnamen; onderhoud labels (“legacy verwijderd”) voorkomt verwarring. | Kleine doc-sync PR na canonical paths. |

### Wat kan weg of versmald worden (met voorbehoud)

- **Geen massale deletes** zonder impactanalyse: het project is integratie-zwaar. Wel: **dead code** en **dubbele experimentele scripts** periodiek laten lopen via coverage + import-graph.

### Scores (Expert 1)

| Segment | Score (/10) | Motivatie |
|---------|-------------|-----------|
| Architectuur | 8.0 | Bounded contexts + container; launcher en ops nog zwaar. |
| Codekwaliteit | 7.5 | Sterk in kernmodules; grote entrypoints trekken gemiddelde omlaag. |
| Onderhoudbaarheid | 7.0 | Docs en ADR’s helpen; megabestanden hinderen. |
| Performance & efficiëntie | 7.5 | Lazy loading en lock-gebruik op plekken; geen clusterbrede perf-strategie zichtbaar. |
| Security | 8.0 | Fail-closed endpoints + hash-chain; secrets blijven aandachtspunt overal. |
| Tradinglogica & effectiviteit | 7.0 | Architectuur ondersteunt discipline; PnL niet onderdeel van deze review. |
| Risicomanagement | 8.5 | HardRiskController, Kelly, cost model — sterk verbonden. |
| Financiële nauwkeurigheid | 7.5 | Cost model aanwezig; uitvoeringspad blijft broker-afhankelijk. |
| AGI/agent-mogelijkheden | 8.0 | Evolution + constitution + shadow — rijk model. |
| Domeinfit (trading bot) | 8.5 | Duidelijk gericht op NT/CME-futures en AI-governance. |
| **Totaal Expert 1** | **7.8** | |

---

## Expert 2 — Code Reviewer & Static Analysis Specialist

### Sterke punten

- **Expliciete veiligheids-API:** `ConstitutionalGuard`, JSON-parse met sentinel i.p.v. stille `{}`, tests op constitution en hash-chain.
- **Tests:** brede `tests/`-boom met markers (`slow`, `nightly`, enz.) — ondersteunt gelaagde CI.
- **Type hints en tooling:** MyPy in CI sluit aan bij Python 3.13.

### Zwaktes en verbeterpunten

| Prioriteit | Punt | Uitleg | Concrete actie |
|------------|------|--------|----------------|
| **High** | **MyPy-baseline over volledige repo** | Workflow checkt `lumina_core/`; andere packages (`lumina_os`, `lumina_agents`) kunnen nog type-gaten hebben. | Uitbreiden naar `lumina_os/` services of expliciet “best effort” documenteren. |
| **Medium** | **Complexiteit evolution-orchestrator** | Grote orchestrator met veel verantwoordelijkheden — regressierisico bij wijzigingen. | Interne modules/services extracten; contracttests op guard/sandbox/shadow. |
| **Medium** | **`# noqa` / lazy imports** | Verstandig voor circular imports, maar verbergt soms coupling. | Periodiek dependency graph; waar mogelijk interfaces i.p.v. late imports. |
| **Low** | **Hash-chain ≠ cryptografische handtekening** | SHA-256-keten is **tamper-evident** bij append-only gebruik; geen asymmetrische signing. | Optioneel: signeer `entry_hash` met HSM/key voor compliance-scenario’s. |

### Wat verwijderen

- **Verouderde commentaar** in docs die nog naar verwijderde modules wijst — voorkomt verkeerde onboarding.

### Scores (Expert 2)

| Segment | Score (/10) |
|---------|-------------|
| Architectuur | 7.5 |
| Codekwaliteit | 8.0 |
| Onderhoudbaarheid | 7.5 |
| Performance & efficiëntie | 7.0 |
| Security | 8.5 |
| Tradinglogica & effectiviteit | 7.0 |
| Risicomanagement | 8.0 |
| Financiële nauwkeurigheid | 7.5 |
| AGI/agent-mogelijkheden | 8.0 |
| Domeinfit | 8.0 |
| **Totaal Expert 2** | **7.7** |

---

## Expert 3 — Daytrader (intraday futures / discretionair)

### Sterke punten

- **Mode-scheiding** (REAL vs SIM/PAPER) en **sessie-/risk-gates** passen bij professioneel risicomanagement.
- **Paper broker** gebruikt nu cost/slippage-modellering — realistischer dan commission 0.
- **REAL sizing floor** vermindert impliciet “altijd minimaal 1 contract”.

### Zwaktes en verbeterpunten

| Prioriteit | Punt | Uitleg | Concrete actie |
|------------|------|--------|----------------|
| **High** | **Live uitvoering vs. REST-semantiek** | Orders hebben idempotency/retry; echte fill lifecycle (gedeeltelijke fills, reject reasons, latency) moet in productie nog steeds broker-specifiek worden gevalideerd. | Paper trading + logging van ruwe broker responses; playbook voor incidenten. |
| **Medium** | **News avoidance** | NewsAgent beïnvloedt via blackboard; harde “no trade” gate rond macro-events vereist expliciete koppeling aan risk engine. | Config vlag: hard block vs. soft multiplier. |
| **Medium** | **Regime mapping** | Symbol→regime expliciet — goed; callers moeten **consistent** regime doorgeven bij `set_open_risk`. | Lint/contract in integration tests. |

### Wat weghalen

- **Geen tradingfeatures schrappen** zonder metingen; wel: dubbele signal-paden die tot tegenstrijdige orders kunnen leiden — traceerbaar maken met één beslissingsaudittrail.

### Scores (Expert 3)

| Segment | Score (/10) |
|---------|-------------|
| Architectuur | 7.5 |
| Codekwaliteit | 7.5 |
| Onderhoudbaarheid | 7.0 |
| Performance & efficiëntie | 7.5 |
| Security | 7.5 |
| Tradinglogica & effectiviteit | 7.5 |
| Risicomanagement | 8.5 |
| Financiële nauwkeurigheid | 7.5 |
| AGI/agent-mogelijkheden | 7.5 |
| Domeinfit | 8.5 |
| **Totaal Expert 3** | **7.7** |

---

## Expert 4 — Financial Advisor (portfolio risk, kapitaalbehoud)

### Sterke punten

- **Daily loss cap, streak cooldown, VaR/ES, MC drawdown, Kelly + fractional caps** — dit is een volwassen risico-stack voor een retail/prosumer context.
- **Constitution** legt harde plafonds vast (o.a. max risk REAL, drawdown kill).
- **Evolution-goedkeuring** faalt nu gesloten in relevante modes en schrijft niet blind naar verkeerde YAML-sectie.

### Zwaktes en verbeterpunten

| Prioriteit | Punt | Uitleg | Concrete actie |
|------------|------|--------|----------------|
| **High** | **Config vs. runtime waarheid** | `config.yaml` + env + goedgekeurde state-bestanden: één diagram “wat geldt wanneer” voor operators. | Runbook + startup log die effectieve risk params dump (na merge). |
| **Medium** | **Margin/snapshot stale** | Risk gebruikt margin snapshots; stale data kan tot verkeerde “kan openen” leiden. | Alarms + fail-closed policy al deels aanwezig — uniform toepassen in REAL. |
| **Low** | **Semantiek vol-target** | Kelly-documents noemen CV vs. “annual” — begrijpelijk in code, maar verwarrend in YAML-labels. | Hernoem of documenteer in config-commentaar. |

### Wat verwijderen

- **Risico-dode configuratiebranches** (oude `risk:` keys als die nergens meer gelezen worden) na grep + migratie — voorkomt “ik dacht dat dit werkte”.

### Scores (Expert 4)

| Segment | Score (/10) |
|---------|-------------|
| Architectuur | 8.0 |
| Codekwaliteit | 7.5 |
| Onderhoudbaarheid | 7.5 |
| Performance & efficiëntie | 7.0 |
| Security | 8.0 |
| Tradinglogica & effectiviteit | 7.5 |
| Risicomanagement | 8.5 |
| Financiële nauwkeurigheid | 8.0 |
| AGI/agent-mogelijkheden | 7.5 |
| Domeinfit | 8.5 |
| **Totaal Expert 4** | **7.9** |

---

## Expert 5 — AGI Developer (veilige autonomie, evolution governance)

### Sterke punten

- **Trading Constitution (15 principes)** + **ConstitutionalGuard** + **SandboxedMutationExecutor** vormen een herkenbaar “safety case”.
- **JSON-only DNA** sluit een eerder echt bypass-pad.
- **Shadow deployment** met statistische AB-gate en kwaliteitsdrempels is een volwassen stap t.o.v. enkel mean-PnL.
- **Evolution API:** API-key fail-closed in protected modes, audit JSONL met hash-chain, constitution-check op approved hyperparams.

### Zwaktes en verbeterpunten

| Prioriteit | Punt | Uitleg | Concrete actie |
|------------|------|--------|----------------|
| **High** | **Sandbox network isolation** | Documentatie claimt “no network”; echte isolatie op OS-niveau (firewall, unshare, container net=none) is sterker dan alleen subprocess-gedrag. | Optionele harde sandboxprofielen voor CI/red-team. |
| **Medium** | **SIM zonder dashboard key** | Als `LUMINA_DASHBOARD_API_KEY` leeg is en mode niet als “protected” gezien wordt, blijven sommige paden open — bewust voor dev, risico bij verkeerde env in staging. | `ENV=production` style guard of verplichte key buiten pure `sim`. |
| **Medium** | **Audit signing** | Hash-chain verifieert integriteit van de keten; het bewijst niet wie append deed. | Operator identity + signing key voor mutatie-endpoints. |
| **Low** | **Meta-swarm / approval complexity** | Meer “democratische” lagen = meer attack surface en meer plaats voor inconsistentie. | Formaliseer minimale promotion pipeline in één state machine. |

### Wat verwijderen

- **Dode evolution hooks** of dubbele guard-paden die nooit meer worden aangeroepen — na statische analyse en testdekking.

### Scores (Expert 5)

| Segment | Score (/10) |
|---------|-------------|
| Architectuur | 8.5 |
| Codekwaliteit | 8.0 |
| Onderhoudbaarheid | 7.5 |
| Performance & efficiëntie | 7.0 |
| Security | 8.5 |
| Tradinglogica & effectiviteit | 7.0 |
| Risicomanagement | 8.0 |
| Financiële nauwkeurigheid | 7.5 |
| AGI/agent-mogelijkheden | 8.5 |
| Domeinfit | 8.5 |
| **Totaal Expert 5** | **8.0** |

---

## Korte eindsynthese

Lumina is **ecosystemisch rijp**: bounded contexts, risk stack, evolution governance en safety-laag zijn **duidelijk boven modaal** voor een solo/geavanceerd retail trading-AI-project. De recente stabilisatie **adresseert eerder geïdentificeerde kritieke hiaten** (constitutie-bypass via platte tekst, regime-accounting, Kelly-drift, broker/paper-realism, gesloten evolution-endpoints, audit-keten, strengere CI).

De grootste **restschuld** zit in **operationele schaalbaarheid en menselijke onderhoudbaarheid**: zeer grote entrypoints (`lumina_launcher`), heterogene deploy-paden (Docker/watchdog vs. Windows), en het **volledig doorvoeren** van goedgekeurde hyperparameters in alle runtime-paden. Daarnaast blijft **echte live broker-complexiteit** (fills, partials, reconciliatie) een apart validatieproject — code kan fail-closed zijn, maar **execution correctness** is broker-specifiek.

---

## Top prioriteiten (bijgewerkt, geordend)

1. **End-to-end wiring van `approved_hyperparams.json`** — overal dezelfde merge-logica als `risk_controller` zodat goedkeuringen niet “op schijf” blijven liggen. *(Critical voor governance→runtime)*  
2. **Refactor `lumina_launcher.py`** — splitsen en testen; verlaagt regressierisico en auditlast. *(High)*  
3. **Live execution playbook** — gestructureerde logging van broker-antwoorden, reconciliatie en incident-runbooks. *(High voor REAL)*  
4. **Harde netwerk-isolatie sandbox** (optioneel profiel) — defense-in-depth voor evolution/red-team. *(High voor AGI-paranoia)*  
5. **Documentatie operatie-config** — single diagram: env + YAML + state files + welke mode welke gate activeert. *(Medium)*  
6. **Watchdog / paden** — cross-platform robuustheid of duidelijke “Linux-only” scope. *(Medium)*  
7. **MyPy/coverage uitbreiden** naar `lumina_os`/`lumina_agents` of expliciet scope-contract in CI. *(Medium)*  

---

## Appendix — eerder kritiek vs. huidige status

| Eerder thema | Status (hoog niveau) |
|--------------|----------------------|
| Plain-text DNA bypass | **Opgelost:** JSON-only + fataal principe |
| Legacy constitution / mutation sandbox | **Opgelost:** verwijderd; canonieke paden |
| Regime exposure hacks | **Opgelost:** expliciete symbol→regime mapping |
| Kelly singleton drift | **Opgelost:** estimator uit engine/config |
| Paper commission 0 / naïeve fills | **Verbeterd:** cost model + side-aware slip |
| Evolution endpoint open zonder key | **Verbeterd:** fail-closed in protected modes |
| Mean-only shadow verdict | **Verbeterd:** AB + kwaliteitsdrempels |
| Audit tampering | **Verbeterd:** hash-chain op security + decisions |
| CI Python vs. project / mypy lax / cov 0 | **Verbeterd:** 3.13, mypy blocking, cov floor |

---

*Einde rapport.*
