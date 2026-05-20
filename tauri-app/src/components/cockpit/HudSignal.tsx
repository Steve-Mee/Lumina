import type { CSSProperties } from "react";
import { useEffect, useRef, useState } from "react";
import { motion, useSpring, useTransform } from "framer-motion";

import { useOrganismEnvelope } from "@/context/OrganismEnvelopeContext";
import { AnimatedMetric } from "@/components/cockpit/AnimatedMetric";
import { usePrefersReducedMotion } from "@/hooks/usePrefersReducedMotion";
import type { IntegrityTier } from "@/lib/riskCitadelMetrics";
import { springSnappy } from "@/lib/motionPresets";
import { modeTransition } from "@/lib/modePresentation";
import { selectCurrentMode, useCoreStore } from "@/store/coreStore";
import { cn } from "@/lib/utils";

export type HudSignalGlow = "cyan" | "amber" | "warn" | "emerald" | "gold" | "violet" | "neutral";

interface HudSignalProps {
  label: string;
  value: string;
  glow?: HudSignalGlow;
  intensity?: number;
  className?: string;
}

const GLOW_CLASS: Record<HudSignalGlow, string> = {
  cyan: "hud-signal--cyan",
  amber: "hud-signal--amber",
  warn: "hud-signal--warn",
  emerald: "hud-signal--emerald",
  gold: "hud-signal--gold",
  violet: "hud-signal--violet",
  neutral: "hud-signal--neutral",
};

export function HudSignal({
  label,
  value,
  glow = "cyan",
  intensity = 0.85,
  className,
}: HudSignalProps) {
  const envelope = useOrganismEnvelope();
  const mode = useCoreStore(selectCurrentMode);
  const prevValue = useRef(value);
  const [flash, setFlash] = useState(false);
  const breatheIntensity = intensity * (0.85 + envelope * 0.15);

  useEffect(() => {
    if (prevValue.current !== value) {
      prevValue.current = value;
      setFlash(true);
      const id = window.setTimeout(() => setFlash(false), 220);
      return () => window.clearTimeout(id);
    }
    return undefined;
  }, [value]);

  return (
    <div
      data-flash={flash ? "" : undefined}
      data-mode={mode}
      className={cn("hud-signal shrink-0", GLOW_CLASS[glow], className)}
      style={{ "--hud-signal-intensity": breatheIntensity } as CSSProperties}
    >
      <span className="hud-signal__label">{label}</span>
      <AnimatedMetric value={value} className="hud-signal__value" />
      <span className="hud-signal__glow" aria-hidden />
    </div>
  );
}

const ARC_TIER_STROKE: Record<IntegrityTier, string> = {
  green: "var(--hud-arc-emerald, #34d399)",
  orange: "var(--hud-arc-amber, #fbbf24)",
  red: "var(--hud-arc-red, #ef4444)",
};

interface HudSignalArcProps {
  label: string;
  integrity: number;
  tier: IntegrityTier;
  className?: string;
}

export function HudSignalArc({ label, integrity, tier, className }: HudSignalArcProps) {
  const reducedMotion = usePrefersReducedMotion();
  const mode = useCoreStore(selectCurrentMode);
  const envelope = useOrganismEnvelope();
  const clamped = Math.max(0, Math.min(100, integrity));
  const radius = 18;
  const circumference = Math.PI * radius;
  const arcSpring = modeTransition(mode, reducedMotion) ?? springSnappy;
  const spring = useSpring(clamped, arcSpring);
  const arcOpacity = mode === "REAL" ? 0.72 + envelope * 0.28 : 0.85 + envelope * 0.15;

  useEffect(() => {
    spring.set(clamped);
  }, [clamped, spring]);

  const dashOffset = useTransform(
    spring,
    (v) => circumference - (v / 100) * circumference,
  );
  const staticOffset = circumference - (clamped / 100) * circumference;

  return (
    <div
      className={cn("hud-signal hud-signal-arc shrink-0", className)}
      style={{ "--hud-arc-opacity": arcOpacity } as CSSProperties}
    >
      <span className="hud-signal__label">{label}</span>
      <div className="hud-signal-arc__wrap">
        <svg className="hud-signal-arc__svg" viewBox="0 0 48 28" aria-hidden>
          <path
            d="M 6 24 A 18 18 0 0 1 42 24"
            fill="none"
            stroke="color-mix(in srgb, var(--deck-accent, var(--lumina-cyan)) 12%, transparent)"
            strokeWidth="3"
            strokeLinecap="round"
          />
          {reducedMotion ? (
            <path
              d="M 6 24 A 18 18 0 0 1 42 24"
              fill="none"
              stroke={ARC_TIER_STROKE[tier]}
              strokeWidth="3"
              strokeLinecap="round"
              strokeDasharray={circumference}
              strokeDashoffset={staticOffset}
              className="hud-signal-arc__fill"
            />
          ) : (
            <motion.path
              d="M 6 24 A 18 18 0 0 1 42 24"
              fill="none"
              stroke={ARC_TIER_STROKE[tier]}
              strokeWidth="3"
              strokeLinecap="round"
              strokeDasharray={circumference}
              style={{ strokeDashoffset: dashOffset }}
              className="hud-signal-arc__fill"
            />
          )}
        </svg>
        <span className="hud-signal-arc__value">{Math.round(clamped)}%</span>
      </div>
    </div>
  );
}
