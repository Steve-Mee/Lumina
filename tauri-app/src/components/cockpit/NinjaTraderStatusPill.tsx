import { useCoreStore, selectNinjaTraderStatus } from "@/store/coreStore";
import { cn } from "@/lib/utils";

interface NinjaTraderStatusPillProps {
  className?: string;
}

export function NinjaTraderStatusPill({ className }: NinjaTraderStatusPillProps) {
  const status = useCoreStore(selectNinjaTraderStatus);

  if (!status) {
    return null;
  }

  const connected = status.connected && status.state === "connected";
  const degraded = status.state === "degraded";
  const safeMode = (status.safe_mode ?? "UNKNOWN").toUpperCase();
  const inSafe = safeMode === "SAFE" || safeMode === "FULL_SAFE";

  let label = "NT8 off";
  if (connected) {
    label = inSafe ? `NT8 ${safeMode}` : "NT8";
  } else if (degraded) {
    label = "NT8 deg";
  }

  const account = status.account ? ` · ${status.account}` : "";
  const target = status.fabric_target ? ` @ ${status.fabric_target}` : "";
  const title = [
    `NinjaTrader/Fabric: ${status.state}`,
    `safe_mode=${safeMode}`,
    status.gateway ? `gateway=${status.gateway}` : "",
    account.trim(),
    target.trim(),
    status.recent_alerts ? `alerts=${status.recent_alerts}` : "",
  ]
    .filter(Boolean)
    .join(" ");

  const tone = connected
    ? inSafe
      ? "border-[color:var(--status-warn-border)] bg-[color:var(--status-warn-bg)] text-[color:var(--status-warn-fg)]"
      : "border-emerald-500/40 bg-emerald-500/10 text-emerald-300"
    : degraded
      ? "border-[color:var(--status-warn-border)] bg-[color:var(--status-warn-bg)] text-[color:var(--status-warn-fg)]"
      : "border-muted-foreground/30 bg-muted/30 text-muted-foreground";

  const dot = connected
    ? inSafe
      ? "bg-[color:var(--status-warn-icon)]"
      : "bg-emerald-400"
    : degraded
      ? "bg-[color:var(--status-warn-icon)]"
      : "bg-muted-foreground/60";

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide",
        tone,
        className,
      )}
      title={title}
    >
      <span className={cn("mr-1.5 inline-block h-1.5 w-1.5 rounded-full", dot)} />
      {label}
      {connected && status.account ? (
        <span className="ml-1 normal-case text-[9px] opacity-80">{status.account}</span>
      ) : null}
    </span>
  );
}
