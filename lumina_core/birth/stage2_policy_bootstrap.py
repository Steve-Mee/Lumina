"""Stage-2 cold bootstrap: detox Stage-1 survival prior without floor theater.

Elon rule: keep the feature encoder (eyes), reinit the action head (hands).
Then warm only on net-of-cost oracle trajectories so range learning does not
inherit anti-edge Stage-1 survival (~26% WR).
"""

from __future__ import annotations

from typing import Any

from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.stage2_bootstrap")


def reinit_policy_action_head(model: Any, *, reinit_value_net: bool = True) -> dict[str, Any]:
    """Reset SB3 MlpPolicy action (and optional value) head; keep body/features.

    Returns a small telemetry dict. Never invents edge — only clears poisoned
    action distribution so oracle warm-start can write range behavior.
    """
    out: dict[str, Any] = {
        "ok": False,
        "action_modules": 0,
        "value_modules": 0,
        "reason": "",
    }
    if model is None:
        out["reason"] = "no_model"
        return out
    policy = getattr(model, "policy", None)
    if policy is None:
        out["reason"] = "no_policy"
        return out
    try:
        import torch.nn as nn
    except Exception as exc:  # pragma: no cover
        out["reason"] = f"torch_import:{type(exc).__name__}"
        return out

    def _reset_module(mod: Any) -> int:
        n = 0
        if mod is None:
            return 0
        for m in mod.modules():
            if isinstance(m, nn.Linear):
                # Small gain: continuous action mean starts near zero (more HOLD).
                nn.init.orthogonal_(m.weight, gain=0.01)
                if m.bias is not None:
                    nn.init.zeros_(m.bias)
                n += 1
            elif hasattr(m, "reset_parameters") and m is not mod:
                try:
                    m.reset_parameters()  # type: ignore[operator]
                    n += 1
                except Exception:
                    pass
        return n

    try:
        action_net = getattr(policy, "action_net", None)
        out["action_modules"] = _reset_module(action_net)
        if reinit_value_net:
            value_net = getattr(policy, "value_net", None)
            out["value_modules"] = _reset_module(value_net)
        # Continuous Gaussian: reset log_std toward exploratory but bounded.
        log_std = getattr(policy, "log_std", None)
        if log_std is not None and hasattr(log_std, "data"):
            try:
                log_std.data.fill_(-0.5)
                out["log_std_reset"] = True
            except Exception:
                out["log_std_reset"] = False
        out["ok"] = out["action_modules"] > 0 or bool(out.get("log_std_reset"))
        out["reason"] = "reinitialized" if out["ok"] else "no_action_params"
        logger.info(
            "birth.stage2.action_head_reinit ok=%s action_lin=%s value_lin=%s",
            out["ok"],
            out["action_modules"],
            out["value_modules"],
        )
    except Exception as exc:
        out["reason"] = f"error:{type(exc).__name__}:{exc}"
        logger.warning("birth.stage2.action_head_reinit_failed: %s", exc)
    return out


def curate_buffer_for_stage2_bootstrap(
    buffer: Any,
    *,
    min_reward: float = 0.0,
    max_keep: int = 4000,
) -> dict[str, Any]:
    """Keep only non-negative reward trajectories (oracle net winners preferred).

    Fail-soft: if buffer API unknown, leave intact and report.
    """
    out = {"removed": 0, "kept": 0, "mode": "noop"}
    if buffer is None:
        return out
    try:
        # Prefer explicit curate if available.
        if hasattr(buffer, "filter_min_reward"):
            before = int(len(buffer))
            buffer.filter_min_reward(float(min_reward))  # type: ignore[operator]
            kept_n = int(len(buffer))
            out["kept"] = kept_n
            out["removed"] = max(0, before - kept_n)
            out["mode"] = "filter_min_reward"
            return out
        if hasattr(buffer, "items") and callable(getattr(buffer, "items", None)):
            items = list(buffer.items())  # type: ignore[operator]
        elif hasattr(buffer, "_storage"):
            items = list(getattr(buffer, "_storage") or [])
        elif isinstance(buffer, list):
            items = list(buffer)
        else:
            # Top-quartile distill fallback used elsewhere in birth.
            try:
                from lumina_core.birth.recovery_compress import curate_buffer_top_quartile

                removed = curate_buffer_top_quartile(buffer, keep_pct=0.35)
                out["removed"] = int(removed or 0)
                out["kept"] = int(len(buffer)) if hasattr(buffer, "__len__") else 0
                out["mode"] = "top_quartile"
                return out
            except Exception:
                out["mode"] = "unsupported"
                return out

        kept: list[Any] = []
        for row in items:
            if isinstance(row, dict):
                rew = float(row.get("reward", row.get("pnl", 0.0)) or 0.0)
            else:
                rew = float(getattr(row, "reward", 0.0) or 0.0)
            if rew >= float(min_reward):
                kept.append(row)
        if max_keep > 0 and len(kept) > max_keep:
            # Keep highest reward first.
            def _rew(r: Any) -> float:
                if isinstance(r, dict):
                    return float(r.get("reward", r.get("pnl", 0.0)) or 0.0)
                return float(getattr(r, "reward", 0.0) or 0.0)

            kept.sort(key=_rew, reverse=True)
            kept = kept[: int(max_keep)]
        out["removed"] = max(0, len(items) - len(kept))
        out["kept"] = len(kept)
        if isinstance(buffer, list):
            buffer[:] = kept
            out["mode"] = "list_rewrite"
        elif hasattr(buffer, "clear") and hasattr(buffer, "add"):
            buffer.clear()
            for row in kept:
                try:
                    buffer.add(row, priority=1.0)
                except TypeError:
                    buffer.add(row)
            out["mode"] = "clear_add"
        else:
            out["mode"] = "read_only"
        return out
    except Exception as exc:
        logger.warning("birth.stage2.buffer_curate_failed: %s", exc)
        out["mode"] = f"error:{type(exc).__name__}"
        return out


