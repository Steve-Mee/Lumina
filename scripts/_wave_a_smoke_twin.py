from lumina_core.evolution.approval_twin_agent import (
    ApprovalTwinAgent,
    ApprovalTwinState,
    LocalHeuristicBackend,
    OllamaTwinBackend,
)

print("ok", ApprovalTwinAgent, ApprovalTwinState, LocalHeuristicBackend, OllamaTwinBackend)
assert hasattr(ApprovalTwinAgent, "evaluate_dna_promotion")
assert hasattr(ApprovalTwinAgent, "bind_event_bus")
assert hasattr(ApprovalTwinAgent, "rlhf_light_update")
assert hasattr(ApprovalTwinAgent, "_score")
print("methods ok")
