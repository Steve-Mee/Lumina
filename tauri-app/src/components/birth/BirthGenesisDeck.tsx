import { useState } from "react";
import { motion } from "framer-motion";
import { ChevronDown } from "lucide-react";

import { BirthHoloSlider } from "@/components/birth/BirthHoloSlider";
import { BirthLaunchButton } from "@/components/birth/BirthLaunchButton";
import { usePrefersReducedMotion } from "@/hooks/usePrefersReducedMotion";
import { helpFor } from "@/lib/helpTexts";
import { distressPanelClass, warnOverlayBodyClass } from "@/lib/modePresentation";
import { cn } from "@/lib/utils";
import type { OnboardingDraft } from "@/store/onboardingStore";

interface BirthGenesisDeckProps {
  training: OnboardingDraft["training"];
  activating: boolean;
  error?: string | null;
  onChangeTraining: (training: Partial<OnboardingDraft["training"]>) => void;
  onActivate: () => void;
  className?: string;
}

export function BirthGenesisDeck({
  training,
  activating,
  error = null,
  onChangeTraining,
  onActivate,
  className,
}: BirthGenesisDeckProps) {
  const reducedMotion = usePrefersReducedMotion();
  const [genesisOpen, setGenesisOpen] = useState(false);
  const [helixPrimed, setHelixPrimed] = useState(false);
  const [sequencing, setSequencing] = useState(false);

  return (
    <motion.div
      className={cn(
        "birth-activation-deck-inner",
        (activating || sequencing) && "birth-activation-deck-inner--dim",
        className,
      )}
      initial={reducedMotion ? false : { opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.45, delay: 0.1 }}
    >
      <p className="birth-activation-eyebrow">Birth Protocol</p>
      <h2 className="birth-activation-title">Neural Genesis</h2>
      <p className="birth-activation-desc">
        Seal the genesis vector. The organism awakens through certified SIM training before deck
        entry.
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
        onSequencingChange={setSequencing}
        onClick={onActivate}
        className="mb-4"
      />

      {activating || sequencing ? (
        <p className="birth-activation-progress mb-4 text-center font-mono text-[0.6rem] tracking-[0.16em] uppercase text-cyan-400/80">
          {activating
            ? "Saving genesis settings and starting birth engine…"
            : "Sequencing neural lattice…"}
        </p>
      ) : null}

      <div className="birth-activation-primary-param">
        <BirthHoloSlider
          label="Training Trades"
          value={training.training_trades}
          min={5000}
          max={500000}
          step={5000}
          format={(v) => v.toLocaleString()}
          onChange={(v) => onChangeTraining({ training_trades: v })}
          disabled={activating || sequencing}
        />
      </div>

      <button
        type="button"
        className="birth-advanced-toggle birth-activation-genesis-toggle"
        onClick={() => setGenesisOpen((v) => !v)}
        aria-expanded={genesisOpen}
      >
        <span>Genesis parameters</span>
        <ChevronDown
          className={cn("size-4 transition-transform", genesisOpen && "rotate-180")}
          aria-hidden
        />
      </button>

      {genesisOpen ? (
        <div className="birth-activation-genesis-panel mt-2">
          <BirthHoloSlider
            label="Max Historical Days"
            value={training.max_real_days}
            min={30}
            max={365}
            step={5}
            onChange={(v) => onChangeTraining({ max_real_days: v })}
            disabled={activating || sequencing}
          />
          <div className="birth-holo-chips mt-2">
            <label className="birth-holo-chip" title={helpFor("prefer_real_data_only")}>
              <input
                type="checkbox"
                checked={training.prefer_real_data_only}
                disabled={activating || sequencing}
                onChange={(e) => onChangeTraining({ prefer_real_data_only: e.target.checked })}
              />
              Real historical data only
            </label>
            <label className="birth-holo-chip" title={helpFor("allow_minimal_synthetic_fallback")}>
              <input
                type="checkbox"
                checked={training.allow_minimal_synthetic_fallback}
                disabled={activating || sequencing}
                onChange={(e) =>
                  onChangeTraining({ allow_minimal_synthetic_fallback: e.target.checked })
                }
              />
              Minimal synthetic fallback
            </label>
          </div>
        </div>
      ) : null}
    </motion.div>
  );
}
