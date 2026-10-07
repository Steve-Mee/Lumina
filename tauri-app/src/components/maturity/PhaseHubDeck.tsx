import type { ReactNode } from "react";
import { Trash2 } from "lucide-react";

import {
  CharterTile,
  RecoveryActionCard,
} from "@/components/birth/BirthGenesisDeckPrimitives";
import { PhaseHubHonestyBoard } from "@/components/maturity/PhaseHubHonestyBoard";
import { hubExamStatusLine } from "@/components/maturity/phaseHubChecklist";
import {
  HUB_WIPE_CARDS,
  phaseLabel,
  phaseStartIncomplete,
  startPhaseCtaLabel,
  type HubWipeKind,
} from "@/components/maturity/phaseHubFormat";
import { resolveHubCharterTiles } from "@/components/maturity/phaseHubTiles";
import { HelpTip } from "@/components/ui/HelpTip";
import { buildAwakeningExam, buildPhaseExam } from "@/lib/phaseExamModel";
import {
  PhaseCtaBar,
  PhaseGenesisFrame,
  PhasePanelToolbar,
} from "@/components/shared/PhaseCinematicFrames";
import { cn } from "@/lib/utils";
import type { MaturityHubPayload } from "@/lib/maturationClient";
import type { TwinReadiness } from "@/lib/twinClient";

function HubWipeBoard({
  disabled,
  onWipe,
}: {
  disabled: boolean;
  onWipe: (kind: HubWipeKind) => void;
}) {
  return (
    <section className="phase-hub-wipes-board shrink-0" aria-label="Named wipes">
      <div className="phase-hub-advance__head">
        <p className="risk-envelope-field-label mb-0">Danger</p>
        <HelpTip
          text="Named wipes. Three-step typed phrase. Wipe Awakening keeps the Birth plant and frozen π*."
          label="Named wipes info"
        />
      </div>
      <div className="genesis-recovery-action-grid genesis-recovery-action-grid--3">
        {HUB_WIPE_CARDS.map((card) => (
          <RecoveryActionCard
            key={card.kind}
            label={card.label}
            tip={card.tip}
            hint={card.hint}
            tone={card.tone}
          >
            <button
              type="button"
              className={cn(
                "genesis-recovery-action-card__btn",
                card.tone === "danger"
                  ? "genesis-recovery-action-card__btn--danger"
                  : "genesis-recovery-action-card__btn--warn",
              )}
              disabled={disabled}
              onClick={() => onWipe(card.kind)}
            >
              <Trash2 className="size-3.5 shrink-0" aria-hidden />
              <span>{card.label}</span>
            </button>
          </RecoveryActionCard>
        ))}
      </div>
    </section>
  );
}

export interface PhaseHubDeckProps {
  hub: MaturityHubPayload | null;
  twinReady?: TwinReadiness | null;
  busy: boolean;
  runnerActive: boolean;
  onStartNext: () => void;
  onOpenDeck: () => void;
  onWipe: (kind: HubWipeKind) => void;
  children?: ReactNode;
}

export function PhaseHubDeck({
  hub,
  twinReady,
  busy,
  runnerActive,
  onStartNext,
  onOpenDeck,
  onWipe,
  children,
}: PhaseHubDeckProps) {
  const nextPhase = hub?.next_phase ?? null;
  const nextSpec = nextPhase ? hub?.phase_specs?.[nextPhase] : null;
  const tiles = resolveHubCharterTiles(hub);
  const missing = hub?.exit_eval && !hub.exit_eval.ok ? (hub.exit_eval.missing ?? []) : [];
  const birthNext = nextPhase === "birth";
  const ctaLocked = busy || runnerActive || !nextPhase;
  const running = Boolean(hub?.active_phase) || runnerActive;
  const retry = phaseStartIncomplete(hub);
  const focusId = hub?.focus_phase || hub?.active_phase || nextPhase || "awakening";
  const focusLearned = hub?.focus_learned ?? {};
  const exam =
    focusId === "awakening"
      ? buildAwakeningExam({
          hub,
          learned: focusLearned,
          running,
          missing,
          progressMessage: hub?.progress_message,
        })
      : buildPhaseExam({
          phaseId: focusId,
          hub,
          learned: focusLearned,
          running,
          missing,
          progressMessage: hub?.progress_message,
          performanceLabel: "Phase exam",
          fallbackGoal: nextSpec?.human_goal || "—",
        });
  const panelTitle = focusId === "awakening" ? "First Watch" : phaseLabel(focusId);
  const statusLine = hubExamStatusLine(hub, { running, retry });
  const startable = Boolean(nextPhase);
  const wipeLocked = busy || runnerActive;

  const cta = startable ? (
    <PhaseCtaBar
      footnote={
        birthNext
          ? "Opens the Genesis deck. Activate Birth starts the new Birth there."
          : focusId === "awakening"
            ? "Click to start Awakening · after-this-phase preference is not a gate"
            : "Click to start · REAL still needs you"
      }
      primaryLabel={
        birthNext ? "ACTIVATE BIRTH" : startPhaseCtaLabel(nextPhase, { retry }).toUpperCase()
      }
      onPrimary={onStartNext}
      primaryDisabled={ctaLocked}
      primaryActivating={runnerActive}
      primaryActiveLabel={`${phaseLabel(focusId).toUpperCase()} CLOCK RUNNING`}
      secondaryLabel="Open Command Deck"
      onSecondary={onOpenDeck}
      secondaryDisabled={busy}
    />
  ) : (
    <div className="risk-envelope-cta-bar genesis-launch-cta phase-hub-cta shrink-0">
      <p className="mb-1.5 text-center font-mono text-[0.5rem] tracking-[0.12em] text-white/30 uppercase">
        No next phase
      </p>
      <div className="phase-hub-cta__row">
        <button
          type="button"
          className="genesis-recovery-action-card__btn genesis-recovery-action-card__btn--idle phase-hub-cta__deck"
          onClick={onOpenDeck}
        >
          Open Command Deck
        </button>
      </div>
    </div>
  );

  return (
    <PhaseGenesisFrame activating={runnerActive} ariaLabel="Phase hub charter">
      <div className="phase-hub-deck birth-genesis-panel__layout flex min-h-0 flex-1 flex-col overflow-hidden">
        <PhasePanelToolbar
          title={panelTitle}
          subtitle={`${phaseLabel(focusId)} · ${exam.progressLine}`}
          titleTip={exam.goal}
        />
        {hub ? <PhaseHubHonestyBoard hub={hub} twinReady={twinReady} /> : null}
        <div className="phase-hub-body birth-genesis-panel__body">
          <p className="phase-hub-status-line" title={statusLine}>
            {statusLine}
          </p>
          <div className="genesis-charter-tile-grid phase-hub-kpi-grid">
            {tiles.map((tile) => (
              <CharterTile
                key={tile.label}
                label={tile.label}
                value={tile.value}
                tip={tile.tip}
                footnote={tile.footnote}
              />
            ))}
          </div>
          {children}
          <HubWipeBoard disabled={wipeLocked} onWipe={onWipe} />
        </div>
        {cta}
      </div>
    </PhaseGenesisFrame>
  );
}
