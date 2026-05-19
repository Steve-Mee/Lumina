import { useState } from "react";
import { Wrench } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { deleteAllTrades, deleteDemoData } from "@/lib/opsClient";
import { resetFirstBoot } from "@/lib/runtimeClient";
import { cn } from "@/lib/utils";

export function AdminPanel({ className }: { className?: string }) {
  const [resetStep, setResetStep] = useState(1);
  const [phrase, setPhrase] = useState("");

  return (
    <div className={cn("space-y-4 overflow-y-auto p-1", className)}>
      <div className="flex items-center gap-2">
        <Wrench className="size-4 text-amber-300/90" />
        <h3 className="font-mono text-[11px] tracking-[0.14em] text-amber-200/90 uppercase">
          Admin Console
        </h3>
      </div>

      <section className="rounded-lg border border-white/10 bg-black/25 p-3 space-y-2">
        <p className="font-mono text-[10px] uppercase text-muted-foreground">Data maintenance</p>
        <div className="flex flex-wrap gap-2">
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
      </section>

      <section className="rounded-lg border border-red-500/30 bg-red-950/15 p-3 space-y-3">
        <p className="font-mono text-[10px] uppercase text-red-200/90">First-boot reset (step {resetStep}/3)</p>
        {resetStep === 1 ? (
          <p className="text-xs text-red-200/80">
            This wipes training artifacts and returns the workspace to post-setup. A backup is created first.
          </p>
        ) : null}
        {resetStep === 2 ? (
          <label className="block text-xs">
            Type <span className="font-mono text-amber-200">RESET FIRST BOOT</span>
            <input
              className="mt-1 w-full rounded border border-white/10 bg-black/40 px-2 py-1 font-mono text-xs"
              value={phrase}
              onChange={(e) => setPhrase(e.target.value)}
            />
          </label>
        ) : null}
        {resetStep === 3 ? (
          <p className="text-xs text-red-200/80">Confirm to execute reset. Engine will be stopped.</p>
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
              onClick={() =>
                void resetFirstBoot(phrase)
                  .then(() => {
                    toast.success("First-boot reset complete");
                    setResetStep(1);
                    setPhrase("");
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
    </div>
  );
}
