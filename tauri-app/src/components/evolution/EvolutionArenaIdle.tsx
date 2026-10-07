import { BirthOrganismVisual } from "@/components/birth/BirthOrganismVisual";
import { StatusChip } from "@/components/birth/BirthGenesisDeckPrimitives";
import { modeTitleClass } from "@/lib/modePresentation";
import { cn } from "@/lib/utils";
import type { TradingMode } from "@/store/coreStore";

interface EvolutionArenaIdleProps {
  mode: TradingMode;
  onRefresh: () => void;
}

export function EvolutionArenaIdle({ mode, onRefresh }: EvolutionArenaIdleProps) {
  return (
    <div className="command-deck-ops__arena-idle">
      <BirthOrganismVisual className="size-28 opacity-80 md:size-36" />
      <p className={cn("risk-envelope-panel__toolbar-title", modeTitleClass(mode))}>
        Evolution arena
      </p>
      <p className="max-w-sm font-mono text-[11px] leading-relaxed tracking-wide text-white/45">
        No harvested lineage on this deck. Strategies appear here after Birth completes and
        mutation proposals are written.
      </p>
      <div className="command-deck-ops__arena-strip" role="status" aria-label="Arena status">
        <StatusChip label="TREE IDLE" state="idle" tip="No harvested evolution tree." />
        <StatusChip label="PENDING 0" state="idle" tip="No mutation proposals in the queue." />
        <StatusChip label="CHAMPION —" state="idle" tip="No champion DNA planted on this deck." />
      </div>
      <button
        type="button"
        className="genesis-recovery-action-card__btn genesis-recovery-action-card__btn--accent command-deck-ops__organ-btn"
        onClick={onRefresh}
      >
        Refresh
      </button>
    </div>
  );
}
