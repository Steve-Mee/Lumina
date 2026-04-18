from __future__ import annotations

from enum import Enum
from typing import Callable, Dict

import networkx as nx

from .errors import ErrorSeverity, LuminaError


class DecisionNode(Enum):
    MARKET_DATA = "market_data"
    AGENT_PROPOSALS = "agent_proposals"
    RISK_GATES = "risk_gates"
    POLICY_ENGINE = "policy_engine"
    EXECUTION = "execution"
    RECONCILIATION = "reconciliation"


class DecisionGraph:
    def __init__(self, mode: str):
        self.graph = nx.DiGraph()
        self.mode = mode
        self._build_graph()

    def _build_graph(self) -> None:
        # Volgorde is HARD en immutable per mode
        self.graph.add_edge(DecisionNode.MARKET_DATA, DecisionNode.AGENT_PROPOSALS)
        self.graph.add_edge(DecisionNode.AGENT_PROPOSALS, DecisionNode.RISK_GATES)
        self.graph.add_edge(DecisionNode.RISK_GATES, DecisionNode.POLICY_ENGINE)
        self.graph.add_edge(DecisionNode.POLICY_ENGINE, DecisionNode.EXECUTION)
        self.graph.add_edge(DecisionNode.EXECUTION, DecisionNode.RECONCILIATION)

    def execute(self, blackboard, current_mode: str) -> bool:
        if blackboard is None:
            raise LuminaError(
                severity=ErrorSeverity.FATAL_UNRECOVERABLE,
                code="DECISION_GRAPH_BLACKBOARD_MISSING",
                message="DecisionGraph requires a blackboard instance with registered handlers.",
            )
        handlers_obj = getattr(blackboard, "_decision_graph_handlers", None)
        if not isinstance(handlers_obj, dict):
            raise LuminaError(
                severity=ErrorSeverity.FATAL_UNRECOVERABLE,
                code="DECISION_GRAPH_HANDLERS_MISSING",
                message="Blackboard is missing _decision_graph_handlers mapping.",
            )
        handlers: Dict[DecisionNode | str, Callable[[object, str], bool | None]] = handlers_obj

        for node in nx.topological_sort(self.graph):
            handler = handlers.get(node) or handlers.get(node.value)
            if not callable(handler):
                raise LuminaError(
                    severity=ErrorSeverity.FATAL_UNRECOVERABLE,
                    code="DECISION_GRAPH_HANDLER_UNDEFINED",
                    message=f"No callable handler registered for node '{node.value}'.",
                )
            ok = handler(blackboard, current_mode)
            if ok is False:
                return False

        return True
