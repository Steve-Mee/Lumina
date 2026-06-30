import * as React from "react";
import * as TabsPrimitive from "@radix-ui/react-tabs";
import { motion } from "framer-motion";

import { useModeMotion } from "@/hooks/useModeMotion";
import { usePrefersReducedMotion } from "@/hooks/usePrefersReducedMotion";
import { panelCrossfadeWith, transitionOrNone } from "@/lib/motionPresets";
import { cn } from "@/lib/utils";

function Tabs({
  className,
  ...props
}: React.ComponentProps<typeof TabsPrimitive.Root>) {
  return (
    <TabsPrimitive.Root
      data-slot="tabs"
      className={cn("flex flex-col gap-2", className)}
      {...props}
    />
  );
}

function TabsList({
  className,
  ...props
}: React.ComponentProps<typeof TabsPrimitive.List>) {
  return (
    <TabsPrimitive.List
      data-slot="tabs-list"
      className={cn(
        "inline-flex w-fit items-center rounded-lg lumina-glass p-0.5",
        className,
      )}
      {...props}
    />
  );
}

function TabsTrigger({
  className,
  ...props
}: React.ComponentProps<typeof TabsPrimitive.Trigger>) {
  return (
    <TabsPrimitive.Trigger
      data-slot="tabs-trigger"
      className={cn(
        "deck-tab-trigger lumina-interactive lumina-interactive--ghost inline-flex h-7 items-center justify-center rounded-md px-3 font-mono text-[10px] tracking-[0.14em] whitespace-nowrap uppercase transition-all",
        "text-muted-foreground hover:bg-white/5",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400/40",
        "disabled:pointer-events-none disabled:opacity-50",
        className,
      )}
      {...props}
    />
  );
}

function TabsContent({
  className,
  ...props
}: React.ComponentProps<typeof TabsPrimitive.Content>) {
  return (
    <TabsPrimitive.Content
      data-slot="tabs-content"
      className={cn("min-h-0 flex-1 outline-none", className)}
      {...props}
    />
  );
}

function ModeTabPanel({
  tabKey,
  className,
  children,
}: {
  tabKey: string;
  className?: string;
  children: React.ReactNode;
}) {
  const reducedMotion = usePrefersReducedMotion();
  const modeMotion = useModeMotion();

  return (
    <motion.div
      key={tabKey}
      className={cn("flex min-h-0 flex-1 flex-col", className)}
      variants={panelCrossfadeWith(modeMotion)}
      initial={reducedMotion ? false : "hidden"}
      animate="visible"
      transition={transitionOrNone(reducedMotion, modeMotion)}
    >
      {children}
    </motion.div>
  );
}

export { Tabs, TabsList, TabsTrigger, TabsContent, ModeTabPanel };
