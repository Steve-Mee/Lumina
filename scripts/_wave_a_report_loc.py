"""Report Wave A façade LOC + new files."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

facades = [
    "lumina_core/birth/plateau_escalator.py",
    "lumina_core/birth/starship_birth.py",
    "lumina_core/birth/stage_scorecard.py",
    "lumina_core/birth/certificate_pipeline.py",
    "lumina_core/birth/engine.py",
    "lumina_core/evolution/approval_twin_agent.py",
    "lumina_core/risk/shadow.py",
]
new_files = [
    "lumina_core/birth/plateau_rolling.py",
    "lumina_core/birth/plateau_enter.py",
    "lumina_core/birth/plateau_terminal.py",
    "lumina_core/birth/plateau_telemetry.py",
    "lumina_core/birth/starship_edgescore.py",
    "lumina_core/birth/starship_swarm_gates.py",
    "lumina_core/birth/stage_blocker.py",
    "lumina_core/birth/certificate_preflight.py",
    "lumina_core/birth/certificate_remediation.py",
    "lumina_core/birth/certificate_runway.py",
    "lumina_core/birth/certificate_patch_bridge.py",
    "lumina_core/evolution/approval_twin_backends.py",
    "lumina_core/evolution/approval_twin_bus.py",
    "lumina_core/evolution/approval_twin_scoring.py",
    "lumina_core/evolution/approval_twin_evaluators.py",
    "lumina_core/evolution/approval_twin_training.py",
    "lumina_core/evolution/approval_twin_patch_bridge.py",
    "lumina_core/risk/shadow_types.py",
    "lumina_core/risk/shadow_registry.py",
    "lumina_core/risk/shadow_isolation.py",
    "lumina_core/risk/shadow_assessment.py",
    "lumina_core/risk/shadow_experiment.py",
    "lumina_core/risk/shadow_human_approval.py",
]

print("=== FACADES ===")
for rel in facades:
    n = len((ROOT / rel).read_text(encoding="utf-8").splitlines())
    print(f"{n:5d}  {rel}")

print("=== NEW FILES ===")
for rel in new_files:
    p = ROOT / rel
    n = len(p.read_text(encoding="utf-8").splitlines()) if p.exists() else -1
    print(f"{n:5d}  {rel}")
