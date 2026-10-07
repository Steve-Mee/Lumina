import { describe, expect, it } from "vitest";

import {
  birthExitKeepsPhaseHub,
  phaseHubWhenAwakeningNotStarted,
} from "@/lib/awakening/awakeningStartHandoff";
import type { OnboardingPayload } from "@/lib/onboardingSteps";

function payload(surface: OnboardingPayload["app_surface"], exitOk: boolean): OnboardingPayload {
  return {
    backend: { reachable: true, url: "http://127.0.0.1:8000" },
    setup_complete: true,
    skip_wizard: true,
    app_surface: surface,
    birth: { status: "completed", artifacts_ok: true, birth_exit_ok: exitOk },
    intelligence: {
      ollama_installed: true,
      ollama_required: true,
      recommended_model_key: "qwen",
      recommended_ollama_tag: "qwen3.5:4b",
      recommended_model_present: true,
      recommended_provider: "ollama",
      hardware: {},
      adaptive_intelligence: {},
      missing: [],
    },
    model_catalog: [],
    readiness: [],
    credentials: { missing: [], has_admin_api_key: true, wizard_required: false },
    required_steps: ["welcome"],
    wizard_steps: [],
    step_status: {},
    defaults: { mode: "sim", sim: {}, real: {}, evolution: {}, first_boot: {}, risk_controller: {} },
    smart_setup_running: false,
  };
}

describe("birthExitKeepsPhaseHub", () => {
  it("keeps Phase Hub after a real Birth exit", () => {
    expect(birthExitKeepsPhaseHub({ birthExitOk: true, birthUiPhase: "idle" })).toBe(true);
    expect(birthExitKeepsPhaseHub({ birthExitOk: true, birthUiPhase: "finale" })).toBe(true);
  });

  it("releases Phase Hub when a wipe closed the Birth exit, even if finale is stale", () => {
    expect(birthExitKeepsPhaseHub({ birthExitOk: false, birthUiPhase: "finale" })).toBe(false);
    expect(birthExitKeepsPhaseHub({ birthExitOk: false, birthUiPhase: "idle" })).toBe(false);
  });

  it("keeps the handoff on finale only while exit is still unknown", () => {
    expect(birthExitKeepsPhaseHub({ birthExitOk: undefined, birthUiPhase: "finale" })).toBe(true);
    expect(birthExitKeepsPhaseHub({ birthExitOk: undefined, birthUiPhase: "idle" })).toBe(false);
  });
});

describe("phaseHubWhenAwakeningNotStarted", () => {
  it("keeps Phase Hub when Birth exited and Awakening has not started", () => {
    const next = phaseHubWhenAwakeningNotStarted(payload("hub", true));
    expect(next.app_surface).toBe("hub");
    expect(next.app_surface_reason).toBeUndefined();
  });

  it("rewrites a pending Awakening surface back to Phase Hub", () => {
    const next = phaseHubWhenAwakeningNotStarted({
      ...payload("awakening", true),
      app_surface_reason: "awakening_pending",
    });
    expect(next.app_surface).toBe("hub");
    expect(next.app_surface_reason).toBe("maturation_hub");
  });

  it("keeps a running Awakening clock on First Watch", () => {
    const next = phaseHubWhenAwakeningNotStarted({
      ...payload("awakening", true),
      app_surface_reason: "awakening_running",
    });
    expect(next.app_surface).toBe("awakening");
    expect(next.app_surface_reason).toBe("awakening_running");
  });

  it("does not move the surface while Birth has not exited", () => {
    const next = phaseHubWhenAwakeningNotStarted({
      ...payload("awakening", false),
      app_surface_reason: "awakening_pending",
    });
    expect(next.app_surface).toBe("awakening");
  });
});
