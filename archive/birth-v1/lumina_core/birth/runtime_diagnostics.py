"""Birth runtime diagnostics — pin process, module paths, code fingerprints.

Used to prove which code is loaded when Stage-2 quality/geometry goes wrong.
SSOT for identity is progress JSON (``birth_code_fingerprint``). Logs are the
loud channel: WARNING only when identity or geometry is defective; healthy
boot is one INFO line per process.
"""

from __future__ import annotations

import hashlib
import os
import sys
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.runtime_diagnostics")

# Bump when diagnostic contract changes so progress file proves new binary.
# v4: time-ordered geometry forensics (shuffle-poison reject + contiguous windows).
BIRTH_DIAG_CONTRACT = "quality_geom_v4"

_FINGERPRINT_CACHE: dict[str, Any] | None = None
_LAST_PROGRESS_DIAG_LOG_AT = 0.0
_HEALTHY_FINGERPRINT_LOGGED = False
_HEALTHY_PROGRESS_LOGGED = False

_REQUIRED_FEATURE_TRUTH: tuple[tuple[str, str], ...] = (
    ("periodic_has_failclosed", "periodic_failclosed_missing"),
    ("enrich_emits_birth_trade_stop", "geom_enrich_missing"),
    ("coerce_meta_plan", "coerce_missing"),
    ("geometry_has_is_time_ordered", "geometry_time_guard_missing"),
    ("geometry_rejects_disordered", "geometry_poison_reject_missing"),
)


def reset_runtime_diagnostics_for_tests() -> None:
    """Clear process-once gates and fingerprint cache. Tests only."""
    global _FINGERPRINT_CACHE, _LAST_PROGRESS_DIAG_LOG_AT
    global _HEALTHY_FINGERPRINT_LOGGED, _HEALTHY_PROGRESS_LOGGED
    _FINGERPRINT_CACHE = None
    _LAST_PROGRESS_DIAG_LOG_AT = 0.0
    _HEALTHY_FINGERPRINT_LOGGED = False
    _HEALTHY_PROGRESS_LOGGED = False


def _file_mtime(path: Path) -> str:
    try:
        return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(path.stat().st_mtime))
    except OSError:
        return "missing"


def _short_hash(path: Path, *, nbytes: int = 4096) -> str:
    try:
        data = path.read_bytes()[: max(64, int(nbytes))]
        return hashlib.sha256(data).hexdigest()[:12]
    except OSError:
        return "unreadable"


def _module_path(mod_name: str) -> Path | None:
    try:
        mod = sys.modules.get(mod_name)
        if mod is None:
            __import__(mod_name)
            mod = sys.modules.get(mod_name)
        if mod is None:
            return None
        p = getattr(mod, "__file__", None)
        return Path(p) if p else None
    except Exception:
        return None


def _repo_root() -> Path:
    """Lumina checkout root: ``<repo>/lumina_core/birth/runtime_diagnostics.py`` → parents[2]."""
    return Path(__file__).resolve().parents[2]


def _path_in_repo(path: object) -> bool:
    """True when *path* resolves under (or is) the Lumina repo root.

    Empty / ``.`` sys.path entries mean cwd — resolve them. Prefer real path
    containment over a folder-name substring so Linux CI checkouts, xdist
    workers, and editable installs still count as on-tree.
    """
    raw = str(path or "").strip()
    try:
        root = _repo_root()
        candidate = Path.cwd() if raw in {"", "."} else Path(raw)
        resolved = candidate.resolve()
        return resolved == root or root in resolved.parents
    except (OSError, RuntimeError, ValueError):
        return "ninjatraderai_bot" in raw.replace("\\", "/").lower()


def _macro_stop_threshold() -> float:
    try:
        from lumina_core.birth.birth_trade_geometry import MACRO_STOP_THRESHOLD

        return float(MACRO_STOP_THRESHOLD)
    except Exception:
        return 0.005