def run_stage2_cold_bootstrap(
    *,
    host: Any,
    cur_cfg: Any,
    oracle_patterns: int,
    buffer: Any | None = None,
) -> dict[str, Any]:
    """Full Stage-2 entry detox: reinit head → curate buffer → PPO warm."""
    result: dict[str, Any] = {
        "action_head_reinit": {},
        "buffer_curate": {},
        "ppo_steps": 0,
        "patterns": int(oracle_patterns),
        "ok": False,
    }
    cold = bool(getattr(cur_cfg, "stage2_cold_bootstrap_policy", True))
    boot_steps = int(getattr(cur_cfg, "stage2_oracle_bootstrap_steps", 3000) or 0)
    reinit = bool(getattr(cur_cfg, "stage2_reinit_action_head", True))
    # If Stage-1 graduation already reinit'd the action head, still reinit again
    # at Stage-2 entry (defense in depth) unless config disables stage2 reinit.
    prior = getattr(host, "_stage1_transfer_handoff", None)
    if isinstance(prior, dict):
        result["stage1_prior_handoff_ok"] = bool(prior.get("ok"))
        result["stage1_prior_wr"] = prior.get("stage1_wr")
    if not cold:
        result["reason"] = "disabled"
        return result

    # Prefer engine.rl_policy_model / host.current_policy.
    model = getattr(host, "current_policy", None)
    if model is None:
        eng = getattr(host, "runtime", None) or getattr(host, "engine", None)
        model = getattr(eng, "rl_policy_model", None) if eng is not None else None
        if model is None and hasattr(host, "ppo_trainer"):
            model = getattr(host.ppo_trainer, "_resolve_active_model", lambda: None)()

    if reinit and model is not None:
        result["action_head_reinit"] = reinit_policy_action_head(model, reinit_value_net=True)
        host.current_policy = model
        try:
            eng = getattr(host, "runtime", None) or getattr(host, "engine", None)
            if eng is not None and hasattr(eng, "set_rl_policy"):
                eng.set_rl_policy(model)
        except Exception:
            pass
    else:
        result["action_head_reinit"] = {"ok": False, "reason": "skipped_or_no_model"}

    buf = buffer if buffer is not None else getattr(host, "buffer", None)
    # PR-F: prefer non-negative trajectories only (quality bootstrap, not dump).
    min_rew = float(getattr(cur_cfg, "stage2_bootstrap_min_buffer_reward", 0.0) or 0.0)
    min_rew = max(0.0, min_rew)
    max_keep = int(getattr(cur_cfg, "stage2_bootstrap_max_buffer", 4000) or 4000)
    # Cap warm patterns so 10k dump cannot dominate early PPO.
    warm_cap = int(getattr(cur_cfg, "stage2_bootstrap_max_buffer", 4000) or 4000)
    max_keep = max(200, min(max_keep, warm_cap))
    result["buffer_curate"] = curate_buffer_for_stage2_bootstrap(
        buf, min_reward=min_rew, max_keep=max_keep
    )
    # Refuse massive warm if buffer still thin after curate.
    buf_len = len(buf) if buf is not None else 0
    min_buf = int(getattr(cur_cfg, "stage2_bootstrap_min_buffer_size", 80) or 80)

    if boot_steps > 0 and oracle_patterns > 0 and buf is not None and buf_len >= min_buf:
        try:
            host.current_policy = host.ppo_trainer.update_from_buffer(
                buffer=buf,
                timesteps=boot_steps,
                birth_phase=True,
            )
            host.ppo_steps = int(getattr(host, "ppo_steps", 0) or 0) + boot_steps
            result["ppo_steps"] = boot_steps
            result["ok"] = True
            result["reason"] = "warmed"
        except Exception as exc:
            result["reason"] = f"ppo_failed:{type(exc).__name__}"
            logger.warning("birth.stage2.cold_bootstrap_ppo_failed: %s", exc)
    else:
        result["reason"] = (
            f"skip_warm steps={boot_steps} patterns={oracle_patterns} "
            f"buffer={len(buf) if buf is not None else 0}"
        )
        # Head reinit alone still counts as partial detox.
        result["ok"] = bool(result.get("action_head_reinit", {}).get("ok"))
    logger.info(
        "birth.stage2.cold_bootstrap ok=%s ppo=%s reinit=%s curate=%s reason=%s",
        result["ok"],
        result["ppo_steps"],
        result.get("action_head_reinit", {}).get("ok"),
        result.get("buffer_curate", {}).get("mode"),
        result.get("reason"),
    )
    return result


__all__ = [
    "curate_buffer_for_stage2_bootstrap",
    "reinit_policy_action_head",
    "run_stage2_cold_bootstrap",
]
