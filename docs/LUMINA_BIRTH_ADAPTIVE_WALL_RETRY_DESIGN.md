# Lumina Birth Phase – Adaptive Self-Correction System (Elon Edition v2.1)
**Version**: 2.1 (Final Implementation-Ready Spec)  
**Date**: 2026-06-25  
**Status**: Complete & Production-Ready for AI Coding Agent  
**Goal**: One high-leverage, radically simple mechanism that turns stall events into autonomous intelligent recovery. Minimal code. Maximum autonomy. Fail-closed safety.

This document is now the single, complete source of truth. Any competent AI coding agent can read this file and implement the full feature with high fidelity and very little additional clarification.

---

## 0. Executive Summary (Elon Style)

**Current Problem**: After passing the volume gate in STAGE1_TREND, Lumina drops to `chunk_target = 1`. When winrate stops improving (or declines), it hits an early stall ("metrics did not improve within the stage wall") even before the time wall. Human intervention is required.

**Solution**: Add one small, high-leverage adaptation decision point inside the existing research loop. When a stall is detected after the volume gate and the winrate trend is negative or flat, the system automatically increases exploration (`chunk_target`), logs the reason, and restarts the stage from checkpoint. Limited retries. No new modules.

**Result**: Lumina recovers intelligently from stagnation with almost zero human touch. The first 1–2 stalls become automatic. Only after exhausting smart retries does a clean, explainable stall occur.

**Design Constraints (Non-Negotiable)**:
- Radical simplicity (changes concentrated in `engine.py`)
- No lowering of the real winrate goal
- Fully backward compatible (`wall_behavior = "strict"` disables everything)
- Transparent and auditable decisions

---

## 1. Current Stall Handling (June 2026)

### Observed State
- Stage: STAGE1_TREND
- Volume gate: Already passed (~386+ trades)
- Winrate: ~30.3% with flat/negative trend
- Trigger: "Trade target was met but pass metrics did not improve within the stage wall"
- Time wall: Not yet expired

### Immediate Recommended Action (Manual)
- Choose **"Expand data & retry"** (preferred) or **"Retry stage"**.
- Avoid "Wipe & restart".
- Let it run 30–40 attempts after retry and observe the winrate slope.

Once the system below is implemented, this exact stall will be handled automatically (see Section 3).

---

## 2. Core Design – Radically Simple

### Files Modified
Only these four files are touched:

| File                              | Type of Change          | Impact |
|-----------------------------------|-------------------------|--------|
| `lumina_core/birth/engine.py`     | Main logic + 1 helper   | High   |
| `lumina_core/birth/stage_scorecard.py` | Trend + richer HUD | Medium |
| `lumina_core/birth/config.py`     | 5 new config fields     | Low    |
| Checkpoint / logging              | Small additions         | Low    |

**No new files. No new complex classes.**

### Single New Data Structure (add near top of engine.py)

```python
from dataclasses import dataclass
from typing import List

@dataclass
class AdaptationDecision:
    should_retry: bool
    reason: str                    # e.g. "negative_winrate_trend_after_volume_gate"
    new_chunk_target: int
    escalation_increase: int = 1
    log_message: str = ""
```

---

## 3. The Core Decision Function (Copy-Paste Ready)

Add this function in `engine.py` (can be a private method of the class or standalone).

```python
def _get_adaptation_decision(
    stage_trades: int,
    required: int,
    winrate: float,
    winrate_history: List[float],
    escalation_level: int,
    cfg: "BirthCurriculumConfig",
) -> AdaptationDecision:
    """
    High-leverage, simple rule.
    Primary signal = recent winrate trend after volume gate has been passed.
    """

    # Calculate simple slope
    if len(winrate_history) >= 5:
        slope = (winrate_history[-1] - winrate_history[0]) / max(1, len(winrate_history) - 1)
    else:
        slope = 0.0

    is_negative_trend = slope < cfg.negative_slope_threshold

    # Increase escalation on every stall
    new_escalation = min(getattr(cfg, "max_escalation_level", 5), escalation_level + 1)

    if stage_trades >= required and is_negative_trend:
        new_chunk = min(25, getattr(cfg, "exploration_chunk_size", 8) * (1 + escalation_level))
        return AdaptationDecision(
            should_retry=True,
            reason="negative_winrate_trend_after_volume_gate",
            new_chunk_target=new_chunk,
            escalation_increase=1,
            log_message=f"Negative trend (slope={slope:.4f}). Boosting exploration to chunk={new_chunk}"
        )

    if stage_trades >= required:
        # Early stall after volume gate but no clear negative trend yet
        return AdaptationDecision(
            should_retry=True,
            reason="metrics_not_improving_within_wall",
            new_chunk_target=getattr(cfg, "exploration_chunk_size", 8),
            escalation_increase=1,
            log_message="Metrics stalled after volume gate. Applying exploration boost."
        )

    # Fallback
    return AdaptationDecision(
        should_retry=True,
        reason="default_stall_retry",
        new_chunk_target=getattr(cfg, "rollout_chunk_trades", 5),
        escalation_increase=1,
        log_message="Standard stall recovery."
    )
```

