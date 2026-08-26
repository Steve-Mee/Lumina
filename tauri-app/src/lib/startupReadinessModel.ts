/**
 * Pure cold-start readiness steps derived from onboarding SSOT.
 * @see docs/adr/0011-tauri-lifecycle-gate-ssot.md
 */
import type { AppSurface, OnboardingPayload, StepStatus } from "@/lib/onboardingSteps";

export type StartupStepId =
  | "backend"
  | "setup"
  | "credentials"
  | "nt_process"
  | "fabric"
  | "birth_session"
  | "birth_artifacts"
  | "route";

export type StartupStepState = "pending" | "running" | "done" | "blocked" | "skipped";

export type StartupStep = {
  id: StartupStepId;
  label: string;
  state: StartupStepState;
  detail?: string;
};

/** Optional light Fabric probe (soft — never blocks hub cold start). */
export type FabricProbeInput = {
  phase: "idle" | "running" | "done" | "error";
  green: boolean | null;
  reason: string | null;
};

export type StartupReadinessView = {
  headline: string;
  subtitle: string;
  steps: StartupStep[];
  /** Surface destination once resolve is complete (null while still probing). */
  resolvedSurface: AppSurface | null;
  /** True when we have enough SSOT to leave the cover. */
  ready: boolean;
  /** Show Retry CTA (backend blocked or fetch error). */
  canRetry: boolean;
  activeStepId: StartupStepId | null;
};

/** NinjaTrader process step (truth: live Fabric needs NT.exe running). */
export function resolveNtProcessStep(opts: {
  backendOk: boolean;
  ntRunning: boolean | null;
  /** Operator chose continue without link this session. */
  ntLinkDeferred: boolean;
  /** Waiting for launch / process poll. */
  ntWaiting: boolean;
  /** Live progress line while waiting (from wait helper). */
  waitDetail?: string | null;
}): { state: StartupStepState; detail: string } {
  if (!opts.backendOk) {
    return { state: "pending", detail: "Waiting for backend" };
  }
  if (opts.ntWaiting) {
    return {
      state: "running",
      detail: opts.waitDetail?.trim() || "Waiting for NinjaTrader to start…",
    };
  }
  if (opts.ntRunning === true) {
    return { state: "done", detail: "NinjaTrader.exe is running" };
  }
  if (opts.ntLinkDeferred) {
    return {
      state: "skipped",
      detail: "Continued without link · trading & Activate Birth blocked",
    };
  }
  if (opts.ntRunning === false) {
    return {
      state: "blocked",
      detail: "Not running · Fabric cannot go GREEN without NT",
    };
  }
  return { state: "pending", detail: "Checking NinjaTrader process…" };
}

/** Map optional fabric probe into step state (policy A: soft on hub/deck). */
export function resolveFabricStep(
  surface: AppSurface,
  backendOk: boolean,
  probe?: FabricProbeInput | null,
): { state: StartupStepState; detail: string } {
  if (!backendOk) {
    return { state: "pending", detail: "Waiting for backend" };
  }

  if (probe?.phase === "running") {
    return { state: "running", detail: "Probing Fabric link…" };
  }

  if (probe?.phase === "done" || probe?.phase === "error") {
    if (probe.green === true) {
      return {
        state: "done",
        detail: probe.reason || "GREEN · link ready",
      };
    }
    // Soft fail: show blocked styling only on birth/setup (operator will hard-gate later)
    if (surface === "birth" || surface === "setup") {
      return {
        state: "blocked",
        detail:
          probe.reason ||
          "Not GREEN · seal vault / start NinjaTrader before Activate",
      };
    }
    return {
      state: "skipped",
      detail:
        probe.reason ||
        "Not GREEN (soft) · hub/deck still open; verify before live orders",
    };
  }

  // No probe yet
  if (surface === "hub" || surface === "deck") {
    return {
      state: "skipped",
      detail: "Soft — optional probe; not required to open hub/deck",
    };
  }
  return {
    state: "pending",
    detail: "Will verify on Activate / vault seal (fail-closed there)",
  };
}

function wizardStepStatus(
  payload: OnboardingPayload,
  step: string,
): StepStatus | undefined {
  return payload.step_status?.[step];
}

