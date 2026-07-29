export function inferPassCriteriaFromStage(
  curriculumStage: string,
  stageTarget: number,
): {
  id: string;
  goalLabel: string;
  metricLabel: string;
  metricTarget: number | null;
  metricMin: number | null;
  metricMax: number | null;
  displayName: string;
  curriculumIndex: number;
} {
  const stage = curriculumStage.toLowerCase();
  if (stage === "stage2_range") {
    return {
      id: "range_edgescore",
      goalLabel: `>=${stageTarget} trades | EdgeScore | flat 30-70% | entropy alive | expectancy >= -15%`,
      metricLabel: "EdgeScore",
      metricTarget: null,
      metricMin: 0.3,
      metricMax: 0.7,
      displayName: "Range patience",
      curriculumIndex: 2,
    };
  }
  if (stage === "stage3_mixed") {
    return {
      id: "mixed_edgescore",
      goalLabel: `>=${stageTarget} trades | EdgeScore | hygiene WR>=35% (lifetime or rolling) | hold cap | entropy alive | expectancy >= -15%`,
      metricLabel: "EdgeScore",
      metricTarget: null,
      metricMin: null,
      metricMax: 0.7,
      displayName: "Mixed regimes",
      curriculumIndex: 3,
    };
  }
  return {
    id: "trend_edgescore",
    goalLabel: `>=${stageTarget} trades | EdgeScore | hygiene WR>=35% (lifetime or rolling) | hold band | entropy alive | expectancy >= -15% (WR 45% recommended)`,
    metricLabel: "EdgeScore",
    metricTarget: null,
    metricMin: null,
    metricMax: null,
    displayName: "Trend",
    curriculumIndex: 1,
  };
}
