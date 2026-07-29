from lumina_core.birth.certificate_pipeline import BirthCertificatePipeline

print("ok", BirthCertificatePipeline)
for name in (
    "ensure_holdout_preflight",
    "run_certificate_remediation",
    "complete_certified_birth",
    "run_stage8_polish_and_certificate",
):
    assert hasattr(BirthCertificatePipeline, name), name
print("methods ok")
