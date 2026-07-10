import { AlertTriangle, Cpu, RotateCcw } from "lucide-react";

import { cn } from "@/lib/utils";

interface BirthGenesisStatusChipsProps {
  engineLive?: boolean;
  resumePlateauRisk?: boolean;
  resumePlateauRiskTrades?: number | null;
  checkpointAvailable?: boolean;
  checkpointSummary?: string | null;
  resumeTierHint?: string | null;
  className?: string;
}

const PLATEAU_TITLE =
  "Hervatten zonder reset kan plateau opnieuw triggeren. Gebruik Wis birth-data (cache behouden) of Start birth opnieuw.";

const CHECKPOINT_BASE =
  "Hervat checkpoint gaat verder waar je stopte; curriculum wordt niet gewist. Data-prep kan kort opnieuw draaien.";

/**
 * Compact status row — full context in native title tooltips (no scroll blocks).
 */
export function BirthGenesisStatusChips({
  engineLive = false,
  resumePlateauRisk = false,
  resumePlateauRiskTrades = null,
  checkpointAvailable = false,
  checkpointSummary = null,
  resumeTierHint = null,
  className,
}: BirthGenesisStatusChipsProps) {
  const hasChip =
    engineLive || resumePlateauRisk || (checkpointAvailable && Boolean(checkpointSummary));

  if (!hasChip) {
    return null;
  }

  const plateauTitle =
    resumePlateauRiskTrades != null
      ? `${PLATEAU_TITLE} (${resumePlateauRiskTrades.toLocaleString()} stage trades geladen.)`
      : PLATEAU_TITLE;

  const checkpointTitle = [checkpointSummary, CHECKPOINT_BASE, resumeTierHint]
    .filter(Boolean)
    .join(" · ");

  return (
    <div
      className={cn("birth-genesis-status-chips", className)}
      role="status"
      aria-label="Birth checkpoint status"
    >
      {engineLive ? (
        <span className="birth-genesis-status-chip birth-genesis-status-chip--live" title="Birth engine draait nog op de achtergrond — stop eerst voordat je wist.">
          <Cpu className="size-3 shrink-0" aria-hidden />
          Engine live
        </span>
      ) : null}
      {resumePlateauRisk ? (
        <span className="birth-genesis-status-chip birth-genesis-status-chip--warn" title={plateauTitle}>
          <AlertTriangle className="size-3 shrink-0" aria-hidden />
          Plateau risk
          {resumePlateauRiskTrades != null ? (
            <span className="birth-genesis-status-chip__meta">
              {resumePlateauRiskTrades.toLocaleString()} trades
            </span>
          ) : null}
        </span>
      ) : null}
      {checkpointAvailable && checkpointSummary ? (
        <span
          id="birth-resume-checkpoint-hint"
          className="birth-genesis-status-chip birth-genesis-status-chip--checkpoint"
          title={checkpointTitle}
        >
          <RotateCcw className="size-3 shrink-0" aria-hidden />
          <span className="birth-genesis-status-chip__truncate">{checkpointSummary}</span>
        </span>
      ) : null}
    </div>
  );
}
