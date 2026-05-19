import type { Transition, Variants } from "framer-motion";

export const springSnappy = {
  type: "spring" as const,
  stiffness: 420,
  damping: 28,
  mass: 0.6,
};

export const springSoft = {
  type: "spring" as const,
  stiffness: 180,
  damping: 22,
  mass: 0.8,
};

export const fadeUp: Variants = {
  hidden: { opacity: 0, y: 12 },
  visible: { opacity: 1, y: 0 },
};

export const fadeIn: Variants = {
  hidden: { opacity: 0 },
  visible: { opacity: 1 },
};

export const scaleIn: Variants = {
  hidden: { opacity: 0, scale: 0.96 },
  visible: { opacity: 1, scale: 1 },
};

export const slideDown: Variants = {
  hidden: { opacity: 0, y: -8, height: 0 },
  visible: { opacity: 1, y: 0, height: "auto" },
  exit: { opacity: 0, y: -6, height: 0 },
};

export const staggerContainer: Variants = {
  hidden: {},
  visible: {
    transition: { staggerChildren: 0.06, delayChildren: 0.04 },
  },
};

export const staggerItem: Variants = {
  hidden: { opacity: 0, y: 8 },
  visible: {
    opacity: 1,
    y: 0,
    transition: springSnappy,
  },
};

export const metricPop: Variants = {
  initial: { opacity: 0.6, scale: 0.92 },
  animate: { opacity: 1, scale: 1 },
  exit: { opacity: 0.6, scale: 0.96 },
};

export function motionProps<T extends Record<string, unknown>>(
  reducedMotion: boolean,
  props: T,
): T | Record<string, never> {
  return reducedMotion ? {} : props;
}

export function transitionOrNone(
  reducedMotion: boolean,
  transition: Transition,
): Transition | undefined {
  return reducedMotion ? { duration: 0 } : transition;
}
