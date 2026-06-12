"""Birth Certificate v2 — fail-closed completion artifact (ADR-0013)."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class BirthCertificateThresholds(BaseModel):
    model_config = ConfigDict(extra="forbid")

    min_oos_winrate: float = Field(default=0.48, ge=0.0, le=1.0)
    min_oos_sharpe: float = Field(default=0.35, ge=-10.0, le=50.0)
    max_oos_drawdown_pct: float = Field(default=8.0, ge=0.0, le=100.0)
    min_real_data_pct: float = Field(default=95.0, ge=0.0, le=100.0)
    min_regimes: int = Field(default=3, ge=1, le=20)
    min_holdout_trades: int = Field(default=50, ge=1, le=100_000)


class BirthCertificateV2(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Literal["2.0"] = "2.0"
    integrity_version: Literal[2] = 2
    issued_at: datetime
    policy_path: str
    policy_sha256: str = Field(min_length=64, max_length=64)
    real_data_pct: float = Field(ge=0.0, le=100.0)
    oos_winrate: float = Field(ge=0.0, le=1.0)
    oos_sharpe: float
    oos_max_drawdown_pct: float = Field(ge=0.0, le=100.0)
    constitution_violations: int = Field(ge=0)
    regimes_covered: list[str] = Field(min_length=1)
    curriculum_stages_passed: list[str] = Field(min_length=1)
    holdout_days: int = Field(ge=1)
    holdout_trades: int = Field(default=0, ge=0)
    training_trades: int = Field(ge=0)
    ppo_steps: int = Field(ge=0)

    @field_validator("policy_sha256")
    @classmethod
    def _hex_lower(cls, value: str) -> str:
        normalized = str(value).strip().lower()
        if len(normalized) != 64 or any(ch not in "0123456789abcdef" for ch in normalized):
            raise ValueError("policy_sha256 must be 64 lowercase hex chars")
        return normalized

    def meets_thresholds(self, thresholds: BirthCertificateThresholds) -> bool:
        if self.constitution_violations != 0:
            return False
        if self.real_data_pct < thresholds.min_real_data_pct:
            return False
        if self.oos_winrate < thresholds.min_oos_winrate:
            return False
        if self.oos_sharpe < thresholds.min_oos_sharpe:
            return False
        if self.oos_max_drawdown_pct > thresholds.max_oos_drawdown_pct:
            return False
        if len(set(self.regimes_covered)) < thresholds.min_regimes:
            return False
        if self.holdout_trades < thresholds.min_holdout_trades:
            return False
        return True


def certificate_path(workspace_root: Path | str) -> Path:
    return Path(workspace_root) / "state" / "lumina_birth_certificate.json"


def policy_path(workspace_root: Path | str) -> Path:
    return Path(workspace_root) / "lumina_agents" / "ppo" / "lumina_ppo_policy.zip"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_certificate(workspace_root: Path | str) -> BirthCertificateV2 | None:
    path = certificate_path(workspace_root)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    try:
        return BirthCertificateV2.model_validate(payload)
    except Exception:
        return None


def write_certificate(workspace_root: Path | str, certificate: BirthCertificateV2) -> Path:
    path = certificate_path(workspace_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = certificate.model_dump(mode="json")
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
    return path


def validate_certificate_artifacts(
    workspace_root: Path | str,
    *,
    thresholds: BirthCertificateThresholds | None = None,
) -> tuple[bool, str, BirthCertificateV2 | None]:
    """Return (ok, reason, certificate)."""
    import os

    if os.getenv("LUMINA_BIRTH_V2_DISABLED", "").strip().lower() in {"1", "true", "yes"}:
        root = Path(workspace_root)
        legacy_flag = root / "state" / "lumina_birth_completed.flag"
        legacy_legacy = root / "state" / "first_boot_completed.flag"
        pol = policy_path(root)
        if (legacy_flag.exists() or legacy_legacy.exists()) and pol.is_file():
            return True, "v1_compat_disabled_v2", None
        return False, "v1_compat_missing_artifacts", None

    root = Path(workspace_root)
    path = certificate_path(root)
    if not path.is_file():
        return False, "missing_or_invalid_certificate", None
    try:
        raw_payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False, "missing_or_invalid_certificate", None
    if not isinstance(raw_payload, dict):
        return False, "missing_or_invalid_certificate", None
    if raw_payload.get("integrity_version") != 2:
        return False, "certificate_integrity_version_invalid", None

    cert = load_certificate(workspace_root)
    if cert is None:
        return False, "missing_or_invalid_certificate", None

    pol = policy_path(workspace_root)
    if not pol.is_file():
        return False, "missing_policy_zip", cert

    try:
        actual_hash = sha256_file(pol)
    except OSError:
        return False, "policy_read_failed", cert

    if actual_hash != cert.policy_sha256:
        return False, "policy_hash_mismatch", cert

    if thresholds is not None and not cert.meets_thresholds(thresholds):
        return False, "certificate_thresholds_not_met", cert

    return True, "ok", cert


def build_certificate_from_eval(
    *,
    workspace_root: Path | str,
    eval_result: dict[str, Any],
    curriculum_stages_passed: list[str],
    training_trades: int,
    ppo_steps: int,
) -> BirthCertificateV2:
    pol = policy_path(workspace_root)
    policy_sha = sha256_file(pol) if pol.is_file() else "0" * 64
    return BirthCertificateV2(
        issued_at=datetime.now(timezone.utc),
        policy_path=str(pol),
        policy_sha256=policy_sha,
        real_data_pct=float(eval_result.get("real_data_pct", 0.0) or 0.0),
        oos_winrate=float(eval_result.get("oos_winrate", 0.0) or 0.0),
        oos_sharpe=float(eval_result.get("oos_sharpe", 0.0) or 0.0),
        oos_max_drawdown_pct=float(eval_result.get("oos_max_drawdown_pct", 100.0) or 100.0),
        constitution_violations=int(eval_result.get("constitution_violations", 999) or 999),
        regimes_covered=list(eval_result.get("regimes_covered") or []),
        curriculum_stages_passed=list(curriculum_stages_passed),
        holdout_days=int(eval_result.get("holdout_days", 1) or 1),
        holdout_trades=int(eval_result.get("holdout_trades", 0) or 0),
        training_trades=int(training_trades),
        ppo_steps=int(ppo_steps),
    )
