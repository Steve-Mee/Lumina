# 2026-05-30 — Uitgebreid project-dna/lumina/anti-patterns.md met historische lessen

**Change / Decision**: Toegevoegd concrete anti-patterns gebaseerd op herhaalde patronen uit de projectgeschiedenis.

**Examples added**:
- Meerdere grote launcher refactors (lumina_launcher.py >3000 regels)
- Monolithische LuminaEngine (god-object flags in reviews)
- Legacy compat layers
- Frequente state resets via backups/reset_*
- Big-bang refactors

**Reasoning**: De bestaande anti-patterns waren nog te generiek om echt preventief te werken.

**Impact**: Maakte anti-patterns.md een scherper, ervaringsgestuurd document dat toekomstige agenten en ontwikkelaars kan waarschuwen voor bekende valkuilen.

**Reversibility**: Aanpassingen via git + nieuwe superseding log entry.