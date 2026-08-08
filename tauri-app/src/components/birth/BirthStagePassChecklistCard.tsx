/**
 * Stage goal board — gates (green/amber/red) vs skill-later (violet).
 * Outer shell stays neutral; worst open *gate* does not paint skill diagnostics red.
 */
import type { StagePassChecklist } from "@/lib/birth/birthStagePassChecklist";
import { CONDITION_VALUE_TEXT_CLASS, type ConditionTone } from "@/lib/conditionTone";
import { cn } from "@/lib/utils";

function statusGlyph(tone: ConditionTone, met: boolean, kind: "gate" | "skill"): string {
  if (kind === "skill") {
    if (met || tone === "ok") return "◆";
    return "◇";
  }
  if (met || tone === "ok") return "●";
  if (tone === "warn") return "◐";
  if (tone === "danger") return "○";
  return "·";
}

function rowToneAttr(tone: ConditionTone): "ok" | "warn" | "danger" | "accent" | undefined {
  if (tone === "ok" || tone === "warn" || tone === "danger" || tone === "accent") return tone;
  return undefined;
}

export function BirthStagePassChecklistCard({
  checklist,
  className,
}: {
  checklist: StagePassChecklist;
  className?: string;
}) {
  const {
    metCount,
    totalCount,
    allMet,
    overallTone,
    requirements,
    stageTitle,
    skillMetCount,
    skillTotalCount,
    passMode,
  } = checklist;

  const skillSuffix =
    skillTotalCount > 0 ? ` · skill ${skillMetCount}/${skillTotalCount}` : "";

  return (
    <div
      className={cn(
        "risk-envelope-field-card birth-field-card birth-stage-pass-checklist",
        className,
      )}
    >
      <div className="birth-stage-pass-checklist__head">
        <div className="min-w-0">
          <p className="risk-envelope-field-label mb-0">
            Stage goal
            {passMode === "survival" ? (
              <span className="birth-stage-pass-checklist__mode"> · survival</span>
            ) : null}
          </p>
          <p
            className={cn(
              "birth-stage-pass-checklist__summary font-mono tabular-nums tracking-tight",
              CONDITION_VALUE_TEXT_CLASS[overallTone],
            )}
          >
            {allMet ? "Ready to pass" : `${metCount}/${totalCount} gates clear`}
            {skillSuffix ? (
              <span className="birth-stage-pass-checklist__skill-summary">{skillSuffix}</span>
            ) : null}
          </p>
        </div>
        <p className="birth-stage-pass-checklist__stage shrink-0 font-mono uppercase">
          {stageTitle}
        </p>
      </div>

      <ul className="birth-stage-pass-checklist__list">
        {requirements.map((req) => {
          const kind = req.kind ?? "gate";
          const tone = rowToneAttr(req.tone);
          return (
            <li
              key={req.id}
              className="birth-stage-pass-checklist__row"
              data-tone={tone}
              data-kind={kind}
              title={
                kind === "skill"
                  ? `${req.label} (skill later — not required to pass): ${req.current} · ${req.need}`
                  : `${req.label}: ${req.current} · need ${req.need}`
              }
            >
              <span
                className={cn(
                  "birth-stage-pass-checklist__glyph",
                  CONDITION_VALUE_TEXT_CLASS[req.tone],
                )}
                aria-hidden
              >
                {statusGlyph(req.tone, req.met, kind)}
              </span>
              <div className="birth-stage-pass-checklist__meta min-w-0">
                <span className="birth-stage-pass-checklist__label truncate">
                  {req.label}
                </span>
                <span className="birth-stage-pass-checklist__need truncate">{req.need}</span>
              </div>
              <span
                className={cn(
                  "birth-stage-pass-checklist__value tabular-nums",
                  CONDITION_VALUE_TEXT_CLASS[req.tone],
                )}
              >
                {req.current}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
