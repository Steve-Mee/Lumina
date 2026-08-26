# ADR-0042: Identity, PKI/mTLS Foundation, and Encryption-at-Rest

**Status:** Accepted  
**Date:** 2026-08-11  
**Deciders:** LUMINA Engineering  
**Related:** ADR-0040, ADR-0041, SECURITY_HARDENING.md

## Context

After 30d Fabric-first law and 90d Sentinel contain plane, residual production
gaps are identity lifecycle, transport PKI for non-loopback Fabric, and
encryption of sensitive state at rest.

## Decision

### 1. Admin API key rotation (dual-key grace)

- Module: `lumina_core/api_key_rotation.py`
- Endpoint: `POST /api/sentinel/rotate-admin-key` (admin + confirm)
- Env SSOT:
  - `LUMINA_ADMIN_API_KEY` (current)
  - `LUMINA_ADMIN_API_KEY_PREVIOUS` (grace)
  - `LUMINA_API_KEY_GRACE_UNTIL` (unix)
- `APIKeyAuthenticator.verify_api_key` accepts previous during grace
- Default grace 24h (1–168h configurable)

### 2. Encryption-at-rest

- Module: `lumina_core/crypto_at_rest.py`
- Key: `LUMINA_STATE_ENCRYPTION_KEY` (Fernet url-safe or passphrase-derived)
- Envelope prefix `LUMINA1:` for versioned ciphertext
- When key set: Sentinel containment JSON encrypted; readers decrypt fail-closed
- When key unset: plaintext local-dev remains valid

### 3. Fabric TLS / mTLS foundation

- Module: `lumina_core/mtls_config.py`
- Env:
  - `LUMINA_FABRIC_TLS_CA` (required to enable TLS channel)
  - `LUMINA_FABRIC_TLS_CERT` + `LUMINA_FABRIC_TLS_KEY` (mTLS client)
  - `LUMINA_FABRIC_TLS_SERVER_NAME` (SNI override, default localhost)
- `FabricGrpcClient` uses `build_grpc_channel` — secure when CA set, else
  insecure localhost (ADR-0035 default)

### 4. Explicitly deferred (still)

- Full OAuth2/OIDC / MFA IdP integration
- Automated scheduled rotation without operator command
- OS-level network quarantine
- Self-evolving IDS rule promotion

## Consequences

### Positive
- Operators can rotate keys without hard downtime
- Sensitive containment state can be encrypted
- Path to remote Fabric without silent insecure multi-host

### Negative
- Ops must manage Fernet key backup (loss = unreadable encrypted state)
- Fabric server must present matching TLS certs when client enables TLS

## Alternatives considered

1. Always-on TLS even for 127.0.0.1 — rejected (local Tauri friction; loopback risk acceptable with bind gate)
2. Asymmetric vault (HashiCorp) only — future; local Fernet is foundation

## Links

- `lumina_core/api_key_rotation.py`
- `lumina_core/crypto_at_rest.py`
- `lumina_core/mtls_config.py`
- `POST /api/sentinel/rotate-admin-key`
