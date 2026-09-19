import { useEffect, useRef, useState } from "react";

/** Hide only after a sustained miss — window resize must not unmount WebGL. */
export const PANEL_VISIBILITY_HIDE_DEBOUNCE_MS = 1500;
/** Ignore non-intersection while the first layout/window settle runs. */
export const PANEL_VISIBILITY_LAYOUT_GRACE_MS = 800;

export function usePanelVisibility() {
  const ref = useRef<HTMLDivElement>(null);
  const [isVisible, setIsVisible] = useState(true);
  const hideTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const graceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const layoutReadyRef = useRef(false);

  useEffect(() => {
    const element = ref.current;
    if (!element) {
      return;
    }

    layoutReadyRef.current = false;
    graceTimerRef.current = setTimeout(() => {
      layoutReadyRef.current = true;
    }, PANEL_VISIBILITY_LAYOUT_GRACE_MS);

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          if (hideTimerRef.current) {
            clearTimeout(hideTimerRef.current);
            hideTimerRef.current = null;
          }
          setIsVisible(true);
          return;
        }

        if (!layoutReadyRef.current) {
          return;
        }

        if (hideTimerRef.current) {
          clearTimeout(hideTimerRef.current);
        }
        hideTimerRef.current = setTimeout(() => {
          setIsVisible(false);
          hideTimerRef.current = null;
        }, PANEL_VISIBILITY_HIDE_DEBOUNCE_MS);
      },
      { threshold: 0.05, rootMargin: "50px" },
    );

    observer.observe(element);

    return () => {
      observer.disconnect();
      if (hideTimerRef.current) {
        clearTimeout(hideTimerRef.current);
        hideTimerRef.current = null;
      }
      if (graceTimerRef.current) {
        clearTimeout(graceTimerRef.current);
        graceTimerRef.current = null;
      }
    };
  }, []);

  return { ref, isVisible };
}
