/** Ongoing dual-channel micro training (app + Telegram). Not base curriculum. */
import { useState } from "react";
import { toast } from "sonner";

import {
  startMicroSession,
  submitMicroAnswer,
  type TwinMcQuestion,
} from "@/lib/twinClient";
import "@/styles/twinTraining.css";

type MicroItem = {
  pending_id: string;
  question?: TwinMcQuestion;
  expires_at?: string;
};

export function TwinMicroSessionCard({ onDone }: { onDone?: () => void }) {
  const [busy, setBusy] = useState(false);
  const [items, setItems] = useState<MicroItem[]>([]);
  const [index, setIndex] = useState(0);
  const [clarify, setClarify] = useState("");

  const current = items[index] ?? null;
  const question = current?.question;

  const start = async () => {
    setBusy(true);
    try {
      const res = (await startMicroSession({
        count: 3,
        dual_channel: true,
        notify_telegram: true,
      })) as { items?: MicroItem[]; count?: number };
      const list = Array.isArray(res.items) ? res.items : [];
      setItems(list);
      setIndex(0);
      setClarify("");
      toast.success(
        `Micro-session: ${list.length} vragen · Deck + Telegram (dual-channel)`,
      );
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Micro start failed");
    } finally {
      setBusy(false);
    }
  };

  const answer = async (choiceId: string) => {
    if (!current) return;
    setBusy(true);
    try {
      await submitMicroAnswer({
        pending_id: current.pending_id,
        choice_id: choiceId,
        clarify,
      });
      setClarify("");
      const next = index + 1;
      if (next >= items.length) {
        toast.success("Micro-session complete — Twin updated");
        setItems([]);
        setIndex(0);
        onDone?.();
      } else {
        setIndex(next);
        toast.message(`Micro ${next + 1}/${items.length}`);
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Micro answer failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="twin-training-panel">
      <div className="twin-training-panel__header">
        <div className="min-w-0 flex-1">
          <p className="twin-training-panel__eyebrow">Ongoing · dual channel</p>
          <p className="twin-training-panel__title">Micro training</p>
        </div>
        <span className="twin-training-chip" data-state={current ? "partial" : "idle"}>
          {current ? `${index + 1}/${items.length}` : "Idle"}
        </span>
      </div>
      <p className="twin-training-copy">
        2–3 korte forced-choice vragen per sessie. Identieke payload in Command Deck en
        Telegram — eerste antwoord wint. Base curriculum zit hier <strong>niet</strong> in.
      </p>
      {!current ? (
        <button
          type="button"
          className="onboarding-cta rounded-md px-3 py-2 text-[0.65rem]"
          disabled={busy}
          onClick={() => void start()}
        >
          {busy ? "Starting…" : "Start micro session"}
        </button>
      ) : question ? (
        <article className="twin-training-question">
          <p className="twin-training-question__axis">
            micro · {question.question_id || current.pending_id.slice(0, 10)}
          </p>
          <p className="twin-training-question__scenario whitespace-pre-wrap">
            {question.scenario}
          </p>
          {question.metrics_hint ? (
            <p className="twin-training-meta mb-2">Kerngetallen: {question.metrics_hint}</p>
          ) : null}
          <div className="twin-training-choices">
            {(question.choices || []).map((c) => (
              <button
                key={c.id}
                type="button"
                className="twin-training-choice"
                disabled={busy}
                onClick={() => void answer(c.id)}
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
            />
          </label>
        </article>
      ) : null}
    </div>
  );
}
