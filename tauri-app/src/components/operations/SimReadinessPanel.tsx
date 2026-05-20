import { useCallback, useEffect, useState } from "react";
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Rocket } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { TrainingControlBar } from "@/components/operations/TrainingControlBar";
import { fetchStabilityReport, type StabilityReport } from "@/lib/opsClient";
import { goLiveReal, runOvernightSim } from "@/lib/runtimeClient";
import {
  ANNEX_CHART_AXIS_TICK,
  ANNEX_CHART_COLORS,
  ANNEX_CHART_TOOLTIP_STYLE,
} from "@/lib/ppoEvolutionChartTheme";
import { cn } from "@/lib/utils";

function CriteriaTile({
  label,
  ok,
  detail,
}: {
  label: string;
  ok: boolean;
  detail: string;
}) {
  return (
    <div
      className={cn(
        "analytics-annex__metric",
        ok ? "border-emerald-500/20" : "border-red-500/20",
      )}
    >
      <p className="font-mono text-[9px] uppercase text-muted-foreground">{label}</p>
      <p className={cn("mt-1 text-sm font-medium", ok ? "text-emerald-300" : "text-red-300")}>
        {ok ? "PASS" : "FAIL"}
      </p>
      <p className="mt-0.5 font-mono text-[10px] text-muted-foreground">{detail}</p>
    </div>
  );
}

export function SimReadinessPanel({ className }: { className?: string }) {
  const [report, setReport] = useState<StabilityReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [runningSim, setRunningSim] = useState(false);
  const [realConfirm, setRealConfirm] = useState(false);
  const [goingLive, setGoingLive] = useState(false);

  const refresh = useCallback(async () => {
    try {
      setReport(await fetchStabilityReport());
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Stability report failed");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
    const id = window.setInterval(() => void refresh(), 30_000);
    return () => window.clearInterval(id);
  }, [refresh]);

  const criteria = (report?.criteria ?? {}) as Record<string, Record<string, unknown>>;
  const consecutive = Number(report?.consecutive_green_days ?? 0);
  const daysToGreen = Number(report?.days_to_green ?? 5);
  const isGreen = Boolean(report?.READY_FOR_REAL);
  const streakPct = daysToGreen > 0 ? Math.min(100, (consecutive / daysToGreen) * 100) : 0;

  const sharpeHistory = Array.isArray(report?.history_tail)
    ? (report!.history_tail as Array<{ day: string; sharpe_annualized: number }>)
    : [];

  return (
    <div className={cn("flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto p-1", className)}>
      <div className="flex items-center gap-2">
        <Rocket className="size-4 text-muted-foreground/70" />
        <h3 className="analytics-annex__section-title text-[11px]">
          SIM Readiness
        </h3>
        <span
          className={cn(
            "ml-auto rounded px-2 py-0.5 font-mono text-[9px] uppercase",
            isGreen ? "bg-emerald-950/40 text-emerald-300" : "bg-red-950/40 text-red-300",
          )}
        >
          {String(report?.status ?? "UNKNOWN")}
        </span>
      </div>

      {loading && !report ? (
        <p className="text-xs text-muted-foreground">Loading stability report…</p>
      ) : null}

      <div className="analytics-annex__metric p-3">
        <p className="analytics-annex__section-title mb-2">
          5-day green streak — {consecutive}/{daysToGreen}
        </p>
        <div className="h-2 overflow-hidden rounded-full bg-white/5">
          <div
            className="h-full rounded-full transition-all duration-500"
            style={{
              width: `${streakPct}%`,
              background: ANNEX_CHART_COLORS.explainedVariance,
            }}
          />
        </div>
      </div>

      {sharpeHistory.length > 0 ? (
        <div className="analytics-annex__metric p-3" style={{ height: 160 }}>
          <p className="analytics-annex__section-title mb-2">Rolling Sharpe (7d)</p>
          <ResponsiveContainer width="100%" height="85%">
            <LineChart data={sharpeHistory}>
              <XAxis dataKey="day" tick={ANNEX_CHART_AXIS_TICK} />
              <YAxis tick={ANNEX_CHART_AXIS_TICK} width={36} />
              <Tooltip contentStyle={ANNEX_CHART_TOOLTIP_STYLE} />
              <Line type="monotone" dataKey="sharpe_annualized" stroke={ANNEX_CHART_COLORS.policyLoss} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      ) : null}

      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
        <CriteriaTile
          label="5d Expectancy"
          ok={Boolean(criteria.positive_expectancy_5d?.ok)}
          detail={`streak ${String(criteria.positive_expectancy_5d?.streak_days ?? 0)}/5`}
        />
        <CriteriaTile
          label="Extended Sharpe"
          ok={Boolean(criteria.extended_run_sharpe?.ok)}
          detail={String(criteria.extended_run_sharpe?.latest_sharpe ?? "—")}
        />
        <CriteriaTile
          label="Consistent Sharpe"
          ok={Boolean(criteria.consistent_sharpe?.ok)}
          detail={`avg ${String(criteria.consistent_sharpe?.average_sharpe ?? "—")}`}
        />
        <CriteriaTile
          label="Zero Risk / VaR"
          ok={Boolean(criteria.zero_risk_and_var?.ok)}
          detail={`events ${String(criteria.zero_risk_and_var?.total_risk_events ?? 0)}`}
        />
        <CriteriaTile
          label="Proposal Trend"
          ok={Boolean(criteria.evolution_proposals_trend?.ok)}
          detail={`7d slope ${String(criteria.evolution_proposals_trend?.slope_7d ?? "—")}`}
        />
      </div>

      <TrainingControlBar className="mt-1" />

      <Button
        type="button"
        size="sm"
        disabled={runningSim}
        onClick={() => {
          setRunningSim(true);
          void runOvernightSim(240)
            .then((r) => toast.success(r.message))
            .catch((e) => toast.error(e instanceof Error ? e.message : "Overnight SIM failed"))
            .finally(() => setRunningSim(false));
        }}
      >
        Run Overnight SIM (240m)
      </Button>

      {isGreen ? (
        <div className="rounded-lg border border-amber-500/25 bg-amber-950/20 p-3">
          <label className="flex items-start gap-2 text-xs text-amber-100/90">
            <input
              type="checkbox"
              className="mt-0.5"
              checked={realConfirm}
              onChange={(e) => setRealConfirm(e.target.checked)}
            />
            I confirm switch to REAL mode (writes .env — restart engine after)
          </label>
          <Button
            type="button"
            size="sm"
            className="mt-3 bg-amber-700/80"
            disabled={!realConfirm || goingLive}
            onClick={() => {
              setGoingLive(true);
              void goLiveReal()
                .then((r) => toast.success(r.message))
                .catch((e) => toast.error(e instanceof Error ? e.message : "Go-live failed"))
                .finally(() => setGoingLive(false));
            }}
          >
            Switch to REAL Mode
          </Button>
        </div>
      ) : (
        <p className="text-xs text-muted-foreground">
          REAL mode locked until 5 consecutive positive-expectancy days ({consecutive}/{daysToGreen}).
        </p>
      )}
    </div>
  );
}
