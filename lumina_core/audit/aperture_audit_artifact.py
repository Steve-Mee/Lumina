"""
Aperture Audit Artifact — Phase 3 Deliverable 1 (One Human, 20 Minutes Audit)

This module provides the official, production-grade interface for generating
self-contained, human-auditable artifacts for any decision_context_id.

It unifies:
- Cryptographic decision lineage (from decision_lineage.py)
- Full FinalArbitration constitution + risk checks
- Agent + DNA + evolution context (including D5 shadow linkage when present)
- Aperture Integrity Score snapshot
- Correlated immutable audit logs

The goal (per the 2026-05-31 90-day roadmap): one human can fully understand
provenance, constitution compliance, risk parameters, agent lineage, and
execution outcome for any trade in under 20 minutes.

Design principles (matching shadow_review.py and the approved plan):
- Library-first (importable functions for dashboards, Guardian, notebooks)
- Best-effort and non-breaking (never fails the caller)
- Clean CLI for daily human use
- Strong "Red Flags First" UX in the rendered markdown
- Explicitly surfaces Phase 2 D5 shadow protection results when available

Usage (CLI):
    python -m lumina_core.audit.aperture_audit <decision_context_id>
    python -m lumina_core.audit.aperture_audit <ctx> --export state/audits/

Usage (library):
    from lumina_core.audit.aperture_audit_artifact import (
        build_aperture_audit_artifact,
        format_aperture_audit_as_markdown,
        export_aperture_audit_bundle,
        discover_recent_final_arbitration_ctxs,  # for D4 campaign + Guardian "live from logs" real data
    )

All changes to this module must follow the Recursive Self-Improvement Protocol,
constitution-guard, risk-safety-review, and produce public evolution entries.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

# Internal imports — all best-effort and defensive
# We deliberately import inside functions where possible to keep startup light


from lumina_core.audit.aperture_audit_build import (  # noqa: E402
    build_aperture_audit_artifact,
)
from lumina_core.audit.aperture_audit_markdown import (  # noqa: E402
    format_aperture_audit_as_markdown,
)

def export_aperture_audit_bundle(
    decision_context_id: str,
    output_dir: Path | str = "state/audits",
    *,
    engine: Any = None,
) -> tuple[Path | None, Path | None]:
    """
    Convenience helper: build the artifact and write both .md and .json to disk.

    Returns (markdown_path, json_path) or (None, None) on failure.
    """
    try:
        artifact = build_aperture_audit_artifact(decision_context_id, engine=engine)
        md = format_aperture_audit_as_markdown(artifact)

        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        safe_ctx = "".join(c if c.isalnum() or c in "-_" else "_" for c in decision_context_id)
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

        md_path = out_dir / f"aperture_audit_{safe_ctx}_{ts}.md"
        json_path = out_dir / f"aperture_audit_{safe_ctx}_{ts}.json"

        md_path.write_text(md, encoding="utf-8")
        json_path.write_text(json.dumps(artifact, indent=2, default=str), encoding="utf-8")

        return md_path, json_path
    except Exception:
        # Best-effort: never break the caller
        return None, None


# =============================================================================
# CLI (modeled directly on the excellent shadow_review.py pattern)
# =============================================================================

def _main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a Phase 3 D1 Aperture Audit Artifact for a decision_context_id"
    )
    parser.add_argument("decision_context_id", help="The decision_context_id to audit")
    parser.add_argument(
        "--export",
        metavar="DIR",
        help="Export both .md and .json to this directory (e.g. state/audits)",
    )

    args = parser.parse_args()

    if args.export:
        md_path, json_path = export_aperture_audit_bundle(
            args.decision_context_id,
            output_dir=args.export,
        )
        if md_path and json_path:
            print(f"Exported:\n  Markdown: {md_path}\n  JSON:     {json_path}")
        else:
            print("Export failed (best-effort).")
    else:
        artifact = build_aperture_audit_artifact(args.decision_context_id)
        print(format_aperture_audit_as_markdown(artifact))


if __name__ == "__main__":
    _main()
