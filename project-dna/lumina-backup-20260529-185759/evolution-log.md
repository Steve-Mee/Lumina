# Evolution Log

This file tracks significant learnings, architectural decisions, and evolutionary steps in the Lumina project.

## Format
- **Date**: YYYY-MM-DD
- **Change / Decision**: Short description
- **Reasoning**: Why this was done
- **Impact**: Expected or observed effect
- **Evidence**: Backtest results, observations, or references (if available)

---

## Entries

### 2026-05-29
- **Added initial Project DNA structure**
  - Created vision.md, principles.md, architecture.md, anti-patterns.md, and this evolution-log.md.
  - Created project-specific AGENTS.md.
  - Reason: Establish a clear, structured foundation for long-term evolution and context management.
  - Impact: Provides a single source of truth for the project’s vision, principles, and guardrails.

### 2026-05-29
- **Recognized missing Recursive Self-Improvement Protocol**
  - Identified that AGENTS.md references a Recursive Self-Improvement Protocol that does not yet exist as a concrete document.
  - This is now tracked as a high-priority meta-evolution item.

### 2026-05-30
- **Introduced minimal Recursive Self-Improvement Protocol**
  - Created `project-dna/lumina/self-improvement-protocol.md`
  - Why: AGENTS.md referenced a protocol that did not exist as a concrete, usable document. This was the most direct gap preventing disciplined self-improvement of the project's own instructions and DNA.
  - What was done: Defined a minimal, practical process covering (1) when meta-improvements may be proposed, (2) mandatory use of Plan Mode, (3) required evolution-log entries, and (4) explicit reversibility via superseding log entries.
  - Impact: Establishes the first executable process for evolving the Project DNA and agent guidance in a way that is consistent with Lumina's own principles (small steps, evidence, documentation, reversibility).
  - Reversibility: The protocol can be replaced or removed by editing/deleting the file and adding a new evolution-log entry that supersedes it.

### 2026-05-30 (update)
- **Refined Self-Improvement Protocol to more concise version**
  - Replaced content of `project-dna/lumina/self-improvement-protocol.md` with a tighter, more direct version (max ~1 page).
  - Focused structure on the four core topics: proposal triggers, mandatory Plan Mode + log entry, documentation/rollback, and extra governance/risk checks.
  - Reason: Previous version was still slightly too verbose for a "minimal" protocol.
  - Impact: Improved usability and adherence to the "klein en praktisch" principle.
  - Reversibility: Previous content can be restored via git; new evolution-log entry supersedes the older version.

### 2026-05-30
- **Verdiept project-dna/lumina/architecture.md**
  - Herschreven met concrete inhoud uit de codebase en docs/architecture.md + AGI_SAFETY.md.
  - Toegevoegd: expliciete bounded contexts tabel, belangrijkste patronen (Event Bus, Admission Chain, ConstitutionalGuard, Shadow + Human Approval), communicatie model tussen lagen, en huidige evolutionaire knelpunten.
  - Reden: De vorige versie was te abstract en niet bruikbaar als echte bron van waarheid voor architectuur-beslissingen.
  - Impact: Maakt de architecture.md nu een praktisch referentiedocument in plaats van alleen een high-level plaatje.
  - Reversibility: Oudere versie terug te halen via git + nieuwe log entry.

### 2026-05-31
- **Current state snapshot of Project DNA**
  - Files currently present under `project-dna/lumina/`:
    - `vision.md`
    - `principles.md`
    - `architecture.md` (recently deepened with bounded contexts, key patterns like Event Bus / Admission Chain / ConstitutionalGuard, communication model, and evolutionary bottlenecks)
    - `anti-patterns.md` (recently expanded with concrete historical examples from refactors and codebase history)
    - `self-improvement-protocol.md` (minimal but usable version created)
    - `evolution-log.md` (this file)
  - Major remaining gaps:
    - The Recursive Self-Improvement Protocol now exists in minimal form, but it is not yet referenced or required from the root `AGENTS.md`. It has not yet been actively used to drive meta-evolution of the DNA itself.
    - Limited cross-references between the DNA files and the actual implementation (e.g. architecture.md could link more explicitly to source modules).
    - The DNA structure is now consolidated under `lumina/`, but the root `AGENTS.md` and other high-level docs still need alignment with the new location and contents.
  - Next priority:
    - Formally integrate the Self-Improvement Protocol into `AGENTS.md` (make it the explicit process for all future improvements to instructions and Project DNA).
    - Use the protocol for the next meta-improvement cycle (e.g. further refinement of architecture.md or anti-patterns.md based on the new protocol).
    - Update root-level references (AGENTS.md, CONTRIBUTING.md, .cursorrules) to point to `project-dna/lumina/` as the primary source of truth.

---

### 2026-05-31
- **Integrated Recursive Self-Improvement Protocol into root AGENTS.md**
  - Updated `AGENTS.md`:
    - Changed primary source of truth reference from `project-dna/` to `project-dna/lumina/`.
    - Made explicit reference to `project-dna/lumina/self-improvement-protocol.md` in the Evolution section.
    - Strengthened the Process section to require following the protocol for meta-improvements (instructions, DNA, agent guidance).
  - Reason: The protocol existed in minimal form but was not yet actionable from the main agent guidance file. This was the highest-leverage next step identified in the previous DNA state snapshot.
  - Impact: The Recursive Self-Improvement Protocol is now the official, required process for evolving Lumina's own instructions and DNA. Future meta-changes should follow it by default.
  - Reversibility: Changes to AGENTS.md can be reverted via git; a superseding evolution-log entry would document the reversal.

### 2026-05-31 (vervolg)
- **Bijgewerkt CONTRIBUTING.md en .cursorrules naar `project-dna/lumina/` als bron van waarheid**
  - CONTRIBUTING.md: Toegevoegd expliciete verwijzing naar `project-dna/lumina/` (inclusief het Self-Improvement Protocol) als primaire bron voor visie, principes en zelfverbetering.
  - .cursorrules: Nieuwe gedragsregel toegevoegd die agents verplicht eerst `project-dna/lumina/` te raadplegen bij architectuur- of proceswijzigingen.
  - Reden: Root-instructiebestanden waren nog niet aligned met de geconsolideerde DNA-structuur onder `lumina/`. Dit sluit de cirkel van de prioriteit "Update root-level references".
  - Impact: Alle belangrijke agent- en contributor-richtlijnen verwijzen nu consistent naar de Project DNA + het Recursive Self-Improvement Protocol.
  - Reversibility: Wijzigingen via git + superseding log entry.

---

*This log will be expanded over time as the system evolves.*