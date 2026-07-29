"""Run Wave B PR-B0 targeted tests."""
from __future__ import annotations

import subprocess
import sys

TARGETS = [
    "tests/birth/test_certificate_pipeline_god_surfaces.py",
    "tests/birth/test_certificate_evaluator.py",
    "tests/birth/test_certificate_runway.py",
    "tests/birth/test_certificate_fast_path.py",
    "tests/birth/test_certificate_schema.py",
    "tests/birth/test_starship_birth.py",
    "tests/birth/test_plateau_escalator.py",
    "tests/birth/test_plateau_dead_zone_beyond_gate.py",
    "tests/birth/test_plateau_phantom_step_cap.py",
    "tests/birth/test_plateau_quarantine.py",
    "tests/birth/test_plateau_handler_bus.py",
    "tests/birth/test_plateau_escalator_god_surfaces.py",
    "tests/test_approval_twin_agent.py",
    "tests/birth/test_expectancy_hygiene_alignment.py",
]

raise SystemExit(
    subprocess.call([sys.executable, "-m", "pytest", *TARGETS, "-q", "--tb=line"])
)
