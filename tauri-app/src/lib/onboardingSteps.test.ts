import { describe, expect, it } from "vitest";

import {
  resolveWizardSteps,
  shouldEnterCockpit,
  visibleSteps,
} from "@/lib/onboardingSteps";
import type { OnboardingPayload } from "@/lib/onboardingSteps";

const basePayload: OnboardingPayload = {
  backend: { reachable: true, url: "http://127.0.0.1:8000" },
  setup_complete: false,
  skip_wizard: false,
  app_surface: "setup",
  birth: { status: "idle", artifacts_ok: false },
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
  credentials: {
    missing: [],
    has_admin_api_key: true,
    wizard_required: false,
    skip_reason: "env_configured",
  },
  required_steps: ["welcome", "configuration", "birth"],
  wizard_steps: ["welcome", "configuration", "birth"],
  step_status: {},
  defaults: {
    mode: "sim",
    sim: {},
    real: {},
    evolution: {},
    first_boot: {},
    risk_controller: {},
  },
  smart_setup_running: false,
};

describe("onboardingSteps", () => {
  it("visibleSteps excludes welcome", () => {
    expect(visibleSteps(["welcome", "backend", "birth"])).toEqual(["backend", "birth"]);
  });

  it("resolveWizardSteps skips welcome on short path", () => {
    expect(resolveWizardSteps(["welcome", "birth"])).toEqual(["birth"]);
  });

  it("shouldEnterCockpit when app_surface is deck", () => {
    expect(
      shouldEnterCockpit({
        ...basePayload,
        app_surface: "deck",
        setup_complete: true,
        skip_wizard: true,
        birth: { status: "completed", artifacts_ok: true },
      }),
    ).toBe(true);
  });

  it("should not enter cockpit when app_surface is birth", () => {
    expect(
      shouldEnterCockpit({
        ...basePayload,
        app_surface: "birth",
        setup_complete: true,
        birth: { status: "running", artifacts_ok: false },
      }),
    ).toBe(false);
  });

  it("should not enter cockpit when setup pending", () => {
    expect(shouldEnterCockpit(basePayload)).toBe(false);
  });
});
