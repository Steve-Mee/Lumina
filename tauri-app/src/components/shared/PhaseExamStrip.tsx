import type { PhaseExamModel } from "@/lib/phaseExamModel";

import { HelpTip } from "@/components/ui/HelpTip";

function Cell({
  label,
  value,
  tip,
}: {
  label: string;
  value: string;
  tip: string;
}) {
  return (
    <p className="phase-exam-strip__cell" title={`${label}: ${value}`}>
      <span className="phase-exam-strip__label inline-flex items-center gap-1">
        {label}
        <HelpTip text={tip} label={`${label} info`} />
      </span>
      <span className="phase-exam-strip__value">{value}</span>
    </p>
  );
}

export function PhaseExamStrip({ exam }: { exam: PhaseExamModel }) {
  const meta = [exam.attemptLine, exam.blockers.length > 0 ? exam.blockers.join(" · ") : ""]
    .filter(Boolean)
    .join(" · ");
  return (
    <section className="phase-exam-strip shrink-0" aria-label="Phase exam">
      <div className="phase-exam-strip__row">
        <Cell label="Goal" value={exam.goal} tip={exam.goal} />
        <Cell
          label="Progress"
          value={exam.progressLine}
          tip={`${exam.progressLine}. This is the live exam clock, not a certificate.`}
        />
        <Cell
          label="Skill"
          value={`${exam.performanceLabel} · ${exam.performanceLine}`}
          tip={`${exam.performanceLabel}: ${exam.performanceLine}`}
        />
      </div>
      {meta ? (
        <p className="phase-exam-strip__meta" title={meta}>
          {meta}
        </p>
      ) : null}
    </section>
  );
}
