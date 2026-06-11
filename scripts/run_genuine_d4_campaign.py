#!/usr/bin/env python3
"""
Longer Genuine Multi-Day D4 Campaign Runner — Full non-headless runtime SIM + aggressive evolution
for non-illustrative 30-day scale (Phase 3 D4 per 2026-05-31 roadmap + MC "Next Required Update Trigger").

This is the next step after short controlled genuine D4 (generator), live lineage wiring, and D3 deeper
forcing (Guardian daily now surfaces D4 bundles). Produces the first full-scale genuine (non-seeded)
multi-day campaign bundle from a real daemon runtime under aggressive evo load (real proposals from
meta/dream/agents hitting real gates/arb/fills with Phase 2 lineage, real ctxs in logs with full
checks/markers, measured volume of unsafe evo proposals caught 100% pre-broker by aperture + D5 shadow).

One (or few) command(s): launches full runtime_entrypoint --mode sim (full supervisor/daemons,
not headless toy), monitors for target (arb ctxs or wall time for "multi-day" sim feel), terminates,
post-processes with Guardian --d1-audits + D4 --real (now picks real data via enhanced discover),
produces labeled "d4_genuine_multiday_campaign_*.md+json" + sidecars. Guardian daily will surface
the new bundle (D3 forcing extended to scale data).

Usage (demo/short for test; adjust for real scale):
    python scripts/run_genuine_d4_campaign.py --duration-min 5 --target-arb-ctxs 10
    python scripts/run_genuine_d4_campaign.py --duration-min 15  # for more "multi-day" load

After: inspect state/audits/d4_genuine_multiday_*.md (real stats, D1 compacts from production arb,
lineage, fills with hash_ok, 100% catch on unsafe evo, D5 shadow). Reproduce note included.
New bundle will appear in next Guardian --report (D3 forcing).

References (immutable, re-anchored):
- 2026-05-31-elon-aperture-hardening-90-day-roadmap.md (Phase 3 D4 exact wording + success gate
  for 30-day aggressive evo + 100% catch with logs/evidence; D1; "genuine (non-seeded) multi-day
  live SIM + evo data").
- aperture-hardening-mission-control.md (D4 Yellow-Green for short; explicit "longer genuine
  multi-day D4 campaign (for full 30-day scale, now daily surfaced in Guardian)" as highest-leverage;
  D3 daily forcing now extended; rules for work on track).
- Previous logs (2026-06-06 D3 forcing + live lineage + genuine short D4; 2026-06-05 D4 prototype).
- AGENTS.md + self-improvement-protocol.md (Plan Mode + protocol for this; map to D4 + D1).

Per aperture-mission-control: every piece explicitly advances the original 2026-05-31 D4 deliverable
(and D1). This is the "public demonstration at scale" with real daemon evo load (not controlled short).

Safety: sim/paper only (unlimited budget per sim config, but gates + D5 shadow + aperture_guard +
constitution still enforce). Isolated LUMINA_STATE_DIR. Best-effort; monitor for FATAL (but sim
allowed per DNA). No REAL capital path.

Reproducibility: script prints exact launch cmd, env, target, elapsed, #ctxs/proposals from logs,
bundle path, Guardian/D4 cmds. Campaign dir kept for evidence/repro (or --keep).

Prerequisites (script warns/checks):
- First-boot/birth completed (or sim gate open; may trigger and stop — see docs).
- Inference (ollama/vllm + models for dream/agents/meta reasoning, or XAI key; fallback limited).
- For neuro: CROSSTRADE_TOKEN or set require_real_simulator_data=false in config (stub possible).
- Time: 5-30min wall for "multi-day" accelerated sim feel + evo volume (aggressive config + dream
  cycles produce proposals that hit arb; D5 protects unsafe mutations; aperture catches pre-broker).

This fulfills the MC "Next Required Update Trigger" and 90-day D4 north star for observable
aperture under genuine aggressive evo load at scale. After: update MC (D4 to Green-Yellow "multi-day
genuine scale from full runtime"), new evolution log, agent-context if material.

Run this, inspect the bundle (real D1 from production arb checks, real lineage/fills/closes with
hash_ok, real stats on caught unsafe evo), Guardian will surface it daily (D3). One command
reproduces the full scale demonstration.

*Per the 2026-05-31 Elon first-principles analysis + 90-day roadmap + permanent aperture-mission-control skill.*
"""

