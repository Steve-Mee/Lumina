import { describe, expect, it } from "vitest";

import {
  applyRealModePreset,
  botConfigDraftEquals,
  defaultBotConfigDraft,
  hydrateBotConfigDraftFromPayload,
} from "@/lib/botConfigDraft";
import type { OnboardingPayload } from "@/lib/onboardingSteps";

function mockPayload(overrides: Partial<OnboardingPayload["defaults"]> = {}): OnboardingPayload {
  return {
    backend: { reachable: true, url: "http://127.0.0.1:8000" },
    setup_complete: true,
    skip_wizard: true,
    birth: { status: "completed", artifacts_ok: true },
    intelligence: {
      ollama_installed: true,
      ollama_required: true,
      recommended_model_key: "qwen",
      recommended_ollama_tag: "qwen",
      recommended_model_present: true,
      recommended_provider: "ollama",
      hardware: {},
      adaptive_intelligence: {},
      missing: [],
    },
    model_catalog: [],
    readiness: [],
    credentials: { missing: [], has_admin_api_key: true },
    required_steps: [],
    wizard_steps: [],
    step_status: {},
    defaults: {
      mode: "sim",
      sim: {
        kelly_fraction: 0.9,
        max_mutation_depth: "moderate",
        aggressive_evolution: true,
        approval_required: false,
      },
      real: { kelly_fraction: 0.25, max_mutation_depth: "conservative" },
      evolution: { approval_required: true },
      first_boot: { training_trades: 25000 },
      risk_controller: { real_capital_safety_threshold_usd: 1200, max_total_open_risk: 2800 },
      ...overrides,
    },
    smart_setup_running: false,
  } as OnboardingPayload;
}

describe("botConfigDraft", () => {
  it("hydrates from onboarding defaults including mutation depth", () => {
    const draft = hydrateBotConfigDraftFromPayload(mockPayload());
    expect(draft.risk.kelly_fraction).toBe(0.9);
    expect(draft.evolution.max_mutation_depth).toBe("moderate");
    expect(draft.risk.real_capital_safety_threshold_usd).toBe(1200);
  });

  it("detects dirty state via equality", () => {
    const a = defaultBotConfigDraft();
    const b = { ...a, risk: { ...a.risk, kelly_fraction: 0.5 } };
    expect(botConfigDraftEquals(a, a)).toBe(true);
    expect(botConfigDraftEquals(a, b)).toBe(false);
  });

  it("hydrates paper and sim_real_guard modes from defaults", () => {
    const paper = hydrateBotConfigDraftFromPayload(mockPayload({ mode: "paper" }));
    expect(paper.mode).toBe("paper");
    const guard = hydrateBotConfigDraftFromPayload(mockPayload({ mode: "sim_real_guard" }));
    expect(guard.mode).toBe("sim_real_guard");
  });

  it("real preset downgrades radical mutation depth", () => {
    const draft = applyRealModePreset({
      ...defaultBotConfigDraft(),
      evolution: {
        approval_required: false,
        aggressive_evolution: true,
        max_mutation_depth: "radical",
      },
    });
    expect(draft.mode).toBe("real");
    expect(draft.evolution.max_mutation_depth).toBe("conservative");
    expect(draft.risk.kelly_fraction).toBe(0.25);
  });
});

describe("BotConfigForm behavior", () => {
  it("blocks radical depth when target mode is real", () => {
    const draft = applyRealModePreset(defaultBotConfigDraft());
    expect(draft.evolution.max_mutation_depth).not.toBe("radical");
  });
});
