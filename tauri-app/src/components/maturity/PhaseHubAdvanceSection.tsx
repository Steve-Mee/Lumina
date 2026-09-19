/** After-phase advance preference — not a Start Awakening gate. */
import { toast } from "sonner";

import { RecoveryActionCard } from "@/components/birth/BirthGenesisDeckPrimitives";
import { Button } from "@/components/ui/button";
import {
  type AdvanceMode,
  type MaturityHubPayload,
  postRefreshTelegramAdvance,
} from "@/lib/maturationClient";
import { cn } from "@/lib/utils";
import { ADVANCE_MODE_HELP, ADVANCE_OPTIONS } from "@/components/maturity/phaseHubFormat";

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
  const selected = hub?.advance_mode ?? "manual";
  return (
    <section className="phase-hub-advance shrink-0">
      <p className="risk-envelope-field-label">After this phase</p>
      <p className="mt-0.5 font-mono text-[10px] leading-snug text-muted-foreground">
        {ADVANCE_MODE_HELP}
      </p>
      <div className="genesis-recovery-action-grid genesis-recovery-action-grid--3 mt-2">
        {ADVANCE_OPTIONS.map((opt) => {
          const on = selected === opt.id;
          return (
            <RecoveryActionCard
              key={opt.id}
              label={opt.label}
              tip={opt.tip}
              hint={opt.hint}
              tone={on ? "accent" : "default"}
            >
              <button
                type="button"
                disabled={busy || on}
                onClick={() => void onSetMode(opt.id)}
                className={cn(
                  "genesis-recovery-action-card__btn",
                  on
                    ? "genesis-recovery-action-card__btn--accent"
                    : "genesis-recovery-action-card__btn--idle",
                )}
              >
                <span>{on ? "Selected" : opt.action}</span>
              </button>
            </RecoveryActionCard>
          );
        })}
      </div>
      {hub?.pending_advance ? (
        <div className="mt-2 space-y-1.5">
          <p className="font-mono text-[10px] text-amber-200/90">
            Telegram pending: {hub.pending_advance.from} → {hub.pending_advance.to}.
            {hub.pending_advance.expired
              ? " Token expired — refresh for a new one."
              : " Reply YES on Telegram, or paste the token here."}
          </p>
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
                    toast.success(
                      r.expires_at
                        ? `New token issued (expires ${r.expires_at})`
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
      ) : hub?.telegram_advance?.mode_is_telegram && hub.telegram_advance.reissue_available ? (
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <p className="font-mono text-[10px] text-muted-foreground">
            Telegram mode — issue a token for the next phase.
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
