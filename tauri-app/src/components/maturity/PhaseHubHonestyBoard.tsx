/** Continuum honesty board for Phase Hub (M6/M7). */
import type { MaturityHubPayload } from "@/lib/maturationClient";

export function PhaseHubHonestyBoard({ hub }: { hub: MaturityHubPayload }) {
  if (
    !(
      hub.next_honest_steps?.length ||
      hub.conflation_warnings?.length ||
      hub.honesty
    )
  ) {
    return null;
  }
  return (
    <div className="mt-2 rounded-md border border-violet-500/25 bg-violet-950/20 px-3 py-2">
      <p className="font-mono text-[9px] tracking-[0.14em] text-violet-200/80 uppercase">
        Continuum honesty
      </p>
      <div className="mt-1 flex flex-wrap gap-2 font-mono text-[10px]">
        <span className={hub.birth_exit_exited ? "text-emerald-200/90" : "text-zinc-400"}>
          Birth exit: {hub.birth_exit_exited ? "yes" : "no"}
        </span>
        <span className="text-zinc-600">·</span>
        <span className={hub.ready_for_real ? "text-amber-200/90" : "text-zinc-400"}>
          READY_FOR_REAL: {hub.ready_for_real ? "yes" : "no"}
        </span>
        <span className="text-zinc-600">·</span>
        <span className={hub.real_eligible ? "text-rose-200/90" : "text-zinc-400"}>
          REAL eligible: {hub.real_eligible ? "yes" : "no"}
        </span>
      </div>
      {hub.conflation_warnings && hub.conflation_warnings.length > 0 ? (
        <ul className="mt-1.5 space-y-0.5 font-mono text-[10px] text-amber-200/85">
          {hub.conflation_warnings.slice(0, 4).map((w) => (
            <li key={w}>⚠ {w}</li>
          ))}
        </ul>
      ) : null}
      {hub.next_honest_steps && hub.next_honest_steps.length > 0 ? (
        <ul className="mt-1.5 space-y-0.5 font-mono text-[10px] text-cyan-200/85">
          {hub.next_honest_steps.slice(0, 5).map((s) => (
            <li key={s}>→ {s}</li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
