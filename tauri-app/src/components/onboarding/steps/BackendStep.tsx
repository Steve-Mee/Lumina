import { useEffect, useState } from "react";
import { motion } from "framer-motion";

import { Button } from "@/components/ui/button";
import type { ReadinessRow } from "@/lib/onboardingSteps";
import {
  probeBackendHealth,
  resolveBackendBaseUrl,
  setBackendBaseUrl,
} from "@/lib/setupClient";
import { cn } from "@/lib/utils";

interface BackendStepProps {
  reachable: boolean;
  readiness?: ReadinessRow[];
  onConnected: () => void;
  onRefresh: () => void;
}

function statusLabel(status: ReadinessRow["status"]): string {
  if (status === "ok") return "Ready";
  if (status === "pending") return "Pending";
  return "Missing";
}

export function BackendStep({ reachable, readiness = [], onConnected, onRefresh }: BackendStepProps) {
  const [url, setUrl] = useState(resolveBackendBaseUrl());
  const [probing, setProbing] = useState(false);
  const [localOk, setLocalOk] = useState(reachable);

  useEffect(() => {
    setLocalOk(reachable);
  }, [reachable]);

  useEffect(() => {
    if (localOk) return;
    const timer = setInterval(async () => {
      const ok = await probeBackendHealth();
      if (ok) {
        setLocalOk(true);
        onRefresh();
      }
    }, 2000);
    return () => clearInterval(timer);
  }, [localOk, onRefresh]);

  const handleTest = async () => {
    setProbing(true);
    setBackendBaseUrl(url);
    const ok = await probeBackendHealth();
    setLocalOk(ok);
    setProbing(false);
    if (ok) onRefresh();
  };

  const orbState = localOk ? "ok" : probing ? "warn" : "error";

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="onboarding-card mx-auto max-w-xl p-8"
    >
      <div className="mb-6 flex items-center gap-3">
        <span className="onboarding-status-orb" data-state={orbState} aria-hidden />
        <h2 className="text-lg font-semibold tracking-wide">Python Backend Connection</h2>
      </div>
      <p className="mb-6 text-sm text-muted-foreground">
        The Neural Command Deck connects to the LUMINA FastAPI backend for telemetry, birth
        phase, and configuration.
      </p>

      {readiness.length > 0 && (
        <div className="mb-6 rounded-lg border border-white/10 bg-black/20 p-4">
          <p className="mb-3 text-xs tracking-wider text-muted-foreground uppercase">
            System readiness
          </p>
          <ul className="space-y-2">
            {readiness.map((row) => (
              <li key={row.id} className="flex items-center justify-between text-sm">
                <span>{row.label}</span>
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
        <Button variant="outline" onClick={handleTest} disabled={probing}>
          {probing ? "Testing…" : "Test Connection"}
        </Button>
        {localOk && (
          <Button className="onboarding-cta" onClick={onConnected}>
            Continue
          </Button>
        )}
      </div>
      {localOk && (
        <p className="mt-4 text-xs text-emerald-400/90">Backend reachable at {url}</p>
      )}
    </motion.div>
  );
}
