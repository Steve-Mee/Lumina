import { useEffect, useState } from "react";
import { motion } from "framer-motion";

import { Button } from "@/components/ui/button";
import type { ReadinessRow } from "@/lib/onboardingSteps";
import {
  probeBackendHealth,
  resolveBackendBaseUrl,
  setBackendBaseUrl,
} from "@/lib/setupClient";
import { luminaSurfaceMutedClass } from "@/lib/glassGlowTaxonomy";
import { cn } from "@/lib/utils";
import { distressPanelClass, warnOverlayBodyClass, warnOverlayTitleClass } from "@/lib/modePresentation";

interface BackendStepProps {
  reachable: boolean;
  readiness?: ReadinessRow[];
  connectionError?: string | null;
  onConnected: () => void;
  onRefresh: () => void;
}

function statusLabel(status: ReadinessRow["status"]): string {
  if (status === "ok") return "Ready";
  if (status === "pending") return "Pending";
  return "Missing";
}

export function BackendStep({
  reachable,
  readiness = [],
  connectionError,
  onConnected,
  onRefresh,
}: BackendStepProps) {
  const [url, setUrl] = useState(resolveBackendBaseUrl());
  const [probing, setProbing] = useState(false);
  const [localOk, setLocalOk] = useState(reachable);
  const [probeError, setProbeError] = useState<string | null>(null);

  useEffect(() => {
    setLocalOk(reachable);
  }, [reachable]);

  useEffect(() => {
    if (localOk) return;
    const timer = setInterval(async () => {
      const ok = await probeBackendHealth();
      if (ok) {
        setLocalOk(true);
        setProbeError(null);
        onRefresh();
      }
    }, 2000);
    return () => clearInterval(timer);
  }, [localOk, onRefresh]);

  const handleTest = async () => {
    setProbing(true);
    setProbeError(null);
    setBackendBaseUrl(url);
    try {
      const ok = await probeBackendHealth();
      setLocalOk(ok);
      if (ok) {
        onRefresh();
      } else {
        setProbeError(
          "Could not reach the backend. Start FastAPI with lumina_os/run_backend.ps1, then test again.",
        );
      }
    } catch (err) {
      setLocalOk(false);
      setProbeError(err instanceof Error ? err.message : "Connection test failed");
    } finally {
      setProbing(false);
    }
  };

  const orbState = localOk ? "ok" : probing ? "warn" : "error";
  const displayError = connectionError ?? probeError;

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="mx-auto w-full max-w-xl p-2 text-foreground md:p-4"
    >
      <div className="mb-6 flex items-center gap-3">
        <span className="onboarding-status-orb" data-state={orbState} aria-hidden />
        <h2 className="text-lg font-semibold tracking-wide text-foreground">
          Python Backend Connection
        </h2>
      </div>
      <p className="mb-6 text-sm text-muted-foreground">
        The Neural Command Deck connects to the LUMINA FastAPI backend for telemetry, birth
        phase, and configuration.
      </p>

      {displayError ? (
        <div className={cn("mb-6 rounded-lg p-4", distressPanelClass())} role="alert">
          <p className={warnOverlayTitleClass()}>Connection issue</p>
          <p className={cn("mt-1", warnOverlayBodyClass())}>{displayError}</p>
          <p className="mt-2 font-mono text-[10px] text-muted-foreground">
            Start backend: powershell -File lumina_os\run_backend.ps1
          </p>
        </div>
      ) : null}

      {readiness.length > 0 && (
        <div className={luminaSurfaceMutedClass("mb-6 rounded-lg p-4")}>
          <p className="mb-3 text-xs tracking-wider text-muted-foreground uppercase">
            System readiness
          </p>
          <ul className="space-y-2">
            {readiness.map((row) => (
              <li key={row.id} className="flex items-center justify-between text-sm">
                <span className="text-foreground/90">{row.label}</span>
                <span
                  className={cn(
                    "text-xs tracking-wide uppercase",
                    row.status === "ok" && "text-emerald-400/90",
                    row.status === "pending" && "text-cyan-300/80",
                    row.status === "missing" && "text-amber-300/90",
                  )}
                >
                  {statusLabel(row.status)}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <label className="mb-2 block text-xs tracking-wider text-muted-foreground uppercase">
        Backend URL
      </label>
      <input
        className="onboarding-field mb-4"
        value={url}
        onChange={(e) => setUrl(e.target.value)}
        placeholder="http://127.0.0.1:8000"
      />
      <div className="flex flex-wrap gap-3">
        <Button variant="outline" onClick={() => void handleTest()} disabled={probing}>
          {probing ? "Testing…" : "Test Connection"}
        </Button>
        <Button type="button" variant="secondary" onClick={() => onRefresh()}>
          Retry setup
        </Button>
        {localOk ? (
          <Button className="onboarding-cta" onClick={onConnected}>
            Continue
          </Button>
        ) : null}
      </div>
      {localOk ? (
        <p className="mt-4 text-xs text-emerald-400/90">Backend reachable at {url}</p>
      ) : (
        <p className="mt-4 text-xs text-muted-foreground">
          Waiting for backend on port 8000 — auto-retry every 2s.
        </p>
      )}
    </motion.div>
  );
}
