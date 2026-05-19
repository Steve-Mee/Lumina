# Launcher Setup And Model Management

## What was implemented

- A first-run setup wizard was added to the launcher.
- Hardware detection now classifies the machine as `light`, `sweet`, or `beast`.
- The start screen now shows the current machine capability and what is needed to move to stronger tiers.
- The setup flow recommends a Qwen3.5 model based on the detected hardware.
- Model management now supports installing the recommended model and showing heavier upgrade targets.
- A model catalog was added so future app updates can offer new Lumina-tested Qwen variants.
- An Unsloth fine-tuning scaffold was added for future Linux/WSL2 CUDA environments.
- The fine-tuning scaffold now includes concrete training, GGUF export, and Ollama registration commands.
- The launcher now disables export and registration actions automatically when the runtime is not Linux or WSL2, or when prerequisites are missing.
- The hardware and model tabs now show explicit readiness badges for tier fit, recommended model state, Ollama, and vLLM.
- Blocked fine-tuning/export/register attempts are now written to a support log so admin users can see what a user tried to run and why it was blocked.
- Launcher setup preferences are configurable via `config.yaml` (`setup:` block).

## `config.yaml` setup block

```yaml
setup:
  mode: smart              # smart | classic | manual
  auto_install_ollama: true
  auto_download_model: true
  allow_force_tier: false
```

| Key | Default | Meaning |
|-----|---------|---------|
| `mode` | `smart` | **smart**: Smart Setup wizard then Guided Setup. **classic**: Guided Setup only (skip intelligence wizard). **manual**: Smart Setup with auto-install/model off by default. |
| `auto_install_ollama` | `true` | Default for Ollama auto-install in Smart Setup (ignored when `mode: manual`). |
| `auto_download_model` | `true` | Default for recommended model pull (ignored when `mode: manual`). |
| `allow_force_tier` | `false` | When `false`, hides High Tier checkbox and blocks `force_high` in Smart Setup. |

Loader: `lumina_launcher.core.setup_config.SetupConfig`. Gate routing: `lumina_launcher.core.setup_gate`.

## New files and their role

- `lumina_core/engine/hardware_inspector.py`: reads RAM, CPU, NVIDIA GPU, compute capability, and Ollama availability.
- `lumina_core/engine/model_catalog.py`: loads the model catalog and resolves upgrade paths.
- `lumina_core/engine/setup_service.py`: runs the guided install and updates `config.yaml`.
- `lumina_launcher/core/setup_config.py`: reads `setup:` from `config.yaml` for Smart Setup defaults and wizard routing.
- `lumina_core/engine/model_trainer.py`: inspects whether Unsloth training is possible and prepares dataset/commands.
- `lumina_core/engine/unsloth_runner.py`: concrete Unsloth LoRA/QLoRA training entrypoint for Linux/WSL2 CUDA environments.
- `lumina_model_catalog.json`: central catalog of Lumina-tested Qwen3.5 variants and upgrade paths.
- `requirements_finetune.txt`: optional dependencies for Unsloth and QLoRA workflows.
- `scripts/bootstrap_lumina.py`: one-shot bootstrap for a brand new machine.
- `scripts/setup_llama_cpp.py`: prepares the `llama.cpp` converter/build chain for Linux or WSL2.

## Setup state written by the app

- `state/hardware_snapshot.json`: last hardware scan.
- `state/lumina_setup_complete.json`: marks the machine as having completed the guided setup.
- `state/lumina_setup_status.json`: stores the last guided setup run and its step results.
- `state/model_catalog_state.json`: stores the last seen catalog version and current model.
- `state/training_pipeline_status.json`: stores the last Unsloth environment inspection.
- `state/finetune_dataset_preview.jsonl`: stores a preview training dataset generated from local logs.
- `state/llama_cpp_setup.json`: stores the last `llama.cpp` toolchain setup result.
- `state/launcher_support_events.jsonl`: stores blocked launcher action attempts with hardware and model context for support.

## Guided installation flow

1. Install launcher dependencies.
2. Install runtime dependencies.
3. Install Ollama when the OS package manager can do it automatically.
4. Pull the recommended Qwen3.5 model.
5. Update `config.yaml` to the detected hardware tier and model.
6. Optionally configure the admin password.
7. Optionally try to install Unsloth dependencies.
8. When a Linux/WSL2 CUDA environment exists, use the generated training, GGUF export, and `ollama create` commands from the launcher admin panel.
9. If `llama.cpp` is not prepared yet, run the launcher button or `python scripts/setup_llama_cpp.py` first.
10. If a user presses a blocked admin action, the launcher records the attempt in `state/launcher_support_events.jsonl` for follow-up.

