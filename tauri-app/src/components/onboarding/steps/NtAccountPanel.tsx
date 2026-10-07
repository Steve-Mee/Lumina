import { useEffect, useState } from "react";

import { DEMO_HELP, REAL_HELP, validateAccountPair } from "@/lib/ntAccountNames";
import { useNtAccountGateStore } from "@/store/ntAccountGateStore";

/** Demo binds NinjaTrader. Real is stored beside it and is never the bind name. */
export function NtAccountPanel() {
  const snapshot = useNtAccountGateStore((s) => s.snapshot);
  const loaded = useNtAccountGateStore((s) => s.loaded);
  const failed = useNtAccountGateStore((s) => s.failed);
  const loadError = useNtAccountGateStore((s) => s.error);
  const refresh = useNtAccountGateStore((s) => s.refresh);
  const save = useNtAccountGateStore((s) => s.save);
  const [demo, setDemo] = useState("");
  const [real, setReal] = useState("");
  const [hydrated, setHydrated] = useState(false);
  const [saving, setSaving] = useState(false);
  const [note, setNote] = useState("");
  const [formError, setFormError] = useState("");

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    if (!loaded || hydrated || !snapshot) return;
    setDemo(snapshot.demo_account ?? "");
    setReal(snapshot.real_account ?? "");
    setHydrated(true);
  }, [loaded, hydrated, snapshot]);

  const local = validateAccountPair(demo, real);
  const demoHelp = snapshot?.demo_help || DEMO_HELP;
  const realHelp = snapshot?.real_help || REAL_HELP;
  const storedReal = (snapshot?.real_account ?? "").trim();

  const onSubmit = async () => {
    if (!local.ok) {
      setFormError(local.errors.join(" "));
      return;
    }
    setSaving(true);
    setFormError("");
    setNote("");
    try {
      const saved = await save(local.demo, local.real);
      setDemo(saved.demo_account ?? local.demo);
      setReal(saved.real_account ?? local.real);
      setNote(saved.bind_note || "Rekeningen opgeslagen.");
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Opslaan is geweigerd.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <form
      className="space-y-3"
      onSubmit={(e) => {
        e.preventDefault();
        void onSubmit();
      }}
    >
      <p className="text-[11px] leading-relaxed text-white/55">
        Kopieer de namen uit NinjaTrader, Control Center, tab Accounts. Eén rij per veld.
        De demo-naam wordt AccountName. De real-naam wordt RealAccountName en blijft alleen bewaard.
      </p>
      <label className="block space-y-1">
        <span className="font-mono text-[10px] uppercase tracking-wider text-white/70">
          Demo-rekening
        </span>
        <input
          className="onboarding-field w-full font-mono text-[13px]"
          value={demo}
          onChange={(e) => setDemo(e.target.value)}
          autoComplete="off"
          spellCheck={false}
          placeholder="DEMO5042070 of Sim101"
          aria-describedby="nt-demo-help"
        />
        <span id="nt-demo-help" className="block text-[11px] leading-relaxed text-white/45">
          {demoHelp}
        </span>
      </label>
      <label className="block space-y-1">
        <span className="font-mono text-[10px] uppercase tracking-wider text-white/70">
          Real-rekening
        </span>
        <input
          className="onboarding-field w-full font-mono text-[13px]"
          value={real}
          onChange={(e) => setReal(e.target.value)}
          autoComplete="off"
          spellCheck={false}
          placeholder="de live naam uit Accounts"
          aria-describedby="nt-real-help"
        />
        <span id="nt-real-help" className="block text-[11px] leading-relaxed text-white/45">
          {realHelp}
        </span>
      </label>
      <p className="text-[11px] leading-relaxed text-white/50">
        {loaded && snapshot
          ? storedReal
            ? `Opgeslagen demo: ${snapshot.demo_account || "—"}. Real-naam staat in RealAccountName.`
            : `Opgeslagen demo: ${snapshot.demo_account || "—"}. Real-naam is nog leeg.`
          : "De opgeslagen namen worden gelezen."}
        {snapshot?.names_aligned === false
          ? " config.yaml en fabric.json noemen een verschillende demo. Opslaan zet ze gelijk."
          : ""}
        {snapshot?.real_bound
          ? " De server meldt een real-binding. Dat hoort leeg te blijven."
          : " Orders lopen op de demo-rekening. REAL blijft gesloten."}
      </p>
      {failed ? <p className="text-[11px] text-red-300/90">{loadError}</p> : null}
      {formError ? <p className="text-[11px] text-red-300/90">{formError}</p> : null}
      {note ? <p className="text-[11px] text-emerald-200/90">{note}</p> : null}
      <button
        type="submit"
        className="onboarding-cta"
        disabled={!local.ok || saving || !loaded || failed}
      >
        {saving ? "Opslaan…" : "Bewaar rekeningen"}
      </button>
    </form>
  );
}
