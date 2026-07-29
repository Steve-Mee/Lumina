from lumina_core.risk.shadow import (
    ShadowContext,
    ShadowExperimentResult,
    ShadowRiskEvaluator,
    ShadowRunRegistry,
)

print("ok", ShadowRiskEvaluator, ShadowContext, ShadowRunRegistry, ShadowExperimentResult)
for name in (
    "evaluate_risk_decision",
    "run_shadow_experiment",
    "execute_shadow_experiment",
    "submit_human_approval_decision",
    "with_persistent_registry",
    "_enforce_shadow_isolation",
):
    assert hasattr(ShadowRiskEvaluator, name), name
print("methods ok")
