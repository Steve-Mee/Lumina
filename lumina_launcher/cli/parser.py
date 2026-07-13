"""Argparse SSOT for ``python -m lumina_launcher``."""

from __future__ import annotations

import argparse

LOOP_MODES = ("auto", "sim", "paper", "real", "sim_real_guard", "live", "nightly")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lumina_launcher",
        description=(
            "LUMINA operator launcher — daemon SIM/Paper loops, headless smoke, birth status.\n"
            "Command Deck UI: backend on :8000 + Tauri (see usage with no args)."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python -m lumina_launcher --mode sim              # daemon full supervisor loop\n"
            "  python -m lumina_launcher --mode paper --foreground # blocking loop\n"
            "  python -m lumina_launcher --headless --mode sim   # 24/7 production headless\n"
            "  python -m lumina_launcher --smoke --mode sim --duration 15m\n"
            "  python -m lumina_launcher birth status --json\n"
            "  python -m lumina_launcher birth watch --interval 5\n"
        ),
    )
    parser.add_argument(
        "--mode",
        default=None,
        choices=LOOP_MODES,
        help="Runtime mode for full supervisor loop (daemon unless --foreground).",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Continuous 24/7 production headless runtime (full supervisor stack).",
    )
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="One-shot HeadlessRuntime smoke/CI validation.",
    )
    parser.add_argument(
        "--foreground",
        action="store_true",
        help="Run full loop in foreground (blocking); default is daemon background.",
    )
    parser.add_argument("--duration", default=None, help="Smoke duration (e.g. 15m, 1h). Requires --smoke.")
    parser.add_argument("--broker", choices=["paper", "live"], default=None, help="Headless broker backend.")
    parser.add_argument("--sim-only", action="store_true", help="Force SIM runtime behavior.")
    parser.add_argument("--real-safe", action="store_true", help="REAL runtime with safety gates.")
    parser.add_argument("--aggressive-sim", action="store_true", help="Aggressive SIM profile (headless).")
    parser.add_argument("--overnight-sim", action="store_true", help="Overnight SIM profile (headless).")
    parser.add_argument(
        "--stability-check",
        action="store_true",
        help="Run SIM stability checker (implies --smoke one-shot).",
    )

    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")
    birth = subparsers.add_parser("birth", help="Birth Phase status reporting")
    birth_sub = birth.add_subparsers(dest="birth_command", required=True)
    status = birth_sub.add_parser("status", help="One-shot birth status")
    status.add_argument("--json", action="store_true", help="Print compact JSON summary")
    watch = birth_sub.add_parser("watch", help="Poll birth progress and emit telemetry on change")
    watch.add_argument("--interval", type=int, default=5, help="Poll interval seconds (default 5)")

    return parser


def parse_argv(argv: list[str]) -> argparse.Namespace:
    parser = build_parser()
    return parser.parse_args(argv)
