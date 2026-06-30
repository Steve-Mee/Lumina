import { useEffect, useState } from "react";

import { toast } from "sonner";



import { BirthHoloSlider } from "@/components/birth/BirthHoloSlider";

import { Button } from "@/components/ui/button";

import {

  saveBirthSettings,

  type BirthSettingsPayload,

} from "@/lib/birthClient";

import { useBirthStore } from "@/store/birthStore";

import { cn } from "@/lib/utils";



interface BirthSettingsPanelProps {

  className?: string;

  initial?: Partial<BirthSettingsPayload>;

}



export function BirthSettingsPanel({ className, initial }: BirthSettingsPanelProps) {

  const status = useBirthStore((s) => s.status);

  const uiPhase = useBirthStore((s) => s.uiPhase);

  const needsAttention = Boolean(status?.progress?.needs_attention);

  const locked = uiPhase === "running" && !needsAttention;

  const showLockedSummary = locked || !needsAttention;

  const [draft, setDraft] = useState<BirthSettingsPayload>({

    training_trades: initial?.training_trades ?? 25000,

    prefer_real_data_only: initial?.prefer_real_data_only ?? true,

    max_real_days: initial?.max_real_days ?? 56,

    allow_minimal_synthetic_fallback: initial?.allow_minimal_synthetic_fallback ?? false,

    require_real_simulator_data: initial?.require_real_simulator_data ?? true,

    stage1_winrate_pass_threshold: initial?.stage1_winrate_pass_threshold ?? 0.45,

  });



  useEffect(() => {

    if (initial) {

      setDraft((prior) => ({ ...prior, ...initial }));

    }

  }, [initial]);



  const gatePct = Math.round((draft.stage1_winrate_pass_threshold ?? 0.45) * 100);

  const gateWarning =

    gatePct >= 45

      ? { tone: "ok" as const, text: "Recommended — aligns with certificate OOS expectations." }

      : gatePct >= 38

        ? {

            tone: "warn" as const,

            text: "Birth can proceed; expect stronger post-birth Evolution Proof.",

          }

        : {

            tone: "danger" as const,

            text: "Pipeline validation only; REAL blocked until Evolution Proof + OOS ≥48%.",

          };



  return (

    <section className={cn("birth-settings-panel rounded-lg p-1", className)}>

      <div className="mb-3 flex items-center justify-between gap-2">

        <h4 className="font-mono text-[10px] tracking-[0.16em] text-cyan-200/80 uppercase">

          Training settings

        </h4>

        {locked ? (

          <span className="font-mono text-[9px] text-amber-300/90 uppercase">Locked during run</span>

        ) : needsAttention ? (

          <span className="font-mono text-[9px] text-orange-300/90 uppercase">

            Unlocked — winrate retry override

          </span>

        ) : (

          <span className="font-mono text-[9px] text-muted-foreground uppercase">

            Genesis contract (read-only)

          </span>

        )}

      </div>

      {showLockedSummary ? (

        <dl className="grid gap-2 text-xs text-muted-foreground sm:grid-cols-2">

          <div>

            <dt className="font-mono text-[9px] uppercase">Training trades</dt>

            <dd className="font-mono text-cyan-100">{draft.training_trades.toLocaleString()}</dd>

          </div>

          <div>

            <dt className="font-mono text-[9px] uppercase">Max real days</dt>

            <dd className="font-mono text-cyan-100">{draft.max_real_days}</dd>

          </div>

          <div>

            <dt className="font-mono text-[9px] uppercase">Stage 1 winrate gate</dt>

            <dd className="font-mono text-cyan-100">{gatePct}%</dd>

          </div>

          <div className="sm:col-span-2">

            <dt className="font-mono text-[9px] uppercase">Data policy</dt>

            <dd className="text-foreground/90">

              {draft.prefer_real_data_only ? "Real data preferred" : "Synthetic allowed"}

              {draft.require_real_simulator_data ? " · Simulator data required" : ""}

            </dd>

          </div>

        </dl>

      ) : (

        <div className="space-y-1 text-sm">

          <BirthHoloSlider

            label="Stage 1 winrate gate"

            value={gatePct}

            min={35}

            max={45}

            step={1}

            format={(v) => `${v}%`}

            disabled={locked}

            onChange={(v) =>

              setDraft((d) => ({ ...d, stage1_winrate_pass_threshold: v / 100 }))

            }

          />

          <p

            className={cn(

              "text-xs",

              gateWarning.tone === "ok"

                ? "text-emerald-200/90"

                : gateWarning.tone === "warn"

                  ? "text-amber-200/90"

                  : "text-orange-200/90",

            )}

          >

            {gateWarning.text}

          </p>

        </div>

      )}

      {!needsAttention ? (

        <p className="mt-2 font-mono text-[10px] text-muted-foreground/80">

          Edit genesis contract on the Neural Genesis deck before ACTIVATE BIRTH.

        </p>

      ) : (

        <p className="mb-2 font-mono text-[10px] text-muted-foreground/80">

          Genesis contract is primary. Adjust winrate here only during retry when birth needs

          attention.

        </p>

      )}

      {needsAttention && !locked ? (

        <div className="mt-4 flex flex-wrap gap-2">

          <Button

            type="button"

            size="sm"

            variant="secondary"

            onClick={() =>

              void saveBirthSettings(draft)

                .then(() => toast.success("Birth settings saved"))

                .catch((e) => toast.error(e instanceof Error ? e.message : "Save failed"))

            }

          >

            Save winrate override

          </Button>

        </div>

      ) : null}

      {status?.progress?.message ? (

        <p className="mt-2 font-mono text-[10px] text-muted-foreground">{status.progress.message}</p>

      ) : null}

    </section>

  );

}

