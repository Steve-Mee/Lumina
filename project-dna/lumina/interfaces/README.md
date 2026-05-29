# Project DNA Interfaces

Dit document beschrijft hoe je de verschillende interfaces van Lumina's Project DNA moet gebruiken.

## Voor Agents (LLM / Cursor / etc.)

**Beste optie**: Laad `export/agent-context.md` in je context. Dit is een compact, high-signal bestand dat de essentie bevat (North Star + Constitution + kern anti-patterns + protocol samenvatting).

Voor diepere context kun je combineren met:
- `core/constitution.md`
- `operating-system/self-improvement-protocol.md`
- `operating-system/truth-metrics.md`

## Voor Mensen (ontwikkelaars, reviewers)

- Begin met `core/north-star.md` voor de essentie.
- Gebruik `current-reality/` voor de actuele staat en bekende debt.
- Gebruik `operating-system/` voor hoe we onszelf verbeteren.
- Gebruik `evolution/log/` voor de historische leerervaringen.

## Machine-Leesbare Exports

- `export/full-context.json` — volledige export (voor tooling)
- `export/principles.yaml` — principes in gestructureerd formaat
- `core/invariants.json` — de harde constitutionele regels

## Regels

- Wijzigingen aan de DNA volgen altijd het Recursive Self-Improvement Protocol.
- Nieuwe interfaces of exports worden alleen toegevoegd als ze aantoonbaar de waarheidsdichtheid of evolueerbaarheid verhogen.

---

Laatste update: als onderdeel van DNA 2.0 redesign (2026-05-29)