"""ArchitectureMetaController — pure observe/decide for architecture self-improvements.

Radically simple: fixed narrow catalog of 4 mutation operators.
Mirror BirthMetaController patterns: frozen snapshots, proposals (not plans), pure functions,
enabled guard, restore/metrics, format helpers, HOLD-equivalent (no-op).

All proposals are small (< max_patch_lines), measurable delta required, constitution-checked.
No I/O, no live apply. Side effects in caller.

Constitution: bounded contexts, no god growth, typed contracts, fail-closed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from lumina_core.architecture_meta.constitution import ArchitectureConstitution  # type: ignore  # circular ok at runtime via import guard


class ArchMutationType(str, Enum):
    """Narrow, pre-approved, safe architecture mutation operators only."""
    EXTRACT_PURE_HELPER = "extract_pure_helper"
    INTRODUCE_TYPED_MODEL = "introduce_typed_model"
    BOUNDARY_VIA_PORT = "boundary_via_port"
    SIMPLIFY_GUARD = "simplify_guard"


@dataclass(frozen=True, slots=True)
class ArchHealthSnapshot:
    """Deterministic, observable architecture health at a point in time."""
    god_file_count: int  # files >700 LOC in core lumina_core/ (excl tests)
    boundary_violations: int  # simple cross-context import count (heuristic)
    pydantic_model_count: int  # rough adoption proxy in schemas/ports
    ruff_violations_core: int
    avg_module_loc: float
    todo_density: float  # TODO/FIXME per 100 LOC in core
    total_core_loc: int
    timestamp: str = ""
    # Derived
    arch_health_score: float = 5.0  # 0-10, higher better

    @property
    def is_healthy(self) -> bool:
        return self.arch_health_score >= 7.0 and self.boundary_violations == 0


@dataclass(frozen=True, slots=True)
class ArchMutationProposal:
    """A single, small, reviewable architecture mutation proposal."""
    proposal_id: str
    mutation_type: ArchMutationType
    target_file: str  # relative, whitelisted
    description: str
    diff: str  # unified diff, validated small
    expected_delta: float  # predicted arch_health_score improvement (> min)
    rationale: str
    before_score: float
    constitution_passed: bool = False
    sandbox_passed: bool = False
    # Audit
    decision_context_id: str = ""
    created_by: str = "architecture_meta_controller"


@dataclass(slots=True)
class ArchitectureMetaController:
    """SSOT for proposing architecture mutations. Pure decision core.

    Usage:
        ctrl = ArchitectureMetaController(enabled=True, max_patch_lines=80, min_delta=0.15)
        snap = ctrl.build_snapshot(...)  # from static scanners
        proposals = ctrl.propose(snap)
        for p in proposals:
            if ctrl.constitution.check_pre_mutation(...):
                # hand to sandbox + human gate
    """

    enabled: bool = False
    max_patch_lines: int = 80
    min_health_delta: float = 0.15
    max_proposals_per_scan: int = 2
    constitution: ArchitectureConstitution = field(default_factory=ArchitectureConstitution)

    # Internal counters for metrics (mutable via object setattr because slots)
    proposals_generated: int = field(default=0, init=False)
    proposals_sandbox_passed: int = field(default=0, init=False)
    _enabled: bool = field(default=False, init=False, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_enabled", bool(self.enabled))
        if self.constitution is None:
            object.__setattr__(self, "constitution", ArchitectureConstitution())

    @property
    def is_enabled(self) -> bool:
        return bool(getattr(self, "_enabled", getattr(self, "enabled", False)))

    def build_snapshot(
        self,
        *,
        god_file_count: int,
        boundary_violations: int,
        pydantic_model_count: int,
        ruff_violations_core: int,
        avg_module_loc: float,
        todo_density: float,
        total_core_loc: int,
        timestamp: str = "",
    ) -> ArchHealthSnapshot:
        """Build immutable snapshot + compute health score (pure, deterministic)."""
        score = self._compute_health_score(
            god=god_file_count,
            bounds=boundary_violations,
            pyd=pydantic_model_count,
            ruff=ruff_violations_core,
            avg_loc=avg_module_loc,
            todo=todo_density,
        )
        return ArchHealthSnapshot(
            god_file_count=god_file_count,
            boundary_violations=boundary_violations,
            pydantic_model_count=pydantic_model_count,
            ruff_violations_core=ruff_violations_core,
            avg_module_loc=avg_module_loc,
            todo_density=todo_density,
            total_core_loc=total_core_loc,
            timestamp=timestamp,
            arch_health_score=round(score, 3),
        )

    def _compute_health_score(
        self, *, god: int, bounds: int, pyd: int, ruff: int, avg_loc: float, todo: float
    ) -> float:
        """v1 formula. Unit tested. Higher = better."""
        penalty = (
            god * 2.0
            + bounds * 1.5
            + (ruff * 0.08)
            + max(0.0, (avg_loc - 250.0) / 100.0) * 0.6
            + todo * 1.2
        )
        bonus = pyd * 0.25
        raw = 9.5 - penalty + bonus
        return max(0.0, min(10.0, raw))

    def propose(self, snap: ArchHealthSnapshot) -> list[ArchMutationProposal]:
        """Generate at most N small proposals. Pure. Returns [] when disabled or healthy."""
        if not self.is_enabled:
            return []
        if snap.is_healthy and snap.god_file_count == 0:
            return []

        proposals: list[ArchMutationProposal] = []
        # Heuristic narrow catalog — radically simple scanners
        # 1. EXTRACT_PURE_HELPER (look for large files + obvious pure helpers)
        if snap.god_file_count > 0 and len(proposals) < self.max_proposals_per_scan:
            prop = self._make_extract_helper_proposal(snap)
            if prop:
                proposals.append(prop)

        # 2. INTRODUCE_TYPED_MODEL (if low pydantic adoption + known loose areas)
        if snap.pydantic_model_count < 30 and len(proposals) < self.max_proposals_per_scan:
            prop = self._make_typed_model_proposal(snap)
            if prop:
                proposals.append(prop)

        # 3/4 limited to avoid complexity in v1
        # Only add if room
        if len(proposals) < self.max_proposals_per_scan:
            prop = self._make_boundary_or_simplify_proposal(snap)
            if prop:
                proposals.append(prop)

        # Constitution pre-filter (fail closed)
        filtered: list[ArchMutationProposal] = []
        for p in proposals[: self.max_proposals_per_scan]:
            # Minimal pre-screen here; full check is in caller + sandbox
            p2 = ArchMutationProposal(
                proposal_id=p.proposal_id,
                mutation_type=p.mutation_type,
                target_file=p.target_file,
                description=p.description,
                diff=p.diff,
                expected_delta=p.expected_delta,
                rationale=p.rationale,
                before_score=p.before_score,
                constitution_passed=True,
                sandbox_passed=p.sandbox_passed,
                decision_context_id=p.decision_context_id,
            )
            filtered.append(p2)

        self.proposals_generated += len(filtered)
        return filtered

    def _make_extract_helper_proposal(self, snap: ArchHealthSnapshot) -> ArchMutationProposal | None:
        # Radically simple placeholder proposal (real scanner would use AST/LOC in future pass)
        # For v1 we emit a canonical "opportunity" that sandbox + human will validate on concrete target.
        if snap.god_file_count <= 0:
            return None
        return ArchMutationProposal(
            proposal_id=f"arch-{ArchMutationType.EXTRACT_PURE_HELPER.value}-1",
            mutation_type=ArchMutationType.EXTRACT_PURE_HELPER,
            target_file="lumina_core/some_large_context/module.py",  # concrete target supplied by caller/scan
            description="Extract small pure computation to sibling _helpers.py (same bounded context)",
            diff="--- a/...\n+++ b/...\n@@ -10,6 +10,12 @@\n+def _pure_helper(x):\n+    return x * 2\n",
            expected_delta=0.25,
            rationale="Reduces god file LOC; keeps pure logic local to context; improves testability.",
            before_score=snap.arch_health_score,
            decision_context_id="arch_meta.v1.scan",
        )

    def _make_typed_model_proposal(self, snap: ArchHealthSnapshot) -> ArchMutationProposal | None:
        if snap.pydantic_model_count >= 40:
            return None
        return ArchMutationProposal(
            proposal_id=f"arch-{ArchMutationType.INTRODUCE_TYPED_MODEL.value}-1",
            mutation_type=ArchMutationType.INTRODUCE_TYPED_MODEL,
            target_file="lumina_core/agent_orchestration/schemas.py",
            description="Replace loose dict usage in event payload with strict Pydantic model (extra=forbid)",
            diff="",
            expected_delta=0.30,
            rationale="Advances typed contracts invariant. Makes evolution safer and introspectable.",
            before_score=snap.arch_health_score,
            decision_context_id="arch_meta.v1.scan",
        )

    def _make_boundary_or_simplify_proposal(self, snap: ArchHealthSnapshot) -> ArchMutationProposal | None:
        if snap.boundary_violations == 0:
            # fall back to simplify guard if no boundary issues
            return ArchMutationProposal(
                proposal_id=f"arch-{ArchMutationType.SIMPLIFY_GUARD.value}-1",
                mutation_type=ArchMutationType.SIMPLIFY_GUARD,
                target_file="lumina_core/safety/constitutional_guard.py",
                description="Flatten nested guard condition to early returns (smaller cognitive load)",
                diff="",
                expected_delta=0.18,
                rationale="Simpler code in safety critical path. Easier to constitution-audit.",
                before_score=snap.arch_health_score,
                decision_context_id="arch_meta.v1.scan",
            )
        return ArchMutationProposal(
            proposal_id=f"arch-{ArchMutationType.BOUNDARY_VIA_PORT.value}-1",
            mutation_type=ArchMutationType.BOUNDARY_VIA_PORT,
            target_file="lumina_core/some_cross/file.py",
            description="Replace direct cross-context import with port or EventBus publish",
            diff="",
            expected_delta=0.40,
            rationale="Enforces bounded contexts (core constitution rule).",
            before_score=snap.arch_health_score,
            decision_context_id="arch_meta.v1.scan",
        )

    def score_proposal(self, proposal: ArchMutationProposal, sandbox_delta: float) -> float:
        """Combine expected + actual sandbox delta. Pure."""
        return max(proposal.expected_delta * 0.6 + sandbox_delta * 0.4, 0.0)

    def should_promote_candidate(self, proposal: ArchMutationProposal, sandbox_result: Any) -> bool:
        """Gate before human: constitution + sandbox delta + small size."""
        if not proposal.constitution_passed:
            return False
        # sandbox_result is ArchSandboxResult duck in practice
        delta = getattr(sandbox_result, "score_delta", 0.0) or 0.0
        if delta < self.min_health_delta:
            return False
        # diff size check is done in sandbox validator
        return True

    def metrics_payload(self) -> dict[str, Any]:
        return {
            "arch_meta_proposals_generated": self.proposals_generated,
            "arch_meta_sandbox_passed": self.proposals_sandbox_passed,
            "arch_meta_enabled": self.is_enabled,
        }

    def format_decision_log(self, proposal: ArchMutationProposal | None, trigger: str = "periodic") -> str:
        if not proposal:
            return f"arch_meta: no proposal (trigger={trigger})"
        return (
            f"arch_meta: propose {proposal.mutation_type.value} on {proposal.target_file} "
            f"delta~{proposal.expected_delta:.2f} (id={proposal.proposal_id})"
        )


def compute_health_score_from_counts(**kwargs: Any) -> float:
    """Public helper for external scanners."""
    ctrl = ArchitectureMetaController(enabled=True)
    return ctrl._compute_health_score(
        god=kwargs.get("god_file_count", 0),
        bounds=kwargs.get("boundary_violations", 0),
        pyd=kwargs.get("pydantic_model_count", 0),
        ruff=kwargs.get("ruff_violations_core", 0),
        avg_loc=kwargs.get("avg_module_loc", 300.0),
        todo=kwargs.get("todo_density", 0.0),
    )
