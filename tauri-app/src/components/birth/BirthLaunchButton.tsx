import { motion } from "framer-motion";
import { useCallback, useEffect, useRef, useState } from "react";

import { usePrefersReducedMotion } from "@/hooks/usePrefersReducedMotion";
import { cn } from "@/lib/utils";

interface BirthLaunchButtonProps {
  activating: boolean;
  primed?: boolean;
  disabled?: boolean;
  onClick: () => void;
  onPrimedChange?: (primed: boolean) => void;
  className?: string;
}

const PARTICLE_COUNT = 10;
const PRELAUNCH_MS = 2200;

const PARTICLE_OFFSETS = Array.from({ length: PARTICLE_COUNT }, (_, i) => ({
  angle: (i / PARTICLE_COUNT) * Math.PI * 2,
  distance: 32 + (i % 3) * 10,
}));

export function BirthLaunchButton({
  activating,
  primed = false,
  disabled = false,
  onClick,
  onPrimedChange,
  className,
}: BirthLaunchButtonProps) {
  const reducedMotion = usePrefersReducedMotion();
  const [hovered, setHovered] = useState(false);
  const [pressed, setPressed] = useState(false);
  const [sequencing, setSequencing] = useState(false);
  const sequenceTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const isDisabled = disabled || activating || sequencing;
  const showIdlePulse = !reducedMotion && !isDisabled;
  const showParticles =
    !reducedMotion && !isDisabled && (hovered || pressed || primed || sequencing);

  useEffect(() => {
    onPrimedChange?.(pressed || sequencing);
  }, [pressed, sequencing, onPrimedChange]);

  useEffect(() => {
    return () => {
      if (sequenceTimer.current) {
        clearTimeout(sequenceTimer.current);
      }
    };
  }, []);

  const handleLaunch = useCallback(() => {
    if (isDisabled) {
      return;
    }
    if (reducedMotion) {
      onClick();
      return;
    }
    setSequencing(true);
    sequenceTimer.current = setTimeout(() => {
      setSequencing(false);
      onClick();
    }, PRELAUNCH_MS);
  }, [isDisabled, onClick, reducedMotion]);

  const label = activating
    ? "INITIALIZING SEQUENCE…"
    : sequencing
      ? "SEQUENCING NEURAL LATTICE…"
      : "ACTIVATE BIRTH";

  return (
    <motion.button
      type="button"
      className={cn(
        "birth-launch-btn",
        showIdlePulse && "birth-launch-btn--idle-pulse",
        primed && "birth-launch-btn--primed",
        sequencing && "birth-launch-btn--sequencing",
        disabled && !activating && "birth-launch-btn--disarmed",
        className,
      )}
      disabled={isDisabled}
      aria-busy={activating || sequencing}
      aria-description={
        disabled ? "Complete setup before arming birth sequence" : undefined
      }
      onClick={handleLaunch}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => {
        setHovered(false);
        setPressed(false);
      }}
      onMouseDown={() => setPressed(true)}
      onMouseUp={() => setPressed(false)}
      animate={{
        scale: pressed && !isDisabled ? 0.97 : 1,
      }}
      transition={{ duration: 0.12 }}
    >
      <span className="birth-launch-btn__charge" aria-hidden />
      <span className="birth-launch-btn__glow" aria-hidden />
      <span className="birth-launch-btn__label">
        <span className="birth-launch-btn__sublabel">Arm sequence</span>
        {label}
      </span>

      {showParticles
        ? PARTICLE_OFFSETS.map((particle, index) => (
            <motion.span
              key={index}
              className="birth-launch-particle"
              initial={{ opacity: 0, scale: 0.3, x: 0, y: 0 }}
              animate={{
                opacity: [0, 1, 0],
                scale: [0.3, 1, 0.2],
                x: Math.cos(particle.angle) * particle.distance * -0.35,
                y: Math.sin(particle.angle) * particle.distance * -0.2,
              }}
              transition={{
                duration: pressed || sequencing ? 0.45 : 0.7,
                delay: index * 0.04,
                repeat: hovered && !pressed && !sequencing ? Infinity : 0,
                repeatDelay: 0.75,
              }}
              aria-hidden
            />
          ))
        : null}
    </motion.button>
  );
}
