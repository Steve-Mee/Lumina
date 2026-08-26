/**
 * Systems Go cold-start orchestrator.
 * One place waits for backend → NT process → Fabric GREEN → birth hydrate.
 * Code Red: never kills NinjaTrader.
 */
import {
  isNinjaTraderRunning,
  launchNinjaTrader,
} from "@/lib/ninjaTraderClient";
import {
  fetchFabricLinkStatus,
  postFabricBootstrap,
  postFabricConnectionTest,
} from "@/lib/setupClient";
import type { StartupStepState } from "@/lib/startupReadinessModel";

export type SystemsStepId = "backend" | "nt_process" | "fabric" | "birth_session" | "route";

export type SystemsStepSnapshot = {
  id: SystemsStepId;
  state: StartupStepState;
  detail: string;
};

export type FabricStartupSnapshot = {
  /** Live GREEN (Brain connected + host up). Never paper-only. */
  green: boolean;
  /** Host up + recent dual-plane proof (or light diagnostic). */
  certified: boolean;
  /** Host process/port usable (AMBER/GREEN/RESTARTING). */
  hostReady?: boolean;
  level?: string;
  reason: string;
  probedAt: number;
};

export type SystemsProgress = {
  steps: SystemsStepSnapshot[];
  headline: string;
  subtitle: string;
  /** Modal: NT not running */
  needNtDialog: boolean;
  /** Modal actions while waiting for NT launch */
  ntWaiting: boolean;
  waitDetail: string | null;
  /** Fabric failed — offer retry / degraded */
  needFabricChoice: boolean;
  /** Birth hydrate failed — offer retry on cover (do not open half-locked Genesis) */
  needBirthRetry: boolean;
  fabricGreen: boolean | null;
};

export type OrchestratorHooks = {
  isCancelled: () => boolean;
  onProgress: (p: SystemsProgress) => void;
  /** Birth hydrate (only when surface is birth). */
  hydrateBirthSession?: () => Promise<boolean>;
  /** app_surface from onboarding */
  appSurface?: string | null;
};

function sleep(ms: number): Promise<void> {
  return new Promise((r) => globalThis.setTimeout(r, ms));
}

function step(
  id: SystemsStepId,
  state: StartupStepState,
  detail: string,
): SystemsStepSnapshot {
  return { id, state, detail };
}

function emit(
  hooks: OrchestratorHooks,
  partial: Omit<SystemsProgress, "steps"> & { steps: SystemsStepSnapshot[] },
): void {
  hooks.onProgress(partial);
}

/** Prefer live AUTH_FAILED / connect errors over generic SAFE "waiting for heartbeats". */
function fabricOperatorReason(link: {
  meaning?: string | null;
  reason?: string | null;
  live?: Record<string, unknown> | null;
  level?: string | null;
}): string {
  const live = link.live ?? {};
  const code = String(live.last_error_code ?? "").trim().toUpperCase();
  const err = String(live.last_error ?? "").trim();
  if (code === "AUTH_FAILED" || /invalid fabric token/i.test(err)) {
    return (
      "Fabric token rejected by host — token SSOT was re-aligned. " +
      "If still blocked: in NinjaTrader open New → LUMINA (reloads host token), then Retry Fabric."
    );
  }
  if (code === "TOKEN_EMPTY") {
    return "Fabric token missing — open Setup → credentials, then Retry Fabric.";
  }
  if (code === "AUTH_TIMEOUT") {
    return "Fabric auth timed out — host busy; wait a moment and Retry Fabric.";
  }
  if (code === "CONNECTION_REFUSED" || code === "NT_PROCESS_GONE") {
    return err || "Fabric host not reachable — start NinjaTrader / New → LUMINA.";
  }
  return (
    String(link.meaning ?? "").trim() ||
    String(link.reason ?? "").trim() ||
    String(link.level ?? "").trim() ||
    "not green"
  );
}

