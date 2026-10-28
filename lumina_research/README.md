# lumina_research

Propose-only research layer for Lumina. This is **not** Lumina-Lab and must not follow the closed `lumina-lab` project.

## Charter

Binding rules: [`RESEARCH_CHARTER.md`](../RESEARCH_CHARTER.md) (repo-root SSOT).

Agents may not write new signals until Phase 1 (Validation Gate implementation here) is complete.

## This layer may only propose

`lumina_research` may generate hypotheses, reports, and Validation Gate evidence. It **must never**:

- modify or bypass the Risk Core
- place, size, or cancel orders
- mutate live DNA, config, or NinjaTrader/Execution Fabric state
- promote a candidate without `PromotionGate`

Promotion of a survivor is a KEEP-fabric decision (`PromotionGate` + Risk Core + human/Twin approval). Research stops at the proposal.

## Linked KEEP surfaces (do not duplicate)

| Surface | Link |
|---------|------|
| Constitution | [`project-dna/lumina/constitution.md`](../project-dna/lumina/constitution.md) |
| Risk Core | [`lumina_core/risk/`](../lumina_core/risk/) (especially `risk_controller.py`) |
| Execution Fabric (gRPC) | [`docs/adr/0035-execution-fabric-grpc.md`](../docs/adr/0035-execution-fabric-grpc.md) · [`integrations/ninjatrader8/Lumina.Execution.Fabric/`](../integrations/ninjatrader8/Lumina.Execution.Fabric/) |
| Event Bus | [`lumina_core/agent_orchestration/event_bus.py`](../lumina_core/agent_orchestration/event_bus.py) |
| PromotionGate | [`lumina_core/evolution/promotion_gate.py`](../lumina_core/evolution/promotion_gate.py) |

Archived Birth-v1 experiments: [`archive/birth-v1/`](../archive/birth-v1/). Do not import them into this layer.
