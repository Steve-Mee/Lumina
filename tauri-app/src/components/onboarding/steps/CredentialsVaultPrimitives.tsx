/** Vault field/status primitives for CredentialsStep (Tauri UI god split). */
import type { ReactNode } from "react";
import {
  CheckCircle2,
  CircleAlert,
  CircleDashed,
  TriangleAlert,
} from "lucide-react";

import { HelpTip } from "@/components/ui/HelpTip";

export type VaultTab = "security" | "fabric" | "alerts" | "data" | "twin";
export type ChipState = "idle" | "ok" | "partial" | "fail";

export function VaultField({
  label,
  hint,
  tip,
  fieldState,
  children,
}: {
  label: string;
  hint?: string;
  tip?: string;
  /** Traffic edge: ok filled · partial needs fill · fail error */
  fieldState?: ChipState;
  children: ReactNode;
}) {
  return (
    <div
      className="credentials-vault-field-card"
      data-field-state={
        fieldState && fieldState !== "idle" ? fieldState : undefined
      }
    >
      <div className="mb-0.5 flex items-center gap-1.5">
        <p className="credentials-vault-field-label mb-0">{label}</p>
        {tip ? <HelpTip text={tip} /> : null}
      </div>
      {children}
      {hint ? <p className="credentials-vault-field-hint">{hint}</p> : null}
    </div>
  );
}

export function StatusIcon({ status }: { status: string }) {
  if (status === "pass") {
    return <CheckCircle2 className="mt-0.5 size-3.5 shrink-0 text-emerald-300" aria-hidden />;
  }
  if (status === "fail") {
    return <CircleAlert className="mt-0.5 size-3.5 shrink-0 text-red-300" aria-hidden />;
  }
  if (status === "warn") {
    return <TriangleAlert className="mt-0.5 size-3.5 shrink-0 text-amber-300" aria-hidden />;
  }
  return <CircleDashed className="mt-0.5 size-3.5 shrink-0 text-white/35" aria-hidden />;
}

export function StatusChip({
  label,
  state,
  tip,
}: {
  label: string;
  state: ChipState;
  tip: string;
}) {
  return (
    <span
      className="credentials-vault-status-chip"
      data-state={state === "idle" ? undefined : state}
      title={tip}
    >
      <span className="credentials-vault-status-chip__dot" />
      {label}
    </span>
  );
}
