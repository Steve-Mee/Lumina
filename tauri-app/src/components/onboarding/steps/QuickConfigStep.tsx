import { useState } from "react";
import { motion } from "framer-motion";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import type { OnboardingDraft } from "@/store/onboardingStore";
import { cn } from "@/lib/utils";

interface QuickConfigStepProps {
  draft: OnboardingDraft;
  onChange: (patch: Partial<OnboardingDraft>) => void;
  onContinue: () => void;
}

export function QuickConfigStep({ draft, onChange, onContinue }: QuickConfigStepProps) {
  const [realConfirmOpen, setRealConfirmOpen] = useState(false);
  const isReal = draft.mode === "real";

  const handleModeSelect = (mode: "sim" | "real") => {
    if (mode === "real") {
      setRealConfirmOpen(true);
      return;
    }
    onChange({
      mode: "sim",
      evolution: { approval_required: false, aggressive_evolution: true },
      risk: { ...draft.risk, kelly_fraction: 1.0, daily_loss_cap: null },
    });
  };

  const confirmReal = () => {
    onChange({
      mode: "real",
      evolution: { approval_required: true, aggressive_evolution: false },
      risk: {
        ...draft.risk,
        kelly_fraction: 0.25,
        daily_loss_cap: -150,
        max_total_open_risk: 150,
      },
    });
    setRealConfirmOpen(false);
  };

  return (
    <>
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        className="onboarding-card mx-auto max-w-xl p-8"
      >
        <h2 className="mb-2 text-lg font-semibold">Quick Configuration</h2>
        <p className="mb-6 text-sm text-muted-foreground">
          Choose your target operations mode and core risk parameters. During Birth Phase, runtime
          is <strong className="text-cyan-300/90">always SIM</strong> (fail-closed).
        </p>

        <div className="mb-6 flex gap-3">
          {(["sim", "real"] as const).map((mode) => (
            <button
              key={mode}
              type="button"
              onClick={() => handleModeSelect(mode)}
              className={cn(
                "flex-1 rounded-lg border px-4 py-3 text-sm font-semibold tracking-wider uppercase transition-all",
                draft.mode === mode
                  ? mode === "sim"
                    ? "border-cyan-400/50 bg-cyan-400/10 text-cyan-200"
                    : "border-amber-500/50 bg-amber-500/10 text-amber-200"
                  : "border-white/10 bg-white/5 text-muted-foreground hover:border-white/20",
              )}
            >
              {mode}
            </button>
          ))}
        </div>

        <div className="space-y-5">
          <div>
            <label className="mb-1 flex justify-between text-xs text-muted-foreground uppercase">
              <span>Kelly Fraction</span>
              <span>{draft.risk.kelly_fraction.toFixed(2)}</span>
            </label>
            <input
              type="range"
              className="onboarding-range"
              min={0.05}
              max={1}
              step={0.05}
              value={draft.risk.kelly_fraction}
              onChange={(e) =>
                onChange({ risk: { ...draft.risk, kelly_fraction: Number(e.target.value) } })
              }
            />
          </div>
          <div>
            <label className="mb-1 flex justify-between text-xs text-muted-foreground uppercase">
              <span>Max Total Open Risk (USD)</span>
              <span>{draft.risk.max_total_open_risk}</span>
            </label>
            <input
              type="range"
              className="onboarding-range"
              min={50}
              max={5000}
              step={50}
              value={draft.risk.max_total_open_risk}
              onChange={(e) =>
                onChange({
                  risk: { ...draft.risk, max_total_open_risk: Number(e.target.value) },
                })
              }
            />
          </div>
          <div>
            <label className="mb-1 flex justify-between text-xs text-muted-foreground uppercase">
              <span>Capital Safety Threshold (USD)</span>
              <span>{draft.risk.real_capital_safety_threshold_usd}</span>
            </label>
            <input
              type="range"
              className="onboarding-range"
              min={100}
              max={10000}
              step={100}
              value={draft.risk.real_capital_safety_threshold_usd}
              onChange={(e) =>
                onChange({
                  risk: {
                    ...draft.risk,
                    real_capital_safety_threshold_usd: Number(e.target.value),
                  },
                })
              }
            />
          </div>
          <label className="flex items-center gap-3 text-sm">
            <input
              type="checkbox"
              checked={draft.evolution.approval_required}
              onChange={(e) =>
                onChange({
                  evolution: { ...draft.evolution, approval_required: e.target.checked },
                })
              }
            />
            Require approval for mutations
          </label>
          <label className="flex items-center gap-3 text-sm">
            <input
              type="checkbox"
              checked={draft.evolution.aggressive_evolution}
              onChange={(e) =>
                onChange({
                  evolution: { ...draft.evolution, aggressive_evolution: e.target.checked },
                })
              }
            />
            Aggressive evolution {isReal ? "(not recommended for REAL)" : ""}
          </label>
        </div>

        <Button className="onboarding-cta mt-8 w-full py-5" onClick={onContinue}>
          Continue
        </Button>
      </motion.div>

      <Dialog open={realConfirmOpen} onOpenChange={setRealConfirmOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Enable REAL Mode?</DialogTitle>
            <DialogDescription>
              REAL mode routes to live capital with strict risk controls. Birth Phase will still
              run in SIM until training completes.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setRealConfirmOpen(false)}>
              Cancel
            </Button>
            <Button className="onboarding-cta" onClick={confirmReal}>
              Confirm REAL
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
