import type { ReactNode } from "react";

import { BirthFieldCard, type BirthFieldTone } from "@/components/birth/BirthFieldCard";
import { CharterTile } from "@/components/birth/BirthGenesisDeckPrimitives";
import { BirthKpiTile, type BirthKpiTone } from "@/components/birth/BirthKpiTile";
import { BirthStagePassChecklistCard } from "@/components/birth/BirthStagePassChecklistCard";
import {
  PhaseCtaBar,
  PhaseGenesisFrame,
  PhaseMissionFrame,
  PhasePanelToolbar,
  PhaseStatusStrip,
  PhaseTextLink,
  type PhaseChip,
} from "@/components/shared/PhaseCinematicFrames";
import type { StagePassChecklist } from "@/lib/birth/birthStagePassChecklist";

export type PhaseKpi = {
  label: string;
  value: string;
  detail?: string;
  tone?: BirthKpiTone;
};

export type PhaseField = {
  label: string;
  value: string;
  hint?: string;
  tip?: string;
  tone?: BirthFieldTone;
};

export type PhaseTile = {
  label: string;
  value: string;
  tip: string;
  footnote: string;
};

export interface LivingPhaseMissionProps {
  running: boolean;
  busy: boolean;
  panelTitle: string;
  panelSubtitle: string;
  titleTip?: string;
  progressLabel?: string;
  statusLine: string;
  notice?: ReactNode;
  chips: PhaseChip[];
  tiles: PhaseTile[];
  kpis: PhaseKpi[];
  fields?: PhaseField[];
  sectionTitle?: string;
  checklist: StagePassChecklist;
  checklistGoal?: string;
  lifePulse?: ReactNode;
  intelTitle?: string;
  intelSubtitle?: string;
  intelChips?: PhaseChip[];
  intelFields?: PhaseField[];
  startLabel: string;
  stopLabel?: string;
  secondaryLabel?: string;
  onStart: () => void;
  onStop: () => void;
  onSecondary?: () => void;
  extraLinkLabel?: string;
  onExtraLink?: () => void;
  wipeLabel?: string;
  onWipe?: () => void;
  ctaFootnote: string;
}

