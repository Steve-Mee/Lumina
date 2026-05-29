# 2026-05-30 — Verdiept project-dna/lumina/architecture.md

**Change / Decision**: Herschreven architecture.md met concrete inhoud uit de codebase en docs/architecture.md + AGI_SAFETY.md.

**What was added**:
- Expliciete bounded contexts tabel
- Belangrijkste patronen (Event Bus, Admission Chain, ConstitutionalGuard, Shadow + Human Approval)
- Communicatie model tussen lagen
- Huidige evolutionaire knelpunten

**Reasoning**: De vorige versie was te abstract en niet bruikbaar als echte bron van waarheid voor architectuur-beslissingen.

**Impact**: Maakte architecture.md een praktisch referentiedocument in plaats van alleen een high-level plaatje.

**Reversibility**: Oudere versie terug te halen via git + nieuwe log entry.