function credentialsDone(payload: OnboardingPayload): boolean {
  if (payload.credentials.wizard_required === false) return true;
  if (payload.credentials.skip_reason) return true;
  const missing = payload.credentials.missing ?? [];
  if (missing.length === 0 && payload.credentials.has_admin_api_key) return true;
  const st = wizardStepStatus(payload, "credentials");
  return st === "done";
}

function setupDone(payload: OnboardingPayload): boolean {
  if (payload.setup_complete) return true;
  const required = payload.required_steps ?? [];
  const blockers = required.filter((s) => s !== "welcome" && s !== "birth");
  if (blockers.length === 0) return payload.backend.reachable;
  return blockers.every((s) => {
    if (s === "credentials") return credentialsDone(payload);
    const st = wizardStepStatus(payload, s);
    return st === "done";
  });
}

function birthArtifactsDone(payload: OnboardingPayload): boolean {
  return payload.birth.birth_exit_ok === true;
}

function birthSessionDetail(payload: OnboardingPayload): string {
  const status = payload.birth.status || "unknown";
  const msg = payload.birth.message?.trim();
  return msg ? `${status} · ${msg}` : status;
}

/**
 * Build readiness view from store snapshot.
 * @param payload null while first fetch in flight
 * @param fetchError last refresh error message
 * @param fetching true while refresh is in progress
 */