def collect_birth_code_fingerprint() -> dict[str, Any]:
    """Process + critical module paths/mtimes/hashes for live forensics."""
    global _FINGERPRINT_CACHE
    if _FINGERPRINT_CACHE is not None:
        # Refresh only mtime fields occasionally is unnecessary; cache per process.
        return dict(_FINGERPRINT_CACHE)

    modules = (
        "lumina_core.birth.meta_decide_periodic",
        "lumina_core.birth.meta_decide_after_rollout",
        "lumina_core.birth.meta_decide_pre_rollout",
        "lumina_core.birth.stage_loop_meta",
        "lumina_core.birth.stage_loop_progress_write_enrich",
        "lumina_core.birth.stage_loop_progress_metrics",
        "lumina_core.birth.expectancy_stall",
        "lumina_core.birth.birth_trade_geometry",
        "lumina_core.birth.stage_loop_data_cache",
        "lumina_core.birth.runtime_diagnostics",
    )
    mod_info: dict[str, Any] = {}
    hash_parts: list[str] = [BIRTH_DIAG_CONTRACT]
    for name in modules:
        path = _module_path(name)
        if path is None:
            mod_info[name] = {"path": None, "mtime": "import_failed", "sha12": "na"}
            continue
        sha = _short_hash(path)
        mod_info[name] = {
            "path": str(path.resolve()) if path.exists() else str(path),
            "mtime": _file_mtime(path),
            "sha12": sha,
        }
        hash_parts.append(f"{name}:{sha}")

    # Feature probes — prove functions exist in loaded code.
    features: dict[str, Any] = {}
    try:
        from lumina_core.birth.expectancy_stall import (
            coerce_meta_plan_under_expectancy_quality,
            loop_expectancy_stall,
            stage2_quality_owns,
        )

        features["coerce_meta_plan"] = callable(coerce_meta_plan_under_expectancy_quality)
        features["loop_expectancy_stall"] = callable(loop_expectancy_stall)
        features["stage2_quality_owns"] = callable(stage2_quality_owns)
    except Exception as exc:
        features["expectancy_stall_import_error"] = True
        features["expectancy_stall_error"] = str(exc)[:200]

    try:
        from lumina_core.birth.meta_decide_periodic import MetaDecidePeriodicMixin
        import inspect

        src = inspect.getsource(MetaDecidePeriodicMixin.decide_periodic_review)
        features["periodic_has_failclosed"] = "stage2_expectancy_failclosed" in src
        features["periodic_has_quality_log"] = "birth.meta.expectancy_quality" in src
        features["periodic_still_has_thrash_string"] = (
            "periodic_declining_pattern_focus_explore" in src
        )
    except Exception as exc:
        features["periodic_probe_error"] = str(exc)[:200]

    try:
        from lumina_core.birth.stage_loop_progress_write_enrich import (
            StageLoopProgressWriteEnrichMixin,
        )
        import inspect

        src = inspect.getsource(StageLoopProgressWriteEnrichMixin._enrich_progress_scorecard)
        features["enrich_emits_birth_trade_stop"] = "birth_trade_stop_pct" in src
        features["enrich_always_zero_fallback"] = "else 0.0" in src
        features["enrich_emits_geometry_time_ordered"] = "geometry_time_ordered" in src
    except Exception as exc:
        features["enrich_probe_error"] = str(exc)[:200]

    try:
        from lumina_core.birth.birth_trade_geometry import (
            is_time_ordered,
            calibrate_birth_stops,
        )
        import inspect

        features["geometry_has_is_time_ordered"] = callable(is_time_ordered)
        gsrc = inspect.getsource(calibrate_birth_stops)
        features["geometry_rejects_disordered"] = "poison_shuffle" in gsrc or "disordered" in gsrc
    except Exception as exc:
        features["geometry_probe_error"] = str(exc)[:200]

    fingerprint = hashlib.sha256("|".join(hash_parts).encode("utf-8")).hexdigest()[:16]
    payload = {
        "birth_diag_contract": BIRTH_DIAG_CONTRACT,
        "birth_code_fingerprint": fingerprint,
        "pid": int(os.getpid()),
        "ppid": int(os.getppid()) if hasattr(os, "getppid") else 0,
        "python_executable": sys.executable,
        "cwd": str(Path.cwd()),
        "sys_path0": str(sys.path[0]) if sys.path else "",
        "sys_path_repo_hit": any(_path_in_repo(p) for p in sys.path),
        "modules": mod_info,
        "features": features,
        "collected_at": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()),
    }
    _FINGERPRINT_CACHE = payload
    return dict(payload)


