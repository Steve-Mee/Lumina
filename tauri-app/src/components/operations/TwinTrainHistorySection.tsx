import { DeckSection } from "@/components/cockpit/DeckSection";
import { formatTwinNum, type TwinLabelRecord } from "@/lib/twinClient";

export interface TwinTrainHistorySectionProps {
  labels: TwinLabelRecord[];
}

export function TwinTrainHistorySection({ labels }: TwinTrainHistorySectionProps) {
  return (
    <DeckSection title="Label history (local audit)">
      {labels.length === 0 ? (
        <p className="text-xs text-muted-foreground">No Steve labels yet.</p>
      ) : (
        <ul className="space-y-1.5">
          {labels.map((row, idx) => (
            <li
              key={`${row.timestamp}-${row.context_dna_hash}-${idx}`}
              className="rounded-md border border-border/40 px-2 py-1.5 font-mono text-[10px] text-muted-foreground"
            >
              <div className="flex flex-wrap gap-x-2">
                <span className="text-violet-200/90">{row.steve_antwoord}</span>
                <span>
                  {row.context_dna_hash.length > 14
                    ? `${row.context_dna_hash.slice(0, 12)}…`
                    : row.context_dna_hash}
                </span>
                <span>conf {formatTwinNum(row.confidence_score, 2)}</span>
                <span>{row.timestamp.slice(0, 19)}</span>
              </div>
              {row.vraag ? (
                <p className="mt-0.5 line-clamp-2 text-[9px] text-muted-foreground/80">
                  {row.vraag}
                </p>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </DeckSection>
  );
}
