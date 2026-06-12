/** Birth gate signals for Command Deck fail-closed overlays. */

export interface DeckBirthSnapshot {
  status: string;
  artifacts_ok?: boolean;
  certificate_ok?: boolean;
  message?: string;
  progress?: {
    progress_pct?: number;
    stage?: string;
    trades_done?: number;
    target_trades?: number;
  };
}

export type DeckBirthGate = "none" | "running" | "incomplete";

function normStatus(value: unknown): string {
  return String(value ?? "")
    .trim()
    .toLowerCase();
}

/** Classify whether the deck must block on birth lifecycle (fail-closed without artifacts). */
export function resolveDeckBirthGate(snapshot: DeckBirthSnapshot | null): DeckBirthGate {
  if (!snapshot) {
    return "none";
  }

  if (snapshot.artifacts_ok === true && snapshot.certificate_ok !== false) {
    return "none";
  }
  if (snapshot.certificate_ok === true && snapshot.artifacts_ok === true) {
    return "none";
  }

  const status = normStatus(snapshot.status);

  if (status === "running" || status === "started" || status === "active") {
    return "running";
  }

  if (status === "completed") {
    const pct = snapshot.progress?.progress_pct ?? 100;
    return pct < 100 ? "running" : "incomplete";
  }

  if (
    status === "interrupted" ||
    status === "error" ||
    status === "certificate_failed" ||
    status === "idle" ||
    status === "not_started" ||
    status === ""
  ) {
    return "incomplete";
  }

  if (snapshot.certificate_ok === false) {
    return "incomplete";
  }

  return "incomplete";
}

export function isDeckBirthRunning(gate: DeckBirthGate): boolean {
  return gate === "running";
}

export function isDeckBirthIncomplete(gate: DeckBirthGate): boolean {
  return gate === "incomplete";
}
