import { describe, expect, it } from "vitest";

import type { OnboardingPayload } from "@/lib/onboardingSteps";
import {
  buildStartupReadinessView,
  resolveFabricStep,
} from "@/lib/startupReadinessModel";

function basePayload(over: Partial<OnboardingPayload> = {}): OnboardingPayload {
  return {
    backend: { reachable: true, url: "http://127.0.0.1:8000" },
    setup_complete: true,
    skip_wizard: true,
    birth: {
      status: "idle",
      artifacts_ok: true,
      certificate_ok: true,
      birth_exit_ok: true,
    },
    intelligence: {
      ollama_installed: true,
      ollama_required: false,
      recommended_model_key: "m",
      recommended_ollama_tag: "m",
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
    required_steps: [],
    wizard_steps: [],
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
    app_surface: "hub",
    app_surface_reason: "birth_complete",
    ...over,
  };
}

describe("buildStartupReadinessView", () => {
  it("shows backend running while payload is null", () => {
    const view = buildStartupReadinessView({ payload: null, fetching: true });
    expect(view.ready).toBe(false);
    expect(view.steps[0]?.id).toBe("backend");
    expect(view.steps[0]?.state).toBe("running");
    expect(view.resolvedSurface).toBeNull();
  });

  it("blocks backend when fetch fails without payload", () => {
    const view = buildStartupReadinessView({
      payload: null,
      fetchError: "network down",
    });
    expect(view.steps[0]?.state).toBe("blocked");
    expect(view.canRetry).toBe(true);
    expect(view.headline).toMatch(/unreachable/i);
  });

  it("marks hub route ready when setup and birth artifacts ok", () => {
    const view = buildStartupReadinessView({ payload: basePayload() });
    expect(view.resolvedSurface).toBe("hub");
    expect(view.ready).toBe(true);
    expect(view.steps.find((s) => s.id === "birth_artifacts")?.state).toBe("done");
    expect(view.steps.find((s) => s.id === "fabric")?.state).toBe("skipped");
    expect(view.steps.find((s) => s.id === "route")?.detail).toMatch(/hub/);
  });

  it("surfaces birth path when artifacts incomplete", () => {
    const view = buildStartupReadinessView({
      payload: basePayload({
        app_surface: "birth",
        app_surface_reason: "birth_incomplete",
        birth: {
          status: "interrupted",
          artifacts_ok: false,
          certificate_ok: false,
          certificate_reason: "missing cert",
        },
      }),
    });
    expect(view.resolvedSurface).toBe("birth");
    expect(view.steps.find((s) => s.id === "birth_artifacts")?.state).toBe("running");
    expect(view.headline).toMatch(/Birth/i);
  });

  it("blocks setup when setup incomplete", () => {
    const view = buildStartupReadinessView({
      payload: basePayload({
        app_surface: "setup",
        setup_complete: false,
        skip_wizard: false,
        required_steps: ["backend", "credentials"],
        step_status: { backend: "done", credentials: "pending" },
        credentials: {
          missing: ["LUMINA_JWT_SECRET_KEY"],
          has_admin_api_key: false,
          wizard_required: true,
        },
      }),
    });
    expect(view.resolvedSurface).toBe("setup");
    expect(view.steps.find((s) => s.id === "credentials")?.state).toBe("running");
  });

  it("marks nt_process blocked when NinjaTrader is not running", () => {
    const view = buildStartupReadinessView({
      payload: basePayload({ app_surface: "hub" }),
      ntRunning: false,
      ntLinkDeferred: false,
    });
    expect(view.steps.find((s) => s.id === "nt_process")?.state).toBe("blocked");
  });

  it("skips nt_process when operator deferred the link", () => {
    const view = buildStartupReadinessView({
      payload: basePayload({ app_surface: "hub" }),
      ntRunning: false,
      ntLinkDeferred: true,
    });
    expect(view.steps.find((s) => s.id === "nt_process")?.state).toBe("skipped");
    expect(view.steps.find((s) => s.id === "nt_process")?.detail).toMatch(/without link/i);
  });

  it("shows live waitDetail on nt_process while waiting", () => {
    const view = buildStartupReadinessView({
      payload: basePayload({ app_surface: "birth" }),
      ntRunning: false,
      ntWaiting: true,
      waitDetail: "Process up — waiting for Fabric host…",
    });
    expect(view.steps.find((s) => s.id === "nt_process")?.state).toBe("running");
    expect(view.steps.find((s) => s.id === "nt_process")?.detail).toMatch(/Fabric host/i);
  });

  it("hydrates fabric step from soft probe without blocking hub ready", () => {
    const green = buildStartupReadinessView({
      payload: basePayload({ app_surface: "hub" }),
      fabricProbe: { phase: "done", green: true, reason: "ok" },
    });
    expect(green.ready).toBe(true);
    expect(green.steps.find((s) => s.id === "fabric")?.state).toBe("done");

    const redHub = buildStartupReadinessView({
      payload: basePayload({ app_surface: "hub" }),
      fabricProbe: { phase: "done", green: false, reason: "gRPC down" },
    });
    expect(redHub.ready).toBe(true);
    expect(redHub.steps.find((s) => s.id === "fabric")?.state).toBe("skipped");

    const redBirth = resolveFabricStep("birth", true, {
      phase: "done",
      green: false,
      reason: "not green",
    });
    expect(redBirth.state).toBe("blocked");
  });
});

