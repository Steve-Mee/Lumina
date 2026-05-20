import { useEffect, useState } from "react";
import { toast } from "sonner";

import { BirthHoloSlider } from "@/components/birth/BirthHoloSlider";
import { Button } from "@/components/ui/button";
import {
  adjustBirthMaxDays,
  saveBirthSettings,
  type BirthSettingsPayload,
} from "@/lib/birthClient";
import { helpFor } from "@/lib/helpTexts";
import { exceeds_max_real_days_window } from "@/lib/birthSettingsModel";
import { useBirthStore } from "@/store/birthStore";
import { cn } from "@/lib/utils";

interface BirthSettingsPanelProps {
  className?: string;
  initial?: Partial<BirthSettingsPayload>;
}

export function BirthSettingsPanel({ className, initial }: BirthSettingsPanelProps) {
  const status = useBirthStore((s) => s.status);
  const uiPhase = useBirthStore((s) => s.uiPhase);
  const locked = uiPhase === "running";
  const showLockedSummary = locked;
  const [draft, setDraft] = useState<BirthSettingsPayload>({
    training_trades: initial?.training_trades ?? 25000,
    prefer_real_data_only: initial?.prefer_real_data_only ?? true,
    max_real_days: initial?.max_real_days ?? 56,
    allow_minimal_synthetic_fallback: initial?.allow_minimal_synthetic_fallback ?? false,
    require_real_simulator_data: initial?.require_real_simulator_data ?? true,
  });

  useEffect(() => {
    if (initial) {
      setDraft((prior) => ({ ...prior, ...initial }));
    }
  }, [initial]);

  const estimateDays = Math.ceil(Math.max(1, draft.training_trades) / 500);
  const exceedsWindow = exceeds_max_real_days_window(estimateDays, draft.max_real_days);

  return (
    <section className={cn("birth-settings-panel rounded-lg p-1", className)}>
      <div className="mb-3 flex items-center justify-between gap-2">
        <h4 className="font-mono text-[10px] tracking-[0.16em] text-cyan-200/80 uppercase">
          Training settings
        </h4>
        {locked ? (
          <span className="font-mono text-[9px] text-amber-300/90 uppercase">Locked during run</span>
        ) : null}
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
            label="Training trades"
            value={draft.training_trades}
            min={500}
            max={500000}
            step={500}
            format={(v) => v.toLocaleString()}
            disabled={locked}
            onChange={(v) => setDraft((d) => ({ ...d, training_trades: v }))}
          />
          <BirthHoloSlider
            label="Max real days"
            value={draft.max_real_days}
            min={30}
            max={365}
            step={1}
            disabled={locked}
            onChange={(v) => setDraft((d) => ({ ...d, max_real_days: v }))}
          />
          {exceedsWindow ? (
            <p className="text-xs text-amber-200/90">
              Trade volume may exceed max real days window (~{estimateDays}d estimated).
            </p>
          ) : null}
          <div className="birth-holo-chips">
            <label className="birth-holo-chip" title={helpFor("prefer_real_data_only")}>
              <input
                type="checkbox"
                disabled={locked}
                checked={draft.prefer_real_data_only}
                onChange={(e) =>
                  setDraft((d) => ({ ...d, prefer_real_data_only: e.target.checked }))
                }
              />
              Real data only
            </label>
            <label className="birth-holo-chip" title={helpFor("require_real_simulator_data")}>
              <input
                type="checkbox"
                disabled={locked}
                checked={draft.require_real_simulator_data}
                onChange={(e) =>
                  setDraft((d) => ({ ...d, require_real_simulator_data: e.target.checked }))
                }
              />
              Require simulator data
            </label>
            <label className="birth-holo-chip">
              <input
                type="checkbox"
                disabled={locked}
                checked={draft.allow_minimal_synthetic_fallback}
                onChange={(e) =>
                  setDraft((d) => ({ ...d, allow_minimal_synthetic_fallback: e.target.checked }))
                }
              />
              Synthetic fallback
            </label>
          </div>
        </div>
      )}
      {!showLockedSummary ? (
        <div className="mt-4 flex flex-wrap gap-2">
          <Button
            type="button"
            size="sm"
            variant="secondary"
            disabled={locked}
            onClick={() =>
              void saveBirthSettings(draft)
                .then(() => toast.success("Birth settings saved"))
                .catch((e) => toast.error(e instanceof Error ? e.message : "Save failed"))
            }
          >
            Save settings
          </Button>
          {exceedsWindow ? (
            <Button
              type="button"
              size="sm"
              variant="outline"
              disabled={locked}
              onClick={() =>
                void adjustBirthMaxDays()
                  .then((r) => {
                    setDraft((d) => ({ ...d, max_real_days: r.max_real_days }));
                    toast.success(`Max days set to ${r.max_real_days}`);
                  })
                  .catch((e) => toast.error(e instanceof Error ? e.message : "Adjust failed"))
              }
            >
              Adjust max days
            </Button>
          ) : null}
        </div>
      ) : null}
      {status?.progress?.message ? (
        <p className="mt-2 font-mono text-[10px] text-muted-foreground">{status.progress.message}</p>
      ) : null}
    </section>
  );
}
