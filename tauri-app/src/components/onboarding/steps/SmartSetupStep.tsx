import { useEffect, useState } from "react";
import { motion } from "framer-motion";

import { Button } from "@/components/ui/button";
import { fetchSmartSetupProgress } from "@/lib/setupClient";
import type { OnboardingPayload } from "@/lib/onboardingSteps";

interface SmartSetupStepProps {
  payload: OnboardingPayload;
  running: boolean;
  onRun: () => void;
  onContinue: () => void;
  onRefresh: () => void;
}

export function SmartSetupStep({
  payload,
  running,
  onRun,
  onContinue,
  onRefresh,
}: SmartSetupStepProps) {
  const [progressMsg, setProgressMsg] = useState("");
  const [percent, setPercent] = useState(0);

  const needsOllama = payload.intelligence.missing.includes("ollama");
  const needsModel = payload.intelligence.missing.some((m) => m.startsWith("model:"));
  const ready =
    !needsOllama &&
    !needsModel &&
    payload.intelligence.recommended_model_present;

  useEffect(() => {
    if (!running && ready) return;
    const timer = setInterval(async () => {
      try {
        const prog = await fetchSmartSetupProgress();
        const statusRecord = prog.status ?? {};
        const phase = String(statusRecord.phase ?? "");
        setProgressMsg(phase || "Working…");
        const steps = statusRecord.steps;
        if (Array.isArray(steps) && steps.length > 0) {
          setPercent(Math.min(95, steps.length * 8));
        }
        if (!prog.running && !needsOllama && !needsModel) {
          onRefresh();
        }
      } catch {
        /* ignore poll errors */
      }
    }, 1500);
    return () => clearInterval(timer);
  }, [running, ready, needsOllama, needsModel, onRefresh]);

  useEffect(() => {
    if (ready) setPercent(100);
  }, [ready]);

  const tier = String(
    (payload.intelligence.adaptive_intelligence as { tier?: string })?.tier ?? "light",
  ).toUpperCase();

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="onboarding-card mx-auto max-w-xl p-8"
    >
      <h2 className="mb-2 text-lg font-semibold">Intelligence Stack</h2>
      <p className="mb-6 text-sm text-muted-foreground">
        Hardware tier <span className="text-cyan-300/90">{tier}</span> — recommended model{" "}
        <span className="font-mono text-cyan-200/80">
          {payload.intelligence.recommended_ollama_tag || payload.intelligence.recommended_model_key}
        </span>
      </p>

      <ul className="mb-6 space-y-2 text-sm">
        <li className={needsOllama ? "text-amber-300/90" : "text-emerald-400/90"}>
          Ollama: {payload.intelligence.ollama_installed ? "Installed" : "Missing"}
        </li>
        <li className={needsModel ? "text-amber-300/90" : "text-emerald-400/90"}>
          Model:{" "}
          {payload.intelligence.recommended_model_present ? "Ready" : "Not pulled"}
        </li>
      </ul>

      {payload.intelligence.recommended_provider !== "ollama" && (
        <p className="mb-4 rounded-lg border border-amber-500/30 bg-amber-500/5 p-3 text-xs text-amber-200/90">
          High-tier provider ({payload.intelligence.recommended_provider}) requires manual vLLM
          setup. See launcher documentation for GPU requirements.
        </p>
      )}

      {(running || percent > 0) && (
        <div className="mb-6">
          <div className="mb-1 h-1.5 overflow-hidden rounded-full bg-white/10">
            <div
              className="h-full bg-gradient-to-r from-cyan-400 to-violet-500 transition-all duration-500"
              style={{ width: `${percent}%` }}
            />
          </div>
          <p className="text-xs text-muted-foreground">{progressMsg || "Starting…"}</p>
        </div>
      )}

      <div className="flex flex-wrap gap-3">
        {!ready && payload.intelligence.recommended_provider === "ollama" && (
          <Button
            className="onboarding-cta"
            onClick={onRun}
            disabled={running}
          >
            {running ? "Installing…" : "Install & Configure"}
          </Button>
        )}
        {ready && (
          <Button className="onboarding-cta" onClick={onContinue}>
            Continue
          </Button>
        )}
      </div>
    </motion.div>
  );
}
