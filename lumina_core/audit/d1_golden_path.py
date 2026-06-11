"""
Phase 3 D1 — Live campaign golden path verification.

Re-validates one-human-20-min audit artifacts against genuine D4 campaign context IDs
(production-path evidence, not illustrative-only).

Library-first; CLI: scripts/phase3_d1_golden_path_verify.py
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from lumina_core.audit.aperture_audit_artifact import (
    build_aperture_audit_artifact,
    discover_recent_final_arbitration_ctxs,
    export_aperture_audit_bundle,
    format_aperture_audit_as_markdown,
    format_compact_aperture_audit,
)

REQUIRED_ARTIFACT_KEYS = frozenset(
    {
        "decision_context_id",
        "generated_at",
        "summary",
        "constitution_checks",
        "risk_numbers",
        "agent_dna_lineage",
        "execution",
        "aperture_context",
        "lineage_chain",
        "raw_sources",
        "missing_data",
    }
)


def find_latest_d4_evidence_json(audits_dir: Path | None = None) -> Path | None:
    root = audits_dir or Path("state/audits")
    if not root.is_dir():
        return None
    candidates = sorted(
        root.glob("d4_genuine_campaign_evidence_*.json"),
        key=lambda p: p.stat().st_mtime if p.exists() else 0,
        reverse=True,
    )
    return candidates[0] if candidates else None


def load_genuine_d4_context_ids(
    *,
    audits_dir: Path | None = None,
    evidence_json: Path | None = None,
    max_ctxs: int = 30,
) -> tuple[list[str], dict[str, Any]]:
    """
    Load decision_context_ids from the latest genuine D4 evidence JSON bundle.

    Returns (ctx_ids, metadata dict from evidence file).
    """
    path = evidence_json or find_latest_d4_evidence_json(audits_dir)
    if path is None or not path.exists():
        return [], {"error": "no d4_genuine_campaign_evidence_*.json found"}

    data = json.loads(path.read_text(encoding="utf-8"))
    reports = data.get("reports") or []
    ctxs: list[str] = []
    for r in reports:
        if not isinstance(r, dict):
            continue
        cid = str(r.get("ctx", "") or "").strip()
        if cid and cid not in ctxs:
            ctxs.append(cid)
    return ctxs[:max_ctxs], {
        "evidence_path": str(path),
        "data_source": data.get("data_source"),
        "total": data.get("total"),
        "unsafe_caught": data.get("unsafe_caught"),
    }


def validate_artifact_contract(artifact: dict[str, Any], *, ctx: str) -> list[str]:
    """Return list of contract violations (empty = ok)."""
    issues: list[str] = []
    if not isinstance(artifact, dict):
        return ["artifact is not a dict"]
    if artifact.get("error"):
        issues.append(f"build error: {artifact.get('error')}")
    missing_keys = REQUIRED_ARTIFACT_KEYS - set(artifact.keys())
    if missing_keys:
        issues.append(f"missing keys: {sorted(missing_keys)}")
    if str(artifact.get("decision_context_id", "")) != ctx:
        issues.append("decision_context_id mismatch")
    return issues


def verify_d1_context(
    ctx: str,
    *,
    output_dir: Path | None = None,
    export: bool = True,
) -> dict[str, Any]:
    """Build + validate D1 artifact for one context id."""
    artifact = build_aperture_audit_artifact(ctx)
    issues = validate_artifact_contract(artifact, ctx=ctx)
    compact = format_compact_aperture_audit(artifact)
    markdown = format_aperture_audit_as_markdown(artifact)

    if ctx not in compact:
        issues.append("compact audit missing ctx id")
    if len(markdown) < 200:
        issues.append("markdown output too short for human review")
    if "# Aperture Audit Artifact" not in markdown:
        issues.append("markdown missing title")

    export_paths: tuple[Path | None, Path | None] = (None, None)
    if export and output_dir is not None:
        export_paths = export_aperture_audit_bundle(ctx, output_dir)
        if export_paths[0] is None:
            issues.append("export bundle failed")

    return {
        "ctx": ctx,
        "ok": len(issues) == 0,
        "issues": issues,
        "compact_preview": compact[:400],
        "export_md": str(export_paths[0]) if export_paths[0] else None,
        "export_json": str(export_paths[1]) if export_paths[1] else None,
    }


def run_d1_golden_path_verify(
    *,
    repo_root: Path | None = None,
    audits_dir: Path | None = None,
    min_verified: int = 3,
    sample_unsafe: int = 2,
    export: bool = True,
) -> dict[str, Any]:
    """
    Golden path: verify D1 artifacts for genuine D4 campaign ctxs + discovery smoke.
    """
    root = repo_root or Path.cwd()
    adir = audits_dir or (root / "state" / "audits")
    ctxs, meta = load_genuine_d4_context_ids(audits_dir=adir)
    if not ctxs:
        return {
            "ok": False,
            "error": "no genuine D4 context ids",
            "meta": meta,
            "results": [],
        }

    unsafe_ctxs = [c for c in ctxs if "unsafe" in c.lower()]
    safe_ctxs = [c for c in ctxs if c not in unsafe_ctxs]
    sample: list[str] = []
    sample.extend(unsafe_ctxs[: max(0, sample_unsafe)])
    for c in safe_ctxs:
        if len(sample) >= min_verified:
            break
        if c not in sample:
            sample.append(c)
    for c in ctxs:
        if len(sample) >= min_verified:
            break
        if c not in sample:
            sample.append(c)

    out_dir = adir / "d1_golden_path_verify" if export else None
    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)

    results = [verify_d1_context(c, output_dir=out_dir, export=export) for c in sample]
    verified_ok = sum(1 for r in results if r.get("ok"))

    discover_ok = False
    discover_note = ""
    campaign_jsonls = sorted(
        adir.glob("genuine_d4_campaign_*/genuine_final_arbitration_campaign.jsonl"),
        key=lambda p: p.stat().st_mtime if p.exists() else 0,
        reverse=True,
    )
    if campaign_jsonls:
        latest_log = campaign_jsonls[0]
        prev = os.environ.get("LUMINA_TRADE_DECISION_AUDIT_LOG")
        try:
            os.environ["LUMINA_TRADE_DECISION_AUDIT_LOG"] = str(latest_log)
            discovered = discover_recent_final_arbitration_ctxs(max_ctxs=30)
            discover_ok = any(c in discovered for c in sample[:3])
            discover_note = f"discover_recent: {len(discovered)} from {latest_log.name}"
        finally:
            if prev is None:
                os.environ.pop("LUMINA_TRADE_DECISION_AUDIT_LOG", None)
            else:
                os.environ["LUMINA_TRADE_DECISION_AUDIT_LOG"] = prev
        if not discover_ok:
            try:
                tail = latest_log.read_text(encoding="utf-8", errors="ignore")[-200_000:]
                discover_ok = any(c in tail for c in sample[:3])
                if discover_ok:
                    discover_note += " (ctx present in campaign jsonl tail)"
            except OSError:
                pass
    else:
        discover_note = "no campaign jsonl for discover smoke (optional)"

    ok = verified_ok >= min_verified and all(r.get("ok") for r in results)
    manifest = {
        "ok": ok,
        "verified_count": verified_ok,
        "min_verified": min_verified,
        "sample_size": len(results),
        "discover_smoke_ok": discover_ok,
        "discover_note": discover_note,
        "d4_meta": meta,
        "results": results,
    }
    if out_dir is not None:
        manifest_path = out_dir / "d1_golden_path_manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
        manifest["manifest_path"] = str(manifest_path)

    return manifest
