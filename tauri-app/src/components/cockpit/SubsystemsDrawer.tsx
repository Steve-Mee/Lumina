import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";
import { Layers, X } from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";

import { useModeMotion } from "@/hooks/useModeMotion";
import { usePrefersReducedMotion } from "@/hooks/usePrefersReducedMotion";
import { modeLabelClass, drawerBadgeClass, type DrawerBadgeVariant } from "@/lib/modePresentation";
import { panelCrossfadeWith, transitionOrNone } from "@/lib/motionPresets";
import { selectCurrentMode, useCoreStore } from "@/store/coreStore";
import { cn } from "@/lib/utils";

export interface DrawerSection<TTab extends string = string> {
  id: string;
  label: string;
  tabs: TTab[];
}

interface SubsystemsDrawerProps<TTab extends string = string> {
  open: boolean;
  activeTab: TTab;
  onOpenChange: (open: boolean) => void;
  onSelectTab: (tab: TTab) => void;
  sections: DrawerSection<TTab>[];
  getTabLabel: (tab: TTab) => string;
  title?: string;
  subtitle?: string;
  footerText?: string;
  footerSlot?: ReactNode;
  triggerLabel?: string;
  triggerIcon?: LucideIcon;
  badgeCount?: number;
  getTabBadge?: (tab: TTab) => number | undefined;
  getTabHighlightClass?: (tab: TTab) => string | undefined;
  className?: string;
}

export type { DrawerBadgeVariant } from "@/lib/modePresentation";
export { drawerBadgeClass } from "@/lib/modePresentation";

export function SubsystemsDrawerTrigger({
  onClick,
  badgeCount = 0,
  badgeVariant = "mode",
  label = "Subsystems",
  icon: Icon = Layers,
  className,
}: {
  onClick: () => void;
  badgeCount?: number;
  badgeVariant?: DrawerBadgeVariant;
  label?: string;
  icon?: LucideIcon;
  className?: string;
}) {
  const operatorMode = useCoreStore(selectCurrentMode);

  return (
    <button
      type="button"
      data-mode={operatorMode}
      onClick={onClick}
      className={cn(
        "deck-tab-chip lumina-glass lumina-glass--panel inline-flex h-8 items-center gap-1.5 px-2.5 font-mono text-[10px] tracking-wide text-muted-foreground uppercase transition-colors lumina-glow-edge hover:text-foreground",
        className,
      )}
    >
      <Icon className="size-3" aria-hidden />
      {label}
      {badgeCount > 0 ? (
        <span
          className={cn(
            "rounded-full px-1.5 py-0 font-mono text-[9px]",
            drawerBadgeClass(badgeVariant, operatorMode),
          )}
        >
          {badgeCount}
        </span>
      ) : null}
    </button>
  );
}

export function SubsystemsDrawer<TTab extends string>({
  open,
  activeTab,
  onOpenChange,
  onSelectTab,
  sections,
  getTabLabel,
  title = "Subsystems",
  subtitle = "Ops panels & platform tools",
  footerText,
  footerSlot,
  getTabBadge,
  getTabHighlightClass,
  className,
}: SubsystemsDrawerProps<TTab>) {
  const reducedMotion = usePrefersReducedMotion();
  const modeMotion = useModeMotion();
  const operatorMode = useCoreStore(selectCurrentMode);

  const selectTab = (tab: TTab) => {
    onSelectTab(tab);
    onOpenChange(false);
  };

  return (
    <AnimatePresence>
      {open ? (
        <>
          <motion.button
            type="button"
            aria-label={`Close ${title.toLowerCase()} drawer`}
            className="subsystems-drawer-scrim fixed inset-0 z-40 backdrop-blur-md"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={transitionOrNone(reducedMotion, modeMotion)}
            onClick={() => onOpenChange(false)}
          />
          <motion.aside
            role="dialog"
            aria-label={title}
            data-mode={operatorMode}
            className={cn(
              "subsystems-drawer-airlock fixed inset-y-0 right-0 z-50 flex w-full max-w-sm flex-col border-l lumina-glass lumina-glass--overlay",
              className,
            )}
            initial={reducedMotion ? false : { x: "100%" }}
            animate={{ x: 0 }}
            exit={reducedMotion ? undefined : { x: "100%" }}
            transition={transitionOrNone(reducedMotion, modeMotion)}
          >
            <div className="relative flex items-center justify-between border-b border-white/10 px-4 py-3">
              <div className="deck-panel-accent absolute inset-x-4 top-0 h-px origin-left" />
              <div>
                <h3 className="font-mono text-xs tracking-[0.14em] text-foreground uppercase">
                  {title}
                </h3>
                <p className="mt-0.5 font-mono text-[10px] text-muted-foreground">{subtitle}</p>
              </div>
              <button
                type="button"
                aria-label="Close"
                className="rounded-md p-1.5 text-muted-foreground hover:bg-white/5 hover:text-foreground"
                onClick={() => onOpenChange(false)}
              >
                <X className="size-4" />
              </button>
            </div>

            <motion.nav
              className="flex-1 overflow-y-auto px-3 py-3"
              variants={panelCrossfadeWith(modeMotion)}
              initial={reducedMotion ? false : "hidden"}
              animate="visible"
              transition={transitionOrNone(reducedMotion, modeMotion)}
            >
              {sections.map((section, sectionIndex) => (
                <motion.div
                  key={section.id}
                  className="mb-4"
                  initial={reducedMotion ? false : { opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{
                    ...modeMotion,
                    delay: reducedMotion ? 0 : sectionIndex * 0.04,
                  }}
                >
                  <p
                    className={cn(
                      "px-2 pb-1 font-mono text-[9px] tracking-[0.12em] uppercase",
                      modeLabelClass(operatorMode),
                    )}
                  >
                    {section.label}
                  </p>
                  <ul className="space-y-0.5">
                    {section.tabs.map((tab) => {
                      const active = activeTab === tab;
                      const badge = getTabBadge?.(tab);
                      return (
                        <li key={tab}>
                          <button
                            type="button"
                            className={cn(
                              "flex w-full items-center justify-between rounded-md px-2 py-2 text-left font-mono text-[10px] tracking-wide uppercase transition-colors hover:bg-white/5 lumina-glass--panel",
                              active
                                ? "deck-accent-text bg-white/5"
                                : "text-muted-foreground/80",
                              getTabHighlightClass?.(tab),
                            )}
                            onClick={() => selectTab(tab)}
                          >
                            <span>{getTabLabel(tab)}</span>
                            {badge != null && badge > 0 ? (
                              <span
                                className={cn(
                                  "rounded-full px-1.5 py-0 font-mono text-[9px]",
                                  drawerBadgeClass("mode", operatorMode),
                                )}
                              >
                                {badge}
                              </span>
                            ) : null}
                          </button>
                        </li>
                      );
                    })}
                  </ul>
                </motion.div>
              ))}
            </motion.nav>

            {footerText || footerSlot ? (
              <div className="subsystems-drawer-airlock__footer flex items-center justify-between gap-3 px-4 py-2">
                {footerText ? (
                  <span className="font-mono text-[9px] text-muted-foreground/60">{footerText}</span>
                ) : (
                  <span />
                )}
                {footerSlot}
              </div>
            ) : null}
          </motion.aside>
        </>
      ) : null}
    </AnimatePresence>
  );
}
