import { motion } from "framer-motion";
import type { ReactNode } from "react";

import { usePrefersReducedMotion } from "@/hooks/usePrefersReducedMotion";
import { fadeUp, springSoft, transitionOrNone } from "@/lib/motionPresets";
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

  return (
    <motion.div
      className={cn(className)}
      layout={layout && !reducedMotion}
      initial={reducedMotion ? false : "hidden"}
      animate="visible"
      variants={fadeUp}
      transition={transitionOrNone(reducedMotion, {
        ...springSoft,
        delay,
      })}
    >
      {children}
    </motion.div>
  );
}
