# Production Machine Setup

This repository is now prepared for a Linux-based Docker deployment where Lumina uses a dedicated vLLM container when GPU-compatible and routes by configured provider order when vLLM is unavailable.

## Recommended target

- Ubuntu 22.04 or 24.04 LTS
- NVIDIA GPU with current driver
- Docker Engine + Docker Compose plugin
- NVIDIA Container Toolkit

## Why this layout

- `vLLM` runs inside Linux where its native extensions are supported.
- `lumina` stays isolated from the inference server and only talks to `http://vllm:8000` when available.
- Install/update scripts auto-enable the `vllm` compose profile only for compatible GPUs (`sm_70+`).
- The app keeps its provider chain behavior if vLLM is unavailable or unhealthy.

## Install order on the real machine

1. Install Ubuntu Linux.
2. Install NVIDIA driver and verify `nvidia-smi` works.
3. Install Docker Engine and Docker Compose plugin.
4. Install NVIDIA Container Toolkit and restart Docker.
5. Clone this repository onto the machine.
6. Copy `deploy/.env.production.example` to `deploy/.env.production` and fill in secrets.
7. Run `bash deploy/preflight_production.sh`.
8. Run `bash deploy/install_production.sh`.
9. Run `bash deploy/smoke_preprod.sh` for an end-to-end pre-prod smoke test.
10. If you want unattended updates after the app is ready, run `bash deploy/install_auto_update.sh`.

Windows operator helper:

- From a Windows shell, run `./deploy/run_preprod_smoke.ps1` for guidance.
- To run through WSL directly, use `./deploy/run_preprod_smoke.ps1 -RunInWsl`.

## Verify the inference layer

Run these checks on the target machine:

```bash
docker compose -f docker-compose.prod.yml ps
curl http://127.0.0.1:8000/health
docker compose -f docker-compose.prod.yml logs vllm --tail=200
docker compose -f docker-compose.prod.yml logs lumina --tail=200
```

Expected result:

- On compatible GPUs: `vllm` becomes healthy and serves model endpoints.
- On incompatible/no NVIDIA GPUs: `vllm` is skipped automatically and `lumina` still runs with remaining configured providers.
- `config.production.yaml` points Lumina to `http://vllm:8000`.

## Automatic updates

- `deploy/update_stack.sh` supports 2 update modes:
	- `tag`: recommended for production; checks out the newest matching release tag
	- `branch`: follows a named branch directly
- Default production policy is `tag`, configured through `deploy/.env.production`.
- `deploy/install_auto_update.sh` installs a systemd timer that runs the update job using `LUMINA_AUTO_UPDATE_INTERVAL`.
- This means the future production machine does not need a Python dev environment; Docker is the runtime boundary.

Recommended production values in `deploy/.env.production`:

```bash
LUMINA_UPDATE_MODE=tag
LUMINA_RELEASE_PREFIX=v
LUMINA_RELEASE_REF=
LUMINA_AUTO_UPDATE_INTERVAL=30min
```

If you explicitly want to track a branch instead:

```bash
LUMINA_UPDATE_MODE=branch
LUMINA_UPDATE_BRANCH=main
```

See [release-workflow.md](c:/NinjaTraderAI_Bot/docs/release-workflow.md) for the recommended tag-based release process.

## Notes

- `deploy/config.production.yaml` is mounted into the app container as `/app/config.yaml`.
- `deploy/.env.production` is the runtime secret/config file used by both services.
- `docker-compose.prod.yml` now includes stronger defaults for long-running containers: `init`, log rotation, `tmpfs`, `nofile` ulimits, `pids_limit`, and `no-new-privileges`.
- If you still want Ollama as secondary local provider on the production host, keep Ollama installed on the host and exposed on port `11434`.
- If you prefer pure remote routing, remove `ollama` from `inference.provider_order` in `deploy/config.production.yaml`.
- Use `bash deploy/smoke_preprod.sh` before first production cutover; it validates the correct inference path (vLLM or alternate provider) automatically.
- If you trigger operations from Windows, `deploy/run_preprod_smoke.ps1` prints the correct Linux command and can invoke WSL when available.

## Current Windows test machine

The current Windows test machine is not a reliable target for native vLLM serving because the runtime lacks the compiled `vllm._C` extension path expected by vLLM. That is why the production recommendation is Linux + Docker.

## Launcher and model management

- The Streamlit launcher now includes a first-run setup wizard for fresh machines.
- Hardware is classified into `light`, `sweet`, and `beast`, and the UI explains what is required to move up a tier.
- The setup wizard recommends a Qwen3.5 model using the local hardware snapshot.
- Model upgrades are driven by `lumina_model_catalog.json`, which means future Lumina-tested Qwen variants can be exposed through normal app updates.
- Unsloth fine-tuning is scaffolded in the app, but the real training/export step still requires Linux or WSL2 with CUDA.