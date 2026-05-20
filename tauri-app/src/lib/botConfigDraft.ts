import type { OnboardingPayload } from "@/lib/onboardingSteps";

export type MutationDepth = "conservative" | "moderate" | "radical";

export type OperationsMode = "paper" | "sim" | "sim_real_guard" | "real";

export interface BotConfigDraft {
  mode: OperationsMode;
  risk: {
    kelly_fraction: number;
    daily_loss_cap: number | null;
    max_total_open_risk: number;
    real_capital_safety_threshold_usd: number;
  };
  evolution: {
    approval_required: boolean;
    aggressive_evolution: boolean;
    max_mutation_depth: MutationDepth;
  };
  preferences: {
    instrument: string;
    voice_enabled: boolean;
    screen_share_enabled: boolean;
    dashboard_enabled: boolean;
    runtime_trace: boolean;
    runtime_trace_interval_sec: number;
    latency_sla_ms: number;
  };
}

export function defaultBotConfigDraft(): BotConfigDraft {
  return {
    mode: "sim",
    risk: {
      kelly_fraction: 1.0,
      daily_loss_cap: null,
      max_total_open_risk: 3000,
      real_capital_safety_threshold_usd: 1000,
    },
    evolution: {
      approval_required: true,
      aggressive_evolution: true,
      max_mutation_depth: "radical",
    },
    preferences: {
      instrument: "ES",
      voice_enabled: true,
      screen_share_enabled: true,
      dashboard_enabled: true,
      runtime_trace: true,
      runtime_trace_interval_sec: 2,
      latency_sla_ms: 300,
    },
  };
}

function parseMutationDepth(value: unknown, fallback: MutationDepth): MutationDepth {
  const normalized = String(value ?? fallback).toLowerCase();
  if (normalized === "conservative" || normalized === "moderate" || normalized === "radical") {
    return normalized;
  }
  return fallback;
}

function parseOperationsMode(value: unknown, fallback: OperationsMode = "sim"): OperationsMode {
  const normalized = String(value ?? fallback).trim().toLowerCase();
  if (
    normalized === "paper" ||
    normalized === "sim" ||
    normalized === "sim_real_guard" ||
    normalized === "real"
  ) {
    return normalized;
  }
  return fallback;
}

export function hydrateBotConfigDraftFromPayload(
  payload: OnboardingPayload,
  prior?: Partial<BotConfigDraft>,
): BotConfigDraft {
  const d = payload.defaults;
  const parsedMode = parseOperationsMode(payload.defaults.mode, "sim");
  const modeKey = parsedMode === "real" ? "real" : "sim";
  const modeDefaults = (d[modeKey] ?? {}) as Record<string, unknown>;
  const rc = d.risk_controller as Record<string, unknown>;
  const evo = d.evolution as Record<string, unknown>;

  return {
    mode: parsedMode,
    risk: {
      kelly_fraction: Number(modeDefaults.kelly_fraction ?? prior?.risk?.kelly_fraction ?? 1.0),
      daily_loss_cap:
        modeDefaults.daily_loss_cap != null
          ? Number(modeDefaults.daily_loss_cap)
          : prior?.risk?.daily_loss_cap ?? null,
      max_total_open_risk: Number(
        modeDefaults.max_total_open_risk ?? rc.max_total_open_risk ?? prior?.risk?.max_total_open_risk ?? 3000,
      ),
      real_capital_safety_threshold_usd: Number(
        rc.real_capital_safety_threshold_usd ??
          prior?.risk?.real_capital_safety_threshold_usd ??
          1000,
      ),
    },
    evolution: {
      approval_required: Boolean(
        modeDefaults.approval_required ?? evo.approval_required ?? prior?.evolution?.approval_required ?? true,
      ),
      aggressive_evolution: Boolean(
        modeDefaults.aggressive_evolution ?? prior?.evolution?.aggressive_evolution ?? true,
      ),
      max_mutation_depth: parseMutationDepth(
        modeDefaults.max_mutation_depth,
        modeKey === "real" ? "conservative" : "radical",
      ),
    },
    preferences: {
      instrument: String(prior?.preferences?.instrument ?? "ES"),
      voice_enabled: prior?.preferences?.voice_enabled ?? true,
      screen_share_enabled: prior?.preferences?.screen_share_enabled ?? true,
      dashboard_enabled: Boolean(
        (d.diagnostics as Record<string, unknown> | undefined)?.dashboard_enabled ??
          prior?.preferences?.dashboard_enabled ??
          true,
      ),
      runtime_trace: Boolean(
        (d.diagnostics as Record<string, unknown> | undefined)?.runtime_trace ??
          prior?.preferences?.runtime_trace ??
          true,
      ),
      runtime_trace_interval_sec: Number(
        (d.diagnostics as Record<string, unknown> | undefined)?.runtime_trace_interval_sec ??
          prior?.preferences?.runtime_trace_interval_sec ??
          2,
      ),
      latency_sla_ms: Number(
        (d.diagnostics as Record<string, unknown> | undefined)?.latency_sla_ms ??
          prior?.preferences?.latency_sla_ms ??
          300,
      ),
    },
  };
}

export function botConfigDraftEquals(a: BotConfigDraft, b: BotConfigDraft): boolean {
  return JSON.stringify(a) === JSON.stringify(b);
}

export function applyPaperModePreset(draft: BotConfigDraft): BotConfigDraft {
  return {
    ...draft,
    mode: "paper",
    evolution: {
      approval_required: false,
      aggressive_evolution: true,
      max_mutation_depth: "moderate",
    },
    risk: {
      ...draft.risk,
      kelly_fraction: 1.0,
      daily_loss_cap: null,
    },
  };
}

export function applySimModePreset(draft: BotConfigDraft): BotConfigDraft {
  return {
    ...draft,
    mode: "sim",
    evolution: {
      approval_required: false,
      aggressive_evolution: true,
      max_mutation_depth: draft.evolution.max_mutation_depth === "conservative" ? "radical" : draft.evolution.max_mutation_depth,
    },
    risk: {
      ...draft.risk,
      kelly_fraction: 1.0,
      daily_loss_cap: null,
    },
  };
}

export function applyRealModePreset(draft: BotConfigDraft): BotConfigDraft {
  return {
    ...draft,
    mode: "real",
    evolution: {
      approval_required: true,
      aggressive_evolution: false,
      max_mutation_depth:
        draft.evolution.max_mutation_depth === "radical" ? "conservative" : draft.evolution.max_mutation_depth,
    },
    risk: {
      ...draft.risk,
      kelly_fraction: 0.25,
      daily_loss_cap: -150,
      max_total_open_risk: 150,
    },
  };
}

export function hydrateBotConfigFromDefaults(
  defaults: OnboardingPayload["defaults"],
): BotConfigDraft {
  return hydrateBotConfigDraftFromPayload({ defaults } as OnboardingPayload);
}

export function toBotConfigPayload(draft: BotConfigDraft) {
  return {
    mode: draft.mode,
    risk: draft.risk,
    evolution: draft.evolution,
    preferences: draft.preferences,
  };
}
