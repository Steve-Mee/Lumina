import { motion, useReducedMotion } from "framer-motion";
import {
  HEALTH_DOT,
  type IntelligenceHealth,
} from "../lib/intelligenceDisplay";

export interface IntelligenceHealthDotProps {
  health: IntelligenceHealth;
  pulse?: boolean;
  size?: "sm" | "md";
  className?: string;
}

export function IntelligenceHealthDot({
  health,
  pulse = false,
  size = "sm",
  className = "",
}: IntelligenceHealthDotProps): JSX.Element {
  const reduceMotion = useReducedMotion() ?? false;
  const visual = HEALTH_DOT[health];
  const dim = size === "md" ? "h-2.5 w-2.5" : "h-2 w-2";
  const shouldPulse = pulse && !reduceMotion;

  return (
    <span
      className={`relative inline-flex shrink-0 ${dim} ${className}`}
      aria-hidden
    >
      {shouldPulse ? (
        <motion.span
          className={`absolute inline-flex ${dim} rounded-full`}
          style={{ backgroundColor: visual.color }}
          animate={{ scale: [1, 2.6], opacity: [0.72, 0] }}
          transition={{ duration: 1.3, repeat: Infinity, ease: "easeOut" }}
        />
      ) : null}
      <span
        className={`relative inline-flex rounded-full ${dim}`}
        style={{
          backgroundColor: visual.color,
          boxShadow: `0 0 10px ${visual.glow}`,
        }}
      />
    </span>
  );
}
