# LUMINA — Release Checklist

> **Extreme intellectual honesty:** een release is pas acceptabel als hij **aantoonbaar** getest, gereviewd en gedocumenteerd is. Geen “hopelijk”; alleen wat je kunt **bewijzen** met logs, CI en deze checklist.

Gebruik optioneel `python scripts/prepare_release.py` voor een **draft changelog** (ADR-snapshot) en een **printbare reminder** van de kernpunten.

**Volledige changelog (aanbevolen voor releases):** [`scripts/generate_changelog.py`](../scripts/generate_changelog.py) combineert ADR’s sinds een datum met **conventional commits** (`git log`) en schrijft een **Keep a Changelog**-compatibele [`CHANGELOG.md`](../CHANGELOG.md). Voorbeeld:

```bash
python scripts/generate_changelog.py --version 5.1.0 --since "2026-04-01" --release-date "2026-05-01"
python scripts/generate_changelog.py --version 5.1.0 --since "2026-04-01" --stdout   # alleen preview
```

Review en pas secties handmatig aan waar automatische classificatie niet genoeg is — **intellectual honesty** vereist menselijke sanity-check op safety-regels.

---

## Pre-Release Checklist (verplicht)

Vink af wat waar is. Bij twijfel op een safety-kritiek punt: **geen release**.

| # | Controle | Status |
|---|----------|--------|
| 1 | **Alle tests groen:** `pytest -m "not slow"` | ☐ |
| 2 | **Ruff + MyPy + Pyright clean** op de release-set (geen nieuwe errors op gewijzigde/gemeteerde paden) | ☐ |
| 3 | **ADR’s up-to-date** — review minimaal de **laatste 5** canonieke `docs/adr/000x-*.md` entries + README-index ([docs/adr/README.md](adr/README.md)) | ☐ |
| 4 | **[README.md](../README.md)** en **[docs/architecture.md](architecture.md)** inhoudelijk gecontroleerd (versiebadges, links, architectuurspoor) | ☐ |
| 5 | **[CONTRIBUTING.md](../CONTRIBUTING.md)** nog aligned met workflow en tooling | ☐ |
| 6 | **Geen open TODO / FIXME** in **kritieke code** (risk, safety, constitution, shadow, broker/execution-paden) — zoek bv. met je IDE of `rg "TODO|FIXME" lumina_core/safety lumina_core/risk` | ☐ |
| 7 | **Shadow Deployment + Trading Constitution** handmatig getest op het scenario dat deze release raakt (SIM/REAL-overwegingen gedocumenteerd) | ☐ |
| 8 | **Version bump** in [`pyproject.toml`](../pyproject.toml) (`[project].version`) | ☐ |
| 9 | **Changelog gegenereerd of bijgewerkt** — merge draft uit `prepare_release.py` of handmatige entries; niets releasen zonder leesbare release notes | ☐ |

**Minimum mindset:** liever een week uitstellen dan REAL-kapitaal of reputatie riskeren.

---

## Release-stappen

Voer dit **sequentieel** uit; geen tag zonder groene pre-release.

### 1. Branch

```text
release/vX.Y.Z
```

Gebruik semver zoals in `pyproject.toml`. Geen force-push op shared history.

### 2. Changelog

- Genereer een basis met **`scripts/generate_changelog.py`** (`--version`, `--since`, optioneel `--release-date`), review de output (Added / Changed / Security / …), **of**
- Update **[CHANGELOG.md](../CHANGELOG.md)** handmatig (aanmaken bij eerste release als die nog ontbreekt), **of**
- Voeg inhoud samen uit ADR’s + commits + draft van `scripts/prepare_release.py`.

### 3. GitHub Release

Maak een **GitHub Release** met:

- **Titel:** `Lumina vX.Y.Z – [Korte beschrijving]`
- **Body-secties (minimaal):**
  - **New Features**
  - **Safety Improvements**
  - **Breaking Changes** (of expliciet “Geen”)
  - **ADR References** (links naar relevante `docs/adr/…`)

### 4. Tag

Tag de release consistent met de versie, bv. `vX.Y.Z` (afspraak team/leiders).

### 5. Badge in README

Werk het **version-badge** in [README.md](../README.md) bij (regel met `badge/version-…`) zodat het visueel matcht met `pyproject.toml`.

---

## Post-release

| Actie | Notities |
|-------|----------|
| Merge **release branch → main** | Normale PR-review; geen squash van kritieke safety-metadata tenzij beleid dat zo wil |
| **Verwijder** de release branch na succesvolle merge | Houd lijst branches schoon |
| **Nieuwe milestone** voor de volgende `vX.Y.(Z+1)` of geplande minor | Planning transparant houden |
| **Community-update** (kort) — wat is er nieuw, wat is er strenger geworden op safety | Eerlijk over breaking changes en operational impact |

---

## Snelle commando’s (referentie)

```bash
pytest -m "not slow"
ruff check .
mypy .
# pyright: volgens lokale setup / CI
python scripts/prepare_release.py
python scripts/generate_changelog.py --version X.Y.Z --since "YYYY-MM-DD"
```

---

*LUMINA — kapitaalbehoud is heilig in REAL; documentatie is geen paperwork, het is accountability.*
