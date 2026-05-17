import { useState } from "react";
import BirthPhasePanel from "./components/BirthPhasePanel";
import MonitoringDashboard from "./components/MonitoringDashboard";

type AppTab = "birth" | "monitoring";

export default function App(): JSX.Element {
  const [tab, setTab] = useState<AppTab>("birth");

  return (
    <>
      <nav className="fixed bottom-6 left-1/2 z-50 flex -translate-x-1/2 gap-1 rounded-full border border-[#00f0ff]/20 bg-black/80 p-1 shadow-2xl backdrop-blur-md">
        <TabButton active={tab === "birth"} onClick={() => setTab("birth")} label="Birth Phase" />
        <TabButton active={tab === "monitoring"} onClick={() => setTab("monitoring")} label="Monitoring" />
      </nav>
      {tab === "birth" ? <BirthPhasePanel /> : <MonitoringDashboard />}
    </>
  );
}

function TabButton({
  active,
  onClick,
  label,
}: {
  active: boolean;
  onClick: () => void;
  label: string;
}): JSX.Element {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-full px-4 py-2 text-sm font-medium transition-colors ${
        active
          ? "bg-gradient-to-r from-[#00f0ff]/25 to-[#00ff9f]/20 text-white"
          : "text-zinc-400 hover:text-zinc-200"
      }`}
    >
      {label}
    </button>
  );
}
