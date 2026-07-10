import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";

import { BirthHoloSlider } from "@/components/birth/BirthHoloSlider";
import { BirthControlDock } from "@/components/birth/BirthControlDock";
import { BirthGenesisStatusChips } from "@/components/birth/BirthGenesisStatusChips";
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
import { formatGenesisCheckpointSummary } from "@/lib/birthPhaseModel";
import { distressPanelClass, warnOverlayBodyClass } from "@/lib/modePresentation";
import { cn } from "@/lib/utils";
import type { BirthStatusPayload, BirthWipeResult } from "@/lib/birthClient";
import type { OnboardingDraft } from "@/store/onboardingStore";

type GenesisDeckTab = "doelen" | "parameters";

const RESUME_TIER_HINT: Record<string, string> = {
  T0: "Laatste cache direct geladen.",
  T1: "Checkpoint-manifest hersteld vanaf cache.",
  T2: "Regime-map herberekend (algo update); curriculum blijft intact.",
  T3: "Data opnieuw voorbereid; curriculum blijft intact.",
  T4: "Nieuwe marktdata — holdout opnieuw berekend; curriculum blijft intact.",
};

interface BirthGenesisDeckProps {
  training: OnboardingDraft["training"];
  activating: boolean;
  checkpointAvailable?: boolean;
  birthStatus?: BirthStatusPayload | null;
  busy?: boolean;
  engineLive?: boolean;
  error?: string | null;
  onChangeTraining: (training: Partial<OnboardingDraft["training"]>) => void;
  onActivate: () => void;
  onWipe?: () => Promise<BirthWipeResult>;
  onStop?: () => void | Promise<void>;
  onResumeCheckpoint?: () => void;
  resumePlateauRisk?: boolean;
  resumePlateauRiskTrades?: number | null;
  className?: string;
}

