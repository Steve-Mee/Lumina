import { motion } from "framer-motion";

import { Button } from "@/components/ui/button";
import type { OnboardingDraft } from "@/store/onboardingStore";

interface BirthActivateStepProps {
  draft: OnboardingDraft;
  setupComplete: boolean;
  activating: boolean;
  error: string | null;
  onChangeTraining: (training: Partial<OnboardingDraft["training"]>) => void;
  onActivate: () => void;
}

export function BirthActivateStep({
  draft,
  setupComplete,
  activating,
  error,
  onChangeTraining,
  onActivate,
}: BirthActivateStepProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="mx-auto max-w-xl space-y-6"
    >
      <div className="onboarding-card p-8">
        <h2 className="mb-2 text-lg font-semibold">Birth Phase</h2>
        <p className="mb-6 text-sm text-muted-foreground">
          Light training configuration. Birth runs certified SIM training on historical data before
          you operate the Command Deck.
        </p>

        <div className="mb-6 space-y-4">
          <div>
            <label className="mb-1 flex justify-between text-xs text-muted-foreground uppercase">
              <span>Training Trades</span>
              <span>{draft.training.training_trades.toLocaleString()}</span>
            </label>
            <input
              type="range"
              className="onboarding-range"
              min={5000}
              max={500000}
              step={5000}
              value={draft.training.training_trades}
              onChange={(e) =>
                onChangeTraining({ training_trades: Number(e.target.value) })
              }
            />
          </div>
          <div>
            <label className="mb-1 flex justify-between text-xs text-muted-foreground uppercase">
              <span>Max Historical Days</span>
              <span>{draft.training.max_real_days}</span>
            </label>
            <input
              type="range"
              className="onboarding-range"
              min={30}
              max={365}
              step={5}
              value={draft.training.max_real_days}
              onChange={(e) =>
                onChangeTraining({ max_real_days: Number(e.target.value) })
              }
            />
          </div>
          <label className="flex items-center gap-3 text-sm">
            <input
              type="checkbox"
              checked={draft.training.prefer_real_data_only}
              onChange={(e) =>
                onChangeTraining({ prefer_real_data_only: e.target.checked })
              }
            />
            Prefer real historical data only
          </label>
        </div>

        <div className="mb-6 rounded-lg border border-white/10 bg-black/20 p-4 text-xs text-muted-foreground">
          <p>
            Mode target: <span className="text-foreground uppercase">{draft.mode}</span> (runtime
            forced SIM during birth)
          </p>
          <p className="mt-1">
            Kelly: {draft.risk.kelly_fraction} · Max risk: ${draft.risk.max_total_open_risk}
          </p>
          {!setupComplete && (
            <p className="mt-2 text-cyan-300/80">Configuration will be saved when you activate.</p>
          )}
        </div>

        {error && (
          <p className="mb-4 text-sm text-red-400/90" role="alert">
            {error}
          </p>
        )}

        <Button
          className="onboarding-cta w-full py-6 text-sm"
          disabled={activating}
          onClick={onActivate}
        >
          {activating
            ? "Activating…"
            : "Activate Birth & Enter Neural Command Deck"}
        </Button>
      </div>
    </motion.div>
  );
}
