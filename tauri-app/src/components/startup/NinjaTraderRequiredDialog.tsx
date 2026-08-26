/** Cold-start modal: start NinjaTrader or continue without Fabric link. */
import { SystemsGoDialog } from "@/components/startup/SystemsGoDialog";

export function NinjaTraderRequiredDialog({
  open,
  busy,
  waitDetail,
  onStart,
  onContinueWithout,
}: {
  open: boolean;
  busy?: boolean;
  waitDetail?: string | null;
  onStart: () => void;
  onContinueWithout: () => void;
  className?: string;
}) {
  return (
    <SystemsGoDialog
      open={open}
      eyebrow="Fabric · precondition"
      title="NinjaTrader must be running"
      titleId="nt-required-title"
      busy={busy}
      primaryLabel="Start NinjaTrader"
      primaryBusyLabel="Waiting for NinjaTrader…"
      onPrimary={onStart}
      secondaryLabel="Continue without link"
      onSecondary={onContinueWithout}
      footnote="Without a link, Lumina still opens for review — trading and Birth activate stay blocked."
    >
      <p className="systems-go-dialog__text" id="nt-required-body">
        The live Fabric link (Brain ↔ NT8) is hosted inside NinjaTrader. Without NinjaTrader
        open, the connection cannot go{" "}
        <span className="font-medium text-[color:var(--status-ok-fg)]">GREEN</span> — no live
        data, no Activate Birth, no orders.
      </p>
      <ul className="systems-go-dialog__list">
        <li>Start NinjaTrader 8 and wait until the datafeed is Connected</li>
        <li>Open New → LUMINA if the host is not already running</li>
      </ul>
      {busy && waitDetail ? (
        <p className="systems-go-dialog__status" role="status">
          {waitDetail}
        </p>
      ) : null}
    </SystemsGoDialog>
  );
}
