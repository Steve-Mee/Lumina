# NinjaTraderAI_Bot

Duidelijke projectstructuur voor de actieve Lumina runtime, deployment en research-assets.

[![Lumina Quality Gate](../../actions/workflows/lumina-quality-gate.yml/badge.svg?branch=main)](../../actions/workflows/lumina-quality-gate.yml)

## Snelle Navigatie

- Runtime entrypoint: lumina_runtime.py
- Supervisie en health: watchdog.py
- Nightly simulator: nightly_infinite_sim.py
- Runtime core package: lumina_core/
- Bible package in app: lumina_bible/
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
- lumina_agents/
  - agent-specifieke code
- lumina_vector_db/
  - lokale vector database files
- scripts/
  - utilities en cron assets
  - validation/ (losse validatie scripts)
- tests/
  - actieve tests voor runtime/core

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

## Risk Bounded Context (`lumina_core/risk/`)

Alle risicobeheer is geconcentreerd in één bounded context:

| Module | Verantwoordelijkheid |
|--------|---------------------|
| `risk_controller.py` | `HardRiskController`, `RiskLimits`, `RiskState` — hard fail-closed limieten |
| `risk_allocator.py` | `RiskAllocatorMixin` — Monte Carlo drawdown, VaR/ES positiebepaling |
| `risk_gates.py` | `RiskGatesMixin` — pre-trade gates, kill-switch, regime guards |
| `dynamic_kelly.py` | `DynamicKellyEstimator` — rolling + volatility-adjusted Kelly |
| `cost_model.py` | `TradeExecutionCostModel` — volledig kostenmodel (slippage + fees) |

### Dynamic Kelly (v54)

```python
from lumina_core.risk.dynamic_kelly import DynamicKellyEstimator

est = DynamicKellyEstimator(
    vol_scaling_enabled=True,
    vol_target_annual=0.15,   # target CV voor vol-scaling
    fractional_kelly_real=0.25,
)
est.record_trade(pnl=150.0)
fraction = est.fractional_kelly("real")  # vol-adjusted, REAL-capped
```

Volatility adjustment: `f_vol = f_kelly × clamp(CV_target / CV_realized, 0, 1)`.
In hoge-volatiliteitsregimes wordt de Kelly-fractie automatisch verlaagd.

### Cost Model (v54)

```python
from lumina_core.risk.cost_model import TradeExecutionCostModel

model = TradeExecutionCostModel.from_config(cfg, instrument="MES JUN26")
cost = model.cost_for_trade(price=5020.0, quantity=1.0, atr=8.0)
print(f"Round-trip: ${cost.total_round_trip_usd:.2f}")
print(f"Break-even: {cost.breakeven_move_ticks:.1f} ticks")
net = model.net_pnl(gross_pnl_usd=125.0, quantity=1.0)
```

Kosten per round-trip (1× MES, normaal markt): commission $2.58 + exchange $0.70 + clearing $0.20 + NFA $0.04 + slippage ≈ **$3.52–$4.50 totaal**.

## Werkafspraken

- Nieuwe operationele notities: docs/notes/
- Nieuwe validatie scripts: scripts/validation/
- Nieuwe tests: tests/
- Vermijd nieuwe losse root-bestanden tenzij het expliciet een entrypoint of top-level config is.
- Root-level `.log` bestanden horen niet thuis in git — gebruik `logs/` of `state/` mappen.

## Nieuwe machine opstarten

- Eerste bootstrap: `python scripts/bootstrap_lumina.py`
- Dit script maakt een lokale `.venv`, installeert launcher/runtime dependencies en start daarna Streamlit.
- De launcher toont bij eerste run een setup-wizard met hardwarescan, aanbevolen Qwen3.5-model en guided installatie.
- De wizard bewaart setup-status in `state/lumina_setup_complete.json` en `state/lumina_setup_status.json`.
- Model-upgrades en hardware-aanbevelingen worden gestuurd door `lumina_model_catalog.json`.
- Unsloth fine-tuning is voorbereid in de app, maar vereist nog steeds Linux of WSL2 met CUDA voordat de echte training kan draaien.
- Voor GGUF export en modelregistratie kan daarna `python scripts/setup_llama_cpp.py` de `llama.cpp` toolchain voorbereiden op Linux of WSL2.
