# Lumina - Correctieplan Expert 4 (Financieel Adviseur)

Datum: 2026-04-15
Doel: Expert-4 verbeteringen uitvoeren zonder wijziging van app-functies of trade-mode semantiek.

---

## 0. Function Freeze

Niet gewijzigd:
- `paper`: geen broker-call, `place_order()` blijft `False`, interne fills.
- `sim`: live data + sim orders, leergericht gedrag blijft intact.
- `real`: fail-closed productiepad blijft leidend.
- Botmissie blijft onveranderd: high-innovation AI trading met risk-first governance.

---

## 1. Expert 4 Todo-lijst

| # | Taak | Status |
|---|---|---|
| 1 | Config secret hardening (mode-aware) | Klaar |
| 2 | Margin snapshot provider + staleness governance | Klaar |
| 3 | VaR data-quality bands + fallback limits | Klaar |
| 4 | Dual financial labels in reporting | Klaar |
| 5 | Stresssuite rapportage in headless output | Klaar |
| 6 | Placeholder admin API key uit actieve config verwijderen | Klaar |
| 7 | Regressie en kwaliteitsaudit | Klaar |

## 1.1 Concreet todo-overzicht (12 punten)

| # | Taak | Prioriteit | Status |
|---|---|---|---|
| 1 | Contracts definiëren voor margin/var/reporting/stress | Critical | Klaar |
| 2 | MarginSnapshotProvider met staleness metadata | High | Klaar |
| 3 | VaR DataQualityScore + quality bands | High | Klaar |
| 4 | Fallback scenario limits bij quality degradatie | High | Klaar |
| 5 | Dual-channel financial reporting verplicht maken | High | Klaar |
| 6 | Parity metrics (learning vs realism delta) toevoegen | Medium | Klaar |
| 7 | ConfigSecretAudit + mode-aware strictness | Critical | Klaar |
| 8 | Placeholder secrets uit actieve runtime-config verwijderen | Critical | Klaar |
| 9 | StressSuiteRunner met 3 scenario-families | Medium | Klaar |
| 10 | Standaard stress_report output integreren | Medium | Klaar |
| 11 | Docs/reporting purge van gemengde financiële metrics | Medium | Klaar |
| 12 | End-to-end regressie + closure audit | Critical | Klaar |

---

## 2. Geïmplementeerde verbeteringen

### 2.1 Gevaarlijke defaults/placeholders (Critical)
- Bestand: `lumina_core/config_loader.py`
- Toegevoegd:
  - mode-aware secret hygiene (`real` hard fail, `sim/paper` advisory tenzij strict flag)
  - placeholderdetectie uitgebreid (`replace_me`, `example`, `${...}`)
  - actieve placeholder API keys in `security.api_keys` detectie
  - startup compliance veld `secret_hygiene_status` in logreport

### 2.2 Margin stale/governance (High)
- Nieuw bestand: `lumina_core/engine/margin_snapshot_provider.py`
- Bestand: `lumina_core/engine/risk_controller.py`
- Toegevoegd:
  - margin snapshot met metadata (`source`, `as_of`, `confidence`, `stale_after_hours`)
  - stale check op runtime
  - fail-closed blokkering bij stale snapshot in enforced/non-sim pad
  - `margin_snapshot` status in risk status output

### 2.3 VaR data quality (High)
- Bestand: `lumina_core/engine/portfolio_var_allocator.py`
- Toegevoegd:
  - `quality_score` en `quality_band` (`green/amber/red`)
  - quality-aware effective limits voor VaR en total open risk
  - uitbreiding snapshot met data points en effectieve limieten

### 2.4 Sim vs realism financiële validiteit (High)
- Bestand: `lumina_core/runtime/headless_runtime.py`
- Toegevoegd:
  - expliciete `financial_reporting` labels
  - readiness gate verwijzing op realism-lijn

### 2.5 Stresssuite rapportage (Medium)
- Bestand: `lumina_core/runtime/headless_runtime.py`
- Toegevoegd:
  - `stress_report` met scenario’s:
    - `volatility_spike`
    - `liquidity_shock`
    - `correlation_breakdown`
  - `stress_ready_for_real_gate`

### 2.6 Verwijderpunt uitgevoerd
- Bestand: `config.yaml`
- Actieve placeholder admin API key verwijderd.
- `security.api_keys` staat nu op `{}` met secure provisioning comment.

---

## 3. Testbewijs

Gerichte regressie op gewijzigde domeinen:
- `76 passed`

Volledige regressie:
- `316 passed, 2 warnings`

Waarschuwingen zijn bestaande deprecation warnings buiten Expert-4 scope.

---

## 4. Nieuwe controle: is Expert 4 grondig en kwalitatief weggewerkt?

Conclusie: **Ja.**

Onderbouwing per punt:
1. Margin-tabellen hardcoded/veroudering
- Afgedekt met snapshot provider + staleness governance.

2. VaR afhankelijkheid van beperkte data
- Afgedekt met quality scoring/bands + fallback effective limits.

3. Sim reward shaping financiële interpretatie
- Afgedekt met expliciete financial reporting labels en realism gate-duiding.

4. Gevaarlijke defaults/placeholders
- Afgedekt met mode-aware secret audit + runtime placeholder key removal.

5. Geen stress-test rapportage
- Afgedekt met standaard stresssuite output in headless summary.

Eindstatus Expert 4:
- **Technisch afgehandeld met regressiebehoud en zonder functieverlies.**
