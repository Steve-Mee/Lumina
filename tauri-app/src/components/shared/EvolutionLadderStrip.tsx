import {
  GenesisMaturityLadder,
  type MaturationPhaseId,
} from "@/components/birth/GenesisMaturityLadder";
import { useMaturationChrome } from "@/hooks/useMaturationChrome";
import { cn } from "@/lib/utils";

interface EvolutionLadderStripProps {
  className?: string;
  /** Force phase (tests / overrides). Default: shared chrome hook. */
  activePhase?: MaturationPhaseId;
  /** Hide REAL eligible badge (compact chrome). */
  hideBadge?: boolean;
  /** Show first blockers under ladder. */
  showBlockers?: boolean;
}

/**
 * Persistent maturation spine — pure pipeline + "You are here" (no meta title row).
 */
export function EvolutionLadderStrip({
  className,
  activePhase,
  hideBadge: _hideBadge = false,
  showBlockers = false,
}: EvolutionLadderStripProps) {
  const chrome = useMaturationChrome();
  const phase = activePhase ?? chrome.phase;

  return (
    <div
      className={cn(
        "evolution-ladder-strip lumina-glass lumina-glass--panel relative z-20 shrink-0 border-b border-white/8 px-3 py-2",
        className,
      )}
      data-phase={phase}
      aria-label="Lumina evolution ladder"
    >
      <GenesisMaturityLadder activePhase={phase} className="evolution-ladder-strip__ladder" />
      {showBlockers && !chrome.eligible && chrome.blockers.length > 0 ? (
        <ul className="mt-1 max-h-10 space-y-0.5 overflow-hidden font-mono text-[9px] text-amber-200/75">
          {chrome.blockers.slice(0, 2).map((item) => (
            <li key={item} className="truncate">
              · {item}
            </li>
          ))}
        </ul>
      ) : null}
      {chrome.error ? (
        <p className="mt-0.5 truncate font-mono text-[9px] text-white/30">{chrome.error}</p>
      ) : null}
    </div>
  );
}
