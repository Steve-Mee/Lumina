import { beforeEach, describe, expect, it } from "vitest";

import { setPreferApprenticeshipHub } from "@/lib/apprenticeship/apprenticeshipSurfacePref";
import { setPreferAwakeningHub } from "@/lib/awakening/awakeningSurfacePref";
import { setPreferPlaygroundHub } from "@/lib/playground/playgroundSurfacePref";
import { setPreferProvingGroundHub } from "@/lib/provingGround/provingGroundSurfacePref";

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

describe("awakening cinematic surface", () => {
  beforeEach(() => {
    setPreferAwakeningHub(false);
  });

  it("maps app_surface awakening to awakening phase", () => {
    const p = payload({ setup_complete: true, skip_wizard: true }, "awakening");
    expect(coldStart(p)).toBe("awakening");
  });

  it("honors session prefer-hub override", () => {
    setPreferAwakeningHub(true);
    const p = payload({ setup_complete: true, skip_wizard: true }, "awakening");
    expect(coldStart(p)).toBe("hub");
  });

  it("preserves awakening on refresh error", () => {
    const p = payload({ setup_complete: true }, "awakening");
    expect(resolvePhaseOnRefreshError("awakening", p)).toBe("awakening");
  });
});

describe("playground habitat surface", () => {
  beforeEach(() => {
    setPreferPlaygroundHub(false);
  });

  it("maps app_surface playground to playground phase", () => {
    const p = payload({ setup_complete: true, skip_wizard: true }, "playground");
    expect(coldStart(p)).toBe("playground");
  });

  it("honors session prefer-hub override", () => {
    setPreferPlaygroundHub(true);
    const p = payload({ setup_complete: true, skip_wizard: true }, "playground");
    expect(coldStart(p)).toBe("hub");
  });

  it("preserves playground on refresh error", () => {
    const p = payload({ setup_complete: true }, "playground");
    expect(resolvePhaseOnRefreshError("playground", p)).toBe("playground");
  });
});

describe("apprenticeship cinematic surface", () => {
  beforeEach(() => {
    setPreferApprenticeshipHub(false);
  });

  it("maps app_surface apprenticeship to apprenticeship phase", () => {
    const p = payload({ setup_complete: true, skip_wizard: true }, "apprenticeship");
    expect(coldStart(p)).toBe("apprenticeship");
  });

  it("honors session prefer-hub override", () => {
    setPreferApprenticeshipHub(true);
    const p = payload({ setup_complete: true, skip_wizard: true }, "apprenticeship");
    expect(coldStart(p)).toBe("hub");
  });

  it("preserves apprenticeship on refresh error", () => {
    const p = payload({ setup_complete: true }, "apprenticeship");
    expect(resolvePhaseOnRefreshError("apprenticeship", p)).toBe("apprenticeship");
  });
});

describe("proving ground cinematic surface", () => {
  beforeEach(() => {
    setPreferProvingGroundHub(false);
  });

  it("maps app_surface proving_ground to proving_ground phase", () => {
    const p = payload({ setup_complete: true, skip_wizard: true }, "proving_ground");
    expect(coldStart(p)).toBe("proving_ground");
  });

  it("honors session prefer-hub override", () => {
    setPreferProvingGroundHub(true);
    const p = payload({ setup_complete: true, skip_wizard: true }, "proving_ground");
    expect(coldStart(p)).toBe("hub");
  });

  it("preserves proving_ground on refresh error", () => {
    const p = payload({ setup_complete: true }, "proving_ground");
    expect(resolvePhaseOnRefreshError("proving_ground", p)).toBe("proving_ground");
  });
});

describe("setup review from Birth", () => {
  it("forces wizard while setupReviewActive even when app_surface is birth", () => {
    const p = payload(
      {
        setup_complete: true,
        birth: { status: "idle", artifacts_ok: false },
      },
      "birth",
    );
    expect(
      mapAppPhase(p, {
        priorPhase: "birth",
        birthPhaseCommitted: false,
        activating: false,
        setupReviewActive: true,
      }),
    ).toBe("wizard");
  });
});

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

  it("T6 birth complete with artifacts → phase hub", () => {
    const p = payload(
      {
        setup_complete: true,
        skip_wizard: true,
        birth: { status: "completed", artifacts_ok: true },
        wizard_steps: [],
      },
      "hub",
    );
    expect(coldStart(p)).toBe("hub");
    expect(shouldEnterCockpit(p)).toBe(false);
  });

  it("T7 restart after T6 → hub checkpoint (not re-birth)", () => {
    const p = payload(
      {
        setup_complete: true,
        skip_wizard: true,
        birth: { status: "completed", artifacts_ok: true },
      },
      "hub",
    );
    expect(coldStart(p)).toBe("hub");
  });

  it("operator deck override keeps cockpit while hub SSOT", () => {
    const p = payload(
      {
        setup_complete: true,
        skip_wizard: true,
        birth: { status: "completed", artifacts_ok: true },
      },
      "hub",
    );
    expect(
      mapAppPhase(p, {
        priorPhase: "cockpit",
        birthPhaseCommitted: false,
        activating: false,
        operatorDeckActive: true,
      }),
    ).toBe("cockpit");
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
    expect(resolvePhaseOnRefreshError("loading", null)).toBe("loading");
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
