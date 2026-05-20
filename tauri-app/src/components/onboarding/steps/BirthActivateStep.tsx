import { lazy, Suspense, useState } from "react";
import { motion } from "framer-motion";
import { ChevronDown } from "lucide-react";

import { BirthCinematicLayout } from "@/components/birth/BirthCinematicLayout";
import { BirthHoloSlider } from "@/components/birth/BirthHoloSlider";
import { BirthLaunchButton } from "@/components/birth/BirthLaunchButton";
import { BirthOrganismVisual } from "@/components/birth/BirthOrganismVisual";
import { helpFor } from "@/lib/helpTexts";
import { distressPanelClass, warnOverlayBodyClass } from "@/lib/modePresentation";
import { cn } from "@/lib/utils";
import type { OnboardingDraft } from "@/store/onboardingStore";

const BirthHelixVisual = lazy(() =>
  import("@/components/birth/BirthHelixVisual").then((module) => ({
    default: module.BirthHelixVisual,
  })),
);

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
  setupComplete: _setupComplete,
  activating,
  error,
  onChangeTraining,
  onActivate,
}: BirthActivateStepProps) {
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [helixPrimed, setHelixPrimed] = useState(false);

  const stage = (
    <>
      <Suspense
        fallback={
          <div className="flex min-h-[320px] items-center justify-center">
            <BirthOrganismVisual className="size-48 opacity-80" />
          </div>
        }
      >
        <BirthHelixVisual
          activating={activating}
          primed={helixPrimed}
          trainingTrades={draft.training.training_trades}
          className="min-h-[340px] md:min-h-[480px]"
        />
      </Suspense>
      <p className="birth-activation-caption">
        {activating
          ? "Activation sequence engaged — organism awakening"
          : helixPrimed
            ? "Neural lattice primed — commit on your mark"
            : "Organism dormant — awaiting activation sequence"}
      </p>
    </>
  );

  const deck = (
    <motion.div
      className={cn("birth-activation-deck-inner", activating && "birth-activation-deck-inner--dim")}
      initial={{ opacity: 0, x: 12 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.45, delay: 0.1 }}
    >
      <p className="birth-activation-eyebrow">Birth Protocol</p>
      <h2 className="birth-activation-title">Neural Genesis</h2>
      <p className="birth-activation-desc">
        Seal the genesis vector. The organism will awaken through certified SIM training before
        you enter the Neural Command Deck.
      </p>

      {error ? (
        <p className={cn("mb-4 rounded-lg p-3 text-sm", distressPanelClass("error"))} role="alert">
          <span className={warnOverlayBodyClass()}>{error}</span>
        </p>
      ) : null}

      <BirthLaunchButton
        activating={activating}
        primed={helixPrimed}
        onPrimedChange={setHelixPrimed}
        onClick={onActivate}
        className="mb-5"
      />

      <BirthHoloSlider
        label="Training Trades"
        value={draft.training.training_trades}
        min={5000}
        max={500000}
        step={5000}
        format={(v) => v.toLocaleString()}
        onChange={(v) => onChangeTraining({ training_trades: v })}
        disabled={activating}
      />

      <BirthHoloSlider
        label="Max Historical Days"
        value={draft.training.max_real_days}
        min={30}
        max={365}
        step={5}
        onChange={(v) => onChangeTraining({ max_real_days: v })}
        disabled={activating}
      />

      <button
        type="button"
        className="birth-advanced-toggle"
        onClick={() => setAdvancedOpen((v) => !v)}
        aria-expanded={advancedOpen}
      >
        <span>Advanced genesis parameters</span>
        <ChevronDown
          className={cn("size-4 transition-transform", advancedOpen && "rotate-180")}
          aria-hidden
        />
      </button>

      {advancedOpen ? (
        <div className="birth-holo-chips mt-2">
          <label className="birth-holo-chip" title={helpFor("prefer_real_data_only")}>
            <input
              type="checkbox"
              checked={draft.training.prefer_real_data_only}
              disabled={activating}
              onChange={(e) =>
                onChangeTraining({ prefer_real_data_only: e.target.checked })
              }
            />
            Real historical data only
          </label>
          <label className="birth-holo-chip" title={helpFor("allow_minimal_synthetic_fallback")}>
            <input
              type="checkbox"
              checked={draft.training.allow_minimal_synthetic_fallback}
              disabled={activating}
              onChange={(e) =>
                onChangeTraining({ allow_minimal_synthetic_fallback: e.target.checked })
              }
            />
            Minimal synthetic fallback
          </label>
        </div>
      ) : null}
    </motion.div>
  );

  return (
    <BirthCinematicLayout
      className="w-full max-w-none px-2 md:px-6"
      stage={stage}
      deck={deck}
    />
  );
}
