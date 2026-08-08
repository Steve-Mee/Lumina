/** Advance mode + Telegram TTL controls for Phase Hub (Tauri UI god split). */
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  type AdvanceMode,
  type MaturityHubPayload,
  postRefreshTelegramAdvance,
} from "@/lib/maturationClient";
import { cn } from "@/lib/utils";
import { ADVANCE_OPTIONS, formatRemainingSec } from "@/components/maturity/phaseHubFormat";

export interface PhaseHubAdvanceSectionProps {
  hub: MaturityHubPayload | null;
  busy: boolean;
  telegramToken: string;
  setTelegramToken: (v: string) => void;
  onSetMode: (mode: AdvanceMode) => void | Promise<void>;
  onAdvance: () => void | Promise<void>;
  setBusy: (v: boolean) => void;
  reload: () => Promise<void>;
}

export function PhaseHubAdvanceSection({
  hub,
  busy,
  telegramToken,
  setTelegramToken,
  onSetMode,
  onAdvance,
  setBusy,
  reload,
}: PhaseHubAdvanceSectionProps) {
  return (
    <section className="rounded-xl border border-border/50 bg-muted/10 p-4 md:col-span-2">

            <h2 className="font-mono text-[10px] tracking-[0.16em] text-cyan-200/90 uppercase">
              Auto evolve preference
            </h2>
            <p className="mt-1 font-mono text-[10px] text-muted-foreground">
              How phases follow each other after completion. REAL always needs explicit human
              approval.
            </p>
            <div className="mt-3 grid gap-2 sm:grid-cols-3">
              {ADVANCE_OPTIONS.map((opt) => {
                const selected = hub?.advance_mode === opt.id;
                return (
                  <button
                    key={opt.id}
                    type="button"
                    disabled={busy}
                    onClick={() => void onSetMode(opt.id)}
                    className={cn(
                      "rounded-lg border px-3 py-3 text-left transition",
                      selected
                        ? "border-cyan-400/60 bg-cyan-950/40 shadow-[0_0_20px_rgba(34,211,238,0.12)]"
                        : "border-border/40 bg-black/20 hover:border-border/70",
                    )}
                  >
                    <span className="block font-mono text-xs font-medium text-foreground">
                      {opt.label}
                      {selected ? " ✓" : ""}
                    </span>
                    <span className="mt-1 block font-mono text-[10px] text-muted-foreground">
                      {opt.hint}
                    </span>
                  </button>
                );
              })}
            </div>
            {hub?.pending_advance ? (
              <div className="mt-3 space-y-2">
                <p className="font-mono text-[10px] text-amber-200/90">
                  Telegram pending: {hub.pending_advance.from} → {hub.pending_advance.to}.
                  {hub.pending_advance.expired
                    ? " Token expired — refresh for a new one."
                    : " Reply YES on Telegram, or paste the token here."}
                </p>
                <div className="flex flex-wrap items-center gap-3 font-mono text-[10px] text-muted-foreground">
                  {hub.pending_advance.status ? (
                    <span
                      className={
                        hub.pending_advance.expired
                          ? "text-rose-300/90"
                          : "text-emerald-300/90"
                      }
                    >
                      status: {hub.pending_advance.status}
                    </span>
                  ) : null}
                  {typeof hub.pending_advance.remaining_sec === "number" ? (
                    <span
                      className={
                        hub.pending_advance.remaining_sec <= 0
                          ? "text-rose-300/90"
                          : hub.pending_advance.remaining_sec < 600
                            ? "text-amber-300/90"
                            : "text-cyan-200/90"
                      }
                    >
                      remaining: {formatRemainingSec(hub.pending_advance.remaining_sec)}
                      {hub.pending_advance.remaining_sec > 0
                        ? ` (${hub.pending_advance.remaining_sec}s)`
                        : ""}
                    </span>
                  ) : null}
                  {hub.pending_advance.expires_at ? (
                    <span>expires {hub.pending_advance.expires_at}</span>
                  ) : null}
                  {hub.telegram_advance?.configured_ttl_sec ? (
                    <span>
                      TTL config:{" "}
                      {formatRemainingSec(hub.telegram_advance.configured_ttl_sec) ||
                        `${hub.telegram_advance.configured_ttl_sec}s`}
                    </span>
                  ) : null}
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <input
                    type="text"
                    value={telegramToken}
                    onChange={(e) => setTelegramToken(e.target.value)}
                    placeholder="Telegram advance token"
                    className="min-w-[12rem] flex-1 rounded border border-border/50 bg-black/40 px-2 py-1.5 font-mono text-[11px] text-foreground"
                    disabled={Boolean(hub.pending_advance.expired)}
                  />
                  <Button
                    type="button"
                    size="sm"
                    disabled={busy || !telegramToken.trim() || Boolean(hub.pending_advance.expired)}
                    onClick={() => void onAdvance()}
                  >
                    Confirm token
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    disabled={busy}
                    onClick={() => {
                      setBusy(true);
                      void postRefreshTelegramAdvance()
                        .then(async (r) => {
                          const rem =
                            typeof r.remaining_sec === "number"
                              ? formatRemainingSec(r.remaining_sec)
                              : "";
                          toast.success(
                            r.expires_at
                              ? `New token issued (expires ${r.expires_at}${rem ? `, ~${rem} left` : ""})`
                              : "New advance token issued — check Telegram",
                          );
                          await reload();
                        })
                        .catch((err) =>
                          toast.error(err instanceof Error ? err.message : "Refresh failed"),
                        )
                        .finally(() => setBusy(false));
                    }}
                  >
                    Refresh token
                  </Button>
                </div>
              </div>
            ) : hub?.telegram_advance?.mode_is_telegram &&
              hub.telegram_advance.reissue_available ? (
              <div className="mt-3 flex flex-wrap items-center gap-2">
                <p className="font-mono text-[10px] text-muted-foreground">
                  Telegram mode active — no pending token. Issue one for the next phase.
                </p>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  disabled={busy}
                  onClick={() => {
                    setBusy(true);
                    void postRefreshTelegramAdvance()
                      .then(async (r) => {
                        toast.success(
                          r.expires_at
                            ? `Advance token issued (expires ${r.expires_at})`
                            : "Advance token issued — check Telegram",
                        );
                        await reload();
                      })
                      .catch((err) =>
                        toast.error(err instanceof Error ? err.message : "Refresh failed"),
                      )
                      .finally(() => setBusy(false));
                  }}
                >
                  Issue Telegram token
                </Button>
              </div>
            ) : null}

    </section>
  );
}
