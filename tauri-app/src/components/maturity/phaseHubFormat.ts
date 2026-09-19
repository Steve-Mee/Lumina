/** Phase Hub operator-facing formatters — never dump nested JSON. */
import type { AdvanceMode, MaturityHubPayload } from "@/lib/maturationClient";

export const ADVANCE_OPTIONS: {
  id: AdvanceMode;
  label: string;
  hint: string;
  tip: string;
  action: string;
}[] = [
  {
    id: "manual",
    label: "Manual",
    hint: "You press Start for every phase",
    tip: "Default. You press Start for the focus phase. After it passes you press Start for the next.",
    action: "Stay manual",
  },
  {
    id: "telegram",
    label: "Telegram",
    hint: "Next phase waits for a YES on Telegram",
    tip: "After a phase finishes, Lumina asks on Telegram. Not required to start the focus phase.",
    action: "Use Telegram",
  },
  {
    id: "auto_evolve",
    label: "Auto evolve",
    hint: "Chain the next phase when this one passes",
    tip: "After a phase passes, the next starts on its own. REAL still needs explicit human approval.",
    action: "Auto-chain",
  },
];

export const ADVANCE_MODE_HELP =
  "Not a gate for Start. This only decides what happens after a phase finishes. Manual is already on.";

export type HubCharterTile = {
  label: string;
  value: string;
  tip: string;
  footnote: string;
};

const SKIP_LEARNED_KEYS = new Set([
  "birth_exit",
  "exit_proofs",
  "soft_block_rate_per_1k_signals",
  "training_mode",
]);

const STAGE_LABELS: Record<string, string> = {
  stage1_trend: "Trend",
  stage2_range: "Range",
  stage3_mixed: "Mixed",
  stage4_viable_plant: "Viable plant",
  stage5_probe_handoff: "Probe & handoff",
};

const PROOF_LABELS: Record<string, string> = {
  evolution_proof_passed: "Evolution proof",
  twin_observability: "Twin watch of this run",
  twin_watch: "Twin watch of this run",
  twin_watch_missing: "Twin watch of this run",
  occupancy_missing: "Occupancy exam band",
  occupancy_in_band: "Occupancy exam band",
  recovery_not_proven: "Recovery without cheat",
  recovery_ok: "Recovery without cheat",
  regime_visibility_missing: "Regime visibility",
  regime_visibility: "Regime visibility",
  birth_freeze_violated: "Birth freeze intact",
  birth_freeze_intact: "Birth freeze intact",
  skill_not_policy_only: "Policy-only skill",
  policy_only: "Policy-only skill",
  child_sha_equals_init: "No substitution (child ≠ parent)",
  no_substitution: "No substitution (child ≠ parent)",
  deck_unlocked: "Command Deck unlock",
  deck_live: "Command Deck live",
  deck_not_live: "Command Deck live",
  sim_envelope_sealed: "SIM envelope sealed",
  first_sim_order_placed: "First SIM order",
  first_honest_fill: "First honest SIM fill",
  "n_P>=150": "Policy SIM closes ≥ 150",
  economic_viability: "WR ≥ geometry BE and mean R ≥ 0",
  awakening_child_loaded: "Awakening child loaded",
  awakening_child_not_loaded: "Awakening child loaded",
  envelope_not_breached: "Envelope not breached",
  envelope_breached: "Envelope not breached",
  mode_sim_fail_closed: "SIM mode fail-closed",
  wr_or_be_missing: "Skill WR vs geometry BE",
  mean_r_missing: "Mean R ≥ 0",
  sim_real_guard_stable: "SIM green streak",
  "n_A>=150": "Policy SIM closes ≥ 150",
  "n_D>=5": "Five green session days",
  risk_discipline: "Sharpe ≥ 0.20 and DD ≤ 12%",
  constitution_0: "Constitution 0",
  constitution_violated: "Constitution 0",
  playground_completed: "Playground completed",
  playground_not_completed: "Playground completed",
  playground_child_loaded: "Playground child loaded",
  playground_child_not_loaded: "Playground child loaded",
  mode_sim_real_guard: "sim_real_guard",
  promotion_gate_passed: "Promotion gate",
  promotion_gate_this_run: "PromotionGate 4/4 this clock",
  shadow_validation_passed: "Shadow validation",
  shadow_this_run: "Shadow of this clock",
  human_real_approval: "Human REAL approval",
  genesis_contract_signed: "Genesis contract",
  setup_complete: "Setup complete",
  foundation_five_receipts_v2: "Five foundation receipts",
  foundation_fitness_vector: "Fitness vector",
  unknown_phase: "Unknown phase (hub ledger gap)",
};

