import {
  ConfigRange,
  FieldCard,
  ToggleRow,
} from "@/components/config/BotConfigFormPrimitives";
import { HelpTip } from "@/components/ui/HelpTip";
import type { BotConfigDraft } from "@/lib/botConfigDraft";
import { helpFor } from "@/lib/helpTexts";

export interface BotConfigOperatorTabProps {
  draft: BotConfigDraft;
  onChange: (patch: Partial<BotConfigDraft>) => void;
  className?: string;
}

export function BotConfigOperatorTab({
  draft,
  onChange,
  className,
}: BotConfigOperatorTabProps) {
  return (
    <div className={className}>
      <div className="mb-1 flex items-center gap-1.5">
        <h3 className="bot-config-section-title mb-0">Operator preferences</h3>
      </div>
      <p className="mb-3 text-[11px] leading-relaxed text-muted-foreground">
        Comfort and diagnostics only — these do not change the risk envelope or
        place capital at risk.
      </p>

      <FieldCard label="Comfort">
        <div className="space-y-2">
          <ToggleRow
            label="Voice (TTS + input)"
            tip={helpFor("config_voice_enabled")}
            checked={draft.preferences.voice_enabled}
            onChange={(voice_enabled) =>
              onChange({
                preferences: { ...draft.preferences, voice_enabled },
              })
            }
          />
          <ToggleRow
            label="Live chart screen share"
            tip={helpFor("config_screen_share")}
            checked={draft.preferences.screen_share_enabled}
            onChange={(screen_share_enabled) =>
              onChange({
                preferences: { ...draft.preferences, screen_share_enabled },
              })
            }
          />
        </div>
      </FieldCard>

      <FieldCard label="Diagnostics" className="mt-3">
        <div className="space-y-3">
          <ToggleRow
            label="Dashboard feedback paths"
            tip={helpFor("dashboard_enabled")}
            checked={draft.preferences.dashboard_enabled}
            onChange={(dashboard_enabled) =>
              onChange({
                preferences: { ...draft.preferences, dashboard_enabled },
              })
            }
          />
          <ToggleRow
            label="Runtime trace"
            tip={helpFor("runtime_trace")}
            checked={draft.preferences.runtime_trace}
            onChange={(runtime_trace) =>
              onChange({
                preferences: { ...draft.preferences, runtime_trace },
              })
            }
          />
          <div>
            <div className="mb-1 flex items-center justify-between gap-2">
              <span className="flex items-center gap-1.5 font-mono text-[0.55rem] tracking-wide text-muted-foreground uppercase">
                Runtime trace interval
                <HelpTip text={helpFor("runtime_trace_interval") ?? ""} />
              </span>
              <span className="font-mono text-xs text-cyan-200/80">
                {draft.preferences.runtime_trace_interval_sec}s
              </span>
            </div>
            <ConfigRange
              label="Runtime trace interval"
              hideLabel
              value={draft.preferences.runtime_trace_interval_sec}
              min={0}
              max={10}
              step={1}
              format={(v) => `${v}s`}
              onChange={(v) =>
                onChange({
                  preferences: {
                    ...draft.preferences,
                    runtime_trace_interval_sec: v,
                  },
                })
              }
            />
          </div>
          <div>
            <div className="mb-1 flex items-center justify-between gap-2">
              <span className="flex items-center gap-1.5 font-mono text-[0.55rem] tracking-wide text-muted-foreground uppercase">
                Latency SLA
                <HelpTip text={helpFor("latency_sla") ?? ""} />
              </span>
              <span className="font-mono text-xs text-cyan-200/80">
                {draft.preferences.latency_sla_ms} ms
              </span>
            </div>
            <ConfigRange
              label="Latency SLA"
              hideLabel
              value={draft.preferences.latency_sla_ms}
              min={150}
              max={1000}
              step={50}
              format={(v) => `${v} ms`}
              onChange={(v) =>
                onChange({
                  preferences: { ...draft.preferences, latency_sla_ms: v },
                })
              }
            />
          </div>
        </div>
      </FieldCard>
    </div>
  );
}
