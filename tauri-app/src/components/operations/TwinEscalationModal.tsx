/** Global Twin doubt escalation modal — dual-channel with Telegram (not base curriculum). */
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";

import {
  fetchPendingEscalations,
  resolveEscalation,
  type TwinEscalationItem,
} from "@/lib/twinClient";
import "@/styles/twinTraining.css";

const POLL_MS = 8000;

export function TwinEscalationModal() {
  const [item, setItem] = useState<TwinEscalationItem | null>(null);
  const [clarify, setClarify] = useState("");
  const [busy, setBusy] = useState(false);

  const poll = useCallback(async () => {
    try {
      const res = await fetchPendingEscalations();
      const first = res.items?.[0] ?? null;
      setItem(first);
    } catch {
      /* soft-fail poll */
    }
  }, []);

  useEffect(() => {
    void poll();
    const t = window.setInterval(() => void poll(), POLL_MS);
    return () => window.clearInterval(t);
  }, [poll]);

  if (!item) return null;

  const eid = String(item.escalation_id || item.pending_id || "");
  const q = item.question;
  if (!q || !eid) return null;

  const onChoose = async (choiceId: string) => {
    setBusy(true);
    try {
      await resolveEscalation(eid, { choice_id: choiceId, clarify });
      toast.success(`Twin escalatie opgelost: ${choiceId}`);
      setClarify("");
      setItem(null);
      void poll();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Resolve failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      className="twin-escalation-backdrop"
      role="dialog"
      aria-modal="true"
      aria-label="Twin escalation"
    >
      <div className="twin-escalation-card">
        <p className="twin-escalation-card__eyebrow">
          Twin doubt · human judgment · deck + telegram
        </p>
        <div className="twin-training-panel__header mb-2">
          <p className="twin-training-panel__title">Escalatie</p>
          <span className="twin-training-chip" data-state="warn">
            Pending
          </span>
        </div>
        <p className="twin-training-meta mb-2">
          id={eid.slice(0, 12)}… · dna={String(item.dna_hash || "").slice(0, 16)}
        </p>
        <p className="twin-training-question__scenario mb-3 whitespace-pre-wrap">
          {q.scenario}
        </p>
        <div className="twin-training-choices">
          {q.choices.map((c) => (
            <button
              key={c.id}
              type="button"
              className="twin-training-choice"
              disabled={busy}
              onClick={() => void onChoose(c.id)}
            >
              <span className="twin-training-choice__id">{c.id}</span>
              <span className="twin-training-choice__label">{c.label}</span>
            </button>
          ))}
        </div>
        <label className="twin-training-clarify">
          <span>Clarify (optioneel)</span>
          <textarea
            maxLength={280}
            value={clarify}
            onChange={(e) => setClarify(e.target.value)}
            placeholder="Waarom? (optioneel)"
          />
        </label>
        <p className="twin-training-meta mt-2">
          Antwoord hier of via Telegram (TWIN &lt;id&gt; A/B/C/D) — eerste wint. Twin leert
          direct. Base curriculum nooit via Telegram.
        </p>
      </div>
    </div>
  );
}
