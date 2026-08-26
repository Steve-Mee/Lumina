/** Col 3 diagnostic results only (actions live in mission column). */
import { StatusIcon } from "@/components/onboarding/steps/CredentialsVaultPrimitives";
import type { FabricConnectionTestReport, FabricHealResult } from "@/lib/setupClient";
import { distressPanelClass, warnOverlayBodyClass, warnOverlayTitleClass } from "@/lib/modePresentation";
import { cn } from "@/lib/utils";

function liveBadgeClass(level: string | null | undefined): string {
  const l = String(level || "").toUpperCase();
  if (l === "GREEN")
    return "bg-emerald-500/15 text-emerald-200 ring-1 ring-emerald-400/35";
  if (l === "AMBER" || l === "RESTARTING")
    return "bg-amber-500/15 text-amber-100 ring-1 ring-amber-400/35";
  if (l === "RED") return "bg-red-500/15 text-red-100 ring-1 ring-red-400/35";
  return "bg-white/5 text-white/40 ring-1 ring-white/10";
}

export function CredentialsVaultDiagnosticResults({
  fabricReport,
  fabricGreen,
  fabricReadyForSeal = false,
  liveLevel = null,
  fabricCertified,
  healResult,
  testingFabric,
  repairingFabric,
}: {
  fabricReport: FabricConnectionTestReport | null;
  /** Live GREEN only. */
  fabricGreen: boolean;
  fabricReadyForSeal?: boolean;
  liveLevel?: string | null;
  fabricCertified: boolean;
  healResult: FabricHealResult | null;
  testingFabric: boolean;
  repairingFabric: boolean;
}) {
  if (testingFabric) {
    return (
      <p className="credentials-vault-detail-empty">Probing Fabric channels…</p>
    );
  }
  if (repairingFabric) {
    return (
      <p className="credentials-vault-detail-empty">
        Repairing NinjaTrader link… the terminal may restart.
      </p>
    );
  }

  const hasHeal = Boolean(healResult?.steps?.length);
  const hasReport = Boolean(fabricReport);
  const hasProof = fabricCertified || fabricReport?.overall === "green";
  const level = String(liveLevel || "").toUpperCase() || null;
  const showBlock = hasHeal || hasReport || hasProof || Boolean(level);

  if (!showBlock) {
    return (
      <p className="credentials-vault-detail-empty">
        Run <strong className="text-white/70">Test connection</strong> or{" "}
        <strong className="text-white/70">Repair</strong> on the left. Results and
        guidance appear here.
      </p>
    );
  }

  return (
    <div className="credentials-vault-channel-panel">
      <div className="flex flex-wrap items-center gap-2">
        <span
          className={cn(
            "rounded-full px-2.5 py-0.5 font-mono text-[0.55rem] font-bold tracking-wider uppercase",
            liveBadgeClass(level || (fabricGreen ? "GREEN" : null)),
          )}
          title="Live host + Brain session (not paper certificate)"
        >
          live {level ? level.toLowerCase() : fabricGreen ? "green" : "—"}
        </span>
        {hasProof ? (
          <span
            className="rounded-full bg-cyan-500/10 px-2.5 py-0.5 font-mono text-[0.55rem] font-bold tracking-wider text-cyan-100/90 uppercase ring-1 ring-cyan-400/30"
            title="Dual-plane diagnostic certificate"
          >
            proof{" "}
            {fabricReport?.checks?.length
              ? `${fabricReport.checks.filter((c) => c.status === "pass").length}/${fabricReport.checks.length}`
              : "ok"}
          </span>
        ) : fabricReport ? (
          <span
            className={cn(
              "rounded-full px-2.5 py-0.5 font-mono text-[0.55rem] font-bold tracking-wider uppercase",
              fabricReport.overall === "amber" &&
                "bg-amber-500/15 text-amber-100 ring-1 ring-amber-400/35",
              fabricReport.overall === "red" &&
                "bg-red-500/15 text-red-100 ring-1 ring-red-400/35",
              fabricReport.overall === "green" &&
                "bg-cyan-500/10 text-cyan-100 ring-1 ring-cyan-400/30",
            )}
          >
            proof {fabricReport.overall}
          </span>
        ) : null}
        {fabricReport ? (
          <span className="font-mono text-[0.55rem] tracking-wide text-white/35">
            {fabricReport.target} · {fabricReport.duration_ms}ms
          </span>
        ) : null}
      </div>

      {healResult?.needs_user?.length ? (
        <div className={cn("rounded-md border px-2.5 py-2", distressPanelClass("warn"))}>
          <p className={cn("font-mono text-[0.55rem] tracking-wider uppercase", warnOverlayTitleClass())}>
            {healResult.needs_user[0].title}
          </p>
          <p className={cn("mt-1 text-[11px] leading-snug", warnOverlayBodyClass())}>
            {healResult.needs_user[0].body}
          </p>
        </div>
      ) : null}

      {healResult?.steps?.length ? (
        <ul className="credentials-vault-diag__list">
          {healResult.steps.map((s) => (
            <li key={s.id} className="credentials-vault-diag__row">
              <StatusIcon
                status={
                  s.status === "pass"
                    ? "pass"
                    : s.status === "warn" || s.status === "skip"
                      ? "warn"
                      : "fail"
                }
              />
              <div className="min-w-0 flex-1">
                <p className="credentials-vault-diag__row-title">{s.title}</p>
                <p className="credentials-vault-diag__row-msg">
                  {s.user_message || s.message}
                </p>
              </div>
            </li>
          ))}
        </ul>
      ) : null}

      {fabricReport ? (
        <ul className="credentials-vault-diag__list">
          {fabricReport.checks.map((c) => (
            <li key={c.id} className="credentials-vault-diag__row">
              <StatusIcon status={c.status} />
              <div className="min-w-0 flex-1">
                <p className="credentials-vault-diag__row-title">{c.title}</p>
                <p className="credentials-vault-diag__row-msg">{c.message}</p>
              </div>
            </li>
          ))}
        </ul>
      ) : null}

      {hasProof && !fabricReport && !healResult?.steps?.length ? (
        <p className="text-[12px] leading-snug text-white/50">
          Dual-plane proof on file
          {fabricReadyForSeal ? " · host ready for Genesis" : " · wait for live host"}.
          Re-run Test after token change or NinjaTrader update.
        </p>
      ) : null}
    </div>
  );
}