/**
 * Soft fabric path: bootstrap (no kill) + link status + optional light connection test.
 *
 * Elon cold-start: bootstrap dual-writes token → status poll auto-aligns + supervisor
 * reconnect → host hot-reloads fabric.json AuthToken → GREEN without false SAFE dialog.
 */
export async function ensureFabricGreen(opts: {
  isCancelled: () => boolean;
  onDetail?: (msg: string) => void;
  timeoutMs?: number;
  pollMs?: number;
}): Promise<FabricStartupSnapshot> {
  const timeoutMs = opts.timeoutMs ?? 50_000;
  const pollMs = opts.pollMs ?? 1_200;
  const detail = opts.onDetail ?? (() => undefined);

  detail("Deploying / aligning Fabric token…");
  try {
    // Bound bootstrap so a hung deploy cannot freeze Systems Go forever.
    const boot = await Promise.race([
      postFabricBootstrap(),
      sleep(15_000).then(() => null),
    ]);
    // Paper cert from bootstrap is not live GREEN — keep polling host health.
    if (boot?.fabric_link_green) {
      detail("Proof present — verifying live Fabric host…");
    } else if (!boot) {
      detail("Fabric bootstrap slow — probing link status…");
    } else {
      detail("Token dual-written — connecting Brain to Fabric host…");
    }
  } catch {
    /* continue to poll */
  }
  if (opts.isCancelled()) {
    return { green: false, certified: false, reason: "cancelled", probedAt: Date.now() };
  }

  const deadline = Date.now() + timeoutMs;
  let lastReason = "probing Fabric link…";
  let triedLightTest = false;
  let authFailStreak = 0;

  while (Date.now() < deadline) {
    if (opts.isCancelled()) {
      return { green: false, certified: false, reason: "cancelled", probedAt: Date.now() };
    }
    try {
      const link = await fetchFabricLinkStatus();
      const level = String(link.level || "").toUpperCase();
      const hostReady = Boolean(link.host_ready || level === "AMBER" || level === "GREEN");
      const proofOk = Boolean(
        link.gate_birth_ok ||
          link.proof?.certified ||
          link.proof?.badge_ok ||
          link.certificate,
      );
      const liveCode = String(link.live?.last_error_code ?? "").trim().toUpperCase();
      if (liveCode === "AUTH_FAILED" || liveCode === "TOKEN_EMPTY") {
        authFailStreak += 1;
      } else {
        authFailStreak = 0;
      }

      // Systems Go success: live GREEN, or host up with dual-plane proof (AMBER ok).
      if (link.green || level === "GREEN") {
        return {
          green: true,
          certified: proofOk || true,
          hostReady: true,
          level: level || "GREEN",
          reason: link.meaning?.trim() || link.reason?.trim() || "Live GREEN",
          probedAt: Date.now(),
        };
      }
      if (hostReady && (link.gate_birth_ok || proofOk)) {
        return {
          green: false,
          certified: true,
          hostReady: true,
          level: level || "AMBER",
          reason:
            link.meaning?.trim() ||
            link.reason?.trim() ||
            "Host ready · proof OK (Brain session optional)",
          probedAt: Date.now(),
        };
      }
      lastReason = fabricOperatorReason(link);
      detail(`Fabric: ${lastReason}`);

      // Persistent AUTH_FAILED after align: stop burning the full 50s — operator must
      // reopen LUMINA host if pre-hot-reload DLL still pins stale AuthToken.
      if (authFailStreak >= 6 && hostReady) {
        return {
          green: false,
          certified: false,
          hostReady: true,
          level: level || "AMBER",
          reason: lastReason,
          probedAt: Date.now(),
        };
      }
    } catch (err) {
      lastReason = err instanceof Error ? err.message : "Fabric status unavailable";
      detail(lastReason);
    }

    // One light diagnostic mid-window (no SAFE_MODE) to settle host after launch.
    if (!triedLightTest && Date.now() > deadline - timeoutMs + 8_000) {
      triedLightTest = true;
      detail("Light Fabric diagnostic…");
      try {
        const report = await postFabricConnectionTest({
          include_safe_mode: false,
          instrument: "",
        });
        if (report.overall === "green" || report.certified) {
          // Re-poll live health — diagnostic alone is proof, not live GREEN.
          try {
            const link = await fetchFabricLinkStatus();
            const level = String(link.level || "").toUpperCase();
            const hostReady = Boolean(link.host_ready || level === "AMBER" || level === "GREEN");
            return {
              green: Boolean(link.green || level === "GREEN"),
              certified: true,
              hostReady,
              level: level || (hostReady ? "AMBER" : "RED"),
              reason: hostReady
                ? "Proof GREEN · host ready after diagnostic"
                : "Proof GREEN · host not ready",
              probedAt: Date.now(),
            };
          } catch {
            return {
              green: false,
              certified: true,
              hostReady: false,
              level: "AMBER",
              reason: "Proof GREEN · recheck live host",
              probedAt: Date.now(),
            };
          }
        }
        lastReason = `diagnostic ${report.overall}`;
        detail(`Fabric diagnostic: ${report.overall}`);
      } catch {
        /* keep polling status */
      }
    }

    await sleep(pollMs);
  }

  return {
    green: false,
    certified: false,
    reason: lastReason || "Fabric not GREEN within timeout",
    probedAt: Date.now(),
  };
}

