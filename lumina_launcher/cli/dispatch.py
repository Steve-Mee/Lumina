"""Route parsed CLI args to runtime and birth handlers."""

from __future__ import annotations

import argparse
import sys

from lumina_launcher.cli.parser import parse_argv
from lumina_launcher.runtime.headless import run_headless
from lumina_launcher.runtime.loop import run_loop_daemon, run_loop_foreground

_HEADLESS_LOOP_FLAGS = (
    "--duration",
    "--broker",
    "--sim-only",
    "--real-safe",
    "--aggressive-sim",
    "--overnight-sim",
    "--stability-check",
    "--parallel-realities",
    "--set-ohlc-dna-stress",
    "--set-neuro-ohlc-rollouts",
    "--test-bypass-readiness-gate",
    "--run-human-loop",
)


def _print_usage() -> None:
    print(
        "LUMINA launcher — Neural Command Deck is the operator UI.\n"
        "\n"
        "Start the Command Deck:\n"
        "  1. Backend:  .\\lumina_os\\run_backend.ps1   (or uvicorn on :8000)\n"
        "  2. Desktop:    cd tauri-app && npm run tauri dev\n"
        "\n"
        "Autonomous SIM/Paper loop (daemon, prints PID):\n"
        "  python -m lumina_launcher --mode sim\n"
        "  python -m lumina_launcher --mode paper\n"
        "\n"
        "Headless smoke (one-shot CI):\n"
        "  python -m lumina_launcher --smoke --mode sim --duration 15m\n"
        "\n"
        "Production headless (24/7):\n"
        "  python -m lumina_launcher --headless --mode sim\n"
        "\n"
        "Birth Phase status:\n"
        "  python -m lumina_launcher birth status --json\n"
        "  python -m lumina_launcher birth phase2-status\n"
        "\n"
        "Approval Twin train (local labels + light RLHF):\n"
        "  python -m lumina_launcher twin metrics\n"
        "  python -m lumina_launcher twin review --limit 5\n"
        "  python -m lumina_launcher twin train\n"
        "\n"
        "First install:\n"
        "  python scripts/bootstrap_lumina.py\n"
        "\n"
        "Full help: python -m lumina_launcher --help\n"
    )


def _extra_runtime_argv(args: argparse.Namespace, raw_argv: list[str]) -> list[str]:
    extra: list[str] = []
    if args.real_safe:
        extra.append("--real-safe")
    if args.sim_only:
        extra.append("--sim-only")
    if args.aggressive_sim:
        extra.append("--aggressive-sim")
    if args.overnight_sim:
        extra.append("--overnight-sim")
    if args.stability_check:
        extra.append("--stability-check")
    if args.duration:
        extra.append(f"--duration={args.duration}")
    if args.broker:
        extra.append(f"--broker={args.broker}")

    i = 0
    while i < len(raw_argv):
        token = raw_argv[i]
        if token in {"--duration", "--broker", "--parallel-realities", "--set-ohlc-dna-stress", "--set-neuro-ohlc-rollouts"}:
            if i + 1 < len(raw_argv) and not raw_argv[i + 1].startswith("-"):
                extra.extend([token, raw_argv[i + 1]])
                i += 2
                continue
        if token.startswith("--duration=") or token.startswith("--broker="):
            extra.append(token)
        elif token in {
            "--aggressive-sim",
            "--overnight-sim",
            "--stability-check",
            "--sim-only",
            "--real-safe",
            "--run-human-loop",
            "--test-bypass-readiness-gate",
        }:
            extra.append(token)
        elif token == "--parallel-realities" or token.startswith("--parallel-realities="):
            extra.append(token)
        elif token.startswith("--set-ohlc-dna-stress") or token.startswith("--set-neuro-ohlc-rollouts"):
            extra.append(token)
        i += 1
    return extra


def _argv_to_smoke(raw_argv: list[str]) -> list[str]:
    """Pass through flags for runtime_entrypoint smoke path."""
    out = [token for token in raw_argv if token != "--headless"]
    if "--smoke" not in out:
        out.insert(0, "--smoke")
    return out


def _argv_to_production_headless(raw_argv: list[str]) -> list[str]:
    """Pass through flags for continuous production headless runtime."""
    out = [token for token in raw_argv if token != "--smoke"]
    if "--headless" not in out:
        out.insert(0, "--headless")
    return out


def _argv_to_headless(raw_argv: list[str]) -> list[str]:
    """Backward-compat alias for smoke argv builder."""
    return _argv_to_smoke(raw_argv)


def main(argv: list[str] | None = None) -> int:
    raw = list(argv if argv is not None else sys.argv[1:])
    if raw and raw[0] in {"-h", "--help"}:
        build_parser = __import__("lumina_launcher.cli.parser", fromlist=["build_parser"]).build_parser
        build_parser().print_help()
        return 0

    if not raw:
        _print_usage()
        return 0

    if raw[0] == "birth":
        from lumina_launcher.birth.status_cli import (
            run_birth_status,
            run_birth_watch,
            run_phase2_status,
        )

        args = parse_argv(raw)
        if args.birth_command == "status":
            return run_birth_status(as_json=bool(args.json))
        if args.birth_command == "watch":
            return run_birth_watch(interval_sec=max(1, int(args.interval)))
        if args.birth_command == "phase2-status":
            return run_phase2_status(
                as_json=bool(getattr(args, "json", False)),
                window_hours=int(getattr(args, "window_hours", 24) or 24),
            )
        print("Unknown birth subcommand.", file=sys.stderr)
        return 2

    if raw[0] == "twin":
        from lumina_launcher.twin_cli import main as twin_main

        # twin_cli.main expects subcommand first (review|train|metrics)
        return twin_main(raw[1:] if len(raw) > 1 else ["metrics"])

    args = parse_argv(raw)

    if bool(args.headless):
        return run_headless(_argv_to_production_headless(raw))

    smoke = bool(args.smoke) or bool(args.stability_check) or bool(args.duration)
    if smoke:
        return run_headless(_argv_to_smoke(raw))

    if args.mode is not None:
        mode = str(args.mode)
        extra = _extra_runtime_argv(args, raw)
        if args.foreground:
            return run_loop_foreground(mode, extra_argv=extra)
        return run_loop_daemon(mode, extra_argv=extra)

    if any(token.startswith(f) or token == f.rstrip("=") for token in raw for f in _HEADLESS_LOOP_FLAGS):
        return run_headless(_argv_to_smoke(raw))

    _print_usage()
    return 0
