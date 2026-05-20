import { motion } from "framer-motion";
import type { ReactNode } from "react";

import { useModeMotion } from "@/hooks/useModeMotion";
import { usePrefersReducedMotion } from "@/hooks/usePrefersReducedMotion";
import { fadeUp, transitionOrNone } from "@/lib/motionPresets";
import { cn } from "@/lib/utils";

interface FadeInViewProps {
  children: ReactNode;
  className?: string;
  delay?: number;
  layout?: boolean;
}

export function FadeInView({
  children,
  className,
  delay = 0,
  layout = false,
}: FadeInViewProps) {
  const reducedMotion = usePrefersReducedMotion();
  const modeMotion = useModeMotion();

  return (
    <motion.div
      className={cn(className)}
      layout={layout && !reducedMotion}
      initial={reducedMotion ? false : "hidden"}
      animate="visible"
      variants={fadeUp}
      transition={transitionOrNone(reducedMotion, {
        ...modeMotion,
        delay,
      })}
    >
      {children}
    </motion.div>
  );
}