export async function waitNtProcess(opts: {
  launch: boolean;
  isCancelled: () => boolean;
  onDetail?: (msg: string) => void;
  processTimeoutMs?: number;
}): Promise<"up" | "failed"> {
  const timeoutMs = opts.processTimeoutMs ?? 90_000;
  const detail = opts.onDetail ?? (() => undefined);

  if (await isNinjaTraderRunning()) return "up";

  if (opts.launch) {
    detail("Starting NinjaTrader…");
    const launched = await launchNinjaTrader();
    if (opts.isCancelled()) return "failed";
    if (!launched.launched && !launched.installed) {
      detail(launched.error?.trim() || "NinjaTrader is not installed");
      return "failed";
    }
    if (!launched.launched && launched.error) {
      detail(launched.error);
      return "failed";
    }
  }

  detail("Waiting for NinjaTrader.exe…");
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (opts.isCancelled()) return "failed";
    if (await isNinjaTraderRunning()) return "up";
    await sleep(1_000);
  }
  detail("Timed out waiting for NinjaTrader.exe");
  return "failed";
}

export type SystemsGoResult =
  | { ok: true; fabric: FabricStartupSnapshot; degraded: boolean }
  | {
      ok: false;
      reason: "need_nt" | "need_fabric_choice" | "need_birth_retry" | "cancelled" | "birth_failed";
      fabric?: FabricStartupSnapshot;
    };

/**
 * Full systems pipeline after backend payload is available.
 * Caller handles NT dialog when result is need_nt.
 */