def fingerprint_identity_defects(fp: Mapping[str, Any] | None) -> list[str]:
    """Return plant-law identity failures. Empty list means loaded code is healthy."""
    if not fp:
        return ["fingerprint_missing"]
    defects: list[str] = []
    if str(fp.get("birth_diag_contract") or "") != BIRTH_DIAG_CONTRACT:
        defects.append("contract_mismatch")
    if not fp.get("sys_path_repo_hit"):
        defects.append("repo_not_on_path")
    feats_raw = fp.get("features") or {}
    feats: Mapping[str, Any] = feats_raw if isinstance(feats_raw, Mapping) else {}
    for probe_error in (
        "expectancy_stall_import_error",
        "periodic_probe_error",
        "enrich_probe_error",
        "geometry_probe_error",
    ):
        if feats.get(probe_error):
            defects.append(str(probe_error))
    for key, code in _REQUIRED_FEATURE_TRUTH:
        if feats.get(key) is not True:
            defects.append(code)
    modules_raw = fp.get("modules") or {}
    if not isinstance(modules_raw, Mapping) or not modules_raw:
        defects.append("modules_missing")
        return defects
    for name, info in modules_raw.items():
        short = str(name).rsplit(".", 1)[-1]
        if not isinstance(info, Mapping):
            defects.append(f"module_invalid:{short}")
            continue
        path = info.get("path")
        mtime = str(info.get("mtime") or "")
        sha = str(info.get("sha12") or "")
        if path is None or mtime == "import_failed":
            defects.append(f"import_failed:{short}")
        elif sha in {"na", "unreadable", ""}:
            defects.append(f"unreadable:{short}")
        elif not _path_in_repo(path):
            defects.append(f"off_tree:{short}")
    return defects


def _log_fingerprint_line(fp: Mapping[str, Any], *, reason: str, defects: list[str]) -> None:
    emit = logger.warning if defects else logger.info
    emit(
        "birth.runtime.fingerprint reason=%s contract=%s fingerprint=%s pid=%s python=%s cwd=%s "
        "repo_on_path=%s periodic_failclosed=%s enrich_geom=%s coerce=%s defects=%s",
        reason,
        fp.get("birth_diag_contract"),
        fp.get("birth_code_fingerprint"),
        fp.get("pid"),
        fp.get("python_executable"),
        fp.get("cwd"),
        fp.get("sys_path_repo_hit"),
        (fp.get("features") or {}).get("periodic_has_failclosed")
        if isinstance(fp.get("features"), Mapping)
        else None,
        (fp.get("features") or {}).get("enrich_emits_birth_trade_stop")
        if isinstance(fp.get("features"), Mapping)
        else None,
        (fp.get("features") or {}).get("coerce_meta_plan")
        if isinstance(fp.get("features"), Mapping)
        else None,
        ",".join(defects) if defects else "none",
    )


def _log_module_lines(fp: Mapping[str, Any]) -> None:
    """Module sha dump — WARNING only, and only when identity is already defective."""
    modules = fp.get("modules")
    if not isinstance(modules, Mapping):
        return
    for name, info in modules.items():
        if not isinstance(info, Mapping):
            continue
        short = str(name).rsplit(".", 1)[-1]
        logger.warning(
            "birth.runtime.module name=%s sha12=%s mtime=%s path=%s",
            short,
            info.get("sha12"),
            info.get("mtime"),
            info.get("path"),
        )


def log_birth_code_fingerprint(*, reason: str = "startup") -> dict[str, Any]:
    """Log identity once when healthy; always WARN (with module dump) when defective."""
    global _HEALTHY_FINGERPRINT_LOGGED
    fp = collect_birth_code_fingerprint()
    defects = fingerprint_identity_defects(fp)
    if defects:
        _log_fingerprint_line(fp, reason=reason, defects=defects)
        _log_module_lines(fp)
        return fp
    if not _HEALTHY_FINGERPRINT_LOGGED:
        _HEALTHY_FINGERPRINT_LOGGED = True
        _log_fingerprint_line(fp, reason=reason, defects=defects)
    return fp


