# 2026-06-11 — Birth Phase v2 (Musk first-principles)

**Classification**: Architecture + SIM training path (no REAL capital-path change).

**Decision**: ADR-0012/0013/0014 — single SIM SSOT, Birth Certificate v2, curriculum + OOS gate.

**Rollback**: Set `LUMINA_BIRTH_V2_DISABLED=1` for temporary v1 flag+policy guard (documented in ADR-0013).

## Verify

```bash
py -3.13 -m pytest tests/birth -q
py -3.13 -m pytest lumina_os/tests/test_birth_endpoints.py -q
```

## Operator migration

1. Pull latest; run `.\scripts\reset-onboarding-dev.ps1` or delete v1 flags without certificate.
2. Run Birth v2 from Tauri Birth screen until certificate issued.
3. Confirm `GET /api/birth/certificate` returns `certificate_ok: true`.
