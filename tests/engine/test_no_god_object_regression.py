from __future__ import annotations

import inspect

import pytest

import lumina_core.engine as engine_exports


@pytest.mark.unit
def test_engine_exports_do_not_reimport_migrated_module_paths() -> None:
    # gegeven
    source = inspect.getsource(engine_exports)
    forbidden_fragments = [
        "from .audit_log_service import",
        "from .agent_decision_log import",
        "from .reasoning_service import",
        "from .session_guard import",
        "from .regime_detector import",
    ]

    # wanneer/dan
    for fragment in forbidden_fragments:
        assert fragment not in source
