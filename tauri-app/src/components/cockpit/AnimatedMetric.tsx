import { AnimatePresence, motion } from "framer-motion";

import { usePrefersReducedMotion } from "@/hooks/usePrefersReducedMotion";
import { metricPop } from "@/lib/motionPresets";
import { cn } from "@/lib/utils";

interface AnimatedMetricProps {
  value: string;
  className?: string;
}

export function AnimatedMetric({ value, className }: AnimatedMetricProps) {
  const reducedMotion = usePrefersReducedMotion();

  if (reducedMotion) {
    return (
      <p className={cn("mt-0.5 font-mono text-sm tabular-nums", className)}>
        {value}
      </p>
    );
  }

  return (
    <AnimatePresence mode="wait" initial={false}>
      <motion.p
        key={value}
        className={cn("mt-0.5 font-mono text-sm tabular-nums", className)}
        variants={metricPop}
        initial="initial"
        animate="animate"
        exit="exit"
        transition={{ duration: 0.18, ease: "easeOut" }}
      >
        {value}
      </motion.p>
    </AnimatePresence>
  );
}
