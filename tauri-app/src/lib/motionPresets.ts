import type { Transition, Variants } from "framer-motion";

/** T0 wizard step fade. */
export const stepFade = {
  type: "tween" as const,
  duration: 0.2,
  ease: "easeOut" as const,
};

/** Birth/onboarding surfaces — slower luxury spring. */
export const springBirthLuxury = {
  type: "spring" as const,
  stiffness: 200,
  damping: 28,
  mass: 0.9,
};

/** HUD overflow / quick chrome — snappy response. */
export const springHudSnappy = {
  type: "spring" as const,
  stiffness: 480,
  damping: 32,
  mass: 0.55,
};

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

export const springLuxury = {
  type: "spring" as const,
  stiffness: 260,
  damping: 26,
  mass: 0.75,
};

export const panelCrossfade: Variants = panelCrossfadeWith(springLuxury);

export function panelCrossfadeWith(transition: Transition): Variants {
  return {
    hidden: { opacity: 0, y: 6 },
    visible: { opacity: 1, y: 0, transition },
    exit: { opacity: 0, y: -4, transition },
  };
}

export const menuPop: Variants = menuPopWith(springSnappy);

export function menuPopWith(transition: Transition): Variants {
  return {
    hidden: { opacity: 0, scale: 0.96, y: -4 },
    visible: { opacity: 1, scale: 1, y: 0, transition },
    exit: { opacity: 0, scale: 0.98, y: -2, transition },
  };
}

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

export const staggerItem: Variants = staggerItemWith(springSnappy);

export function staggerItemWith(transition: Transition): Variants {
  return {
    hidden: { opacity: 0, y: 8 },
    visible: { opacity: 1, y: 0, transition },
  };
}

export const metricPop: Variants = {
  initial: { opacity: 0.6, scale: 0.92 },
  animate: { opacity: 1, scale: 1, transition: springSnappy },
  exit: { opacity: 0.6, scale: 0.96, transition: springSnappy },
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
