import { useCallback, useEffect, useState } from "react";
import { Wrench } from "lucide-react";
import { toast } from "sonner";

import { DeckMetricTile } from "@/components/cockpit/DeckMetricTile";
import { PhaseResetPanel } from "@/components/operations/PhaseResetPanel";
import { Button } from "@/components/ui/button";
import { deleteAllTrades, deleteDemoData, fetchAdminSetupSnapshot } from "@/lib/opsClient";
import { resetFirstBoot } from "@/lib/runtimeClient";
import { modeTextTier2Class, modeTitleClass, utilityCodeBlockClass, utilityFieldInputClass } from "@/lib/modePresentation";
import { selectCurrentMode, useCoreStore } from "@/store/coreStore";
import { cn } from "@/lib/utils";

export function AdminPanel({ className }: { className?: string }) {
  const operatorMode = useCoreStore(selectCurrentMode);
  const [resetStep, setResetStep] = useState(1);
  const [phrase, setPhrase] = useState("");
  const [snapshot, setSnapshot] = useState<Record<string, unknown> | null>(null);

  const refreshSnapshot = useCallback(async () => {
    try {
      setSnapshot(await fetchAdminSetupSnapshot());
    } catch {
      setSnapshot(null);
    }
  }, []);

  useEffect(() => {
    void refreshSnapshot();
  }, [refreshSnapshot]);

  const manifest = (snapshot?.reset_manifest ?? {}) as Record<string, string[]>;

  return (
    <div className={cn("phase-reset-admin flex h-full min-h-0 flex-1 flex-col", className)}>
      <div className="flex shrink-0 items-center gap-2">
        <Wrench className={cn("size-3.5", modeTitleClass(operatorMode))} />
        <h3 className={cn("deck-title text-[11px] tracking-[0.14em]", modeTextTier2Class(operatorMode))}>
          Reset & maintenance
        </h3>
      </div>

      <PhaseResetPanel />

      <div className="phase-reset-admin__tools">
        <details className="phase-reset-admin__fold">
          <summary>Setup snapshot</summary>
          <div className="mt-2 grid grid-cols-2 gap-2">
            <DeckMetricTile
              label="Setup"
              value={snapshot?.setup_completed ? "complete" : "incomplete"}
            />
            <DeckMetricTile label="Mode" value={String(snapshot?.runtime_mode ?? "—")} />
            <div className="col-span-2">
              <DeckMetricTile
                label="First-boot trades"
                value={String(snapshot?.configured_first_boot_trades ?? "—")}
              />
            </div>
          </div>
          <details className="mt-2 rounded-md lumina-surface-muted p-2">
            <summary className="cursor-pointer text-muted-foreground">Config JSON</summary>
            <pre className={utilityCodeBlockClass()}>
              {JSON.stringify(snapshot?.config_yaml_subset ?? {}, null, 2)}
            </pre>
          </details>
        </details>

        <details className="phase-reset-admin__fold">
          <summary>Data maintenance</summary>
          <div className="mt-2 flex flex-wrap gap-2">
            <Button
              type="button"
              size="sm"
              variant="secondary"
              onClick={() =>
                void deleteAllTrades()
                  .then((r) => toast.success(`Deleted ${r.deleted} trades`))
                  .catch((e) => toast.error(e instanceof Error ? e.message : "Delete failed"))
              }
            >
              Delete all trades
            </Button>
            <Button
              type="button"
              size="sm"
              variant="secondary"
              onClick={() =>
                void deleteDemoData()
                  .then((r) => toast.success(`Demo cleanup: ${JSON.stringify(r)}`))
                  .catch((e) => toast.error(e instanceof Error ? e.message : "Delete failed"))
              }
            >
              Delete demo data
            </Button>
          </div>
        </details>

        <details className="phase-reset-admin__fold">
          <summary>First-boot reset (step {resetStep}/3)</summary>
          <section className="mt-2 space-y-2">
            {resetStep === 1 ? (
              <p className="text-xs text-red-200/80">
                This wipes training artifacts and returns the workspace to post-setup. A backup is
                created first.
              </p>
            ) : null}
            {resetStep === 2 ? (
              <div className="grid gap-3 text-[11px] text-muted-foreground sm:grid-cols-2">
                <div>
                  <p className="mb-1 font-mono text-[9px] uppercase text-red-200/80">Will be removed</p>
                  <ul className="space-y-0.5 font-mono">
                    {(manifest.wipe_directories ?? []).map((item) => (
                      <li key={item}>• {item}</li>
                    ))}
                    {(manifest.delete_targets ?? []).slice(0, 8).map((item) => (
                      <li key={item}>• {item}</li>
                    ))}
                  </ul>
                </div>
                <div>
                  <p className="mb-1 font-mono text-[9px] uppercase text-emerald-200/80">Preserved</p>
                  <ul className="space-y-0.5 font-mono">
                    <li>• config.yaml</li>
                    <li>• .env</li>
                    {(manifest.preserved_state_files ?? []).map((item) => (
                      <li key={item}>• state/{item}</li>
                    ))}
                  </ul>
                </div>
              </div>
            ) : null}
            {resetStep === 3 ? (
              <label className="block text-xs">
                Type <span className="font-mono text-[var(--status-warn-fg)]">RESET FIRST BOOT</span>
                <input
                  className={utilityFieldInputClass()}
                  value={phrase}
                  onChange={(e) => setPhrase(e.target.value)}
                />
              </label>
            ) : null}
            <div className="flex gap-2">
              {resetStep < 3 ? (
                <Button type="button" size="sm" variant="destructive" onClick={() => setResetStep((s) => s + 1)}>
                  Continue
                </Button>
              ) : (
                <Button
                  type="button"
                  size="sm"
                  variant="destructive"
                  disabled={phrase.trim() !== "RESET FIRST BOOT"}
                  onClick={() =>
                    void resetFirstBoot(phrase)
                      .then(() => {
                        toast.success("First-boot reset complete");
                        setResetStep(1);
                        setPhrase("");
                        void refreshSnapshot();
                      })
                      .catch((e) => toast.error(e instanceof Error ? e.message : "Reset failed"))
                  }
                >
                  Execute reset
                </Button>
              )}
              {resetStep > 1 ? (
                <Button type="button" size="sm" variant="ghost" onClick={() => setResetStep(1)}>
                  Cancel
                </Button>
              ) : null}
            </div>
          </section>
        </details>
      </div>
    </div>
  );
}
