# Lumina - Correctieplan Expert 2 (Zonder Functionele Wijziging)

Datum: 2026-04-10  
Doel: de onderstaande Expert-2 zwakke punten oplossen zonder wijziging van app-doel of runtime-semantiek.  
Belangrijke randvoorwaarde: paper/sim/real gedrag blijft exact conform de trade-mode referentie in `lumina_analyse.md`.

---

## 0. Invarianten (Mogen Niet Veranderen)

Deze regels zijn hard en gelden tijdens alle fasen:

1. `paper` blijft: geen broker-call, `place_order()` retourneert `False`, fills via supervisor-loop.
2. `sim` blijft: live marktdata + broker op sim-account, SessionGuard actief, HardRiskController advisory (`enforce_rules=False`).
3. `real` blijft: SessionGuard + HardRiskController fail-closed volledig actief.
4. Geen wijzigingen aan tradingdoel, strategie-intentie of business flows; enkel correctheid, veiligheid, onderhoudbaarheid en documentatie.
5. Elke wijziging krijgt regressietest of verificatiestap die aantoont dat gedrag functioneel gelijk blijft.

---

## 1. Scope (Exact de 6 punten)

1. Kritieke logische fout in `operations_service.place_order`
2. Ontbrekende auth dependency op belangrijke backend endpoints
3. Inconsistente config-validatie (nested `security.*`)
4. Fragiele `sys.path` mutatie in backend app
5. Documentatie-drift in README
6. UTF-16/artefact-achtig `test_results.txt` in root

---

## 2. Aanpak Per Punt

### 2.1 `operations_service.place_order` control-flow (Critical)

Probleem:
- Paper-return kan risk-gate pad onbereikbaar maken in foutieve flowstructuur.

Aanpak:
1. Eerst mode-beslissing expliciet en centraal maken.
2. Daarna per mode de verplichte checks in vaste volgorde:
- `paper`: expliciet kort pad, geen broker-call, return `False`.
- `sim`: SessionGuard verplicht, risk advisory (`enforce_rules=False`), broker submit.
- `real`: SessionGuard + volledige HardRiskController gate, broker submit.
3. Geen semantiek-wijziging, alleen flow-herstructurering en verduidelijking.
4. Regressietests voor alle modepaden + no-broker-assert in `paper`.

Acceptatiecriteria:
- 1-op-1 modegedrag blijft gelijk aan trade-mode referentie.
- Testsuite met mode-specifieke assertions groen.

---

### 2.2 Backend endpoint auth (Critical)

Probleem:
- Belangrijke POST/GET routes hebben wel rate-limit maar niet overal verplichte API-auth.

Aanpak:
1. Endpoint-inventaris op `lumina_os/backend`:
- publieke endpoints expliciet whitelisten,
- alle overige read/write trade-gevoelige routes onder `Depends(verify_api_key)`.
2. Openbare uitzonderingen documenteren in codecomment en runbook.
3. Security-tests toevoegen:
- zonder key -> 401,
- met geldige key -> 2xx/verwachte response.

Acceptatiecriteria:
- Geen niet-openbare route zonder auth dependency.
- Public/private route-matrix gedocumenteerd.

---

### 2.3 Config-validatie (`security.*`) normaliseren (High)

Probleem:
- Validator leest delen alsof keys top-level zijn, terwijl input nested config gebruikt.

Aanpak:
1. Validator refactoren naar eenduidige namespace-resolutie (`security.*`, `broker.*`, etc.).
2. Placeholder-secret checks op nested paden afdwingen.
3. Tests voor nested scenario's:
- geldig nested config,
- ontbrekende nested key,
- placeholder value -> startup fail.

Acceptatiecriteria:
- Validator werkt uitsluitend op correcte namespace.
- Geen false negatives bij nested security waarden.

---

### 2.4 `sys.path` mutatie verwijderen (High)

Probleem:
- Runtime-afhankelijk importgedrag door handmatige pad-injectie.

Aanpak:
1. Verwijderen van `sys.path.insert(...)` workaround.
2. Startcommando en package-resolutie standaardiseren via module-layout.
3. Import-smoketest:
- backend start zonder path hack,
- imports resolven in lokale en container context.

Acceptatiecriteria:
- Geen `sys.path` hack in backend app.
- Backend boot consistent in dev/prod.

---

### 2.5 README documentatie-drift (Medium)

Probleem:
- README kan mappen/paden noemen die niet meer bestaan.

Aanpak:
1. README sync met actuele repositorystructuur.
2. Archieflocaties expliciet benoemen (bv. `docs/history`).
3. Lichte docs-check opnemen (script/CI): genoemde paden bestaan echt.

Acceptatiecriteria:
- Geen dode padverwijzingen in README.
- Docs-check slaagt op CI/local.

---

### 2.6 `test_results.txt` artefact (Low)

Probleem:
- Niet-canoniek artefact in root (encoding/ruis voor reviews).

Aanpak:
1. Root artefact verwijderen of verplaatsen naar artifacts-output pad.
2. Indien behoud nodig: UTF-8 normaliseren en genereren op aanvraag (niet als bronbestand).
3. `.gitignore` afstemmen voor tijdelijke test-output.

Acceptatiecriteria:
- Geen review-ruis door test artefacten in root.

---

## 3. Faseringsplan (Veilig en Reproduceerbaar)