export async function runSystemsGoAfterBackend(opts: {
  hooks: OrchestratorHooks;
  /** Operator already chose continue without NT/fabric this session */
  degraded?: boolean;
  /** Force re-run fabric after NT launch */
  forceFabric?: boolean;
}): Promise<SystemsGoResult> {
  const { hooks } = opts;
  const degraded = Boolean(opts.degraded);
  const surface = hooks.appSurface ?? null;

  const base = (over: Partial<SystemsProgress> & { steps: SystemsStepSnapshot[] }): SystemsProgress => ({
    headline: "Systems Go",
    subtitle: "Bringing Lumina online — one clean start",
    needNtDialog: false,
    ntWaiting: false,
    waitDetail: null,
    needFabricChoice: false,
    needBirthRetry: false,
    fabricGreen: null,
    ...over,
  });

  // NT process
  let ntUp = false;
  try {
    ntUp = await isNinjaTraderRunning();
  } catch {
    ntUp = false;
  }

  if (!ntUp && !degraded) {
    emit(
      hooks,
      base({
        steps: [
          step("backend", "done", "Control plane reachable"),
          step("nt_process", "blocked", "NinjaTrader not running"),
          step("fabric", "pending", "Needs NinjaTrader"),
          step(
            "birth_session",
            surface === "birth" ? "pending" : "skipped",
            surface === "birth" ? "After Fabric" : "Not required",
          ),
          step("route", "pending", "Waiting for systems"),
        ],
        needNtDialog: true,
        headline: "NinjaTrader required",
        subtitle: "Start NinjaTrader before Fabric can go GREEN",
      }),
    );
    return { ok: false, reason: "need_nt" };
  }

  emit(
    hooks,
    base({
      steps: [
        step("backend", "done", "Control plane reachable"),
        step(
          "nt_process",
          degraded && !ntUp ? "skipped" : "done",
          degraded && !ntUp ? "Continued without NT" : "NinjaTrader.exe running",
        ),
        step("fabric", "running", "Aligning Fabric link…"),
        step(
          "birth_session",
          surface === "birth" ? "pending" : "skipped",
          surface === "birth" ? "After Fabric" : "Not required",
        ),
        step("route", "pending", "Waiting for systems"),
      ],
      subtitle: "Connecting Fabric (Brain ↔ NinjaTrader)…",
    }),
  );

  if (hooks.isCancelled()) return { ok: false, reason: "cancelled" };

  let fabric: FabricStartupSnapshot;
  // Degraded continue must NOT re-poll Fabric for 50s — operator already chose review-only.
  if (degraded) {
    fabric = {
      green: false,
      certified: false,
      reason: ntUp
        ? "Operator continued without live Fabric GREEN"
        : "Deferred — no NinjaTrader link",
      probedAt: Date.now(),
    };
  } else {
    fabric = await ensureFabricGreen({
      isCancelled: hooks.isCancelled,
      onDetail: (msg) => {
        emit(
          hooks,
          base({
            steps: [
              step("backend", "done", "Control plane reachable"),
              step("nt_process", "done", "NinjaTrader.exe running"),
              step("fabric", "running", msg),
              step(
                "birth_session",
                surface === "birth" ? "pending" : "skipped",
                surface === "birth" ? "After Fabric" : "Not required",
              ),
              step("route", "pending", "Waiting for systems"),
            ],
            waitDetail: msg,
            fabricGreen: null,
            subtitle: msg,
          }),
        );
      },
    });
  }

  if (hooks.isCancelled()) return { ok: false, reason: "cancelled", fabric };

  // Systems Go proceeds when live GREEN OR host ready + dual-plane proof (AMBER ok).
  // Paper cert alone is never enough (host_ready false).
  const fabricProceed =
    fabric.green || Boolean(fabric.hostReady && fabric.certified);

  if (!fabricProceed && !degraded) {
    emit(
      hooks,
      base({
        steps: [
          step("backend", "done", "Control plane reachable"),
          step("nt_process", "done", "NinjaTrader.exe running"),
          step("fabric", "blocked", fabric.reason),
          step(
            "birth_session",
            surface === "birth" ? "pending" : "skipped",
            surface === "birth" ? "Blocked on Fabric" : "Not required",
          ),
          step("route", "pending", "Fabric not ready"),
        ],
        needFabricChoice: true,
        fabricGreen: false,
        waitDetail: fabric.reason,
        headline: "Fabric link not ready",
        subtitle: "Retry connection or continue in review-only mode",
      }),
    );
    return { ok: false, reason: "need_fabric_choice", fabric };
  }

  // Birth session hydrate on cover (removes 30s Genesis lock)
  if (surface === "birth" && hooks.hydrateBirthSession && (fabricProceed || degraded)) {
    emit(
      hooks,
      base({
        steps: [
          step("backend", "done", "Control plane reachable"),
          step(
            "nt_process",
            degraded && !ntUp ? "skipped" : "done",
            degraded && !ntUp ? "Continued without NT" : "NinjaTrader.exe running",
          ),
          step(
            "fabric",
            fabricProceed ? "done" : "skipped",
            fabricProceed ? fabric.reason : "Degraded — no live link",
          ),
          step("birth_session", "running", "Loading birth session…"),
          step("route", "pending", "Almost ready"),
        ],
        fabricGreen: fabric.green,
        subtitle: "Hydrating birth session…",
      }),
    );
    const ok = await hooks.hydrateBirthSession();
    if (hooks.isCancelled()) return { ok: false, reason: "cancelled", fabric };
    if (!ok && !degraded) {
      // Stay on cover — do not open a half-locked Genesis (capital-trust).
      emit(
        hooks,
        base({
          steps: [
            step("backend", "done", "Control plane reachable"),
            step("nt_process", "done", "NinjaTrader.exe running"),
            step("fabric", fabricProceed ? "done" : "skipped", fabric.reason),
            step("birth_session", "blocked", "Birth status unavailable"),
            step("route", "pending", "Retry birth session"),
          ],
          fabricGreen: fabric.green,
          needBirthRetry: true,
          waitDetail: "Could not load birth session — retry before opening Genesis",
          headline: "Birth session not ready",
          subtitle: "Retry on this screen — do not open a half-loaded Genesis",
        }),
      );
      return { ok: false, reason: "need_birth_retry", fabric };
    }
    // Final all-green (or all-settled) frame — caller holds paint before leaving cover.
    emit(
      hooks,
      base({
        steps: [
          step("backend", "done", "Control plane reachable"),
          step(
            "nt_process",
            degraded && !ntUp ? "skipped" : "done",
            degraded && !ntUp ? "Continued without NT" : "NinjaTrader.exe running",
          ),
          step(
            "fabric",
            fabricProceed ? "done" : "skipped",
            fabricProceed ? fabric.reason : "Degraded — no live link",
          ),
          step("birth_session", ok ? "done" : "skipped", ok ? "Session ready" : "Skipped (degraded)"),
          step("route", "done", surface ? `Ready · ${surface}` : "Ready"),
        ],
        fabricGreen: fabric.green,
        headline: fabric.green
          ? "All systems green"
          : fabricProceed
            ? "Systems ready (host + proof)"
            : "Ready (degraded)",
        subtitle: fabric.green
          ? "Everything online — entering Lumina…"
          : fabricProceed
            ? "Host ready — Brain link optional until training"
            : "Review mode — trading blocked without Fabric GREEN",
      }),
    );
  } else {
    emit(
      hooks,
      base({
        steps: [
          step("backend", "done", "Control plane reachable"),
          step(
            "nt_process",
            degraded && !ntUp ? "skipped" : "done",
            degraded && !ntUp ? "Continued without NT" : "NinjaTrader.exe running",
          ),
          step(
            "fabric",
            fabricProceed ? "done" : "skipped",
            fabricProceed ? fabric.reason : "Degraded — no live link",
          ),
          // Still show birth as done/skipped green-path for a full checklist moment
          step("birth_session", "skipped", "Not required on this surface"),
          step("route", "done", surface ? `Ready · ${surface}` : "Ready"),
        ],
        fabricGreen: fabric.green,
        headline: fabric.green
          ? "All systems green"
          : fabricProceed
            ? "Systems ready (host + proof)"
            : "Ready (degraded)",
        subtitle: fabric.green
          ? "Everything online — entering Lumina…"
          : fabricProceed
            ? "Host ready — Brain link optional until training"
            : "Review mode — trading blocked without Fabric GREEN",
      }),
    );
  }

  return {
    ok: true,
    fabric,
    degraded: degraded || (!fabric.green && !fabricProceed),
  };
}
