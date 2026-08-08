"""Apply/revert ops for CodeEvolutionApplyGate (global residual)."""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lumina_core.code_evolution.operators import PARAMETER_CATALOG
from lumina_core.code_evolution.proposal import CodeMutationOperator, CodeMutationProposal

logger = logging.getLogger(__name__)

# Keep in sync with apply_gate.py store layout.
PARAMS_FILE = "params.json"
INDICATORS_DIR = "indicators"
SNIPPETS_DIR = "snippets"
APPLIED_LOG = "applied.jsonl"
_SAFE_ID = re.compile(r"^[\w.\-]{1,80}$")


class CodeEvolutionApplyOpsMixin:
    def try_apply(self, evidence: Any) -> dict[str, Any]:
        """Evaluate + apply to sandbox store if allowed. Never touches live tree."""
        decision = self.evaluate(evidence)
        base: dict[str, Any] = {
            "applied": False,
            "proposal_id": evidence.proposal.proposal_id,
            "target_store": "sandbox_state",
            "gate": decision.to_dict(),
            "capital_mode": str(evidence.capital_mode or "sim"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if not decision.allowed:
            base["reason"] = decision.reason
            base["fail_reasons"] = list(decision.fail_reasons)
            return base

        try:
            write_res = self._write_sandbox_store(evidence.proposal)
        except Exception as exc:
            logger.exception("code_evolution sandbox apply write failed")
            base["reason"] = f"apply_write_failed:{exc}"
            base["fail_reasons"] = ["apply_write_failed"]
            return base

        if not write_res.get("ok"):
            base["reason"] = str(write_res.get("reason") or "apply_write_rejected")
            base["fail_reasons"] = list(write_res.get("fail_reasons") or ["apply_write_rejected"])
            return base

        self._append_applied_log(
            {
                "event": "code_evolution.applied",
                "proposal_id": evidence.proposal.proposal_id,
                "operator": evidence.proposal.operator.value
                if hasattr(evidence.proposal.operator, "value")
                else str(evidence.proposal.operator),
                "target": evidence.proposal.target,
                "paths": write_res.get("paths"),
                "human_approver": evidence.human_approver,
                "capital_mode": evidence.capital_mode,
                "timestamp": base["timestamp"],
            }
        )
        # Stamp pending bundle
        self._stamp_applied(evidence.proposal.proposal_id, write_res)

        base["applied"] = True
        base["reason"] = "applied_sandbox_store"
        base["paths"] = write_res.get("paths")
        base["store"] = write_res.get("store")
        return base
    def load_applied_params(self) -> dict[str, float]:
        path = self.applied_root / PARAMS_FILE
        if not path.exists():
            return {}
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        if not isinstance(raw, dict):
            return {}
        out: dict[str, float] = {}
        for k, v in raw.items():
            if k in PARAMETER_CATALOG:
                try:
                    out[str(k)] = float(v)
                except (TypeError, ValueError):
                    continue
        return out
    def revert_applied(self, proposal_id: str) -> dict[str, Any]:
        """Restore params from REVERT / before_snapshot; remove artifact files if recorded."""
        if not _SAFE_ID.match(proposal_id or ""):
            return {"reverted": False, "reason": "invalid_proposal_id"}
        pdir = self.pending_root / proposal_id
        revert_path = pdir / "REVERT.json"
        applied_stamp = pdir / "APPLIED.json"
        if not revert_path.exists():
            return {"reverted": False, "reason": "no_revert_artifact"}

        try:
            revert = json.loads(revert_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return {"reverted": False, "reason": f"revert_unreadable:{exc}"}

        restore = revert.get("restore_snapshot") or {}
        restored_params: dict[str, float] = {}
        if isinstance(restore, dict):
            # Merge restore keys into applied params (only catalog keys)
            current = self.load_applied_params()
            for k, v in restore.items():
                if k in PARAMETER_CATALOG:
                    try:
                        current[str(k)] = float(v)
                        restored_params[str(k)] = float(v)
                    except (TypeError, ValueError):
                        continue
            if restored_params:
                self._write_params(current)

        removed: list[str] = []
        params_path = (self.applied_root / PARAMS_FILE).resolve()
        if applied_stamp.exists():
            try:
                stamp = json.loads(applied_stamp.read_text(encoding="utf-8"))
                for p in stamp.get("paths") or []:
                    path = Path(str(p))
                    # Only delete artifact files under applied_root — never wipe params.json
                    # after restore (params are reverted via restore_snapshot merge).
                    try:
                        resolved = path.resolve()
                        if resolved == params_path:
                            continue
                        root_s = str(self.applied_root.resolve())
                        if str(resolved).startswith(root_s) and resolved.is_file():
                            resolved.unlink(missing_ok=True)
                            removed.append(str(resolved))
                    except OSError:
                        continue
            except (OSError, json.JSONDecodeError):
                pass

        self._append_applied_log(
            {
                "event": "code_evolution.reverted",
                "proposal_id": proposal_id,
                "restored_params": restored_params,
                "removed": removed,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
        return {
            "reverted": True,
            "reason": "ok",
            "restored_params": restored_params,
            "removed": removed,
        }
    def _write_sandbox_store(self, proposal: CodeMutationProposal) -> dict[str, Any]:
        op = proposal.operator
        if isinstance(op, str):
            op = CodeMutationOperator(op)
        pid = proposal.proposal_id
        if not _SAFE_ID.match(pid):
            return {"ok": False, "reason": "invalid_proposal_id", "fail_reasons": ["invalid_proposal_id"]}

        if op == CodeMutationOperator.PARAMETER_TWEAK:
            payload = proposal.payload or {}
            key = str(payload.get("key") or "")
            new_v = float(payload.get("new_value"))
            params = self.load_applied_params()
            # seed defaults for missing keys
            for k, meta in PARAMETER_CATALOG.items():
                params.setdefault(k, float(meta["default"]))
            params[key] = new_v
            path = self._write_params(params)
            return {
                "ok": True,
                "store": "params",
                "paths": [str(path)],
                "params": {key: new_v},
            }

        if op == CodeMutationOperator.ADD_SIMPLE_INDICATOR:
            code = str((proposal.payload or {}).get("code") or "")
            if "def indicator" not in code:
                return {"ok": False, "reason": "missing_indicator", "fail_reasons": ["missing_entrypoint"]}
            if self._unsafe_code(code):
                return {"ok": False, "reason": "unsafe_tokens", "fail_reasons": ["unsafe_tokens"]}
            d = self.applied_root / INDICATORS_DIR
            d.mkdir(parents=True, exist_ok=True)
            path = d / f"{pid}.py"
            path.write_text(code, encoding="utf-8")
            return {"ok": True, "store": "indicator", "paths": [str(path)]}

        if op == CodeMutationOperator.STRATEGY_SNIPPET_ADJUST:
            code = str((proposal.payload or {}).get("code") or "")
            if "def generated_strategy" not in code:
                return {"ok": False, "reason": "missing_strategy", "fail_reasons": ["missing_entrypoint"]}
            if self._unsafe_code(code):
                return {"ok": False, "reason": "unsafe_tokens", "fail_reasons": ["unsafe_tokens"]}
            d = self.applied_root / SNIPPETS_DIR
            d.mkdir(parents=True, exist_ok=True)
            path = d / f"{pid}.py"
            path.write_text(code, encoding="utf-8")
            return {"ok": True, "store": "snippet", "paths": [str(path)]}

        return {"ok": False, "reason": "unknown_operator", "fail_reasons": ["unknown_operator"]}
    @staticmethod
    def _unsafe_code(code: str) -> bool:
        bad = ("import ", "open(", "exec(", "eval(", "__import__", "subprocess", "socket")
        return any(tok in code for tok in bad)
    def _write_params(self, params: dict[str, float]) -> Path:
        path = self.applied_root / PARAMS_FILE
        # Only catalog keys
        clean = {k: float(params[k]) for k in PARAMETER_CATALOG if k in params}
        path.write_text(json.dumps(clean, indent=2, sort_keys=True), encoding="utf-8")
        return path
    def _stamp_applied(self, proposal_id: str, write_res: dict[str, Any]) -> None:
        pdir = self.pending_root / proposal_id
        pdir.mkdir(parents=True, exist_ok=True)
        stamp = {
            "applied": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "paths": write_res.get("paths"),
            "store": write_res.get("store"),
        }
        (pdir / "APPLIED.json").write_text(json.dumps(stamp, indent=2), encoding="utf-8")
    def _append_applied_log(self, event: dict[str, Any]) -> None:
        path = self.applied_root / APPLIED_LOG
        try:
            with path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(event, default=str, ensure_ascii=True) + "\n")
        except OSError:
            logger.debug("applied log append failed", exc_info=True)
