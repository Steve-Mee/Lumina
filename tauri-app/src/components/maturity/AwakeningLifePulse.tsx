import { useEffect, useState } from "react";

import {
  awakeningLifeLine,
  resolveAwakeningLifeState,
  type AwakeningLifeInput,
} from "@/lib/awakening/awakeningLife";
import { cn } from "@/lib/utils";

export function AwakeningLifePulse(input: Omit<AwakeningLifeInput, "nowMs">) {
  const [nowMs, setNowMs] = useState(() => Date.now());
  useEffect(() => {
    const id = window.setInterval(() => setNowMs(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, []);
  const live: AwakeningLifeInput = { ...input, nowMs };
  const state = resolveAwakeningLifeState(live);
  const line = awakeningLifeLine(live);
  const caption =
    state === "live"
      ? "Evolving now"
      : state === "computing"
        ? "This cycle is still computing — not stuck"
        : "Clock idle";

  return (
    <div
      className={cn(
        "awakening-life shrink-0",
        state === "live" && "awakening-life--live",
        state === "computing" && "awakening-life--computing",
        state === "idle" && "awakening-life--idle",
      )}
      role="status"
      aria-live="polite"
      aria-label={`${caption}. ${line}`}
    >
      <span className="awakening-life__pulse" aria-hidden>
        <span className="awakening-life__pulse-ring" />
        <span className="awakening-life__pulse-ring awakening-life__pulse-ring--delay" />
        <span className="awakening-life__pulse-core" />
      </span>
      <div className="awakening-life__copy min-w-0">
        <p className="awakening-life__caption">{caption}</p>
        <p className="awakening-life__line font-mono">{line}</p>
      </div>
    </div>
  );
}
