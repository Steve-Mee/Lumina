"""Independent research-time Risk Core. Propose-only. Stdlib only.

This is an additional layer. It does not replace lumina_core/risk.
"""

from __future__ import annotations

from lumina_research.risk_core.config import RiskConfig, load_default_config
from lumina_research.risk_core.engine import RiskCore, propose_order
from lumina_research.risk_core.seal import install_module_seal
from lumina_research.risk_core.types import (
    INSTRUMENT_CLUSTERS,
    Decision,
    DecisionKind,
    OrderProposal,
    cluster_for,
)

__all__ = [
    "INSTRUMENT_CLUSTERS",
    "Decision",
    "DecisionKind",
    "OrderProposal",
    "RiskConfig",
    "RiskCore",
    "cluster_for",
    "load_default_config",
    "propose_order",
]

install_module_seal(
    __name__,
    (
        "Decision",
        "DecisionKind",
        "INSTRUMENT_CLUSTERS",
        "OrderProposal",
        "RiskConfig",
        "RiskCore",
        "cluster_for",
        "load_default_config",
        "propose_order",
    ),
)
