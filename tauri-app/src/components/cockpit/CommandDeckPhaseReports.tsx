import { useEffect, useState } from "react";

import { BirthCompletionSummary } from "@/components/birth/BirthCompletionSummary";
import { CharterTile } from "@/components/birth/BirthGenesisDeckPrimitives";
import { BirthPortaledDialog } from "@/components/birth/BirthPortaledDialog";
import { awakeningTilesFromLearned } from "@/components/maturity/phaseHubAwakening";
import { fetchBirthStatusTyped, type BirthStatusPayload } from "@/lib/birthClient";
import {
  fetchAwakeningProgress,
  fetchMaturityHub,
  type MaturityHubPayload,
} from "@/lib/maturationClient";

type ReportKind = "birth" | "awakening";

function ReportButton({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button
      type="button"
      className="genesis-recovery-action-card__btn genesis-recovery-action-card__btn--idle command-deck-ops__report"
      onClick={onClick}
    >
      {label}
    </button>
  );
}

function BirthReportBody({
  status,
  error,
}: {
  status: BirthStatusPayload | null;
  error: string | null;
}) {
  if (error) return <p className="font-mono text-xs text-rose-200">{error}</p>;
  if (!status) return <p className="font-mono text-xs text-white/50">Loading Birth report…</p>;
  const progress = status.progress;
  const message = progress?.message || status.message || "Birth report";
  const trades = progress?.total_trades ?? progress?.trades_done;
  return (
    <div className="flex flex-col gap-3">
      <p className="font-mono text-[11px] leading-snug text-white/70">{message}</p>
      <dl className="grid grid-cols-2 gap-2 font-mono text-[10px] text-white/60">
        <div>
          <dt className="uppercase tracking-wide text-white/35">Trades</dt>
          <dd className="text-cyan-100/90">{trades == null ? "—" : String(trades)}</dd>
        </div>
        <div>
          <dt className="uppercase tracking-wide text-white/35">Stage</dt>
          <dd className="text-cyan-100/90">{progress?.stage_display_name || progress?.stage || "—"}</dd>
        </div>
        <div>
          <dt className="uppercase tracking-wide text-white/35">Occupancy</dt>
          <dd className="text-cyan-100/90">
            {progress?.occupancy == null ? "—" : Number(progress.occupancy).toFixed(3)}
          </dd>
        </div>
        <div>
          <dt className="uppercase tracking-wide text-white/35">Mean R</dt>
          <dd className="text-cyan-100/90">
            {progress?.mean_r == null ? "—" : Number(progress.mean_r).toFixed(3)}
          </dd>
        </div>
      </dl>
      <BirthCompletionSummary status={status} className="!p-3" />
    </div>
  );
}

function AwakeningReportBody({
  hub,
  note,
  error,
}: {
  hub: MaturityHubPayload | null;
  note: string | null;
  error: string | null;
}) {
  if (error) return <p className="font-mono text-xs text-rose-200">{error}</p>;
  if (!hub) return <p className="font-mono text-xs text-white/50">Loading Awakening report…</p>;
  const record = hub.phase_records.awakening?.learned ?? {};
  const learned =
    hub.focus_phase === "awakening" ? { ...record, ...hub.focus_learned } : record;
  const started =
    hub.completed_phases.includes("awakening") ||
    hub.phase_records.awakening != null ||
    hub.active_phase === "awakening";
  if (!started) {
    return (
      <p className="font-mono text-[11px] leading-snug text-white/70">
        Awakening has not started. The Birth plant is frozen. Open the Awakening start to begin.
      </p>
    );
  }
  const tiles = awakeningTilesFromLearned(learned);
  return (
    <div className="flex flex-col gap-3">
      {note ? <p className="font-mono text-[11px] leading-snug text-white/70">{note}</p> : null}
      <div className="genesis-charter-tile-grid">
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
  );
}

export function CommandDeckPhaseReports() {
  const [kind, setKind] = useState<ReportKind | null>(null);
  const [birth, setBirth] = useState<BirthStatusPayload | null>(null);
  const [hub, setHub] = useState<MaturityHubPayload | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!kind) return;
    let cancelled = false;
    setError(null);
    setBirth(null);
    setHub(null);
    setNote(null);
    const load = async () => {
      try {
        if (kind === "birth") {
          const status = await fetchBirthStatusTyped();
          if (!cancelled) setBirth(status);
          return;
        }
        const [hubPayload, progress] = await Promise.all([
          fetchMaturityHub(),
          fetchAwakeningProgress().catch(() => null),
        ]);
        if (cancelled) return;
        setHub(hubPayload);
        const progressNote =
          typeof progress?.progress?.message === "string"
            ? progress.progress.message
            : hubPayload.progress_message;
        setNote(progressNote ?? null);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Report unavailable");
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, [kind]);

  return (
    <>
      <ReportButton label="Birth report" onClick={() => setKind("birth")} />
      <ReportButton label="Awakening report" onClick={() => setKind("awakening")} />
      <BirthPortaledDialog
        open={kind != null}
        onOpenChange={(open) => {
          if (!open) setKind(null);
        }}
        title={kind === "awakening" ? "Awakening report" : "Birth report"}
        description={
          kind === "awakening" ? (
            <AwakeningReportBody hub={hub} note={note} error={error} />
          ) : (
            <BirthReportBody status={birth} error={error} />
          )
        }
        panelClassName="birth-portaled-dialog__panel--report"
        footer={
          <button
            type="button"
            className="genesis-recovery-action-card__btn genesis-recovery-action-card__btn--idle"
            onClick={() => setKind(null)}
          >
            Close
          </button>
        }
      />
    </>
  );
}