def progress_diagnostic_fields() -> dict[str, Any]:
    """Compact fields always safe to merge into birth progress JSON."""
    fp = collect_birth_code_fingerprint()
    feats_raw = fp.get("features") or {}
    feats: Mapping[str, Any] = feats_raw if isinstance(feats_raw, Mapping) else {}
    defects = fingerprint_identity_defects(fp)
    return {
        "birth_diag_contract": str(fp.get("birth_diag_contract") or ""),
        "birth_code_fingerprint": str(fp.get("birth_code_fingerprint") or ""),
        "birth_runtime_pid": int(fp.get("pid") or 0),
        "birth_runtime_python": str(fp.get("python_executable") or ""),
        "birth_runtime_cwd": str(fp.get("cwd") or ""),
        "birth_code_has_quality_failclosed": bool(feats.get("periodic_has_failclosed")),
        "birth_code_has_geom_enrich": bool(feats.get("enrich_emits_birth_trade_stop")),
        "birth_code_has_coerce": bool(feats.get("coerce_meta_plan")),
        "birth_code_has_geometry_time_guard": bool(
            feats.get("geometry_has_is_time_ordered")
            and feats.get("geometry_rejects_disordered")
        ),
        "birth_code_collected_at": str(fp.get("collected_at") or ""),
        "birth_code_identity_ok": not defects,
        "birth_code_identity_defects": list(defects),
    }


def identity_progress_fields_for_boot(*, reason: str = "birth_phase_bootstrap") -> dict[str, Any]:
    """Log identity once and return progress SSOT fields. Never raises."""
    try:
        log_birth_code_fingerprint(reason=reason)
        return progress_diagnostic_fields()
    except Exception as exc:
        logger.warning("birth.runtime.fingerprint_failed: %s", exc)
        return {
            "birth_diag_contract": "diag_error",
            "birth_code_fingerprint": f"error:{type(exc).__name__}",
            "birth_code_identity_ok": False,
            "birth_code_identity_defects": [f"bootstrap_error:{type(exc).__name__}"],
        }


def log_meta_decision_trace(
    *,
    trigger: str,
    primary: str,
    rationale: str,
    secondary: list[str] | tuple[str, ...] | None = None,
    stage: str = "",
    stage_trades: int = 0,
    stage_wins: int = 0,
    flat: float = 0.0,
    stall: bool | None = None,
    coerced: bool = False,
    source: str = "decide",
) -> None:
    """Structured meta trace. INFO — coerce already has its own WARNING at apply."""
    logger.info(
        "birth.meta.trace source=%s trigger=%s stage=%s primary=%s rationale=%s "
        "secondary=%s trades=%s wins=%s flat=%.4f stall=%s coerced=%s pid=%s fp=%s",
        source,
        trigger,
        stage,
        primary,
        rationale,
        list(secondary or ()),
        int(stage_trades),
        int(stage_wins),
        float(flat),
        stall,
        coerced,
        os.getpid(),
        (collect_birth_code_fingerprint().get("birth_code_fingerprint") or "")[:16],
    )


def _progress_write_defects(scorecard: Mapping[str, Any]) -> list[str]:
    defects: list[str] = []
    if not scorecard.get("birth_code_fingerprint"):
        defects.append("missing_fingerprint")
    if scorecard.get("birth_code_identity_ok") is False:
        defects.append("identity_not_ok")
    raw_extra = scorecard.get("birth_code_identity_defects")
    if isinstance(raw_extra, list):
        defects.extend(str(item) for item in raw_extra if item)
    src = str(scorecard.get("birth_trade_geometry_source") or "")
    try:
        stop = float(scorecard.get("birth_trade_stop_pct") or 0.0)
    except (TypeError, ValueError):
        stop = 0.0
    if src == "move_distribution" and stop >= _macro_stop_threshold():
        defects.append("macro_move_distribution")
    # Absent geometry is encoded as time_ordered=False + source=unset — not a defect.
    if (
        scorecard.get("geometry_time_ordered") is False
        and src not in {"", "unset"}
        and not bool(scorecard.get("geometry_macro_rejected"))
    ):
        defects.append("geometry_not_time_ordered")
    # Deduplicate while preserving order.
    seen: set[str] = set()
    unique: list[str] = []
    for item in defects:
        if item in seen:
            continue
        seen.add(item)
        unique.append(item)
    return unique


