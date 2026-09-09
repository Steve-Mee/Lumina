# Dependencies and Security

LUMINA gebruikt gesplitste requirements-profielen zodat elke omgeving alleen installeert wat nodig is.

## Requirements-profielen

- `requirements-core.txt`: minimale runtime voor API, engine en observability.
- `requirements-trading.txt`: live/paper trading add-ons (market calendars, scheduler, notificaties).
- `requirements-ml.txt`: Linux/WSL2 **Voice serving** extras (vLLM, transformers, ONNX). **Not** the Windows Birth / NinjaTrader first-boot path. **Not** the physics venv.
- `requirements-birth-physics.txt`: Lungs pins (SB3, gymnasium). Torch CUDA wheel comes from `scripts/install_birth_physics_stack.py`.
- `requirements-dev.txt`: test/lint/security tooling.
- `requirements.txt`: aggregator for a Linux ML node. Do not use this as Windows first-boot.

## Two organs

1. **Lungs (training engine / leermotor):** `python scripts/install_birth_physics_stack.py` — torch cu128+ + SB3. Never vLLM.
2. **Voice (thinking assistant / denk-assistent):** Ollama or xAI on Windows. vLLM only on Linux/WSL2 in its **own** venv.

## Install voorbeelden

Productie runtime / Windows NinjaTrader first-boot:

```bash
pip install -r requirements-core.txt -r requirements-trading.txt
python scripts/install_birth_physics_stack.py
```

Lokale development (Linux ML node, not the NT machine):

```bash
pip install -r requirements.txt
```

vLLM serving node (Linux/WSL2, separate venv):

```bash
pip install -r requirements-core.txt -r requirements-trading.txt -r requirements-ml.txt
```

## SBOM generatie (CycloneDX)

Genereer een CycloneDX JSON SBOM:

```bash
pip install -r requirements-core.txt -r requirements-trading.txt
cyclonedx-py environment --output-format json --outfile docs/sbom.json
```

## Security audits

Lokale dependency audits:

```bash
python scripts/validation/run_safety_audit.py
pip-audit --requirement requirements-core.txt
pip-audit --requirement requirements-trading.txt
```

`run_safety_audit.py` gebruikt `safety scan` zodra `SAFETY_API_KEY` gezet is.
Zonder API key valt het script gecontroleerd terug op `safety check` om
interactieve login-prompts in CI te vermijden.

## SAFETY_API_KEY in CI (aanrader)

Voor volledige `safety scan` mode in GitHub Actions:

1. Maak/gebruik een Safety account en genereer een API key.
2. Voeg in GitHub repository settings een Actions secret toe:
   - naam: `SAFETY_API_KEY`
   - waarde: je Safety API key
3. De bestaande workflows gebruiken automatisch scan-mode zodra de secret
   beschikbaar is.

Optionele lokale test met API key:

```bash
set SAFETY_API_KEY=your_key_here
python scripts/validation/run_safety_audit.py
```

CI voert dezelfde checks uit in:

- `.github/workflows/lumina-quality-gate.yml` (PR/push gate)
- `.github/workflows/nightly-security-audit.yml` (nachtelijke audit + artifacts)
