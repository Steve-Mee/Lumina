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
  const label = connected ? "NT8" : "NT8 off";
  const account = status.account ? ` · ${status.account}` : "";

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide",
        connected
          ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-300"
          : "border-muted-foreground/30 bg-muted/30 text-muted-foreground",
        className,
      )}
      title={`NinjaTrader bridge: ${status.state}${account}`}
    >
      <span
        className={cn(
          "mr-1.5 inline-block h-1.5 w-1.5 rounded-full",
          connected ? "bg-emerald-400" : "bg-muted-foreground/60",
        )}
      />
      {label}
      {connected && status.account ? (
        <span className="ml-1 normal-case text-[9px] opacity-80">{status.account}</span>
      ) : null}
    </span>
  );
}