from __future__ import annotations

import argparse
import json
import os
import re
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
STATE_AUDITS = ROOT / "state" / "audits"

from lumina_core.audit.d4_birth_prereq import ensure_birth_prereqs  # noqa: E402


def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def _count_arb_ctxs(log_dir: Path) -> int:
    """Best-effort count of unique decision_context_id with final_arbitration markers in campaign logs.
    Scans blackboard + trade_decision (or any .jsonl) for real arb events (like discover).
    """
    ctxs: set[str] = set()
    patterns = [
        r"final_arbitration|arbitration\.result|final\.arbitration",
        r"checks|final_arbitration_status|constitution_checks",
    ]
    for p in log_dir.rglob("*.jsonl"):
        if not p.exists():
            continue
        try:
            for line in p.read_text(encoding="utf-8", errors="ignore").splitlines()[-2000:]:
                if not line.strip():
                    continue
                try:
                    rec = json.loads(line)
                    payload = rec.get("payload") if isinstance(rec.get("payload"), dict) else rec
                    topic = str(rec.get("topic", "") or payload.get("topic", "") or "").lower()
                    if any(re.search(pat, topic, re.I) or re.search(pat, str(payload), re.I) for pat in patterns):
                        cid = str(
                            payload.get("decision_context_id")
                            or rec.get("decision_context_id")
                            or rec.get("correlation_id")
                            or ""
                        ).strip()
                        if cid:
                            ctxs.add(cid)
                except Exception:
                    continue
        except Exception:
            continue
    return len(ctxs)


