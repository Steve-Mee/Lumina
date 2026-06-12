import { describe, expect, it } from "vitest";

import {
  mapAppPhase,
  markPayloadBackendUnreachable,
  resolveAppPhase,
  resolvePhaseOnRefreshError,
  shouldEnterCockpit,
  type AppPhase,
} from "@/lib/onboardingPhase";
import type { AppSurface, OnboardingPayload } from "@/lib/onboardingSteps";

/** Cold-start: prior phase is always loading after first refresh. */
const COLD_START: AppPhase = "loading";

function payload(
  overrides: Partial<OnboardingPayload> = {},
  surface: AppSurface = "setup",
): OnboardingPayload {
  const { birth: birthOverrides, app_surface: surfaceOverride, ...rest } = overrides;
  return {
    backend: { reachable: true, url: "http://127.0.0.1:8000" },
    setup_complete: false,
    skip_wizard: false,
    app_surface: surfaceOverride ?? surface,
    birth: { status: "idle", artifacts_ok: false, ...birthOverrides },
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
    required_steps: ["welcome", "configuration"],
    wizard_steps: ["welcome", "configuration"],
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
    ...rest,
  };
}

function coldStart(p: OnboardingPayload): AppPhase {
  return mapAppPhase(p, {
    priorPhase: COLD_START,
    birthPhaseCommitted: false,
    activating: false,
  });
}

describe("onboardingPhase cold-start matrix (T1–T8)", () => {
  it("T1 fresh install → setup wizard", () => {
    const p = payload(
      {
        setup_complete: false,
        wizard_steps: ["welcome", "ollama", "credentials", "configuration", "birth"],
      },
      "setup",
    );
    expect(coldStart(p)).toBe("wizard");
  });

  it("T2 setup complete, birth idle → birth phase", () => {
    const p = payload(
      {
        setup_complete: true,
        skip_wizard: false,
        birth: { status: "idle", artifacts_ok: false },
        required_steps: ["welcome", "birth"],
        wizard_steps: ["birth"],
      },
      "birth",
    );
    expect(coldStart(p)).toBe("birth");
  });

  it("T3 birth running → birth phase", () => {
    const p = payload(
      {
        setup_complete: true,
        skip_wizard: false,
        birth: { status: "running", artifacts_ok: false },
        wizard_steps: [],
      },
      "birth",
    );
    expect(coldStart(p)).toBe("birth");
  });

  it("T4 birth interrupted, no artifacts → birth phase", () => {
    const p = payload(
      {
        setup_complete: true,
        birth: { status: "interrupted", artifacts_ok: false },
      },
      "birth",
    );
    expect(coldStart(p)).toBe("birth");
  });

  it("T5 birth error, no artifacts → birth phase", () => {
    const p = payload(
      {
        setup_complete: true,
        birth: { status: "error", artifacts_ok: false },
      },
      "birth",
    );
    expect(coldStart(p)).toBe("birth");
  });

  it("T6 birth complete with artifacts → command deck", () => {
    const p = payload(
      {
        setup_complete: true,
        skip_wizard: true,
        birth: { status: "completed", artifacts_ok: true },
        wizard_steps: [],
      },
      "deck",
    );
    expect(coldStart(p)).toBe("cockpit");
    expect(shouldEnterCockpit(p)).toBe(true);
  });

  it("T7 restart after T6 → deck directly", () => {
    const p = payload(
      {
        setup_complete: true,
        skip_wizard: true,
        birth: { status: "completed", artifacts_ok: true },
      },
      "deck",
    );
    expect(coldStart(p)).toBe("cockpit");
  });

  it("T8 backend unreachable → setup wizard", () => {
    const p = payload(
      {
        setup_complete: true,
        backend: { reachable: false, url: "http://127.0.0.1:8000", error: "down" },
        birth: { status: "completed", artifacts_ok: true },
      },
      "setup",
    );
    expect(coldStart(p)).toBe("wizard");
  });
});

describe("onboardingPhase fail-closed regressions", () => {
  it("completed status without artifacts routes to birth", () => {
    const p = payload(
      {
        setup_complete: true,
        skip_wizard: false,
        birth: { status: "completed", artifacts_ok: false },
      },
      "birth",
    );
    expect(coldStart(p)).toBe("birth");
    expect(shouldEnterCockpit(p)).toBe(false);
  });

  it("refresh from cockpit with incomplete birth returns birth", () => {
    const p = payload(
      {
        setup_complete: true,
        birth: { status: "idle", artifacts_ok: false },
      },
      "birth",
    );
    expect(
      mapAppPhase(p, {
        priorPhase: "cockpit",
        birthPhaseCommitted: false,
        activating: false,
      }),
    ).toBe("birth");
  });

  it("completed + certificate_ok false routes to birth", () => {
    const p = payload(
      {
        setup_complete: true,
        skip_wizard: false,
        birth: { status: "completed", artifacts_ok: true, certificate_ok: false },
      },
      "birth",
    );
    expect(coldStart(p)).toBe("birth");
    expect(shouldEnterCockpit(p)).toBe(false);
  });

  it("certificate_failed status routes to birth", () => {
    const p = payload(
      {
        setup_complete: true,
        skip_wizard: false,
        birth: {
          status: "certificate_failed",
          artifacts_ok: false,
          certificate_ok: false,
        },
      },
      "birth",
    );
    expect(coldStart(p)).toBe("birth");
    expect(shouldEnterCockpit(p)).toBe(false);
  });

  it("error surface never maps to deck", () => {
    const p = payload(
      {
        setup_complete: true,
        skip_wizard: false,
        birth: { status: "error", artifacts_ok: false },
      },
      "birth",
    );
    expect(coldStart(p)).toBe("birth");
    expect(shouldEnterCockpit(p)).toBe(false);
  });
});

describe("resolvePhaseOnRefreshError", () => {
  it("cold start failure → wizard", () => {
    expect(resolvePhaseOnRefreshError("loading", null)).toBe("wizard");
  });

  it("deck session failure → stay on cockpit", () => {
    const last = payload({ setup_complete: true }, "deck");
    expect(resolvePhaseOnRefreshError("cockpit", last)).toBe("cockpit");
  });

  it("birth session failure → stay on birth", () => {
    const last = payload({ setup_complete: true }, "birth");
    expect(resolvePhaseOnRefreshError("birth", last)).toBe("birth");
  });

  it("marks cached payload unreachable without changing app_surface", () => {
    const last = payload({ setup_complete: true }, "birth");
    const marked = markPayloadBackendUnreachable(last, "fetch failed");
    expect(marked.backend.reachable).toBe(false);
    expect(marked.backend.error).toBe("fetch failed");
    expect(marked.app_surface).toBe("birth");
  });
});

describe("resolveAppPhase alias", () => {
  it("matches mapAppPhase for cold start", () => {
    const p = payload({ setup_complete: true }, "birth");
    expect(resolveAppPhase(p, COLD_START, false)).toBe("birth");
  });
});
