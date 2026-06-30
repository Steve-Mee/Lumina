import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";

import { BirthHoloSlider } from "@/components/birth/BirthHoloSlider";
import { BirthControlDock } from "@/components/birth/BirthControlDock";
import { BirthLaunchButton } from "@/components/birth/BirthLaunchButton";
import {
  GenesisMaturityGoalsPreview,
  GenesisMaturityLadder,
  GenesisWinrateGateBlock,
} from "@/components/birth/GenesisMaturityLadder";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { usePrefersReducedMotion } from "@/hooks/usePrefersReducedMotion";
import {
  clampMaxRealDays,
  FIRST_BOOT_EST_TRADES_PER_REAL_DAY,
  FIRST_BOOT_MAX_REAL_DAYS,
  FIRST_BOOT_MIN_REAL_DAYS,
  historicalBarCapDays,
  isHighLoadEstimate,
  linkMaxRealDaysToTrainingTrades,
  resolveDefaultMaxRealDays,
} from "@/lib/firstBootSizing";
import { helpFor } from "@/lib/helpTexts";
import { distressPanelClass, warnOverlayBodyClass } from "@/lib/modePresentation";
import { cn } from "@/lib/utils";
import type { OnboardingDraft } from "@/store/onboardingStore";

type GenesisDeckTab = "doelen" | "parameters";

interface BirthGenesisDeckProps {
  training: OnboardingDraft["training"];
  activating: boolean;
  checkpointAvailable?: boolean;
  busy?: boolean;
  error?: string | null;
  onChangeTraining: (training: Partial<OnboardingDraft["training"]>) => void;
  onActivate: () => void;
  onWipe?: () => void;
  onResumeCheckpoint?: () => void;
  className?: string;
}