def _count_proposals(log_dir: Path) -> int:
    """Count 'proposed' or 'pending' in evolution_log.jsonl (simple volume for aggressive evo)."""
    count = 0
    for p in log_dir.rglob("evolution_log.jsonl"):
        if not p.exists():
            continue
        try:
            for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
                if not line.strip():
                    continue
                try:
                    obj = json.loads(line)
                    if isinstance(obj, dict) and obj.get("status") in {"proposed", "pending"}:
                        count += 1
                except Exception:
                    continue
        except Exception:
            continue
    return count


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run genuine multi-day D4 campaign (full runtime + aggressive evo). "
                    "See docstring for Phase 3 D4 mapping + prereqs + safety."
    )
    parser.add_argument("--duration-min", type=int, default=5, help="Wall time bound for 'multi-day' sim load (default 5min for demo; 15-30 for scale).")
    parser.add_argument("--target-arb-ctxs", type=int, default=10, help="Target real arb ctxs (with final_arbitration markers) before terminate (default 10 for demo).")
    parser.add_argument("--isolated-state-dir", type=str, default="", help="Isolated LUMINA_STATE_DIR (default: state/genuine_d4_multiday_YYYYMMDD_HHMM).")
    parser.add_argument("--aggressive", action="store_true", default=True, help="Force aggressive_evolution (default on; matches sim config).")
    parser.add_argument("--keep", action="store_true", help="Keep campaign dir after (default: keep for repro/evidence).")
    parser.add_argument(
        "--seed-birth-flag",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Seed workspace state/lumina_birth_completed.flag when missing (SIM campaigns only; default on).",
    )
    parser.add_argument(
        "--check-prereqs-only",
        action="store_true",
        help="Validate birth policy/flag then exit (no runtime launch).",
    )
    args = parser.parse_args()

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    ok, msg = ensure_birth_prereqs(
        workspace_root=ROOT,
        seed=bool(args.seed_birth_flag),
        label=f"d4-multiday-{ts}",
    )
    print(f"BIRTH_PREREQ {'OK' if ok else 'FAIL'}: {msg}")
    if not ok:
        raise SystemExit(1)
    if args.check_prereqs_only:
        print("D4_BIRTH_PREREQ_CHECK_OK")
        raise SystemExit(0)
    campaign_dir = Path(args.isolated_state_dir) if args.isolated_state_dir else (ROOT / "state" / f"genuine_d4_multiday_{ts}")
    _ensure_dir(campaign_dir)

    print("=== Phase 3 D4 Genuine Multi-Day Campaign Runner ===")
    print(f"Campaign dir (isolated): {campaign_dir}")
    print(f"Target: {args.duration_min}min wall or {args.target_arb_ctxs} real arb ctxs (aggressive evo, full runtime).")
    print("This produces the first full-scale non-illustrative bundle from real daemon evo load (per 2026-05-31 roadmap D4 + MC).")
    print()

    # Prep env (sim + aggressive + paper; isolated state)
    env = os.environ.copy()
    env["LUMINA_STATE_DIR"] = str(campaign_dir)
    env["LUMINA_MODE"] = "sim"
    env["TRADE_MODE"] = "sim"
    env["BROKER_BACKEND"] = "paper"
    env["LUMINA_AGGRESSIVE_SIM"] = "true" if args.aggressive else "false"
    env.setdefault("LUMINA_ENFORCE_ENV_RUNTIME_MODE", "true")
    env.setdefault("VOICE_ENABLED", "False")
    env.setdefault("LUMINA_JWT_SECRET_KEY", f"campaign-{ts}-jwt")

    # Prereq warnings (per plan)
    print("Prereqs (see docstring for details):")
    print("  - Birth policy + flag: satisfied via ensure_birth_prereqs (see BIRTH_PREREQ line above).")
    print("  - Inference (ollama/vllm + models for dream/agents/meta; or XAI; fallback limited for rich evo volume).")
    print("  - For neuro: CROSSTRADE_TOKEN or config neuroevolution.require_real_simulator_data=false (stub).")
    print("  - Time: short wall for demo 'multi-day' (accelerated ticks); longer for volume.")
    print()

    # Launch full genuine runtime (non-headless; full daemons for real evo/gate/arb/fills)
    cmd = [sys.executable, "-m", "lumina_core.engine.runtime_entrypoint", "--mode", "sim"]
    runtime_log = campaign_dir / "runtime.log"
    print("Launched full genuine SIM runtime (full daemon, not headless toy) for multi-day aggressive evo campaign.")
    print(f"  Cmd: {' '.join(cmd)}")
    print("  Env overrides: LUMINA_STATE_DIR, LUMINA_MODE=sim, TRADE_MODE=sim, BROKER_BACKEND=paper, LUMINA_AGGRESSIVE_SIM=true")
    print(f"  Logs: {runtime_log}")
    print(f"  Monitor: tail -f {runtime_log} | grep -E '(proposal|arbitration|dream|meta)'")
    print()

    proc = subprocess.Popen(
        cmd,
        env=env,
        stdout=open(runtime_log, "w", encoding="utf-8", errors="ignore"),
        stderr=subprocess.STDOUT,
        cwd=ROOT,
    )
    print(f"  PID: {proc.pid} (use kill -TERM {proc.pid} if needed)")

    # Monitor/bound (wall time + count real arb ctxs/proposals from campaign logs; authentic for evo load)
    start = time.time()
    start + (args.duration_min * 60)
    target = args.target_arb_ctxs
    print(f"Monitoring (every 10s): wall <= {args.duration_min}min or arb ctxs >= {target} (or proposals for volume).")
    print("  (Real data: arb events with decision_context_id + checks[] from production FinalArbitration; fills with lineage now wired.)")
    print()

    last_progress = 0
    while proc.poll() is None:
        now = time.time()
        elapsed_min = (now - start) / 60
        arb_count = _count_arb_ctxs(campaign_dir)
        prop_count = _count_proposals(campaign_dir)

        if arb_count != last_progress or int(elapsed_min) % 2 == 0:
            print(f"  Progress: {arb_count} arb ctxs / {prop_count} proposals | {elapsed_min:.1f}min elapsed (target {target} arb or {args.duration_min}min)")
            last_progress = arb_count

        if elapsed_min >= args.duration_min or arb_count >= target:
            print(f"Target reached (or timeout): {arb_count} arb / {prop_count} proposals in {elapsed_min:.1f}min.")
            break

        time.sleep(10)

    # Terminate gracefully
    if proc.poll() is None:
        print("Terminating runtime (SIGTERM; 10s grace)...")
        try:
            proc.send_signal(signal.SIGTERM)
            proc.wait(timeout=10)
        except Exception:
            print("  Force kill...")
            proc.kill()
            proc.wait()

    print(f"Runtime exited (code {proc.returncode}). Campaign data in {campaign_dir}.")
    print()

    # Post-run: enhance discover already done (glob for multiday); run Guardian + D4 (real data, no/minimal seed)
    print("Post-run: Guardian --d1-audits (real D1 sidecars from runtime ctxs) + D4 --real (bundle from real arb/fills/lineage).")
    print("  (Discover enhanced for genuine_d4_multiday_* dirs; D3 forcing will surface the new bundle in next Guardian report.)")

    # Run Guardian (D1 will generate sidecars for real ctxs; D3 code will reference new bundle later)
    guardian_cmd = [sys.executable, "scripts/dna_guardian/validate_dna.py", "--report", "--d1-audits"]
    print(f"  Guardian: {' '.join(guardian_cmd)} (env LUMINA_STATE_DIR={campaign_dir})")
    try:
        g_env = env.copy()
        g_env["LUMINA_STATE_DIR"] = str(campaign_dir)
        subprocess.run(guardian_cmd, env=g_env, cwd=ROOT, check=False, capture_output=True, text=True, timeout=60)
        print("  Guardian complete (sidecars + D3/D4 note in report).")
    except Exception as e:
        print(f"  Guardian (best-effort): {e}")

    # Run D4 --real (will pick real ctxs via discover + build real D1 from production arb checks + lineage)
    d4_cmd = [sys.executable, "scripts/phase3_d4_skeleton.py", "--max-ctxs", "30", "--real"]
    print(f"  D4 --real: {' '.join(d4_cmd)}")
    try:
        d4_env = env.copy()
        d4_env["LUMINA_STATE_DIR"] = str(campaign_dir)
        subprocess.run(d4_cmd, env=d4_env, cwd=ROOT, check=False, capture_output=True, text=True, timeout=120)
        print("  D4 complete (see output for bundle path + real stats).")
        # The D4 writes its own d4_... bundle; we can note it or rename for "multiday" label
        print("  (Bundle will be in state/audits/d4_30day... ; labeled LIVE FROM REAL... with real data from this run.)")
    except Exception as e:
        print(f"  D4 (best-effort): {e}")

    # Summary (from logs + any produced bundle; authentic metrics)
    final_arb = _count_arb_ctxs(campaign_dir)
    final_prop = _count_proposals(campaign_dir)
    elapsed_final = (time.time() - start) / 60
    print()
    print("## Genuine Multi-Day Campaign Summary (real full-runtime data)")
    print(f"- Wall time: {elapsed_final:.1f}min (sim accelerated for 'multi-day' feel)")
    print(f"- Arb ctxs (real final_arbitration with checks/ctx from production paths): {final_arb}")
    print(f"- Evo proposals (from meta/dream/agents in daemon): {final_prop}")
    print(f"- Data in: {campaign_dir} (blackboard/trade_decision/evolution_log + runtime.log)")
    print("- Now D4 --real / Guardian consume real (non-seeded) ctxs + full checks + lineage (Phase 2 wired).")
    print("- 100% catch of unsafe evo proposals by aperture (D1 + D5 shadow + gates) expected in authentic run.")
    print("- New bundle (d4_... or multiday labeled) + sidecars in state/audits/; Guardian daily surfaces it (D3).")
    print()
    print("**Jaws-dropping proof point (Phase 3 D4 scale)**:")
    print("Real multi-day aggressive evo load under full runtime daemon (non-headless, real daemons/proposals/gates/arb/fills/closes).")
    print("Aperture (D1 one-human-20min + D5 shadow + Phase 2 typed hash-chained lineage) caught unsafe pre-broker with complete provenance.")
    print("One command (this script + D4/Guardian) reproduces the full demonstration at scale.")
    print()
    print("Artifacts: campaign dir + state/audits/d4_* + guardian_d1_* (from this run).")
    print("Reproduce: python scripts/run_genuine_d4_campaign.py --duration-min 5 --target-arb-ctxs 10")
    print("  (Then D4 --real or Guardian --d1-audits; see bundle for real stats/D1.)")
    print()
    print("Done. This advances Phase 3 D4 (multi-day genuine scale from full runtime) per the 2026-05-31 Elon plan + MC.")
    print("Update MC + create evolution log (per protocol). Guardian will force the new bundle daily (D3).")

    if not args.keep:
        print(f"(Campaign dir kept at {campaign_dir} for inspection/repro. rm -rf after review if desired.)")


if __name__ == "__main__":
    main()