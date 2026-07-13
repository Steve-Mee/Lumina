"""Per-module coverage gate for birth autonomy, Event Bus, and safety paths."""

from __future__ import annotations

import argparse
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORT_PATH = ROOT / "reports" / "module_coverage.xml"

MODULE_COVERAGE_MANIFEST: tuple[str, ...] = (
    "lumina_core/birth/organism_autonomy.py",
    "lumina_core/birth/organism_autonomy_handler.py",
    "lumina_core/birth/meta_controller_handler.py",
    "lumina_core/birth/adaptation_recovery_engine.py",
    "lumina_core/birth/birth_bus_client.py",
    "lumina_core/birth/birth_bus_choreography.py",
    "lumina_core/birth/birth_bus_serde.py",
    "lumina_core/birth/birth_handler_registry.py",
    "lumina_core/birth/wall_adaptation_handler.py",
    "lumina_core/agent_orchestration/event_bus.py",
    "lumina_core/agent_orchestration/schemas.py",
    "lumina_core/birth/birth_constitution_guard.py",
    "lumina_core/birth/constitution_enforcer.py",
    "lumina_core/birth/death_spiral_guard.py",
    "lumina_core/risk/aperture_guard.py",
    "lumina_core/risk/shadow.py",
)


def _cov_source(module_path: str) -> str:
    """Map manifest path to pytest-cov source (package.module)."""
    return module_path.replace("/", ".").removesuffix(".py")

TEST_TARGETS: tuple[str, ...] = (
    "tests/birth/test_birth_bus_client_fallbacks.py",
    "tests/birth/test_birth_bus_client_coverage.py",
    "tests/birth/test_birth_bus_client.py",
    "tests/birth/test_meta_controller_handler_signals.py",
    "tests/birth/test_wall_adaptation_handler_signals.py",
    "tests/birth/test_safety_guard_coverage.py",
    "tests/birth",
    "tests/agent_orchestration",
    "tests/safety",
    "tests/risk/test_shadow_risk_evaluator.py",
    "tests/test_aperture_guard.py",
)


def _normalize_path(path: str) -> str:
    return path.replace("\\", "/").lstrip("./")


def _line_rate_for_class(class_elem: ET.Element) -> float:
    line_rate = class_elem.get("line-rate")
    if line_rate is not None:
        return float(line_rate) * 100.0
    lines_valid = int(class_elem.get("lines-valid", "0") or 0)
    lines_covered = int(class_elem.get("lines-covered", "0") or 0)
    if lines_valid <= 0:
        return 100.0
    return (lines_covered / lines_valid) * 100.0


def parse_coverage_rates(report_path: Path) -> dict[str, float]:
    tree = ET.parse(report_path)
    rates: dict[str, float] = {}
    for package in tree.getroot().iter("package"):
        for class_elem in package.iter("class"):
            filename = class_elem.get("filename")
            if not filename:
                continue
            rates[_normalize_path(filename)] = _line_rate_for_class(class_elem)
    return rates


def _rate_for_module(rates: dict[str, float], module: str) -> float | None:
    norm = _normalize_path(module)
    short = norm.replace("lumina_core/", "", 1)
    basename = Path(norm).name
    candidates = (
        norm,
        short,
        f"birth/{basename}",
        f"agent_orchestration/{basename}",
        f"risk/{basename}",
    )
    for key in candidates:
        if key in rates:
            return rates[key]
    return None


def run_coverage_pytest() -> int:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    if REPORT_PATH.exists():
        REPORT_PATH.unlink()

    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "-m",
        "not slow and not nightly",
        "--timeout=30",
        "-q",
        "--cov=lumina_core",
        f"--cov-report=xml:{REPORT_PATH}",
        *TEST_TARGETS,
    ]
    print("Running:", " ".join(cmd))
    return int(subprocess.run(cmd, cwd=str(ROOT)).returncode)


def check_manifest(*, fail_under: float) -> int:
    if not REPORT_PATH.exists():
        print(f"Coverage report missing: {REPORT_PATH}", file=sys.stderr)
        return 1

    rates = parse_coverage_rates(REPORT_PATH)
    failures: list[str] = []
    print(f"\nModule coverage gate (threshold={fail_under:.1f}%):")
    for module in MODULE_COVERAGE_MANIFEST:
        rate = _rate_for_module(rates, module)
        if rate is None:
            failures.append(f"{module}: not found in coverage report")
            print(f"  FAIL {module}: missing from report")
            continue
        status = "OK" if rate >= fail_under else "FAIL"
        print(f"  {status} {module}: {rate:.1f}%")
        if rate < fail_under:
            failures.append(f"{module}: {rate:.1f}% < {fail_under:.1f}%")

    if failures:
        print("\nModule coverage gate FAILED:", file=sys.stderr)
        for item in failures:
            print(f"  - {item}", file=sys.stderr)
        return 1

    print("\nModule coverage gate PASSED")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Birth autonomy / Event Bus / safety module coverage gate")
    parser.add_argument("--fail-under", type=float, default=85.0, help="Minimum line coverage percent per module")
    parser.add_argument("--report-only", action="store_true", help="Only check existing coverage XML")
    args = parser.parse_args()

    pytest_rc = 0
    if not args.report_only:
        pytest_rc = run_coverage_pytest()

    if not REPORT_PATH.exists():
        return pytest_rc if pytest_rc != 0 else 1

    manifest_rc = check_manifest(fail_under=float(args.fail_under))
    if manifest_rc != 0:
        return manifest_rc
    return pytest_rc


if __name__ == "__main__":
    raise SystemExit(main())