export function LivingPhaseMission({
  running,
  busy,
  panelTitle,
  panelSubtitle,
  titleTip,
  progressLabel,
  statusLine,
  notice,
  chips,
  tiles,
  kpis,
  fields = [],
  sectionTitle,
  checklist,
  checklistGoal = "AND gates",
  lifePulse,
  intelTitle = "AND gates",
  intelSubtitle,
  intelChips,
  intelFields = [],
  startLabel,
  stopLabel = "STOP CLOCK",
  secondaryLabel = "Phase Hub",
  onStart,
  onStop,
  onSecondary,
  extraLinkLabel,
  onExtraLink,
  wipeLabel,
  onWipe,
  ctaFootnote,
}: LivingPhaseMissionProps) {
  const showExtra = Boolean(extraLinkLabel && onExtraLink);
  const showWipe = Boolean(wipeLabel && onWipe && !running);
  const cta = (
    <PhaseCtaBar
      footnote={ctaFootnote}
      primaryLabel={running ? stopLabel : startLabel}
      onPrimary={running ? onStop : onStart}
      primaryDisabled={busy}
      primaryActivating={false}
      secondaryLabel={secondaryLabel}
      onSecondary={onSecondary}
      secondaryDisabled={busy}
      links={
        showExtra || showWipe ? (
          <>
            {showExtra ? (
              <PhaseTextLink label={extraLinkLabel!} onClick={onExtraLink!} disabled={busy} />
            ) : null}
            {showWipe ? (
              <PhaseTextLink label={wipeLabel!} onClick={onWipe!} disabled={busy} danger />
            ) : null}
          </>
        ) : undefined
      }
    />
  );

  if (!running) {
    return (
      <PhaseGenesisFrame activating={false} ariaLabel={`${panelTitle} charter`}>
        <PhasePanelToolbar title={panelTitle} subtitle={panelSubtitle} titleTip={titleTip} />
        <PhaseStatusStrip chips={chips} label={`${panelTitle} status`} />
        <div className="birth-genesis-panel__body min-h-0 flex-1 overflow-x-hidden overflow-y-auto">
          <div className="flex flex-col gap-1.5 px-2.5 py-1.5">
            {statusLine ? (
              <p
                className="birth-mission-control__status-line birth-phase-subtitle shrink-0 text-left text-[11px] leading-snug text-white/55"
                title={statusLine}
              >
                {statusLine}
              </p>
            ) : null}
            {notice}
            <div className="genesis-charter-tile-grid phase-hub-kpi-grid shrink-0">
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
          </div>
        </div>
        {cta}
      </PhaseGenesisFrame>
    );
  }

  return (
    <PhaseMissionFrame
      activating
      className="living-phase-shell--gates"
      control={
        <section
          className="birth-mission-control lumina-glass lumina-glass--overlay flex h-full min-h-0 flex-col overflow-hidden"
          aria-label={`${panelTitle} mission control`}
        >
          <PhasePanelToolbar
            title={panelTitle}
            subtitle={panelSubtitle}
            titleTip={titleTip}
            trailing={
              progressLabel ? (
                <span className="birth-mission-control__progress-pct font-mono text-[0.55rem] tabular-nums tracking-wide text-cyan-200/80">
                  {progressLabel}
                </span>
              ) : null
            }
          />
          <PhaseStatusStrip chips={chips} label={`${panelTitle} status`} />
          <div className="birth-mission-control__body min-h-0 flex-1 overflow-x-hidden overflow-y-auto">
            <div className="flex flex-col gap-1.5 px-2.5 py-1.5">
              {statusLine ? (
                <p
                  className="birth-mission-control__status-line birth-phase-subtitle shrink-0 text-left text-[11px] leading-snug text-white/55"
                  title={statusLine}
                >
                  {statusLine}
                </p>
              ) : null}
              {lifePulse}
              <div className="birth-kpi-grid birth-intel-field-grid shrink-0">
                {kpis.map((kpi) => (
                  <BirthKpiTile
                    key={kpi.label}
                    label={kpi.label}
                    value={kpi.value}
                    detail={kpi.detail}
                    tone={kpi.tone}
                  />
                ))}
              </div>
              {fields.length > 0 ? (
                <div className="birth-section-card space-y-1.5 shrink-0">
                  {sectionTitle ? (
                    <p className="font-mono text-[0.55rem] tracking-[0.14em] text-cyan-200/80 uppercase">
                      {sectionTitle}
                    </p>
                  ) : null}
                  <div className="birth-intel-field-grid">
                    {fields.map((field) => (
                      <BirthFieldCard
                        key={field.label}
                        label={field.label}
                        value={field.value}
                        hint={field.hint}
                        tip={field.tip}
                        tone={field.tone}
                      />
                    ))}
                  </div>
                </div>
              ) : null}
            </div>
          </div>
          {cta}
        </section>
      }
      intel={
        <section
          className="birth-stage-intel-column lumina-glass lumina-glass--overlay flex h-full min-h-0 flex-col overflow-hidden"
          aria-label={`${panelTitle} gates`}
        >
          <PhasePanelToolbar title={intelTitle} subtitle={intelSubtitle} />
          {intelChips && intelChips.length > 0 ? (
            <PhaseStatusStrip chips={intelChips} label={`${panelTitle} gate status`} />
          ) : null}
          <div
            className={
              notice
                ? "birth-stage-intel-column__body birth-stage-intel-column__body--dock min-h-0 flex-1 px-2.5 py-1.5"
                : "birth-stage-intel-column__body min-h-0 flex-1 space-y-1.5 overflow-x-hidden overflow-y-auto px-2.5 py-1.5"
            }
          >
            <div className="birth-intel-field-grid birth-stage-tab-fields shrink-0">
              <BirthStagePassChecklistCard
                checklist={checklist}
                goalLabel={checklistGoal}
                showMode={false}
              />
              {intelFields.map((field) => (
                <BirthFieldCard
                  key={field.label}
                  label={field.label}
                  value={field.value}
                  hint={field.hint}
                  tip={field.tip}
                  tone={field.tone}
                />
              ))}
            </div>
            {notice ? <div className="playground-sense-slot min-h-0 flex-1">{notice}</div> : null}
          </div>
        </section>
      }
    />
  );
}
