/** Twin API types (store/HUD residual split). */

export type TwinDecision = "approve" | "reject" | "modify";

export type TwinStakes = "high" | "routine";

export type TwinModeTarget = "assisted" | "full_auto" | "advisory" | "active";

export interface TwinReviewItem {
  dna_hash?: string;
  score?: number;
  confidence?: number;
  recommendation?: boolean;
  explanation?: string;
  risk_flags?: string[];
  stakes?: TwinStakes;
  already_labeled?: boolean;
  outcome?: string;
  timestamp?: string;
  [key: string]: unknown;
}

export interface TwinReviewQueueResponse {
  items: TwinReviewItem[];
  count: number;
  high_stakes_count?: number;
  include_labeled?: boolean;
  local_only?: boolean;
  path?: string;
}

export interface TwinLabelRecord {
  vraag: string;
  steve_antwoord: string;
  timestamp: string;
  context_dna_hash: string;
  confidence_score: number;
}

export interface TwinConfidenceDistribution {
  lt_50?: number;
  b50_60?: number;
  b60_80?: number;
  gte_80?: number;
  n?: number;
}

export interface TwinOutcomeCounts {
  auto_approved?: number;
  veto?: number;
  deferred?: number;
  other?: number;
}

export interface TwinModeReadiness {
  assisted?: boolean | Record<string, unknown>;
  full_auto?: boolean | Record<string, unknown>;
  [key: string]: unknown;
}

export interface TwinRollingAgreement {
  w20?: number | null;
  w50?: number | null;
  w100?: number | null;
  w20_n?: number;
  w50_n?: number;
  w100_n?: number;
  [key: string]: number | null | undefined;
}

export interface TwinAgreementPeriod {
  period?: string;
  samples?: number;
  agreement_pct?: number;
  false_positive_pct?: number;
}

export interface TwinCalibrationBucket {
  n?: number;
  mean_conf?: number | null;
  agreement_rate?: number | null;
  twin_approve_rate?: number | null;
  gt_approve_rate?: number | null;
}

export interface TwinCalibration {
  scored_samples?: number;
  buckets?: Record<string, TwinCalibrationBucket>;
  high_conf_threshold?: number;
  high_conf_samples?: number;
  high_conf_agreement_pct?: number | null;
  mean_abs_calibration_error?: number | null;
  last_avg_error?: number | null;
}

export interface TwinPromotionCriterionProgress {
  current?: number;
  required?: number;
  max_allowed?: number;
  ratio?: number;
}

export interface TwinModeTargetProgress {
  target?: string;
  ready?: boolean;
  fail_reasons?: string[];
  reason?: string;
  samples?: TwinPromotionCriterionProgress;
  agreement?: TwinPromotionCriterionProgress;
  false_positive?: TwinPromotionCriterionProgress;
  risk_flags_caught?: TwinPromotionCriterionProgress;
  constitution_adherence_pct?: number;
}

export interface TwinModePromotionProgress {
  current_mode?: string;
  authority?: string;
  thresholds?: Record<string, unknown>;
  progress?: {
    assisted?: TwinModeTargetProgress;
    full_auto?: TwinModeTargetProgress;
  };
  recent_promotions?: Record<string, unknown>[];
}

export interface TwinMetrics {
  avg_prediction_error?: number | null;
  reward?: number | null;
  training_steps?: number;
  threshold?: number;
  last_avg_error?: number | null;
  twin_steve_agreement_pct?: number | null;
  samples?: number | null;
  labels_total_recent_cap?: number;
  local_only?: boolean;
  model_path?: string;
  decisions_path?: string;
  training_path?: string;
  mode?: string;
  authority?: string;
  twin_agreement_pct?: number | null;
  false_positives?: number | null;
  false_positive_pct?: number | null;
  false_negatives?: number | null;
  risk_flags_caught?: number | null;
  risk_flags_caught_pct?: number | null;
  risk_flags_missed?: number | null;
  risk_flags_missed_pct?: number | null;
  risk_flags_catch_rate_pct?: number | null;
  constitution_adherence_pct?: number | null;
  mode_samples?: number | null;
  mode_readiness?: TwinModeReadiness | null;
  mode_metrics?: Record<string, unknown> | null;
  decisions_total?: number;
  decision_window?: number;
  confidence_distribution?: TwinConfidenceDistribution | null;
  outcome_counts?: TwinOutcomeCounts | null;
  risk_flag_top?: Record<string, number> | null;
  rolling_agreement?: TwinRollingAgreement | null;
  agreement_over_time?: TwinAgreementPeriod[] | null;
  calibration?: TwinCalibration | null;
  mode_promotion_progress?: TwinModePromotionProgress | null;
  promotion_audit_tail?: Record<string, unknown>[] | null;
}

export interface TwinModeStatus {
  mode?: string;
  authority?: string;
  readiness?: TwinModeReadiness;
  mode_promotion_progress?: TwinModePromotionProgress;
  local_only?: boolean;
  [key: string]: unknown;
}

export interface TwinLabelResponse {
  recorded: boolean;
  decision: TwinDecision;
  label: string;
  record: TwinLabelRecord;
  rlhf?: Record<string, unknown> | null;
  audit?: Record<string, string>;
  local_only?: boolean;
  metrics?: TwinMetrics | null;
}

export interface TwinTrainResponse {
  result?: Record<string, unknown>;
  metrics?: TwinMetrics | null;
  local_only?: boolean;
  [key: string]: unknown;
}

export interface TwinPromoteResponse {
  promoted?: boolean;
  reason?: string;
  mode?: string;
  result?: Record<string, unknown>;
  [key: string]: unknown;
}
