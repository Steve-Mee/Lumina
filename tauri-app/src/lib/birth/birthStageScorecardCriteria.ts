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
      id: "selectivity",
      goalLabel: `>=${stageTarget} trades | occupancy 30-70% | median loss R <= 1.5`,
      metricLabel: "Occupancy",
      metricTarget: null,
      metricMin: 0.3,
      metricMax: 0.7,
      displayName: "Selectivity",
      curriculumIndex: 2,
    };
  }
  if (stage === "stage3_mixed") {
    return {
      id: "mixed_regimes",
      goalLabel: `>=${stageTarget} trades | occupancy 25-75% | edge >= -5pp vs first-touch`,
      metricLabel: "Edge vs first-touch",
      metricTarget: null,
      metricMin: -0.05,
      metricMax: null,
      displayName: "Mixed regimes",
      curriculumIndex: 3,
    };
  }
  if (stage === "stage4_viable_plant") {
    return {
      id: "viable_plant",
      goalLabel: `>=${stageTarget} trades | skill WR >= first-touch AND mean R >= E_mech-0.10`,
      metricLabel: "Edge vs first-touch",
      metricTarget: null,
      metricMin: 0,
      metricMax: null,
      displayName: "Viable plant",
      curriculumIndex: 4,
    };
  }
  if (stage === "stage5_probe_handoff") {
    return {
      id: "probe_handoff",
      goalLabel: `>=${stageTarget} trades | holdout edge >= -3pp | Sharpe > -2 | DD <= 25%`,
      metricLabel: "OOS edge",
      metricTarget: null,
      metricMin: -0.03,
      metricMax: null,
      displayName: "Probe & handoff",
      curriculumIndex: 5,
    };
  }
  return {
    id: "closed_loop",
    goalLabel: `>=${stageTarget} trades | median loss R <= 1.5 | settlement | entropy alive`,
    metricLabel: "Median loss R",
    metricTarget: null,
    metricMin: null,
    metricMax: 1.5,
    displayName: "Closed loop",
    curriculumIndex: 1,
  };
}
