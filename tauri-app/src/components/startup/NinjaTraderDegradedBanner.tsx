/**
 * Session banner when cold start was degraded or live link is down.
 * Shows until Fabric is GREEN again or operator dismisses.
 */
import { useEffect, useRef, useState } from "react";

import { isNinjaTraderRunning } from "@/lib/ninjaTraderClient";
import { ensureFabricGreen, waitNtProcess } from "@/lib/startupSystemsOrchestrator";
import { useOnboardingStore } from "@/store/onboardingStore";
import { cn } from "@/lib/utils";

export function NinjaTraderDegradedBanner({ className }: { className?: string }) {
  const phase = useOnboardingStore((s) => s.phase);
  const ntLinkDeferred = useOnboardingStore((s) => s.ntLinkDeferred);
  const ntStartupResolved = useOnboardingStore((s) => s.ntStartupResolved);
  const fabricStartup = useOnboardingStore((s) => s.fabricStartup);
  const dismissed = useOnboardingStore((s) => s.ntDegradedBannerDismissed);
  const dismiss = useOnboardingStore((s) => s.dismissNtDegradedBanner);
  const setNtLinkDeferred = useOnboardingStore((s) => s.setNtLinkDeferred);
  const setFabricStartup = useOnboardingStore((s) => s.setFabricStartup);
  const [ntUp, setNtUp] = useState<boolean | null>(null);
  const [starting, setStarting] = useState(false);
  const genRef = useRef(0);

  // Live GREEN or host+proof — never paper cert alone.
  const fabricGreen = Boolean(
    fabricStartup?.green ||
      (fabricStartup?.hostReady && fabricStartup?.certified),
  );
  const linkDegraded =
    ntLinkDeferred || (fabricStartup != null && !fabricGreen);

  useEffect(() => {
    if (phase === "loading" || !ntStartupResolved) return;
    let cancelled = false;
    const tick = async () => {
      try {
        const up = await isNinjaTraderRunning();
        if (!cancelled) setNtUp(up);
      } catch {
        if (!cancelled) setNtUp(false);
      }
    };
    void tick();
    const id = globalThis.setInterval(() => void tick(), 8000);
    return () => {
      cancelled = true;
      globalThis.clearInterval(id);
    };
  }, [phase, ntStartupResolved]);

  // Clear degraded only when Fabric is actually GREEN again.
  useEffect(() => {
    if (fabricGreen && ntLinkDeferred) {
      setNtLinkDeferred(false);
    }
  }, [fabricGreen, ntLinkDeferred, setNtLinkDeferred]);

  if (phase === "loading" || !ntStartupResolved || dismissed) return null;
  // Fully healthy: fabric green and NT up (or unknown still probing)
  if (fabricGreen && ntUp !== false) return null;
  // Nothing wrong known yet
  if (!linkDegraded && ntUp !== false) return null;

  const handleStart = () => {
    const gen = ++genRef.current;
    const cancelled = () => genRef.current !== gen;
    setStarting(true);
    void (async () => {
      const nt = await waitNtProcess({
        launch: true,
        isCancelled: cancelled,
      });
      if (cancelled()) return;
      if (nt === "failed") {
        setStarting(false);
        return;
      }
      setNtUp(true);
      const fabric = await ensureFabricGreen({
        isCancelled: cancelled,
        timeoutMs: 45_000,
        pollMs: 1_000,
      });
      if (cancelled()) return;
      setStarting(false);
      setFabricStartup(fabric);
      if (fabric.green) {
        setNtLinkDeferred(false);
      }
    })();
  };

  const title = !ntUp
    ? "No NinjaTrader link"
    : fabricGreen
      ? "NinjaTrader link"
      : "Fabric not GREEN";

  const body = !ntUp
    ? "Lumina is open for review. Trading, Activate Birth, and live market data need NinjaTrader running with the LUMINA host."
    : "NinjaTrader is running but the Fabric link is not GREEN. Trading and Activate Birth stay blocked until the link is ready.";

  return (
    <div
      className={cn(
        "systems-go-banner fixed bottom-0 left-0 right-0 z-[60] px-4 py-2.5",
        className,
      )}
      role="status"
      aria-label="NinjaTrader or Fabric link degraded"
    >
      <div className="mx-auto flex max-w-4xl flex-wrap items-center justify-between gap-3">
        <p className="min-w-0 flex-1 text-[12px] leading-snug">
          <span className="inline-flex items-center gap-1.5 font-mono text-[0.55rem] tracking-wider text-[color:var(--status-partial-fg)] uppercase">
            <span
              className="size-1.5 rounded-full bg-[color:var(--status-partial)] shadow-[0_0_8px_var(--status-partial)]"
              aria-hidden
            />
            {title}
          </span>
          <span className="mt-0.5 block text-white/55">{body}</span>
        </p>
        <div className="flex shrink-0 flex-wrap gap-2">
          <button
            type="button"
            className="onboarding-cta rounded-md px-3 py-1.5 text-[0.6rem]"
            disabled={starting}
            onClick={handleStart}
          >
            {starting
              ? "Connecting…"
              : ntUp
                ? "Retry Fabric"
                : "Start NinjaTrader"}
          </button>
          <button
            type="button"
            className="onboarding-btn-secondary rounded-md px-3 py-1.5 font-mono text-[0.5rem] tracking-wider uppercase"
            onClick={() => dismiss()}
          >
            Dismiss
          </button>
        </div>
      </div>
    </div>
  );
}