const PHASE_LABELS: Record<string, string> = {
  genesis: "Genesis",
  birth: "Birth",
  awakening: "Awakening",
  playground: "Playground",
  apprenticeship: "Apprenticeship",
  proving_ground: "Proving Ground",
  real: "REAL",
};

export function phaseLabel(id: string | null | undefined): string {
  if (!id) return "—";
  return PHASE_LABELS[id] ?? id;
}

export function proofLabel(code: string): string {
  const raw = String(code || "").trim();
  if (!raw) return "";
  if (PROOF_LABELS[raw]) return PROOF_LABELS[raw];
  const twin = raw.match(/^twin_samples>=(\d+)$/);
  if (twin) return `Twin watch of this run (dump ${twin[1]} does not count)`;
  const nb = raw.match(/^n_B=(\d+) < (\d+)$/);
  if (nb) return `Policy closes ${nb[1]} / ${nb[2]}`;
  const np = raw.match(/^n_P=(\d+) < (\d+)$/);
  if (np) return `Playground policy closes ${np[1]} / ${np[2]}`;
  const na = raw.match(/^n_A=(\d+) < (\d+)$/);
  if (na) return `Apprenticeship policy closes ${na[1]} / ${na[2]}`;
  const ndg = raw.match(/^n_([DG])=(\d+) < (\d+)$/);
  if (ndg) return ndg[1] === "D" ? `Green session days ${ndg[2]} / ${ndg[3]}` : `Proving Ground policy closes ${ndg[2]} / ${ndg[3]}`;
  return raw.replace(/_/g, " ");
}

export function stageLabel(stage: string | null | undefined): string {
  if (!stage) return "—";
  return STAGE_LABELS[stage] ?? stage.replace(/_/g, " ");
}

function asFiniteNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim() !== "") {
    const n = Number(value);
    return Number.isFinite(n) ? n : null;
  }
  return null;
}

export function formatPct(value: unknown): string {
  const n = asFiniteNumber(value);
  if (n == null) return "—";
  const ratio = Math.abs(n) <= 1.5 ? n : n / 100;
  return `${(ratio * 100).toFixed(1)}%`;
}

export function formatCount(value: unknown): string {
  const n = asFiniteNumber(value);
  if (n == null) return "—";
  return Math.round(n).toLocaleString("en-US");
}

export function formatScore(value: unknown, digits = 2): string {
  const n = asFiniteNumber(value);
  if (n == null) return "—";
  return n.toFixed(digits);
}

function scalarLine(key: string, value: unknown): string | null {
  if (value == null || value === "") return null;
  if (typeof value === "object") return null;
  if (key === "trades") return `Trades ${formatCount(value)}`;
  if (key === "stage_winrate") return `Stage WR ${formatPct(value)}`;
  if (key === "edgescore") return `EdgeScore ${formatScore(value)}`;
  if (key === "curriculum_stage") return `Last stage ${stageLabel(String(value))}`;
  if (key === "message") return String(value);
  if (key === "milestones" && Array.isArray(value)) {
    return `Milestones: ${value.map((m) => proofLabel(String(m))).join(", ")}`;
  }
  return `${key.replace(/_/g, " ")}: ${String(value)}`;
}

