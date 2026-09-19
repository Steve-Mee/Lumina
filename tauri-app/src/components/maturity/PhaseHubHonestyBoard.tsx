/** Continuum honesty strip for Phase Hub (M6/M7). */
import { StatusChip } from "@/components/birth/BirthGenesisDeckPrimitives";
import type { MaturityHubPayload } from "@/lib/maturationClient";
import type { TwinReadiness } from "@/lib/twinClient";

export function PhaseHubHonestyBoard({
  hub,
  twinReady,
}: {
  hub: MaturityHubPayload;
  twinReady?: TwinReadiness | null;
}) {
  const warning = hub.conflation_warnings?.[0] ?? null;
  return (
    <div className="phase-hub-honesty-strip shrink-0 px-1">
      <div className="flex flex-wrap items-center gap-1.5">
        {twinReady ? (
          <StatusChip
            label={
              twinReady.birth_ready
                ? "Twin Birth-ready"
                : `Twin ${Number(twinReady.base_training_completion_pct ?? 0).toFixed(0)}%`
            }
            state={twinReady.birth_ready ? "ok" : "warn"}
            tip="Twin sole-auto stays fail-closed until base curriculum is complete."
          />
        ) : null}
        <StatusChip
          label={`Birth exit ${hub.birth_exit_exited ? "yes" : "no"}`}
          state={hub.birth_exit_exited ? "ok" : "warn"}
          tip="Five foundation v2 receipts + fitness. Not a certificate. Not REAL."
        />
        <StatusChip
          label={`READY_FOR_REAL ${hub.ready_for_real ? "yes" : "no"}`}
          state={hub.ready_for_real ? "ok" : "idle"}
          tip="Apprenticeship multi-day SIM green streak — not Birth exit."
        />
        <StatusChip
          label={`REAL ${hub.real_eligible ? "yes" : "no"}`}
          state={hub.real_eligible ? "warn" : "idle"}
          tip="Promotion + Perfect Birth + human approve-real. Fail-closed."
        />
      </div>
      {warning ? (
        <p className="mt-1 truncate font-mono text-[10px] text-amber-200/80" title={warning}>
          {warning}
        </p>
      ) : null}
    </div>
  );
}
