import { useEffect, useState } from "react";

import {
  apprenticeshipLifeLine,
  resolveApprenticeshipLifeState,
  type ApprenticeshipLifeInput,
} from "@/lib/apprenticeship/apprenticeshipLife";
import { cn } from "@/lib/utils";

export function ApprenticeshipLifePulse(input: Omit<ApprenticeshipLifeInput, "nowMs">) {
  const [nowMs, setNowMs] = useState(() => Date.now());
  useEffect(() => {
    const id = window.setInterval(() => setNowMs(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, []);
  const live: ApprenticeshipLifeInput = { ...input, nowMs };
  const state = resolveApprenticeshipLifeState(live);
  const line = apprenticeshipLifeLine(live);
  const caption =
    state === "live"
      ? "Walking now"
      : state === "computing"
        ? "Session still open — not stuck"
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
