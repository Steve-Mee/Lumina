# Dependencies and Security

LUMINA gebruikt gesplitste requirements-profielen zodat elke omgeving alleen installeert wat nodig is.

## Requirements-profielen

- `requirements-core.txt`: minimale runtime voor API, engine en observability.
- `requirements-trading.txt`: live/paper trading add-ons (market calendars, scheduler, notificaties).
- `requirements-ml.txt`: training/inference stack (RL, transformers, vLLM, ONNX, CV).
- `requirements-dev.txt`: test/lint/security tooling.
- `requirements.txt`: aggregator die alle bovenstaande profielen include.

## Install voorbeelden

Productie runtime:

```bash
pip install -r requirements-core.txt -r requirements-trading.txt
```

Lokale development (alles):

```bash
pip install -r requirements.txt
```

ML-trainingsnode:

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
