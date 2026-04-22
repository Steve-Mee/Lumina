"""Hierarchical meta-swarm: five specialized agents deliberate promotion fitness.

Agents vote, publish challenges, then re-score in a second round. Risk Guardian
holds a hard veto; consensus uses weighted approval and mean scores.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Protocol

from lumina_core.config_loader import ConfigLoader


def meta_swarm_governance_enabled() -> bool:
    """Whether five-agent deliberation runs (EvolutionOrchestrator + nightly meta_review)."""
    evolution_cfg = ConfigLoader.section("evolution", default={}) or {}
    if not isinstance(evolution_cfg, dict):
        return True
    ms = evolution_cfg.get("meta_swarm", {})
    if not isinstance(ms, dict):
        return True
    return bool(ms.get("enabled", True))


def parallel_realities_from_config() -> int:
    """Stress-universe count from evolution.multiweek_fitness (1–50)."""
    evolution_cfg = ConfigLoader.section("evolution", default={}) or {}
    mw_cfg = evolution_cfg.get("multiweek_fitness", {}) if isinstance(evolution_cfg, dict) else {}
    if not isinstance(mw_cfg, dict):
        return 1
    try:
        n = int(mw_cfg.get("parallel_realities", 1) or 1)
    except (TypeError, ValueError):
        return 1
    return max(1, min(50, n))


@dataclass(slots=True)
class SwarmAgentVote:
    agent_id: str
    approve: bool
    score: float
    veto: bool
    challenges: tuple[str, ...] = ()
    note: str = ""


@dataclass(slots=True)
class SwarmConsensus:
    allow_promotion: bool
    collective_score: float
    risk_veto: bool
    round_one: list[SwarmAgentVote] = field(default_factory=list)
    round_two: list[SwarmAgentVote] = field(default_factory=list)
    challenge_log: list[str] = field(default_factory=list)


class SwarmAgent(Protocol):
    role: str

    def initial_vote(self, ctx: dict[str, Any]) -> SwarmAgentVote: ...

    def challenged_vote(
        self,
        ctx: dict[str, Any],
        *,
        peer_challenges: tuple[str, ...],
    ) -> SwarmAgentVote: ...


@dataclass
class CreativityAgent:
    role: str = "creativity"

    def initial_vote(self, ctx: dict[str, Any]) -> SwarmAgentVote:
        wf = float(ctx.get("winner_fitness", float("-inf")))
        pf = float(ctx.get("previous_fitness", float("-inf")))
        delta = wf - pf if all(math.isfinite(x) for x in (wf, pf)) else 0.0
        approve = delta > -1e-6
        score = 0.55 + min(0.4, max(0.0, delta * 0.02))
        ch: list[str] = []
        if not approve:
            ch.append("risk:creativity_rejects_regression")
        return SwarmAgentVote(self.role, approve, score, False, tuple(ch), "explore/improve delta")

    def challenged_vote(
        self,
        ctx: dict[str, Any],
        *,
        peer_challenges: tuple[str, ...],
    ) -> SwarmAgentVote:
        v = self.initial_vote(ctx)
        if any("risk" in c for c in peer_challenges):
            score = max(0.2, v.score - 0.2)
            return SwarmAgentVote(v.agent_id, v.approve and score >= 0.35, score, False, v.challenges, v.note + "; damped by risk")
        return v


@dataclass
class RiskGuardianAgent:
    role: str = "risk_guardian"

    def initial_vote(self, ctx: dict[str, Any]) -> SwarmAgentVote:
        report = dict(ctx.get("nightly_report", {}) or {})
        eq = max(1.0, float(report.get("account_equity", 50_000.0) or 50_000.0))
        dd = abs(float(report.get("max_drawdown", 0.0) or 0.0))
        ratio = dd / eq
        veto = ratio > 0.42
        approve = not veto and ratio < 0.28
        score = max(0.0, 1.0 - ratio * 2.5)
        ch = ("execution:drawdown_stress_high",) if ratio > 0.22 else ()
        return SwarmAgentVote(self.role, approve, score, veto, ch, f"dd_ratio={ratio:.4f}")

    def challenged_vote(
        self,
        ctx: dict[str, Any],
        *,
        peer_challenges: tuple[str, ...],
    ) -> SwarmAgentVote:
        v = self.initial_vote(ctx)
        if any("dream" in c for c in peer_challenges) and not v.veto:
            return SwarmAgentVote(v.agent_id, v.approve, min(1.0, v.score + 0.05), False, v.challenges, v.note + "; dream appeal")
        return v


@dataclass
class ExecutionAgent:
    role: str = "execution"

    def initial_vote(self, ctx: dict[str, Any]) -> SwarmAgentVote:
        mode = str(ctx.get("mode", "sim")).lower()
        sim_days = int(ctx.get("sim_days", 1) or 1)
        ok_mode = mode in {"sim", "paper", "real"}
        ok_depth = 1 <= sim_days <= 366
        approve = ok_mode and ok_depth
        score = 0.7 if approve else 0.25
        ch = () if approve else ("reflection:sim_window_invalid",)
        return SwarmAgentVote(self.role, approve, score, False, ch, "ops window")

    def challenged_vote(
        self,
        ctx: dict[str, Any],
        *,
        peer_challenges: tuple[str, ...],
    ) -> SwarmAgentVote:
        v = self.initial_vote(ctx)
        if peer_challenges:
            return SwarmAgentVote(v.agent_id, v.approve, max(0.15, v.score - 0.05), False, v.challenges, v.note + "; peer review")
        return v


@dataclass
class ReflectionAgent:
    role: str = "reflection"

    def initial_vote(self, ctx: dict[str, Any]) -> SwarmAgentVote:
        report = dict(ctx.get("nightly_report", {}) or {})
        pnl = float(report.get("net_pnl", 0.0) or 0.0)
        sharpe = float(report.get("sharpe", 0.0) or 0.0)
        approve = pnl > -25_000.0 and sharpe > -2.5
        score = 0.5 + (0.01 if sharpe > 0 else 0.0) + (0.01 if pnl > 0 else 0.0)
        ch = ("creativity:pnl_memory_conflict",) if pnl < -5_000 else ()
        return SwarmAgentVote(self.role, approve, min(0.95, score), False, ch, "nightly memory")

    def challenged_vote(
        self,
        ctx: dict[str, Any],
        *,
        peer_challenges: tuple[str, ...],
    ) -> SwarmAgentVote:
        v = self.initial_vote(ctx)
        if any("execution" in c for c in peer_challenges):
            return SwarmAgentVote(v.agent_id, v.approve, v.score - 0.03, False, v.challenges, v.note + "; execution flagged")
        return v


@dataclass
class DreamAgent:
    role: str = "dream"

    def initial_vote(self, ctx: dict[str, Any]) -> SwarmAgentVote:
        pr = int(ctx.get("parallel_realities", 1) or 1)
        wf = float(ctx.get("winner_fitness", float("-inf")))
        bonus = min(0.15, max(0.0, (pr - 1) * 0.004))
        approve = math.isfinite(wf) and wf > float("-inf")
        score = 0.52 + bonus + (0.05 if approve else 0.0)
        ch = ("risk:dream_wants_more_stress",) if pr < 3 else ()
        return SwarmAgentVote(self.role, approve, min(0.98, score), False, ch, "long-horizon robustness prior")

    def challenged_vote(
        self,
        ctx: dict[str, Any],
        *,
        peer_challenges: tuple[str, ...],
    ) -> SwarmAgentVote:
        v = self.initial_vote(ctx)
        if any("risk" in c and "stress" in c for c in peer_challenges):
            return SwarmAgentVote(v.agent_id, True, v.score, False, ("reflection:dream_defends_exploration",), v.note)
        return v


class MetaSwarm:
    """Five-agent council: Creativity, Risk, Execution, Reflection, Dream."""

    __slots__ = ("_agents",)

    def __init__(self) -> None:
        self._agents: tuple[SwarmAgent, ...] = (
            CreativityAgent(),
            RiskGuardianAgent(),
            ExecutionAgent(),
            ReflectionAgent(),
            DreamAgent(),
        )

    def deliberate(self, ctx: dict[str, Any]) -> SwarmConsensus:
        r1 = [a.initial_vote(ctx) for a in self._agents]
        challenge_log: list[str] = []
        peer: list[str] = []
        for v in r1:
            challenge_log.extend(f"{v.agent_id}:{c}" for c in v.challenges)
            peer.extend(v.challenges)

        peer_t = tuple(peer)
        r2 = [a.challenged_vote(ctx, peer_challenges=peer_t) for a in self._agents]

        risk_veto = any(v.veto for v in r2 if v.agent_id == "risk_guardian") or any(
            v.veto for v in r1 if v.agent_id == "risk_guardian"
        )
        weights = {"creativity": 1.0, "risk_guardian": 1.35, "execution": 1.1, "reflection": 1.05, "dream": 0.95}
        w_sum = sum(weights.get(v.agent_id, 1.0) for v in r2)
        collective = sum(v.score * weights.get(v.agent_id, 1.0) for v in r2) / max(1e-9, w_sum)
        approvals = sum(1 for v in r2 if v.approve)
        allow = not risk_veto and approvals >= 3 and collective >= 0.38

        return SwarmConsensus(
            allow_promotion=bool(allow),
            collective_score=float(collective),
            risk_veto=bool(risk_veto),
            round_one=list(r1),
            round_two=list(r2),
            challenge_log=challenge_log,
        )
