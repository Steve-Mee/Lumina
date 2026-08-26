/** Live Twin judgment feed — same content as Telegram (Q / A / why + feedback). */
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";

import {
  fetchTwinDecisionsRecent,
  postTwinDecisionFeedback,
  type TwinDecisionFeedItem,
} from "@/lib/twinClient";
import { cn } from "@/lib/utils";
import "@/styles/twinTraining.css";

const POLL_MS = 10_000;

export function TwinDecisionFeed({ className }: { className?: string }) {
  const [items, setItems] = useState<TwinDecisionFeedItem[]>([]);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [notes, setNotes] = useState<Record<string, string>>({});

  const refresh = useCallback(async () => {
    try {
      const res = await fetchTwinDecisionsRecent(12);
      setItems(res.items ?? []);
    } catch {
      /* soft */
    }
  }, []);

  useEffect(() => {
    void refresh();
    const t = window.setInterval(() => void refresh(), POLL_MS);
    return () => window.clearInterval(t);
  }, [refresh]);

  const feedback = async (id: string, action: "OK" | "A" | "V" | "M") => {
    setBusyId(id);
    try {
      await postTwinDecisionFeedback(id, {
        action,
        notes: notes[id] ?? "",
      });
      toast.success(
        action === "OK"
          ? "Twin bevestigd — label opgeslagen"
          : `Twin gecorrigeerd (${action}) — leert direct`,
      );
      setNotes((n) => ({ ...n, [id]: "" }));
      await refresh();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Feedback failed");
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div className={cn("twin-training-panel", className)}>
      <div className="twin-training-panel__header">
        <div className="min-w-0 flex-1">
          <p className="twin-training-panel__eyebrow">Live · Telegram mirror</p>
          <p className="twin-training-panel__title">Twin besluiten</p>
        </div>
        <span className="twin-training-chip" data-state={items.length ? "partial" : "idle"}>
          {items.length} recent
        </span>
      </div>
      <p className="twin-training-copy">
        Post-hoc audit: Twin heeft al geoordeeld (geen pre-approval). Telegram + dit feed tonen{" "}
        <strong>vraag · antwoord · waarom</strong>. OK/FIX leert de Twin naderhand — het stopt
        geen doorgegeven besluit.
      </p>

      {items.length === 0 ? (
        <p className="twin-training-meta">Nog geen Twin-besluiten in deze sessie.</p>
      ) : null}

      <div className="flex flex-col gap-2">
        {items.map((item) => {
          const id = item.decision_id;
          const done = Boolean(item.feedback);
          return (
            <article key={id} className="twin-training-question">
              <p className="twin-training-question__axis">
                {id.slice(0, 12)} · {item.mode ?? "—"} ·{" "}
                {item.created_at ? String(item.created_at).slice(0, 19) : ""}
                {done ? " · feedback ✓" : ""}
              </p>
              <p className="twin-training-meta mb-1">VRAAG (Lumina)</p>
              <p className="twin-training-question__scenario whitespace-pre-wrap text-[0.75rem]">
                {item.lumina_question || item.explanation || item.dna_hash || "—"}
              </p>
              <p className="twin-training-meta mb-1">TWIN ANTWOORD</p>
              <p className="mb-1 font-mono text-sm text-cyan-100/90">
                {item.twin_answer ||
                  `${item.recommendation ? "APPROVE" : "VETO"} (${Number(item.confidence ?? 0).toFixed(0)}%)`}
              </p>
              <p className="twin-training-meta mb-1">WAAROM</p>
              <p className="mb-2 whitespace-pre-wrap text-[0.7rem] text-white/70">
                {item.why || item.explanation || "—"}
              </p>
              {!done ? (
                <>
                  <label className="twin-training-clarify">
                    <span>Feedback note (optioneel)</span>
                    <textarea
                      maxLength={280}
                      value={notes[id] ?? ""}
                      onChange={(e) =>
                        setNotes((n) => ({
                          ...n,
                          [id]: e.target.value,
                        }))
                      }
                      placeholder="Waarom corrigeren?"
                    />
                  </label>
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    <button
                      type="button"
                      className="onboarding-cta rounded-md px-2 py-1.5 text-[0.58rem]"
                      disabled={busyId === id}
                      onClick={() => void feedback(id, "OK")}
                    >
                      OK
                    </button>
                    <button
                      type="button"
                      className="onboarding-btn-secondary rounded-md px-2 py-1.5 font-mono text-[0.52rem] uppercase"
                      disabled={busyId === id}
                      onClick={() => void feedback(id, "A")}
                    >
                      FIX A
                    </button>
                    <button
                      type="button"
                      className="onboarding-btn-secondary rounded-md px-2 py-1.5 font-mono text-[0.52rem] uppercase"
                      disabled={busyId === id}
                      onClick={() => void feedback(id, "V")}
                    >
                      FIX V
                    </button>
                    <button
                      type="button"
                      className="onboarding-btn-secondary rounded-md px-2 py-1.5 font-mono text-[0.52rem] uppercase"
                      disabled={busyId === id}
                      onClick={() => void feedback(id, "M")}
                    >
                      FIX M
                    </button>
                  </div>
                </>
              ) : (
                <p className="twin-training-meta">
                  Feedback: {JSON.stringify(item.feedback).slice(0, 120)}
                </p>
              )}
            </article>
          );
        })}
      </div>
    </div>
  );
}