### Fase A - Baseline & Guardrails
1. Volledige testbaseline draaien.
2. Endpoint- en config-inventaris maken.
3. Invarianten vastleggen in testnotities (paper/sim/real).

### Fase B - Critical fixes eerst
1. `operations_service.place_order` flow corrigeren + regressietests.
2. Backend auth-dependencies harden + endpoint tests.

### Fase C - High fixes
1. Config-validator namespace normalisatie + nested tests.
2. `sys.path` hack verwijderen + boot/import smoke tests.

### Fase D - Medium/Low hygiene
1. README sync + docs-check.
2. Root artefact cleanup (`test_results.txt` beleid).

### Fase E - Eindvalidatie
1. Regressiesuite volledig.
2. Security endpoint checks.
3. Trade-mode semantiek expliciet gevalideerd (paper/sim/real).
4. Changelog met bewijs per punt.

---

## 4. Teststrategie (Functioneel Ongewijzigd Bewijzen)

Verplicht:
1. Unit tests op mode-control-flow (`paper/sim/real`).
2. API auth tests (401/authorized matrix).
3. Config validator tests (nested + placeholders).
4. Backend startup smoke test (zonder `sys.path` mutatie).
5. Non-regression suite op bestaande kritieke paden.

Extra veiligheidscheck:
- Voor en na wijzigingen een korte parity-check op:
- paper return-gedrag,
- sim advisory risk-mode,
- real fail-closed enforcement.

---

## 5. Risicobeheersing

1. Geen grote gecombineerde refactor in 1 stap; per punt kleine wijzigingssets.
2. Elke critical/high wijziging pas mergen na groene tests.
3. Bij afwijking van trade-mode semantiek: direct rollback van die wijziging.
4. Alle wijzigingen documenteren met "gedrag behouden" notitie.

---

## 6. Definition of Done

Alle onderstaande zijn waar:

1. De 6 Expert-2 punten zijn aantoonbaar afgehandeld.
2. Trade-mode gedrag is ongewijzigd en conform referentie.
3. Relevante tests zijn groen.
4. README en analyse-documentatie zijn actueel.
5. Geen onbedoelde functionele wijziging in app-doel of kernflow.

---

## 7. Uitvoeringsvolgorde (Concreet)

1. Critical #1: `place_order` flow + tests
2. Critical #2: endpoint auth hardening + tests
3. High #3: config-validator namespaces + tests
4. High #4: `sys.path` cleanup + startup smoke
5. Medium #5: README + docs-check
6. Low #6: test artefact policy cleanup
7. Final: full regression + release note

---

## 8. Gedetailleerde Todo List + Uitvoering (Afgerond)

| # | Taak | Status | Uitvoering/Bewijs |
|---|---|---|---|
| 1 | Baseline status en gap-analyse | ✅ Afgerond | Trade-mode referentie opnieuw gevalideerd tegen `lumina_analyse.md` voordat wijzigingen zijn toegepast. |
| 2 | Critical: `operations_service.place_order` control-flow | ✅ Afgerond | Reeds eerder gecorrigeerd in codebase; non-regressie bevestigd met `tests/test_order_path_regression.py` (14 passed). |
| 3 | Critical: API auth dependencies | ✅ Afgerond | `Depends(verify_api_key)` toegevoegd op niet-openbare trade/upload/status routes in `lumina_os/backend/app.py`. |
| 4 | High: nested config-validatie normaliseren | ✅ Afgerond | `DangerousConfigValidator.validate()` leest nu correct `security` namespace en resolve't paden robuust (`security.*` en compatibel fallback-pad). |
| 5 | High: `sys.path` mutatie verwijderen | ✅ Afgerond | Bevestigd: geen `sys.path.insert(...)` meer in backend app; enkel standaard package imports. |
| 6 | Medium: README documentatie-drift | ✅ Afgerond | Niet-bestaande mapverwijzing verwijderd, README in sync gebracht met werkelijke structuur. |
| 7 | Low: UTF-16 root artefact `test_results.txt` | ✅ Afgerond | Bestand verwijderd uit repository en toegevoegd aan `.gitignore` om herintroductie te voorkomen. |
| 8 | Docs pad-validatie toevoegen | ✅ Afgerond | Nieuw script toegevoegd: `scripts/validation/check_docs_paths.py`. |
| 9 | Volledige eindcontrole | ✅ Afgerond | Volledige test-run en syntaxiscontrole uitgevoerd; resultaten hieronder. |

---

## 9. Eindcontrole (Post-implementatie)

Uitgevoerde controles:

1. `get_errors` op aangepaste bestanden:
- `lumina_os/backend/app.py` -> geen fouten
- `lumina_core/security.py` -> geen fouten
- `scripts/validation/check_docs_paths.py` -> geen fouten
- `README.md` -> geen fouten

2. Gerichte regressies:
- `pytest tests/test_order_path_regression.py -q` -> **14 passed**
- `pytest tests/test_broker_bridge.py -q` -> **3 passed**

3. Volledige regressiesuite:
- `pytest tests/ -q --tb=no` -> **308 passed, 2 skipped**

4. Docs drift check:
- `python scripts/validation/check_docs_paths.py` -> **OK: README path check passed**

Conclusie:
- Alle 6 Expert-2 punten zijn technisch afgehandeld.
- Trade-mode semantiek (`paper/sim/real`) bleef ongewijzigd conform referentie.
- App-functies en kerndoel zijn behouden.
