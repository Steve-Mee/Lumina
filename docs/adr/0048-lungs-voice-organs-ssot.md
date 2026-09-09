# ADR-0048: Lungs vs Voice organ SSOT

**Status:** Accepted
**Date:** 2026-09-09
**Deciders:** LUMINA Engineering (Steve + Grok Build)

## Context

Hardware already knew `vllm_supported` is false on Windows. Smart Setup still sold one “intelligence stack” and hid Ollama when the recommended provider was not Ollama. `requirements-ml.txt` mixed CUDA/SB3 (Lungs) with vLLM (Voice). News lived next to a language client without an organ SSOT. Operators could not tell whether they were installing a training engine or a chatbot.

First principles: two organs. Training physics is not a talking server. News is talking, never the order path. Radical simplicity for a non-engineer first boot.

## Decision

- `lumina_core/intelligence/` is the SSOT (`organs_truth_v1`). AdaptiveIntelligenceManager keeps tier/provider/model and wraps organs.
- Lungs installer (`scripts/install_birth_physics_stack.py`) installs torch (cu128+) + SB3 only. Refuses `--with-vllm`. Contaminated if `import vllm` succeeds.
- Voice providers in order: Ollama (Windows default), grok_remote, vLLM (Linux/WSL2, HTTP only, own venv).
- Windows never allows or recommends vLLM. `force_high` may pick a larger Ollama tag, never vLLM.
- News is a Voice workload. `order_path_coupled` is invariant false. Provider off → neutral, multiplier 1.0.
- Setup UI is three cards: how it learns, how it talks, what happens next. Voice off does not block Genesis/Birth.

## Consequences

### Positive

- First boot on a Windows NT PC works without WSL or vLLM.
- Physics venv cannot pull vLLM through documented first-boot paths.
- Operator copy names organs in grade-8 English (Setup) and Dutch (Telegram).

### Negative

- Linux ML nodes must still install `requirements-ml.txt` in a **separate** serving venv.
- `force_high` no longer implies “unlock beast vLLM” on Windows.

## Alternatives considered

1. One “AI engine” radio (vLLM or CUDA) — rejected: false dichotomy, kills Lungs.
2. Keep `pip -r requirements-ml.txt` as first boot — rejected: ResolutionImpossible / CUDA loss.
3. Require Voice for Birth — rejected: plant first, mouth later.

## Links

- ADR-0043 Telegram I/O SSOT
- ADR-0027 maturation ladder
- `docs/DEPENDENCIES.md`
- `lumina_core/intelligence/organs.py`
