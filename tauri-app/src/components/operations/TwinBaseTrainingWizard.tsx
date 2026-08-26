/** Birth-ready base training wizard (ADR-0037) — app-only forced-choice. */
import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import {
  completeBaseTraining,
  fetchBaseStatus,
  startBaseTraining,
  submitBaseAnswer,
  type TwinBaseStatus,
  type TwinMcQuestion,
  type TwinReadiness,
} from "@/lib/twinClient";
import { resolveMonitoringApiKey } from "@/lib/monitoringClient";
import { cn } from "@/lib/utils";
import "@/styles/twinTraining.css";

export interface TwinBaseTrainingWizardProps {
  readiness?: TwinReadiness | null;
  onCompleted?: () => void;
  className?: string;
  /** vault = Operator Vault embed; deck = Intelligence annex */
  variant?: "vault" | "deck";
}

function isSessionActive(s: TwinBaseStatus | null | undefined): boolean {
  if (!s) return false;
  if (s.active === true) return true;
  const st = String(s.status || "").toLowerCase();
  return st === "in_progress" || st === "ready_to_complete";
}

export function TwinBaseTrainingWizard({
  readiness,
  onCompleted,
  className,
  variant = "deck",
}: TwinBaseTrainingWizardProps) {
  const [status, setStatus] = useState<TwinBaseStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [starting, setStarting] = useState(false);
  const [clarify, setClarify] = useState("");
  const [lastError, setLastError] = useState<string | null>(null);
  const alreadyReady = Boolean(readiness?.birth_ready || readiness?.base_trained);

  const refresh = useCallback(async () => {
    try {
      const s = await fetchBaseStatus();
      setStatus(s);
      setLastError(null);
      return s;
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Status ophalen mislukt";
      setLastError(msg);
      return null;
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const sessionActive = useMemo(() => isSessionActive(status), [status]);
  const question: TwinMcQuestion | null | undefined = status?.question;

  const normalizeStatus = (res: TwinBaseStatus & { started?: boolean }): TwinBaseStatus => ({
    ...res,
    active: res.active === true || res.status === "in_progress" || res.status === "ready_to_complete",
  });

  const handleStart = async (force = false) => {
    if (!resolveMonitoringApiKey()) {
      const msg =
        "API-key ontbreekt. Zet Admin API key in Operator Vault (Security) en sync/genereer die eerst.";
      setLastError(msg);
      toast.error(msg);
      return;
    }
    setBusy(true);
    setStarting(true);
    setLastError(null);
    try {
      // Single round-trip: start already returns active + first question (no second GET).
      const res = await startBaseTraining(force);
      if (res.started === false && (res.birth_ready || alreadyReady)) {
        setStatus(normalizeStatus(res));
        toast.message("Base training already complete");
        return;
      }
      const normalized = normalizeStatus(res);
      if (normalized.question || isSessionActive(normalized)) {
        setStatus(normalized);
        toast.success("Base training gestart — app only · ~10–12 min");
      } else {
        // Rare: incomplete payload — one status fetch as fallback
        const next = await refresh();
        if (next && isSessionActive(next)) {
          toast.success("Base training gestart — app only · ~10–12 min");
        } else {
          toast.message(String(res.message || "Session response received — probeer opnieuw laden"));
        }
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Start failed";
      setLastError(msg);
      toast.error(msg);
    } finally {
      setBusy(false);
      setStarting(false);
    }
  };

  const handleChoice = async (choiceId: string) => {
    if (!question) return;
    setBusy(true);
    setLastError(null);
    try {
      const out = (await submitBaseAnswer({
        question_id: question.question_id,
        choice_id: choiceId,
        clarify,
        session_id: status?.session_id,
      })) as { progress?: TwinBaseStatus };
      setClarify("");
      if (out.progress) {
        setStatus({
          ...out.progress,
          active:
            out.progress.active === true ||
            out.progress.status === "in_progress" ||
            out.progress.status === "ready_to_complete",
        });
      } else {
        await refresh();
      }
      const prog =
        out.progress ??
        (await fetchBaseStatus().catch(() => null)) ??
        status;
      if (
        prog &&
        (prog.status === "ready_to_complete" ||
          (prog.answered != null &&
            prog.total != null &&
            prog.answered >= prog.total))
      ) {
        const done = await completeBaseTraining();
        toast.success(String(done.message || "Twin base training complete — Birth-ready"));
        await refresh();
        onCompleted?.();
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Answer failed";
      setLastError(msg);
      toast.error(msg);
    } finally {
      setBusy(false);
    }
  };

  const pct = Number(
    status?.progress_pct ??
      readiness?.base_training_completion_pct ??
      (alreadyReady ? 100 : 0),
  );
  const eta = status?.estimated_seconds_left ?? readiness?.estimated_seconds_left ?? 0;
  const chipState = alreadyReady
    ? "ok"
    : sessionActive || pct > 0
      ? "partial"
      : "idle";

  return (
    <div
      className={cn("twin-training-panel", className)}
      data-variant={variant}
      data-app-only="true"
    >
      <div className="twin-training-panel__header">
        <div className="min-w-0 flex-1">
          <p className="twin-training-panel__eyebrow">Foundation · app only</p>
          <p className="twin-training-panel__title">Twin base training</p>
        </div>
        <span className="twin-training-chip" data-state={chipState}>
          {alreadyReady ? "Birth-ready" : sessionActive ? "In progress" : "Required"}
        </span>
        <span className="twin-training-meta">
          {pct.toFixed(0)}% · ~{Math.max(0, Math.ceil(eta / 60))} min
        </span>
      </div>

      <div className="twin-training-progress" aria-hidden>
        <div
          className="twin-training-progress__fill"
          style={{ width: `${Math.min(100, Math.max(0, pct))}%` }}
        />
      </div>

      <p className="twin-training-copy">
        Forced-choice training van <strong className="text-white/85">jouw</strong> REAL-conscience
        (kapitaalbehoud, mutatie, regime, drawdown). Geen Telegram — alleen in de app.
      </p>

      {!alreadyReady ? (
        <p className="twin-training-banner">
          <strong>Eén Twin-DNA · dual authority:</strong> antwoorden alsof kapitaal telt (REAL /
          sim_real_guard). In pure SIM/Birth blokkeert de Twin de leerlus niet — jouw labels zijn
          de standaard wanneer kapitaal wél telt. Geen “altijd approve omdat SIM”.
        </p>
      ) : null}

      {variant === "deck" && !alreadyReady ? (
        <p className="twin-training-banner">
          Primair pad: <strong>Operator Vault → Twin</strong>. Zonder basistraining start Birth
          niet.
        </p>
      ) : null}

      {variant === "vault" && !alreadyReady ? (
        <p className="twin-training-banner" data-tone="warn">
          Bouwsteen verplicht · seal + Birth geblokkeerd tot complete.
        </p>
      ) : null}

      {lastError ? (
        <p className="twin-training-banner" data-tone="warn" role="alert">
          {lastError}
        </p>
      ) : null}

      {!sessionActive && !alreadyReady && !starting ? (
        <button
          type="button"
          className="onboarding-cta rounded-md px-3 py-2 text-[0.65rem]"
          disabled={busy}
          onClick={() => void handleStart(false)}
        >
          Start base training
        </button>
      ) : null}

      {/* Immediate feedback while first question is loading (avoids “broken” feel) */}
      {starting ? (
        <div className="twin-training-question twin-training-question--loading" aria-busy="true">
          <p className="twin-training-question__axis">Laden…</p>
          <p className="twin-training-question__scenario">
            Base training wordt gestart — eerste vraag verschijnt zo.
          </p>
          <div className="twin-training-skeleton" />
          <div className="twin-training-skeleton twin-training-skeleton--short" />
          <div className="twin-training-skeleton twin-training-skeleton--short" />
        </div>
      ) : null}

      {alreadyReady && !sessionActive ? (
        <button
          type="button"
          className="onboarding-btn-secondary rounded-md px-3 py-2 font-mono text-[0.55rem] tracking-wider uppercase"
          disabled={busy}
          onClick={() => void handleStart(true)}
        >
          Retrain base (force)
        </button>
      ) : null}

      {sessionActive && question ? (
        <article className="twin-training-question">
          <p className="twin-training-question__axis">
            {question.axis} · {question.question_id}
            {question.metrics_hint ? ` · ${question.metrics_hint}` : ""}
            {status?.answered != null && status?.total != null
              ? ` · ${status.answered + 1}/${status.total}`
              : ""}
          </p>
          <p className="twin-training-question__scenario whitespace-pre-wrap">
            {question.scenario}
          </p>
          {question.metrics_hint ? (
            <p className="twin-training-meta mb-2">
              Kerngetallen: {question.metrics_hint}
            </p>
          ) : null}
          <div className="twin-training-choices">
            {question.choices.map((c) => (
              <button
                key={c.id}
                type="button"
                className="twin-training-choice"
                disabled={busy}
                onClick={() => void handleChoice(c.id)}
              >
                <span className="twin-training-choice__id">{c.id}</span>
                <span className="twin-training-choice__label">{c.label}</span>
              </button>
            ))}
          </div>
          {question.allow_clarify !== false ? (
            <label className="twin-training-clarify">
              <span>Clarify (optioneel, max 280)</span>
              <textarea
                maxLength={280}
                value={clarify}
                onChange={(e) => setClarify(e.target.value)}
                placeholder="Waarom? (optioneel)"
              />
            </label>
          ) : null}
        </article>
      ) : null}

      {sessionActive && !question && !busy ? (
        <div className="twin-training-banner" data-tone="warn">
          Sessie actief maar geen vraag geladen.{" "}
          <button
            type="button"
            className="underline"
            onClick={() => void refresh()}
          >
            Opnieuw laden
          </button>
        </div>
      ) : null}
    </div>
  );
}
