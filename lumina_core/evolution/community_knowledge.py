"""Community / external knowledge ingestion: vector queue → shadow + twin → Lumina Bible."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from lumina_bible.vector_api import VectorContributionAPI, stable_community_document_id

from lumina_core.config_loader import ConfigLoader
from lumina_core.state.state_manager import safe_append_jsonl, safe_with_file_lock

from .dna_registry import PolicyDNA
from .evolution_guard import _normalize_confidence
from .lumina_bible import LuminaBible

logger = logging.getLogger(__name__)


def _community_knowledge_config() -> dict[str, Any]:
    evolution_cfg = ConfigLoader.section("evolution", default={}) or {}
    if not isinstance(evolution_cfg, dict):
        return {}
    raw = evolution_cfg.get("community_knowledge", {})
    return raw if isinstance(raw, dict) else {}


def _normalize_queue_item(raw: dict[str, Any]) -> dict[str, Any] | None:
    hyp = str(raw.get("hypothesis", "") or raw.get("title", "")).strip()
    excerpt = str(raw.get("excerpt", "") or raw.get("detail", "") or hyp).strip()
    source = str(raw.get("source", "community")).strip().lower()
    if source not in {"paper", "trader", "community", "blog", "docs"}:
        source = "community"
    if len(hyp) < 8 or len(excerpt) < 16:
        return None
    item_id = str(raw.get("id") or stable_community_document_id(source=source, content=hyp + excerpt))
    return {"id": item_id, "hypothesis": hyp, "excerpt": excerpt, "source": source}


def append_community_queue_item(
    item: dict[str, Any],
    *,
    queue_path: Path | None = None,
) -> bool:
    """Append one external knowledge item to the JSONL queue (ingestion entry point).

    Items are only promoted into the Lumina Bible and Chroma after shadow sim + approval twin
    in :func:`run_community_knowledge_nightly`. Returns False if validation fails.
    """
    if not isinstance(item, dict) or _normalize_queue_item(item) is None:
        return False
    cfg = _community_knowledge_config()
    path = queue_path if queue_path is not None else Path(str(cfg.get("queue_path", "state/community_knowledge_queue.jsonl")))
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        safe_append_jsonl(path, item, hash_chain=False)
        return True
    except Exception as exc:
        logger.warning("[COMMUNITY_KNOWLEDGE] queue append failed: %s", exc)
        return False


def _read_queue(path: Path, *, limit: int) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except Exception:
                continue
            if isinstance(payload, dict):
                rows.append(payload)
    return rows[-max(1, int(limit)) * 3 :]


def _load_processed(path: Path) -> set[str]:
    if not path.exists():
        return set()
    try:
        return {ln.strip() for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()}
    except Exception:
        return set()


def _append_processed(path: Path, item_id: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    def _write_locked(target: Path) -> None:
        with target.open("a", encoding="utf-8") as handle:
            handle.write(str(item_id) + "\n")

    safe_with_file_lock(path, _write_locked)


def _dna_for_community_item(
    item: dict[str, Any],
    *,
    active_dna: PolicyDNA | None,
    generation_offset: int,
) -> PolicyDNA:
    content = {
        "candidate_name": f"community_{item['source']}",
        "prompt_tweak": str(item["excerpt"])[:2000],
        "regime_focus": "neutral",
        "community_knowledge": True,
        "hypothesis": str(item["hypothesis"]),
        "external_source": str(item["source"]),
    }
    gen = int(active_dna.generation) if active_dna is not None else 0
    fit = float(active_dna.fitness_score) if active_dna is not None else 0.0
    lin = str(active_dna.lineage_hash) if active_dna is not None else "COMMUNITY"
    return PolicyDNA.create(
        prompt_id="community_external",
        version="candidate",
        content=content,
        fitness_score=fit,
        generation=gen + int(generation_offset),
        lineage_hash=lin,
    )


def run_community_knowledge_nightly(
    *,
    bible: LuminaBible,
    sim_runner: Any,
    approval_twin: Any,
    guard: Any,
    active_dna: PolicyDNA | None,
    base_metrics: dict[str, Any],
    generation_offset: int,
    vector_collection: Any | None = None,
) -> dict[str, Any]:
    cfg = _community_knowledge_config()
    if not bool(cfg.get("enabled", True)):
        return {"enabled": False, "examined": 0, "committed": 0, "skipped": 0}

    max_commit = max(0, min(20, int(cfg.get("max_commit_per_generation", 3) or 3)))
    queue_path = Path(str(cfg.get("queue_path", "state/community_knowledge_queue.jsonl")))
    processed_path = Path(str(cfg.get("processed_path", "state/community_knowledge_processed.txt")))
    twin_min = float(cfg.get("twin_confidence_min", 0.82) or 0.82)

    processed = _load_processed(processed_path)
    raw_rows = _read_queue(queue_path, limit=max(max_commit * 2, 5))
    vector_api = VectorContributionAPI()

    examined = 0
    committed = 0
    skipped = 0

    for raw in raw_rows:
        if committed >= max_commit:
            break
        if not isinstance(raw, dict):
            skipped += 1
            continue
        item = _normalize_queue_item(raw)
        if item is None:
            skipped += 1
            continue
        if item["id"] in processed:
            skipped += 1
            continue

        examined += 1
        dna = _dna_for_community_item(item, active_dna=active_dna, generation_offset=generation_offset)

        try:
            shadow = sim_runner.evaluate_variants(
                [dna],
                days=1,
                nightly_report=dict(base_metrics),
                shadow_mode=True,
            )
        except Exception as exc:
            logger.warning("[COMMUNITY_KNOWLEDGE] shadow sim failed: %s", exc)
            skipped += 1
            continue

        if not shadow:
            skipped += 1
            continue
        sh0 = shadow[0]
        shadow_pnl = float(getattr(sh0, "avg_pnl", 0.0) or 0.0)
        shadow_ok = guard.shadow_validation_passed(
            shadow_total_pnl=shadow_pnl,
            veto_blocked=False,
            risk_flags=[],
        )
        if not shadow_ok:
            skipped += 1
            continue

        twin: dict[str, Any] = {}
        try:
            if approval_twin is not None and hasattr(approval_twin, "evaluate_dna_promotion"):
                twin = dict(approval_twin.evaluate_dna_promotion(dna) or {})
        except Exception as exc:
            logger.warning("[COMMUNITY_KNOWLEDGE] twin eval failed: %s", exc)
            skipped += 1
            continue

        if not bool(twin.get("recommendation", False)):
            skipped += 1
            continue
        t_flags = [str(x) for x in list(twin.get("risk_flags", []) or [])]
        if len(t_flags) > 0:
            skipped += 1
            continue
        if _normalize_confidence(float(twin.get("confidence", 0.0) or 0.0)) < twin_min:
            skipped += 1
            continue

        try:
            bible.append_community_external_rule(
                source=str(item["source"]),
                hypothesis=str(item["hypothesis"]),
                excerpt=str(item["excerpt"]),
                vetting="shadow_twin_ok",
                fitness=float(getattr(sh0, "fitness", 0.0) or 0.0),
                generation=int(getattr(dna, "generation", 0) or 0),
                lineage_hash=str(getattr(dna, "lineage_hash", "COMMUNITY") or "COMMUNITY"),
            )
        except Exception as exc:
            logger.warning("[COMMUNITY_KNOWLEDGE] bible append failed: %s", exc)
            skipped += 1
            continue

        vec_ok = vector_api.upload_community_vetted(
            vector_collection,
            document=f"{item['hypothesis']}\n\n{item['excerpt']}",
            source=str(item["source"]),
            metadata={
                "hypothesis": item["hypothesis"][:512],
                "generation": int(generation_offset),
                "document_id": item["id"],
            },
        )
        if vector_collection is not None and not vec_ok:
            logger.warning(
                "[COMMUNITY_KNOWLEDGE] Chroma upsert failed after bible commit; id=%s",
                str(item["id"])[:40],
            )

        _append_processed(processed_path, item["id"])
        processed.add(item["id"])
        committed += 1

    return {
        "enabled": True,
        "examined": examined,
        "committed": committed,
        "skipped": skipped,
        "queue_path": str(queue_path),
    }
