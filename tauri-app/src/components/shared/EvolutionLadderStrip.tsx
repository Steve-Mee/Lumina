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
  /** Optional exit from Command Deck back to the originating surface. */
  returnLabel?: string;
  onReturn?: () => void;
}

/**
 * Persistent maturation spine — pure pipeline + "You are here" (no meta title row).
 */
export function EvolutionLadderStrip({
  className,
  activePhase,
  hideBadge: _hideBadge = false,
  showBlockers = false,
  returnLabel,
  onReturn,
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
      <div className="flex items-center gap-2">
        <GenesisMaturityLadder
          activePhase={phase}
          className="evolution-ladder-strip__ladder min-w-0 flex-1"
        />
        {returnLabel && onReturn ? (
          <button
            type="button"
            className="evolution-ladder-strip__return shrink-0 font-mono text-[9px] tracking-[0.14em] text-cyan-200/80 uppercase underline-offset-2 hover:underline"
            onClick={onReturn}
          >
            {returnLabel}
          </button>
        ) : null}
      </div>
      {showBlockers && !chrome.eligible && chrome.blockers.length > 0 ? (
        <ul className="mt-1 max-h-10 space-y-0.5 overflow-hidden font-mono text-[9px] text-amber-200/75">
          {chrome.blockers.slice(0, 2).map((item) => (
            <li key={item} className="truncate">
              · {item}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