export function BirthGenesisDeck({
  training,
  activating,
  checkpointAvailable = false,
  busy = false,
  error = null,
  onChangeTraining,
  onActivate,
  onWipe,
  onResumeCheckpoint,
  className,
}: BirthGenesisDeckProps) {
  const reducedMotion = usePrefersReducedMotion();
  const [genesisTab, setGenesisTab] = useState<GenesisDeckTab>("doelen");
  const [helixPrimed, setHelixPrimed] = useState(false);
  const [sequencing, setSequencing] = useState(false);
  const disabled = activating || sequencing || busy;
  const gatePct = Math.round((training.stage1_winrate_pass_threshold ?? 0.45) * 100);
  const estimatedDays = resolveDefaultMaxRealDays(training.training_trades);
  const barCapDays = historicalBarCapDays();

  const migratedRef = useRef(false);

  useEffect(() => {
    if (migratedRef.current) return;
    migratedRef.current = true;
    const linked = linkMaxRealDaysToTrainingTrades(training.training_trades);
    if (training.max_real_days !== linked) {
      onChangeTraining({ max_real_days: linked });
    }
    // One-time draft migration; manual max_real_days edits must not be overwritten.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleTrainingTradesChange = (trainingTrades: number) => {
    onChangeTraining({
      training_trades: trainingTrades,
      max_real_days: linkMaxRealDaysToTrainingTrades(trainingTrades),
    });
  };

  const handleMaxRealDaysChange = (maxRealDays: number) => {
    onChangeTraining({ max_real_days: clampMaxRealDays(maxRealDays) });
  };

  return (
    <div className={cn("birth-genesis-panel__layout flex min-h-0 flex-1 flex-col overflow-hidden", className)}>
      <motion.div
        className={cn(
          "birth-genesis-panel__hero birth-genesis-panel__inner birth-activation-deck-inner",
          disabled && "birth-activation-deck-inner--dim",
        )}
        initial={reducedMotion ? false : { opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.45, delay: 0.1 }}
      >
        <p
          className="birth-activation-desc line-clamp-2"
          title={helpFor("genesis_maturity_charter")}
        >
          Teken het groeicontract vóór Birth Phase. Hier stel je in hoe Lumina leert (historische
          data) en welke drempels later REAL kapitaal unlocken.
        </p>

        <GenesisMaturityLadder activePhase="genesis" className="mb-2" />

        {error ? (
          <p className={cn("mb-3 rounded-lg p-3 text-sm", distressPanelClass("error"))} role="alert">
            <span className={warnOverlayBodyClass()}>{error}</span>
          </p>
        ) : null}

        <BirthLaunchButton
          activating={activating}
          primed={helixPrimed}
          onPrimedChange={setHelixPrimed}
          onSequencingChange={setSequencing}
          onClick={onActivate}
          className="mb-3"
        />

        {disabled ? (
          <p className="birth-activation-progress mb-3 text-center font-mono text-[0.6rem] tracking-[0.16em] uppercase text-cyan-400/80">
            {activating
              ? "Saving genesis settings and starting birth engine…"
              : "Sequencing neural lattice…"}
          </p>
        ) : null}

        <div className="birth-activation-primary-param space-y-3">
          <BirthHoloSlider
            label="Training Trades"
            value={training.training_trades}
            min={5000}
            max={500000}
            step={5000}
            format={(v) => v.toLocaleString()}
            onChange={handleTrainingTradesChange}
            disabled={disabled}
          />
          <GenesisWinrateGateBlock
            gatePct={gatePct}
            disabled={disabled}
            onChange={(pct) =>
              onChangeTraining({ stage1_winrate_pass_threshold: pct / 100 })
            }
          />
        </div>
      </motion.div>

      <Tabs
        value={genesisTab}
        onValueChange={(value) => setGenesisTab(value as GenesisDeckTab)}
        className="birth-genesis-panel__tabs flex min-h-0 flex-1 flex-col gap-0"
      >
        <div className="birth-genesis-tab-panel min-h-0 flex-1">
          <TabsList
            className="birth-genesis-tab-list"
            aria-label="Genesis charter sections"
          >
            <TabsTrigger value="doelen">Doelen</TabsTrigger>
            <TabsTrigger value="parameters">Parameters</TabsTrigger>
          </TabsList>

          <div className="birth-genesis-tab-panel__body min-h-0 flex-1">
            <TabsContent
              value="doelen"
              className="birth-genesis-tab-content birth-genesis-tab-content--doelen mt-0 h-full outline-none data-[state=inactive]:hidden"
            >
              <GenesisMaturityGoalsPreview />
            </TabsContent>
            <TabsContent
              value="parameters"
              className="birth-genesis-tab-content mt-0 h-full outline-none data-[state=inactive]:hidden"
            >
              <div className="birth-activation-genesis-panel birth-genesis-tab-panel__content space-y-2">
                <BirthHoloSlider
                  label="Max Historical Days"
                  value={clampMaxRealDays(training.max_real_days)}
                  min={FIRST_BOOT_MIN_REAL_DAYS}
                  max={FIRST_BOOT_MAX_REAL_DAYS}
                  step={5}
                  onChange={handleMaxRealDaysChange}
                  disabled={disabled}
                  className="birth-genesis-tab-panel__slider"
                />
                <p
                  className="text-center font-mono text-[10px] tracking-wide text-muted-foreground"
                  title={helpFor("max_real_days")}
                >
                  ~{FIRST_BOOT_EST_TRADES_PER_REAL_DAY.toLocaleString()} trades/dag →{" "}
                  {estimatedDays.toLocaleString()} dagen bij huidige trade-target (30–
                  {FIRST_BOOT_MAX_REAL_DAYS.toLocaleString()} bereik)
                </p>
                {training.max_real_days < estimatedDays ? (
                  <p className="text-center text-xs text-amber-200/90">
                    Onder aanbevolen minimum voor huidige trade-target.
                  </p>
                ) : null}
                {isHighLoadEstimate(estimatedDays) ? (
                  <p className="text-center text-xs text-amber-200/90">
                    Grote trade-target ({estimatedDays.toLocaleString()} dagen) — langere load en
                    hogere hardware-load verwacht.
                  </p>
                ) : null}
                {estimatedDays > barCapDays && training.prefer_real_data_only ? (
                  <p className="text-center text-xs text-amber-200/90">
                    Bar-fetch capped op ~{barCapDays.toLocaleString()} kalenderdagen; daarboven kan
                    synthetic top-up nodig zijn ondanks real-data-only.
                  </p>
                ) : null}
                <div className="birth-holo-chips birth-genesis-tab-panel__chips">
                  <label className="birth-holo-chip" title={helpFor("prefer_real_data_only")}>
                    <input
                      type="checkbox"
                      checked={training.prefer_real_data_only}
                      disabled={disabled}
                      onChange={(e) => onChangeTraining({ prefer_real_data_only: e.target.checked })}
                    />
                    Real historical data only
                  </label>
                  <label
                    className="birth-holo-chip"
                    title={helpFor("allow_minimal_synthetic_fallback")}
                  >
                    <input
                      type="checkbox"
                      checked={training.allow_minimal_synthetic_fallback}
                      disabled={disabled}
                      onChange={(e) =>
                        onChangeTraining({ allow_minimal_synthetic_fallback: e.target.checked })
                      }
                    />
                    Minimal synthetic fallback
                  </label>
                  <label className="birth-holo-chip" title={helpFor("require_real_simulator_data")}>
                    <input
                      type="checkbox"
                      checked={training.require_real_simulator_data}
                      disabled={disabled}
                      onChange={(e) =>
                        onChangeTraining({ require_real_simulator_data: e.target.checked })
                      }
                    />
                    Require simulator data
                  </label>
                </div>
              </div>
            </TabsContent>
          </div>
        </div>
      </Tabs>

      <div className="birth-genesis-panel__actions">
        <BirthControlDock
          mode="genesis"
          checkpointAvailable={checkpointAvailable}
          busy={busy || activating}
          showStartButton={false}
          onWipe={onWipe}
          onResumeCheckpoint={onResumeCheckpoint}
          inline
          className="justify-start border-0 bg-transparent p-0 shadow-none backdrop-blur-none"
        />
      </div>
    </div>
  );
}
