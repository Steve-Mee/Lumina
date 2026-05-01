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
pip-audit --requirement requirements-core.txt
pip-audit --requirement requirements-trading.txt
safety check -r requirements-core.txt -r requirements-trading.txt --full-report
```

CI voert dezelfde checks uit in:

- `.github/workflows/lumina-quality-gate.yml` (PR/push gate)
- `.github/workflows/nightly-security-audit.yml` (nachtelijke audit + artifacts)