/** Operator lines only — nested objects are omitted, never JSON.stringified. */
export function formatLearned(learned: Record<string, unknown> | undefined): string[] {
  if (!learned || typeof learned !== "object") return [];
  const lines: string[] = [];
  for (const [key, value] of Object.entries(learned)) {
    if (SKIP_LEARNED_KEYS.has(key)) continue;
    if (key === "milestones" && Array.isArray(value)) {
      const line = scalarLine(key, value);
      if (line) lines.push(line);
      continue;
    }
    const line = scalarLine(key, value);
    if (line) lines.push(line);
  }
  return lines.slice(0, 8);
}

export function hubVerdict(hub: MaturityHubPayload | null): string {
  const focus = hub?.focus_phase || hub?.next_phase || "";
  const focusMsg =
    hub?.focus_learned && typeof hub.focus_learned.note === "string"
      ? hub.focus_learned.note.trim()
      : "";
  if (focus === "awakening") {
    return focusMsg || "Awakening: open eyes — prefer better than frozen π*. STABLE + n_B≥500 AND.";
  }
  if (focus === "playground") {
    return focusMsg || "Playground: crawl in NT SIM. First fill, n_P≥150, WR≥BE, mean R≥0.";
  }
  if (focus === "apprenticeship") {
    return focusMsg || "Apprenticeship: walk. 5 green sim_real_guard days, Sharpe≥0.20, DD≤12%.";
  }
  if (focus === "proving_ground") return focusMsg || "Proving Ground: driving test. Cert 48%/0.35/8% + shadow + PromotionGate.";
  const message = hub?.learned && typeof hub.learned.message === "string" ? hub.learned.message.trim() : "";
  if (message) return message;
  if (hub?.birth_exit_exited) {
    return "Birth Foundation complete — evolvable plant. Next is Awakening.";
  }
  return "Birth Foundation still open — five v2 receipts + fitness required.";
}

export function hubCharterTiles(hub: MaturityHubPayload | null): HubCharterTile[] {
  const learned = hub?.learned ?? {};
  const nextLabel = phaseLabel(hub?.next_phase);
  return [
    {
      label: "Last completed",
      value: phaseLabel(hub?.last_completed),
      tip: "Continuum checkpoint. Birth is Foundation 5/5 + fitness, not a certificate.",
      footnote: hub?.birth_exit_exited ? "Foundation 5/5 · fitness checksum ok" : "Birth exit not satisfied",
    },
    {
      label: "Trades",
      value: formatCount(learned.trades),
      tip: "Closed Birth curriculum trades (honest MES 1-lot), not a profit exam.",
      footnote: "Survival loop · not REAL PnL",
    },
    {
      label: "Stage WR",
      value: formatPct(learned.stage_winrate),
      tip: "Last-stage winrate is diagnostic. Birth pass is occupancy / process-R / edge.",
      footnote: "Not a WR pass gate",
    },
    {
      label: "EdgeScore",
      value: formatScore(learned.edgescore),
      tip: "Birth survival EdgeScore from the last foundation stage.",
      footnote: stageLabel(
        typeof learned.curriculum_stage === "string" ? learned.curriculum_stage : null,
      ),
    },
    {
      label: "Birth exit",
      value: hub?.birth_exit_exited ? "Yes" : "No",
      tip: "Five foundation v2 receipts + fitness vector. Certificate OOS is Proving Ground.",
      footnote: hub?.birth_exit_exited ? "Hub checkpoint saved" : "Need receipts + fitness",
    },
    {
      label: "Next phase",
      value: nextLabel,
      tip: "Operator starts the next continuum phase. REAL always needs explicit human approval.",
      footnote: "Operator-started · REAL stays human-gated",
    },
  ];
}

export function formatRemainingSec(sec: number | null | undefined): string {
  if (sec == null || Number.isNaN(sec)) return "";
  const s = Math.max(0, Math.floor(sec));
  if (s <= 0) return "expired";
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const r = s % 60;
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return `${m}m ${r}s`;
  return `${r}s`;
}