export function buildStartupReadinessView(opts: {
  payload: OnboardingPayload | null;
  fetchError?: string | null;
  fetching?: boolean;
  /** Soft fabric light probe (policy A — never blocks hub ready). */
  fabricProbe?: FabricProbeInput | null;
  /** null = not probed yet */
  ntRunning?: boolean | null;
  ntLinkDeferred?: boolean;
  ntWaiting?: boolean;
  waitDetail?: string | null;
}): StartupReadinessView {
  const {
    payload,
    fetchError,
    fetching = false,
    fabricProbe = null,
    ntRunning = null,
    ntLinkDeferred = false,
    ntWaiting = false,
    waitDetail = null,
  } = opts;

  if (!payload) {
    const backendState: StartupStepState = fetchError
      ? "blocked"
      : fetching
        ? "running"
        : "running";
    const steps: StartupStep[] = [
      {
        id: "backend",
        label: "Backend reachability",
        state: backendState,
        detail: fetchError?.trim() || "Contacting Lumina backend…",
      },
      {
        id: "setup",
        label: "Setup completeness",
        state: "pending",
      },
      {
        id: "credentials",
        label: "Operator vault",
        state: "pending",
      },
      {
        id: "nt_process",
        label: "NinjaTrader process",
        state: "pending",
        detail: "Required for live Fabric GREEN",
      },
      {
        id: "fabric",
        label: "NinjaTrader Fabric",
        state: "pending",
        detail: "Checked when Birth or execution needs the link",
      },
      {
        id: "birth_session",
        label: "Birth session",
        state: "pending",
      },
      {
        id: "birth_artifacts",
        label: "Birth certificate",
        state: "pending",
      },
      {
        id: "route",
        label: "Route surface",
        state: "pending",
      },
    ];
    return {
      headline: fetchError ? "Backend unreachable" : "Starting Lumina",
      subtitle: fetchError
        ? "Cannot reach the control plane. Retry when the backend is up."
        : "Resolving lifecycle surface…",
      steps,
      resolvedSurface: null,
      ready: false,
      canRetry: Boolean(fetchError),
      activeStepId: "backend",
    };
  }

  const surface = payload.app_surface;
  const backendOk = payload.backend.reachable;
  const setupOk = setupDone(payload);
  const credsOk = credentialsDone(payload);
  const artifactsOk = birthArtifactsDone(payload);
  const birthStatus = (payload.birth.status || "").toLowerCase();
  const birthSessionHydrated = Boolean(payload.birth.status);

  const nt = resolveNtProcessStep({
    backendOk,
    ntRunning,
    ntLinkDeferred,
    ntWaiting,
    waitDetail,
  });
  const fabric = resolveFabricStep(surface, backendOk, fabricProbe);

  const steps: StartupStep[] = [
    {
      id: "backend",
      label: "Backend reachability",
      state: backendOk ? "done" : "blocked",
      detail: backendOk
        ? payload.backend.latency_ms != null
          ? `${payload.backend.url} · ${payload.backend.latency_ms}ms`
          : payload.backend.url
        : payload.backend.error || fetchError || "Unreachable",
    },
    {
      id: "setup",
      label: "Setup completeness",
      state: !backendOk ? "pending" : setupOk ? "done" : "blocked",
      detail: setupOk
        ? "Setup complete"
        : `Incomplete · surface will be setup (${payload.required_steps?.length ?? 0} required steps)`,
    },
    {
      id: "credentials",
      label: "Operator vault",
      state: !backendOk
        ? "pending"
        : credsOk
          ? "done"
          : surface === "setup"
            ? "running"
            : "blocked",
      detail: credsOk
        ? payload.credentials.skip_reason
          ? `Ready · ${payload.credentials.skip_reason}`
          : "Credentials ready"
        : `${payload.credentials.missing?.length ?? 0} missing keys`,
    },
    {
      id: "nt_process",
      label: "NinjaTrader process",
      state: nt.state,
      detail: nt.detail,
    },
    {
      id: "fabric",
      label: "NinjaTrader Fabric",
      state: fabric.state,
      detail: fabric.detail,
    },
    {
      id: "birth_session",
      label: "Birth session",
      state: !backendOk
        ? "pending"
        : surface === "setup"
          ? "skipped"
          : birthSessionHydrated
            ? birthStatus === "error" || birthStatus === "certificate_failed"
              ? "blocked"
              : "done"
            : "running",
      detail:
        surface === "setup"
          ? "Skipped until setup is complete"
          : birthSessionDetail(payload),
    },
    {
      id: "birth_artifacts",
      label: "Birth certificate",
      state: !backendOk
        ? "pending"
        : surface === "setup"
          ? "skipped"
          : artifactsOk
            ? "done"
            : surface === "birth"
              ? "running"
              : "blocked",
      detail: artifactsOk
        ? payload.birth.artifacts_label || "Certificate / artifacts OK"
        : payload.birth.certificate_reason ||
          payload.birth.artifacts_label ||
          "Artifacts or certificate incomplete",
    },
    {
      id: "route",
      label: "Route surface",
      state: backendOk ? "done" : "pending",
      detail: backendOk
        ? `${surface}${payload.app_surface_reason ? ` · ${payload.app_surface_reason}` : ""}`
        : "Waiting for backend",
    },
  ];

  const active =
    steps.find((s) => s.state === "blocked" || s.state === "running") ??
    steps.find((s) => s.state === "pending") ??
    null;

  // Ready: we have SSOT app_surface and backend answered (or setup surface for unreachable is handled by mapAppPhase).
  // Stay on cover only while first paint has no phase yet — parent exits when phase !== loading.
  const ready = backendOk || surface === "setup";

  let headline = "Starting Lumina";
  let subtitle = "Resolving lifecycle surface…";
  if (!backendOk) {
    headline = "Backend unreachable";
    subtitle = "Control plane offline — retry when the backend is running.";
  } else if (surface === "setup") {
    headline = "Setup required";
    subtitle = "Opening the operator setup path.";
  } else if (surface === "birth") {
    headline = "Birth surface";
    subtitle = artifactsOk
      ? "Birth session ready — entering mission control."
      : "Birth incomplete — recovery and training live here.";
  } else if (surface === "hub") {
    headline = "Phase Hub";
    subtitle = "Organism ready — opening maturation hub.";
  } else if (surface === "deck") {
    headline = "Command Deck";
    subtitle = "Entering the neural command deck.";
  }

  if (fetching && backendOk) {
    subtitle = "Refreshing status…";
  }

  return {
    headline,
    subtitle,
    steps,
    resolvedSurface: surface,
    ready,
    canRetry: !backendOk || Boolean(fetchError),
    activeStepId: active?.id ?? "route",
  };
}

export function startupStepStateLabel(state: StartupStepState): string {
  switch (state) {
    case "done":
      return "done";
    case "running":
      return "running";
    case "blocked":
      return "blocked";
    case "skipped":
      return "skip";
    default:
      return "pending";
  }
}
