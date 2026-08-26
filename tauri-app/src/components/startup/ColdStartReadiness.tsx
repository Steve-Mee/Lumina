/**
 * Systems Go cover — one wait, then the app is usable.
 * Holds until Fabric GREEN (or degraded) + birth session hydrate when needed.
 */
import { useCallback, useEffect, useRef, useState } from "react";

import { StartupReadinessScreen } from "@/components/startup/StartupReadinessScreen";
import {
  runSystemsGoAfterBackend,
  waitNtProcess,
  type SystemsProgress,
} from "@/lib/startupSystemsOrchestrator";
import {
  applySystemsGoWindowSize,
  restoreDeckWindowSize,
} from "@/lib/systemsGoWindow";
import type { OnboardingPayload } from "@/lib/onboardingSteps";
import { useBirthStore } from "@/store/birthStore";
import { useOnboardingStore } from "@/store/onboardingStore";
import { isTauri } from "@tauri-apps/api/core";

const COLD_PROBE_ATTEMPTS = 12;
const COLD_PROBE_GAP_MS = 400;

function sleep(ms: number): Promise<void> {
  return new Promise((r) => globalThis.setTimeout(r, ms));
}

export function ColdStartReadiness() {
  const payload = useOnboardingStore((s) => s.payload);
  const error = useOnboardingStore((s) => s.error);
  const refresh = useOnboardingStore((s) => s.refresh);
  const ntLinkDeferred = useOnboardingStore((s) => s.ntLinkDeferred);
  const setNtStartupResolved = useOnboardingStore((s) => s.setNtStartupResolved);
  const setNtLinkDeferred = useOnboardingStore((s) => s.setNtLinkDeferred);
  const setFabricStartup = useOnboardingStore((s) => s.setFabricStartup);
  const targetTrades = useOnboardingStore((s) => s.draft.training.training_trades);

  const poll = useBirthStore((s) => s.poll);
  const bootstrapSession = useBirthStore((s) => s.bootstrapSession);
  const markSessionProbeError = useBirthStore((s) => s.markSessionProbeError);

  const [progress, setProgress] = useState<SystemsProgress | null>(null);
  const [busy, setBusy] = useState(false);
  const genRef = useRef(0);
  const mountedRef = useRef(true);
  const ranForPayloadRef = useRef<string | null>(null);

  useEffect(() => {
    mountedRef.current = true;
    // Option A: hug the Systems Go card with the native window.
    void applySystemsGoWindowSize();
    return () => {
      mountedRef.current = false;
      genRef.current += 1;
      // Safety: if cover unmounts without completeSystems, still restore deck size.
      void restoreDeckWindowSize();
    };
  }, []);

  const hydrateBirthSession = useCallback(async () => {
    let payloadStatus = null as Awaited<ReturnType<typeof poll>>;
    for (let attempt = 0; attempt < COLD_PROBE_ATTEMPTS; attempt += 1) {
      if (!mountedRef.current) return false;
      payloadStatus = await poll();
      if (payloadStatus) break;
      if (useBirthStore.getState().sessionProbeState === "ready") break;
      await sleep(COLD_PROBE_GAP_MS);
    }
    if (!payloadStatus && !useBirthStore.getState().sessionHydrated) {
      markSessionProbeError(
        useBirthStore.getState().pollError ??
          "Birth session status is still loading.",
      );
      await sleep(1_000);
      payloadStatus = await poll();
    }
    if (payloadStatus || useBirthStore.getState().sessionHydrated) {
      await bootstrapSession({
        appSurfaceReason: useOnboardingStore.getState().payload?.app_surface_reason,
        targetTrades,
      });
      return (
        useBirthStore.getState().sessionHydrated ||
        useBirthStore.getState().sessionProbeState === "ready"
      );
    }
    markSessionProbeError(
      useBirthStore.getState().pollError ??
        "Could not reach the birth service. Check backend, then retry.",
    );
    return false;
  }, [poll, bootstrapSession, markSessionProbeError, targetTrades]);

  const completeSystems = useCallback(
    async (fabric: {
      green: boolean;
      certified: boolean;
      reason: string;
      probedAt: number;
    }, degraded: boolean) => {
      setFabricStartup(fabric);
      if (degraded) {
        setNtLinkDeferred(true);
      }
      // Expand to deck size first, then leave cover so Genesis lands full-window.
      await restoreDeckWindowSize();
      setNtStartupResolved(true);
    },
    [setFabricStartup, setNtLinkDeferred, setNtStartupResolved],
  );

  /** Hold cover so operator sees every step green (incl. birth + route) before Genesis. */
  const ALL_GREEN_HOLD_MS = 1_250;

  const runPipeline = useCallback(
    async (opts?: { degraded?: boolean }) => {
      const gen = ++genRef.current;
      const cancelled = () => genRef.current !== gen || !mountedRef.current;
      setBusy(true);

      const result = await runSystemsGoAfterBackend({
        degraded: opts?.degraded || ntLinkDeferred,
        hooks: {
          isCancelled: cancelled,
          onProgress: (p) => {
            if (!cancelled()) setProgress(p);
          },
          appSurface: useOnboardingStore.getState().payload?.app_surface,
          hydrateBirthSession,
        },
      });

      if (cancelled()) return;

      setBusy(false);

      if (result.ok) {
        // Let React paint the final all-green checklist, then expand + enter Lumina.
        await sleep(ALL_GREEN_HOLD_MS);
        if (cancelled()) return;
        await completeSystems(result.fabric, result.degraded);
        return;
      }

      if (
        result.reason === "need_nt" ||
        result.reason === "need_fabric_choice" ||
        result.reason === "need_birth_retry"
      ) {
        // Stay on cover; UI shows dialogs / retry from progress flags
        return;
      }
      if (result.reason === "cancelled") return;
    },
    [ntLinkDeferred, hydrateBirthSession, completeSystems],
  );

  // Auto-run once backend is reachable.
  useEffect(() => {
    if (!payload?.backend.reachable) {
      setProgress({
        steps: [
          {
            id: "backend",
            state: error ? "blocked" : "running",
            detail: error?.trim() || "Contacting Lumina backend…",
          },
          { id: "nt_process", state: "pending", detail: "Waiting for backend" },
          { id: "fabric", state: "pending", detail: "Waiting for backend" },
          { id: "birth_session", state: "pending", detail: "Waiting for backend" },
          { id: "route", state: "pending", detail: "Waiting for backend" },
        ],
        headline: error ? "Backend unreachable" : "Systems Go",
        subtitle: error
          ? "Cannot reach the control plane. Retry when the backend is up."
          : "Contacting control plane…",
        needNtDialog: false,
        ntWaiting: false,
        waitDetail: null,
        needFabricChoice: false,
        needBirthRetry: false,
        fabricGreen: null,
      });
      return;
    }

    if (!isTauri()) {
      setFabricStartup({
        green: false,
        certified: false,
        reason: "Non-desktop session",
        probedAt: Date.now(),
      });
      setNtStartupResolved(true);
      return;
    }

    const key = `${payload.app_surface}:${payload.backend.reachable}`;
    if (ranForPayloadRef.current === key && !ntLinkDeferred) {
      // Allow re-run after NT start via handlers
      return;
    }
    ranForPayloadRef.current = key;
    void runPipeline();
    // Intentionally not depending on runPipeline identity — gate by payload key.
    // eslint-disable-next-line react-hooks/exhaustive-deps -- one Systems Go run per payload key
  }, [payload?.backend.reachable, payload?.app_surface, error]);

  const handleStartNt = () => {
    const gen = ++genRef.current;
    const cancelled = () => genRef.current !== gen || !mountedRef.current;
    setBusy(true);
    setProgress((p) =>
      p
        ? {
            ...p,
            ntWaiting: true,
            needNtDialog: true,
            waitDetail: "Starting NinjaTrader…",
            subtitle: "Starting NinjaTrader…",
          }
        : p,
    );
    void (async () => {
      const nt = await waitNtProcess({
        launch: true,
        isCancelled: cancelled,
        onDetail: (msg) => {
          if (!cancelled()) {
            setProgress((p) =>
              p ? { ...p, waitDetail: msg, subtitle: msg, ntWaiting: true } : p,
            );
          }
        },
      });
      if (cancelled()) return;
      if (nt === "failed") {
        setBusy(false);
        setProgress((p) =>
          p
            ? {
                ...p,
                ntWaiting: false,
                needNtDialog: true,
                waitDetail:
                  p.waitDetail || "Could not start NinjaTrader — retry or continue without link",
              }
            : p,
        );
        return;
      }
      // Force new pipeline run with NT up
      ranForPayloadRef.current = null;
      await runPipeline();
    })();
  };

  const handleContinueWithout = () => {
    genRef.current += 1;
    ranForPayloadRef.current = null;
    // Orchestrator completes with degraded + completeSystems sets deferred flag.
    void runPipeline({ degraded: true });
  };

  const handleRetryFabric = () => {
    ranForPayloadRef.current = null;
    void runPipeline();
  };

  const handleRetryBirth = () => {
    ranForPayloadRef.current = null;
    void runPipeline();
  };

  const showNtDialog = Boolean(progress?.needNtDialog);
  const showFabricChoice = Boolean(progress?.needFabricChoice);
  const showBirthRetry = Boolean(progress?.needBirthRetry);

  return (
    <StartupReadinessScreen
      payload={payload as OnboardingPayload | null}
      fetchError={error}
      systemsProgress={progress}
      showNtDialog={showNtDialog}
      showFabricChoice={showFabricChoice}
      showBirthRetry={showBirthRetry}
      ntWaiting={Boolean(progress?.ntWaiting) || busy}
      waitDetail={progress?.waitDetail}
      onStartNinjaTrader={handleStartNt}
      onContinueWithoutNt={handleContinueWithout}
      onRetryFabric={handleRetryFabric}
      onRetryBirth={handleRetryBirth}
      onRetry={() => {
        ranForPayloadRef.current = null;
        void refresh().then(() => runPipeline());
      }}
    />
  );
}
