import { AnimatePresence, motion } from "framer-motion";
import { Activity, MoreHorizontal } from "lucide-react";
import { useEffect, useRef, type ReactNode } from "react";

import { useModeMotion } from "@/hooks/useModeMotion";
import { usePrefersReducedMotion } from "@/hooks/usePrefersReducedMotion";
import { modeSpring } from "@/lib/modePresentation";
import { menuPopWith, transitionOrNone } from "@/lib/motionPresets";
import type { TradingMode } from "@/store/coreStore";
import { cn } from "@/lib/utils";

interface HudNerveTapProps {
  mode: TradingMode;
  engineAlive: boolean;
  apiKeyConfigured: boolean;
  configDirty: boolean;
  menuOpen: boolean;
  onActivate: () => void;
  onToggleMenu: () => void;
  onMenuClose: () => void;
  menu?: ReactNode;
  className?: string;
}

export function HudNerveTap({
  mode,
  engineAlive,
  apiKeyConfigured,
  configDirty,
  menuOpen,
  onActivate,
  onToggleMenu,
  onMenuClose,
  menu,
  className,
}: HudNerveTapProps) {
  const reducedMotion = usePrefersReducedMotion();
  const modeMotion = useModeMotion();
  const anchorRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!menuOpen) {
      return;
    }
    const onPointerDown = (event: MouseEvent) => {
      if (anchorRef.current && !anchorRef.current.contains(event.target as Node)) {
        onMenuClose();
      }
    };
    document.addEventListener("mousedown", onPointerDown);
    return () => document.removeEventListener("mousedown", onPointerDown);
  }, [menuOpen, onMenuClose]);

  const handleClick = () => {
    if (engineAlive) {
      onToggleMenu();
      return;
    }
    onActivate();
  };

  const title = !apiKeyConfigured
    ? "Configure admin API key in Settings to start the engine"
    : engineAlive
      ? "Engine live — open command menu"
      : configDirty
        ? "Save configuration and start engine"
        : "Start engine";

  return (
    <div className={cn("relative", className)} ref={anchorRef}>
      <motion.button
        type="button"
        data-mode={mode}
        className={cn(
          "hud-nerve-tap lumina-interactive relative flex h-9 w-9 shrink-0 items-center justify-center rounded-full border",
          engineAlive ? "hud-nerve-tap--alive" : "hud-nerve-tap--dormant",
          !apiKeyConfigured && "opacity-45",
        )}
        aria-expanded={engineAlive ? menuOpen : undefined}
        aria-haspopup={engineAlive ? "menu" : undefined}
        aria-label={title}
        title={title}
        disabled={!apiKeyConfigured && !engineAlive}
        onClick={handleClick}
        animate={{ scale: reducedMotion ? 1 : engineAlive ? 1 : 0.96 }}
        transition={transitionOrNone(reducedMotion, modeMotion)}
      >
        <span className="hud-nerve-tap__ring" aria-hidden />
        <span className="hud-nerve-tap__core" aria-hidden />
        {engineAlive ? (
          <MoreHorizontal className="relative z-[1] size-4 text-foreground/85" />
        ) : (
          <Activity className="hud-nerve-tap__icon relative z-[1] size-4" />
        )}
      </motion.button>
      <AnimatePresence>
        {menuOpen && engineAlive && menu ? (
          <motion.div
            key="hud-overflow"
            role="menu"
            className="deck-overflow-menu absolute right-0 top-full z-50 mt-1 w-56 rounded-lg p-2 lumina-glass lumina-glass--overlay lumina-glow-edge"
            variants={menuPopWith(modeSpring(mode))}
            initial={reducedMotion ? false : "hidden"}
            animate="visible"
            exit={reducedMotion ? undefined : "exit"}
            transition={transitionOrNone(reducedMotion, modeMotion)}
          >
            {menu}
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  );
}