export function BirthGenesisDeck({
  training,
  activating,
  checkpointAvailable = false,
  birthStatus = null,
  busy = false,
  engineLive = false,
  error = null,
  onChangeTraining,
  onActivate,
  onWipe,
  onStop,
  onResumeCheckpoint,
  resumePlateauRisk = false,
  resumePlateauRiskTrades = null,
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
  const checkpointSummary = checkpointAvailable
    ? formatGenesisCheckpointSummary(birthStatus)
    : null;
  const resumeTier = String(birthStatus?.progress?.resume_cache_tier ?? "").trim().toUpperCase();
  const resumeTierHint = RESUME_TIER_HINT[resumeTier] ?? null;

  const loadHints: string[] = [];
  if (training.max_real_days < estimatedDays) {
    loadHints.push("Onder aanbevolen minimum voor huidige trade-target.");
  }
  if (isHighLoadEstimate(estimatedDays)) {
    loadHints.push(
      `Grote trade-target (${estimatedDays.toLocaleString()} dagen) — langere load en hogere hardware-load.`,
    );
  }
  if (estimatedDays > barCapDays && training.prefer_real_data_only) {
    loadHints.push(
      `Bar-fetch capped op ~${barCapDays.toLocaleString()} dagen; synthetic top-up mogelijk.`,
    );
  }

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

  const maxDaysHint = [
    helpFor("max_real_days"),
    `~${FIRST_BOOT_EST_TRADES_PER_REAL_DAY.toLocaleString()} trades/dag → ${estimatedDays.toLocaleString()} dagen bij huidige target.`,
    ...loadHints,
  ].join(" ");

  return (
    <div className={cn("birth-genesis-panel__layout flex min-h-0 flex-1 flex-col overflow-hidden", className)}>
      <div className="birth-genesis-panel__body min-h-0 flex-1 overflow-hidden">
        <motion.div
          className={cn(
            "birth-genesis-panel__hero birth-genesis-panel__inner birth-activation-deck-inner",
            disabled && "birth-activation-deck-inner--dim",
          )}
          initial={reducedMotion ? false : { opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.45, delay: 0.1 }}
        >
          <GenesisMaturityLadder activePhase="genesis" className="mb-1.5" />

          {error ? (
            <p
              className={cn("mb-2 rounded-lg p-2 text-xs", distressPanelClass("error"))}
              role="alert"
              title={error}
            >
              <span className={cn(warnOverlayBodyClass(), "line-clamp-2")}>{error}</span>
            </p>
          ) : null}

          <BirthLaunchButton
            activating={activating}
            primed={helixPrimed}
            onPrimedChange={setHelixPrimed}
            onSequencingChange={setSequencing}
            onClick={onActivate}
            className="mb-2"
          />

          {disabled ? (
            <p className="birth-activation-progress mb-2 text-center font-mono text-[0.55rem] tracking-[0.14em] uppercase text-cyan-400/80">
              {activating
                ? "Saving genesis settings and starting birth engine…"
                : "Sequencing neural lattice…"}
            </p>
          ) : null}

          <div className="birth-activation-primary-param birth-genesis-slider-grid">
            <div className="birth-genesis-slider-card">
              <p className="mb-1 font-mono text-[0.55rem] tracking-[0.12em] uppercase text-cyan-400/70">
                Auto Charter
              </p>
              <p className="text-xs text-muted-foreground">
                Training trades: <strong>{training.training_trades.toLocaleString()}</strong> (computed)
              </p>
              <p className="text-xs text-muted-foreground">
                Winrate gate: <strong>{gatePct}%</strong> (computed)
              </p>
              <BirthHoloSlider
                label="Training Trades"
                value={training.training_trades}
                min={5000}
                max={500000}
                step={5000}
                format={(v) => v.toLocaleString()}
                onChange={handleTrainingTradesChange}
                disabled
                className="birth-holo-slider--genesis-card opacity-70"
              />
            </div>
            <div className="birth-genesis-slider-card">
              <GenesisWinrateGateBlock
                gatePct={gatePct}
                disabled
                className="birth-holo-slider--genesis-card opacity-70"
                onChange={(pct) =>
                  onChangeTraining({ stage1_winrate_pass_threshold: pct / 100 })
                }
              />
            </div>
          </div>
        </motion.div>

        <Tabs
          value={genesisTab}
          onValueChange={(value) => setGenesisTab(value as GenesisDeckTab)}
          className="birth-genesis-panel__tabs flex min-h-0 flex-1 flex-col"
        >
          <div className="birth-genesis-tab-panel min-h-0 flex-1">
            <TabsList className="birth-genesis-tab-list" aria-label="Genesis charter sections">
              <TabsTrigger value="doelen">Doelen</TabsTrigger>
              <TabsTrigger value="parameters">Parameters</TabsTrigger>
            </TabsList>

            <div className="birth-genesis-tab-panel__body min-h-0 flex-1">
              <TabsContent
                value="doelen"
                className="birth-genesis-tab-content birth-genesis-tab-content--doelen mt-0 outline-none data-[state=inactive]:hidden"
              >
                <GenesisMaturityGoalsPreview />
              </TabsContent>
              <TabsContent
                value="parameters"
                className="birth-genesis-tab-content mt-0 outline-none data-[state=inactive]:hidden"
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
                    hint={maxDaysHint}
                    className="birth-genesis-tab-panel__slider"
                  />
                  {loadHints.length > 0 ? (
                    <details className="birth-genesis-hints-details">
                      <summary>Load hints ({loadHints.length})</summary>
                      <ul>
                        {loadHints.map((hint) => (
                          <li key={hint}>{hint}</li>
                        ))}
                      </ul>
                    </details>
                  ) : null}
                  <div className="birth-holo-chips birth-genesis-tab-panel__chips birth-genesis-tab-panel__chips--compact">
                    <label className="birth-holo-chip" title={helpFor("prefer_real_data_only")}>
                      <input
                        type="checkbox"
                        checked={training.prefer_real_data_only}
                        disabled={disabled}
                        onChange={(e) => onChangeTraining({ prefer_real_data_only: e.target.checked })}
                      />
                      Real data only
                    </label>
                    <label className="birth-holo-chip" title={helpFor("allow_minimal_synthetic_fallback")}>
                      <input
                        type="checkbox"
                        checked={training.allow_minimal_synthetic_fallback}
                        disabled={disabled}
                        onChange={(e) =>
                          onChangeTraining({ allow_minimal_synthetic_fallback: e.target.checked })
                        }
                      />
                      Synthetic fallback
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
                      Simulator data
                    </label>
                  </div>
                </div>
              </TabsContent>
            </div>
          </div>
        </Tabs>
      </div>

      <div className="birth-genesis-panel__actions">
        <BirthGenesisStatusChips
          engineLive={engineLive}
          resumePlateauRisk={resumePlateauRisk}
          resumePlateauRiskTrades={resumePlateauRiskTrades}
          checkpointAvailable={checkpointAvailable}
          checkpointSummary={checkpointSummary}
          resumeTierHint={resumeTierHint}
        />
        <BirthControlDock
          mode="genesis"
          checkpointAvailable={checkpointAvailable}
          busy={busy}
          activating={activating}
          engineLive={engineLive}
          showStartButton={false}
          onWipe={onWipe}
          onStop={onStop}
          onResumeCheckpoint={onResumeCheckpoint}
          inline
          className="justify-start border-0 bg-transparent p-0 shadow-none backdrop-blur-none"
        />
      </div>
    </div>
  );
}