export function formatAwakeningProbe(
  learned: Record<string, unknown> | undefined,
): string | null {
  const base = asFiniteNumber(learned?.birth_oos_wr ?? learned?.baseline_oos_wr);
  const probe = asFiniteNumber(learned?.wr ?? learned?.probe_oos_wr);
  if (base == null || probe == null) return null;
  const lift = probe - base;
  const sign = lift >= 0 ? "+" : "";
  return `Birth OOS ${formatPct(base)} → shot ${formatPct(probe)} (lift ${sign}${formatPct(lift)})`;
}

export type HubWipeKind = "awakening" | "playground" | "apprenticeship" | "proving_ground" | "birth" | "full";

export const HUB_WIPE_CARDS: {
  kind: HubWipeKind;
  label: string;
  hint: string;
  tip: string;
  tone: "warn" | "danger";
}[] = [
  {
    kind: "awakening",
    label: "Wipe Awakening",
    hint: "Keep Birth · destroy shot",
    tip: "Remove generated Awakening data only. Birth plant, frozen π*, history, and setup stay. Two-step confirm.",
    tone: "warn",
  },
  {
    kind: "birth",
    label: "Wipe Birth",
    hint: "Keep history · destroy plant",
    tip: "Destroy the Birth plant and Awakening. Tick cache and setup stay. Two-step confirm.",
    tone: "warn",
  },
  {
    kind: "full",
    label: "Full wipe",
    hint: "Setup kept · blank Genesis",
    tip: "Wipe Birth, Awakening, and tick cache. Smart Setup stays. You restart from a blank Genesis deck. Two-step confirm.",
    tone: "danger",
  },
];

export function startPhaseCtaLabel(
  nextPhase: string | null,
  opts?: { retry?: boolean },
): string {
  if (!nextPhase) return "Continuum complete";
  if (nextPhase === "real") return "Approve REAL (human)";
  const verb = opts?.retry ? "Retry" : "Start";
  return `${verb} ${phaseLabel(nextPhase)}`;
}

function lastResultRecord(
  hub: MaturityHubPayload | null,
): Record<string, unknown> | null {
  const raw = hub?.last_result;
  return raw && typeof raw === "object" ? raw : null;
}

export function phaseStartIncomplete(hub: MaturityHubPayload | null): boolean {
  if (!hub) return false;
  if (hub.runner_active) return false;
  const result = lastResultRecord(hub);
  if (result && result.ok === false) return true;
  return hub.focus_status === "failed";
}

function missingProofLabels(hub: MaturityHubPayload | null): string[] {
  const fromResult = lastResultRecord(hub)?.missing;
  const codes = Array.isArray(fromResult)
    ? fromResult
    : hub?.exit_eval && !hub.exit_eval.ok
      ? hub.exit_eval.missing ?? []
      : [];
  return codes.map((code) => proofLabel(String(code))).filter(Boolean);
}

export function describePhaseStartOutcome(
  hub: MaturityHubPayload | null,
  startedPhase: string,
): { ok: boolean; message: string } {
  const label = phaseLabel(startedPhase);
  if (!hub) {
    return { ok: false, message: `${label} start could not be confirmed — hub unavailable` };
  }
  if (hub.runner_active) {
    return { ok: true, message: `${label} is running` };
  }
  const result = lastResultRecord(hub);
  if (result && result.ok === true) {
    return { ok: true, message: `${label} complete` };
  }
  const missing = missingProofLabels(hub);
  if (missing.length > 0) {
    return {
      ok: false,
      message: `${label} did not pass: ${missing.join(", ")}. Proofs stay fail-closed.`,
    };
  }
  const err =
    (typeof hub.error === "string" && hub.error.trim()) ||
    (typeof result?.error === "string" ? result.error : "");
  return {
    ok: false,
    message: err ? `${label} did not pass: ${err}` : `${label} did not pass`,
  };
}
