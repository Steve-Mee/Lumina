from __future__ import annotations

from enum import Enum
from typing import Callable, Dict, List

import networkx as nx


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
        handlers: Dict[DecisionNode | str, Callable[[object, str], bool | None]] = {}
        if blackboard is not None:
            handlers_obj = getattr(blackboard, "_decision_graph_handlers", {})
            if isinstance(handlers_obj, dict):
                handlers = handlers_obj

        for node in nx.topological_sort(self.graph):
            handler = handlers.get(node) or handlers.get(node.value)
            if callable(handler):
                ok = handler(blackboard, current_mode)
                if ok is False:
                    return False
                continue

            # Backward-compatible fallback: run legacy supervisor flow on execution stage.
            if node == DecisionNode.EXECUTION and blackboard is not None:
                legacy_flow = getattr(blackboard, "_legacy_supervisor_loop", None)
                if callable(legacy_flow):
                    legacy_flow()
                    return True

        return True
