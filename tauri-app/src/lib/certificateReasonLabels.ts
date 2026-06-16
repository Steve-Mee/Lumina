const CERTIFICATE_REASON_LABELS: Record<string, string> = {
  missing_or_invalid_certificate: "Certificate missing or invalid",
  certificate_thresholds_not_met: "OOS thresholds not met",
  certificate_integrity_version_invalid: "Certificate integrity version invalid",
  missing_policy_zip: "Policy zip missing",
  policy_hash_mismatch: "Policy hash mismatch",
  policy_read_failed: "Policy file unreadable",
  v1_compat_missing_artifacts: "Legacy artifacts missing",
};

export function formatCertificateReason(reason: unknown): string {
  const key = String(reason ?? "").trim();
  if (!key) return "Certificate validation failed";
  return CERTIFICATE_REASON_LABELS[key] ?? key.replace(/_/g, " ");
}