## Tauri desktop build signing (Guided Setup)

During **Guided Setup → credentials**, operators can generate a Tauri updater minisign keypair:

- Private key file: `state/lumina-tauri-signing.key` (gitignored)
- Public key is synced into `tauri-app/src-tauri/tauri.conf.json` (`plugins.updater.pubkey`)
- `.env` receives `TAURI_SIGNING_PRIVATE_KEY_PATH=state/lumina-tauri-signing.key`

Use **Regenerate** only when you accept that existing installs may no longer verify updates.

Release build from repo root (loads `.env` and resolves the key path):

```powershell
.\scripts\tauri-build.ps1
```

Or from `tauri-app/`:

```powershell
npm run build:release
```

## Trading mode selection for operators

Use the trading mode according to operational intent:

- `paper`: strategy and UI validation without live broker constraints.
- `sim`: aggressive learning path with advisory risk behavior.
- `sim_real_guard`: SIM account intent with REAL-like guardrails (session, risk, EOD, reconciler).
- `real`: full capital-at-risk mode with strict fail-closed enforcement.

For `sim_real_guard` selection:

1. Configure `trade_mode=sim_real_guard`.
2. Keep `broker.backend=live`.
3. Set `TRADERLEAGUE_ACCOUNT_MODE=sim`.
4. Verify parity metrics are visible in observability/dashboard before considering REAL promotion.

## Adaptive Intelligence (SSOT + monitoring)

LUMINA uses a single public facade for runtime intelligence selection:

- `AdaptiveIntelligenceManager` — SSOT for tier, model, provider, reasoning mode, and degrade state
- `HardwareIntelligenceManager` — internal helper for hardware snapshot + model catalog resolution (not a second public status API)

Canonical intelligence tiers in code/UI/logging:

- `high`
- `standard`
- `light`

Legacy hardware profile names (`beast`, `sweet`, `light`) are mapped internally to these canonical tiers.

Configuration (`config.yaml`):

```yaml
intelligence:
  mode: auto   # auto | force_high | force_standard | force_light
```

State files written at runtime:

- `state/adaptive_intelligence_status.json` — latest published intelligence event envelope
- `state/adaptive_intelligence_events.jsonl` — transition history (deduplicated identical states)

Event bus topic:

- `inference.adaptive_intelligence.state` (typed Pydantic contract)

Monitoring API (FastAPI backend on port 8000, requires `X-API-Key`):

```powershell
curl http://localhost:8000/api/monitoring/adaptive-intelligence/latest -H "X-API-Key: $env:LUMINA_ADMIN_API_KEY"
curl "http://localhost:8000/api/monitoring/adaptive-intelligence/history?limit=100" -H "X-API-Key: $env:LUMINA_ADMIN_API_KEY"
```

Launcher visibility:

- First Boot tab shows current adaptive intelligence status (tier, provider, mode, degraded)
- Operations sidebar shows the same status via birth-service SSOT

## Current Qwen3.5 defaults

- `light`: `qwen3.5:4b`
- `sweet`: `qwen3.5:9b`
- `beast`: `qwen3.5:35b`

These defaults are represented in `lumina_model_catalog.json` and are surfaced in the launcher.

## What still depends on the right environment

The app now prepares the full command chain for the Unsloth flow, but it does not complete a full fine-tuning/export run on this Windows workspace because the required environment is still missing.

Missing environment pieces for the real fine-tune stage:

- Linux or WSL2 instead of Windows native
- NVIDIA CUDA runtime
- Enough GPU VRAM for the selected LoRA/QLoRA target
- A validated conversion/export toolchain to GGUF and `ollama create`

## Added tests

- `tests/engine/test_hardware_and_setup_services.py`: validates hardware classification and setup config updates.
- `tests/engine/test_model_trainer_pipeline.py`: validates dataset preview creation, pipeline commands, and export instructions.

## Recommended next additions when the Linux/WSL2 training environment is available

1. Add smoke tests for `HardwareInspector`, `ModelCatalog`, `SetupService`, and `ModelTrainer`.
2. Add a validated local `llama.cpp` toolchain under `tools/` or document the required converter path in deployment automation.
3. Add one-click launcher actions to execute the export/register commands when Linux/WSL2 is detected.
4. Add signed remote catalog update support if model releases will come from a server instead of the repo.