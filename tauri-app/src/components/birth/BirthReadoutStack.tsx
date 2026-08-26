import { CONDITION_VALUE_TEXT_CLASS, type ConditionTone } from "@/lib/conditionTone";
import { cn } from "@/lib/utils";

export interface BirthReadoutStat {
  key: string;
  value: string;
  note?: string;
}

/** Compact Life / Roll / Windows instrument stack — keys left, values right. */
export function BirthReadoutStack({
  stats,
  tone = "default",
}: {
  stats: BirthReadoutStat[];
  tone?: ConditionTone;
}) {
  if (stats.length === 0) return null;
  return (
    <dl className="birth-readout-stack">
      {stats.map((stat) => (
        <div key={stat.key} className="birth-readout-stack__row">
          <dt className="birth-readout-stack__key">{stat.key}</dt>
          <dd
            className={cn(
              "birth-readout-stack__val tabular-nums",
              CONDITION_VALUE_TEXT_CLASS[tone],
            )}
          >
            <span>{stat.value}</span>
            {stat.note ? (
              <span className="birth-readout-stack__note">{stat.note}</span>
            ) : null}
          </dd>
        </div>
      ))}
    </dl>
  );
}
