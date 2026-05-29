# AGENTS.md - Lumina

Primary source of truth: `project-dna/lumina/` (zie `project-dna/lumina/` voor vision, principles, architecture, anti-patterns en het Recursive Self-Improvement Protocol)

## Project Purpose
Lumina is a self-evolving autonomous trading system. Its core strength lies in continuous, evidence-based improvement while maintaining strict risk discipline.

## Core Principles
- Evolution is the primary mechanism of progress.
- Risk management is non-negotiable and must remain explicit and auditable.
- All significant changes must be supported by data and proper validation.
- Modular design enables safer and faster evolution.
- Truth-seeking > performance chasing.

## Architecture Guidance
- Maintain clear separation between research, backtesting, and live execution.
- Use modular components with well-defined interfaces.
- Prefer blackboard or lightweight multi-agent patterns for complex decision-making.
- Keep risk logic highly visible and isolated.

## Working Rules

### Risk & Validation
- Never hide or soften risk parameters.
- Require proper backtesting + out-of-sample validation before considering changes to strategy or risk logic.
- Use Plan Mode for any modification to core trading or risk components.

### Evolution
- Prefer small, measurable, low-risk evolutionary steps.
- Document the reasoning and evidence behind changes.
- When improving the system (especially instructions, DNA, or agent guidance), follow the **Recursive Self-Improvement Protocol** defined in `project-dna/lumina/self-improvement-protocol.md`.
- Always record significant meta-improvements in `project-dna/lumina/evolution-log.md`.

### Code Quality
- Apply strict modular architecture.
- No god files. Small, focused, independently testable components.
- Clear naming and separation of concerns.

## Output Standards
- Be direct and precise.
- Distinguish between hypotheses, validated results, and production-ready logic.
- When uncertain, state assumptions and limitations clearly.

## Process
1. Consult `project-dna/lumina/` first (this is the authoritative source).
2. Apply relevant capabilities (backtesting discipline, modular architecture, risk awareness).
3. For any improvement to instructions, Project DNA, AGENTS.md, or agent guidance: follow the **Recursive Self-Improvement Protocol** (`project-dna/lumina/self-improvement-protocol.md`). This includes mandatory use of Plan Mode and an evolution-log entry.
4. Keep risk and reasoning transparent.