---

## 4. Integration into the Main Loop (Exact Pattern)

In `_run_stage_research_loop` (or equivalent), replace/extend the stall handling section with the following pattern:

```python
# === EXISTING CODE (keep) ===
stall_result = _certified_stage_stall_result(...)

if stall_result is not None:
    # === NEW ADAPTIVE SELF-CORRECTION LOGIC ===
    if getattr(cfg, "adaptation_enabled", True) and getattr(cfg, "wall_behavior", "adaptive") == "adaptive":
        decision = self._get_adaptation_decision(
            stage_trades=stage_trades,
            required=required,
            winrate=stage_wins / max(1, stage_trades),
            winrate_history=winrate_history,
            escalation_level=escalation_level,
            cfg=cfg,
        )

        if decision.should_retry and retries_this_stage < getattr(cfg, "max_stage_retries", 3):
            # Apply adaptation
            escalation_level += decision.escalation_increase
            # Temporarily override chunk size for the next window
            original_chunk = getattr(cur_cfg, "rollout_chunk_trades", 5)
            cur_cfg.rollout_chunk_trades = decision.new_chunk_target

            logger.info("birth.adaptation.applied",
                        reason=decision.reason,
                        new_chunk=decision.new_chunk_target,
                        message=decision.log_message,
                        escalation=escalation_level)

            # Record in checkpoint
            if "adaptation_history" not in checkpoint:
                checkpoint["adaptation_history"] = []
            checkpoint["adaptation_history"].append({
                "timestamp": time.time(),
                "reason": decision.reason,
                "chunk_target": decision.new_chunk_target,
                "escalation": escalation_level,
                "winrate": stage_wins / max(1, stage_trades),
            })

            retries_this_stage += 1

            # Persist and restart stage with new parameters
            self._persist_checkpoint(checkpoint)
            logger.info("birth.stage.auto_retrying_with_adaptation", retry=retries_this_stage)

            # Restart the stage research loop with updated config
            return self._run_stage_research_loop(...)  # or equivalent restart logic

    # If we reach here: no more retries or strict mode → real stall
    return stall_result
```

**Note**: The exact restart mechanism (`_run_stage_research_loop` recursive call or dedicated restart method) should follow the existing checkpoint + stage restart pattern already present in the codebase.

---

## 5. Supporting Changes

### 5.1 Config (`birth/config.py`)

Add to `BirthCurriculumConfig`:

```python
adaptation_enabled: bool = True
wall_behavior: str = "adaptive"           # "adaptive" or "strict"
max_stage_retries: int = 3
exploration_chunk_size: int = 8
winrate_trend_window: int = 12
negative_slope_threshold: float = -0.005
```

### 5.2 Winrate History Tracking (engine.py)

Maintain and persist a rolling list:

```python
winrate_history: List[float] = []

# After each meaningful update of stage_trades
current_winrate = stage_wins / max(1, stage_trades)
winrate_history.append(current_winrate)
if len(winrate_history) > cfg.winrate_trend_window:
    winrate_history.pop(0)
```

Persist `winrate_history` and `retries_this_stage` in checkpoints.

### 5.3 HUD / Scorecard (`stage_scorecard.py`)

Enrich payload:

```python
payload["volume_gate_status"] = "PASSED" if stage_trades >= required else "PENDING"
payload["winrate_trend_slope"] = calculate_simple_slope(winrate_history)
payload["last_adaptation"] = (checkpoint.get("adaptation_history") or [{}])[-1]
```

Update progress text to clearly show adaptation status.

---

## 6. Implementation Verification Checklist (for the AI Agent)

Before considering the task complete, verify:

- [ ] Config fields added and have sensible defaults
- [ ] `winrate_history` is maintained and persisted in checkpoints
- [ ] `_get_adaptation_decision` function exists and is correct
- [ ] Stall path in main loop calls the decision function when `wall_behavior == "adaptive"`
- [ ] On successful adaptation: `escalation_level` increased, `chunk_target` raised, decision logged, history recorded, stage restarted
- [ ] After `max_stage_retries` → clean stall with full history
- [ ] `wall_behavior = "strict"` completely disables the feature
- [ ] HUD / progress shows volume gate status + trend + last adaptation
- [ ] No new files were created
- [ ] All changes are in `lumina_core/birth/`

---

## 7. Why This Design is Correct (Elon Lens)

- One high-leverage idea (increase exploration on negative trend after volume gate).
- Extremely small diff.
- Transparent decisions (one function, clear reasons).
- Strong safety (hard retry limit + strict mode + constitution bypass).
- Directly solves the exact stall the user is experiencing today.
- Moves Lumina meaningfully closer to a self-correcting living system.

---

**This document (v2.1) is now complete, precise, and ready for direct implementation by any capable AI coding agent.**

**End of Spec**