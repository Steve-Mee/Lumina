import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export interface BirthRecoveryAction {
  id: string;
  label: string;
  loadingLabel?: string;
  onClick: () => void;
  variant?: "primary" | "secondary" | "outline" | "ghost";
  disabled?: boolean;
}

interface BirthRecoveryActionBarProps {
  actions: BirthRecoveryAction[];
  loading?: boolean;
  className?: string;
  footer?: ReactNode;
}

function variantFor(action: BirthRecoveryAction["variant"]) {
  if (action === "secondary") return "secondary" as const;
  if (action === "outline") return "outline" as const;
  if (action === "ghost") return "ghost" as const;
  return "default" as const;
}

export function BirthRecoveryActionBar({
  actions,
  loading = false,
  className,
  footer,
}: BirthRecoveryActionBarProps) {
  return (
    <div className={cn("birth-recovery-actions", className)}>
      {actions.map((action) => (
        <Button
          key={action.id}
          type="button"
          variant={variantFor(action.variant)}
          className={cn(
            "birth-recovery-action",
            action.variant === "primary" && "onboarding-cta",
          )}
          disabled={loading || action.disabled}
          onClick={action.onClick}
        >
          {loading && action.variant === "primary"
            ? action.loadingLabel ?? "Starting…"
            : action.label}
        </Button>
      ))}
      {footer ? <div className="birth-recovery-actions__footer">{footer}</div> : null}
    </div>
  );
}