def log_progress_write_trace(
    *,
    phase: str,
    curriculum_stage: str,
    stage_trades: int,
    scorecard: dict[str, Any],
    throttle_sec: float = 30.0,
) -> None:
    """Log geometry/quality keys at progress write. WARNING only on defects."""
    global _LAST_PROGRESS_DIAG_LOG_AT, _HEALTHY_PROGRESS_LOGGED
    defects = _progress_write_defects(scorecard)
    keys = (
        "birth_trade_stop_pct",
        "birth_trade_geometry_source",
        "geometry_time_ordered",
        "geometry_macro_rejected",
        "expectancy_stall_detected",
        "meta_primary_strategy",
        "meta_last_rationale",
        "birth_code_fingerprint",
        "closes_stop",
    )
    present = {k: (k in scorecard) for k in keys}
    now = time.time()
    if defects:
        if _LAST_PROGRESS_DIAG_LOG_AT > 0 and (now - _LAST_PROGRESS_DIAG_LOG_AT) < throttle_sec:
            return
        _LAST_PROGRESS_DIAG_LOG_AT = now
        emit = logger.warning
    else:
        if _HEALTHY_PROGRESS_LOGGED:
            return
        _HEALTHY_PROGRESS_LOGGED = True
        emit = logger.info
    emit(
        "birth.progress.write_trace phase=%s stage=%s trades=%s keys=%s "
        "geom_stop=%s geom_src=%s meta=%s rationale=%s stall=%s fp=%s pid=%s defects=%s",
        phase,
        curriculum_stage,
        stage_trades,
        present,
        scorecard.get("birth_trade_stop_pct"),
        scorecard.get("birth_trade_geometry_source"),
        scorecard.get("meta_primary_strategy"),
        scorecard.get("meta_last_rationale"),
        scorecard.get("expectancy_stall_detected"),
        scorecard.get("birth_code_fingerprint"),
        os.getpid(),
        ",".join(defects) if defects else "none",
    )


def _geometry_trace_defects(
    *,
    stop_pct: float | None,
    source: str,
    pool_size: int,
    time_ordered: bool | None,
    macro_rejected: bool | None,
) -> list[str]:
    defects: list[str] = []
    try:
        stop = float(stop_pct) if stop_pct is not None else 0.0
    except (TypeError, ValueError):
        stop = 0.0
    src = str(source or "")
    if src == "move_distribution" and stop >= _macro_stop_threshold():
        defects.append("macro_move_distribution")
    if time_ordered is False and not bool(macro_rejected):
        defects.append("disordered_unrejected")
    if int(pool_size) <= 0:
        defects.append("empty_pool")
    return defects


def log_geometry_trace(
    *,
    where: str,
    stop_pct: float | None,
    target_pct: float | None,
    source: str = "",
    pool_size: int = 0,
    oracle_stop: float | None = None,
    oracle_target: float | None = None,
    time_ordered: bool | None = None,
    macro_rejected: bool | None = None,
    p40_raw: float | None = None,
) -> None:
    defects = _geometry_trace_defects(
        stop_pct=stop_pct,
        source=source,
        pool_size=pool_size,
        time_ordered=time_ordered,
        macro_rejected=macro_rejected,
    )
    emit = logger.warning if defects else logger.info
    emit(
        "birth.geometry.trace where=%s stop=%.6f target=%.6f source=%s pool=%s "
        "oracle_stop=%s oracle_target=%s ordered=%s macro_rej=%s p40=%s pid=%s defects=%s",
        where,
        float(stop_pct or 0.0),
        float(target_pct or 0.0),
        source,
        pool_size,
        f"{float(oracle_stop):.6f}" if oracle_stop is not None else "na",
        f"{float(oracle_target):.6f}" if oracle_target is not None else "na",
        time_ordered,
        macro_rejected,
        f"{float(p40_raw):.6f}" if p40_raw is not None else "na",
        os.getpid(),
        ",".join(defects) if defects else "none",
    )


__all__ = [
    "BIRTH_DIAG_CONTRACT",
    "collect_birth_code_fingerprint",
    "fingerprint_identity_defects",
    "identity_progress_fields_for_boot",
    "log_birth_code_fingerprint",
    "log_geometry_trace",
    "log_meta_decision_trace",
    "log_progress_write_trace",
    "progress_diagnostic_fields",
    "reset_runtime_diagnostics_for_tests",
]
