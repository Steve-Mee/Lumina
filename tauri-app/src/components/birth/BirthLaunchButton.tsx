import type { CSSProperties } from "react";
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
  onSequencingChange?: (sequencing: boolean) => void;
  className?: string;
}

const PARTICLE_COUNT = 10;
const PRELAUNCH_MS = 600;
const HOLD_MS = 800;

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
  onSequencingChange,
  className,
}: BirthLaunchButtonProps) {
  const reducedMotion = usePrefersReducedMotion();
  const [hovered, setHovered] = useState(false);
  const [pressed, setPressed] = useState(false);
  const [sequencing, setSequencing] = useState(false);
  const [holdProgress, setHoldProgress] = useState(0);
  const sequenceTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const holdTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const holdStartRef = useRef<number | null>(null);
  const holdRafRef = useRef<number | null>(null);
  const holdingRef = useRef(false);
  const sequenceStartedRef = useRef(false);

  const isDisabled = disabled || activating || sequencing;

  useEffect(() => {
    if (activating) {
      sequenceStartedRef.current = false;
      setSequencing(false);
    }
  }, [activating]);

  const showIdlePulse = !reducedMotion && !isDisabled;
  const showParticles =
    !reducedMotion && !isDisabled && (hovered || pressed || primed || sequencing || holdProgress > 0);

  useEffect(() => {
    onPrimedChange?.(pressed || sequencing || holdProgress > 0.05);
  }, [pressed, sequencing, holdProgress, onPrimedChange]);

  useEffect(() => {
    onSequencingChange?.(sequencing);
  }, [sequencing, onSequencingChange]);

  useEffect(() => {
    return () => {
      if (sequenceTimer.current) {
        clearTimeout(sequenceTimer.current);
      }
      if (holdTimer.current) {
        clearTimeout(holdTimer.current);
      }
      if (holdRafRef.current != null) {
        cancelAnimationFrame(holdRafRef.current);
      }
    };
  }, []);

  const clearHoldTimers = useCallback(() => {
    holdingRef.current = false;
    holdStartRef.current = null;
    if (holdTimer.current) {
      clearTimeout(holdTimer.current);
      holdTimer.current = null;
    }
    if (holdRafRef.current != null) {
      cancelAnimationFrame(holdRafRef.current);
      holdRafRef.current = null;
    }
  }, []);

  const cancelHold = useCallback(() => {
    clearHoldTimers();
    setHoldProgress(0);
  }, [clearHoldTimers]);

  const finishCosmeticSequence = useCallback(() => {
    sequenceTimer.current = setTimeout(() => {
      setSequencing(false);
      if (!activating) {
        sequenceStartedRef.current = false;
      }
    }, PRELAUNCH_MS);
  }, [activating]);

  const beginSequence = useCallback(() => {
    if (disabled || activating || sequenceStartedRef.current) {
      return;
    }
    sequenceStartedRef.current = true;
    clearHoldTimers();
    setPressed(false);

    if (reducedMotion) {
      onClick();
      sequenceStartedRef.current = false;
      return;
    }

    setHoldProgress(1);
    setSequencing(true);
    onClick();
    finishCosmeticSequence();
  }, [activating, clearHoldTimers, disabled, finishCosmeticSequence, onClick, reducedMotion]);

  const tickHold = useCallback(() => {
    if (!holdingRef.current || holdStartRef.current == null) {
      return;
    }
    const elapsed = Date.now() - holdStartRef.current;
    const progress = Math.min(1, elapsed / HOLD_MS);
    setHoldProgress(progress);
    if (progress >= 1) {
      beginSequence();
      return;
    }
    holdRafRef.current = requestAnimationFrame(tickHold);
  }, [beginSequence]);

  const handlePointerDown = useCallback(() => {
    if (isDisabled || reducedMotion || sequenceStartedRef.current) {
      return;
    }
    setPressed(true);
    holdingRef.current = true;
    holdStartRef.current = Date.now();
    holdRafRef.current = requestAnimationFrame(tickHold);
    holdTimer.current = setTimeout(() => {
      if (holdingRef.current) {
        beginSequence();
      }
    }, HOLD_MS);
  }, [beginSequence, isDisabled, reducedMotion, tickHold]);

  const handlePointerRelease = useCallback(() => {
    setPressed(false);
    if (!sequencing && !sequenceStartedRef.current) {
      cancelHold();
    }
  }, [cancelHold, sequencing]);

  const handleClick = useCallback(() => {
    if (isDisabled || sequenceStartedRef.current) {
      return;
    }
    beginSequence();
  }, [beginSequence, isDisabled]);

  const label = activating
    ? "INITIALIZING SEQUENCE…"
    : sequencing
      ? "SEQUENCING NEURAL LATTICE…"
      : holdProgress > 0 && holdProgress < 1
        ? "ARMING SEQUENCE…"
        : "ACTIVATE BIRTH";

  const chargeProgress = sequencing ? 1 : holdProgress;

  return (
    <motion.button
      type="button"
      className={cn(
        "birth-launch-btn",
        showIdlePulse && "birth-launch-btn--idle-pulse",
        (primed || holdProgress > 0) && "birth-launch-btn--primed",
        sequencing && "birth-launch-btn--sequencing",
        disabled && !activating && "birth-launch-btn--disarmed",
        className,
      )}
      style={{ "--launch-charge-progress": chargeProgress } as CSSProperties}
      disabled={isDisabled}
      aria-busy={activating || sequencing}
      aria-description={
        disabled ? "Complete setup before arming birth sequence" : undefined
      }
      onClick={handleClick}
      onPointerDown={handlePointerDown}
      onPointerUp={handlePointerRelease}
      onPointerCancel={handlePointerRelease}
      onPointerLeave={() => {
        setHovered(false);
        handlePointerRelease();
      }}
      onMouseEnter={() => setHovered(true)}
      animate={{
        scale: pressed && !isDisabled ? 0.97 : 1,
      }}
      transition={{ duration: 0.12 }}
    >
      <span className="birth-launch-btn__charge" aria-hidden />
      <span className="birth-launch-btn__glow" aria-hidden />
      <span className="birth-launch-btn__label">
        <span className="birth-launch-btn__sublabel">Click to activate · hold to prime</span>
        {label}
      </span>

      <span className="birth-launch-btn__fx" aria-hidden>
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
                  repeat: hovered && !pressed && !sequencing && holdProgress === 0 ? Infinity : 0,
                  repeatDelay: 0.75,
                }}
              />
            ))
          : null}
      </span>
    </motion.button>
  );
}
