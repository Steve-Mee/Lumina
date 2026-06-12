# LUMINA Core API Contracts

> **Version:** 1.0  
> **Status:** Draft — production contract specification  
> **Schema dialect:** JSON Schema Draft 2020-12  
> **Scope:** Neural Command Deck REST and WebSocket contracts under `/api/core/*`, `/api/evolution/*`, `/ws/core/*`, `/ws/evolution`  
> **Companion:** [lumina-core-architecture.md](lumina-core-architecture.md)

---

## Namespace Note

The **`/api/core/*`** and **`/ws/core/*`** paths defined here are the **canonical contract namespace** for the Neural Command Deck. The architecture document's `/api/command-deck/*` and `/ws/v1/command-deck` paths are logical aliases to be unified during backend Phase 1 implementation.

---

## Table of Contents

1. [Conventions](#1-conventions)
2. [Shared Definitions ($defs)](#2-shared-definitions-defs)
3. [GET /api/core/status](#3-get-apicorestatus)
4. [GET /api/evolution/tree](#4-get-apievolutiontree)
5. [POST /api/core/approve-mutation](#5-post-apicoreapprove-mutation)
6. [WS /ws/core/live](#6-ws-wscorelive)
7. [WS /ws/evolution](#7-ws-wsevolution)
8. [SIM vs REAL Mode Delta](#8-sim-vs-real-mode-delta)
9. [Setup & Onboarding — GET /api/setup/onboarding](#9-setup--onboarding--get-apisetuponboarding)
10. [Related Documents](#10-related-documents)

See also [ppo-evolution.md](ppo-evolution.md) for **`/ws/ppo-evolution`** — raw JSONL PPO training metrics during birth phase.

---

## 1. Conventions

### 1.1 Strictness Rules

All schemas in this document enforce:

| Rule | Value |
|------|-------|
| `additionalProperties` | `false` on every object |
| `required` | Explicit on every object |
| `$schema` | `https://json-schema.org/draft/2020-12/schema` |
| `$id` prefix | `https://lumina.local/schemas/core/v1/` |
| Hash format | SHA-256 hex, 64 chars |
| Timestamps | Unix seconds (number) or ISO 8601 UTC (string) |

### 1.2 Authentication

| Transport | Method |
|-----------|--------|
| REST | Header `X-API-Key: <key>` |
| WebSocket | First frame `{ "type": "auth", "token": "<jwt>" }` within 5 seconds |
| JWT issuance | `POST /api/command-deck/ws/token` (see architecture doc) |
| Admin routes | API key with `role: admin` in `config.yaml` `security.api_keys` |

### 1.3 Trade Modes

Aligned with [`lumina_core/engine/mode_capabilities.py`](../lumina_core/engine/mode_capabilities.py):

```
paper | sim | sim_real_guard | real
```

---

## 2. Shared Definitions ($defs)

Central registry reused by all endpoint schemas. Backend validators should import equivalent Pydantic models from [`lumina_core/agent_orchestration/schemas.py`](../lumina_core/agent_orchestration/schemas.py) and [`lumina_core/governance/approval_chain.py`](../lumina_core/governance/approval_chain.py).

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://lumina.local/schemas/core/v1/defs",
  "$defs": {
    "SchemaVersion": {
      "type": "string",
      "const": "1.0"
    },
    "UnixTimestamp": {
      "type": "number",
      "minimum": 0
    },
    "IsoDateTime": {
      "type": "string",
      "format": "date-time"
    },
    "TradeMode": {
      "type": "string",
      "enum": ["paper", "sim", "sim_real_guard", "real"]
    },
    "BrokerBackend": {
      "type": "string",
      "enum": ["paper", "live"]
    },
    "DnaHash": {
      "type": "string",
      "pattern": "^[a-f0-9]{64}$"
    },
    "ProposalHash": {
      "type": "string",
      "minLength": 8,
      "maxLength": 128
    },
    "ModeCapabilities": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "requires_live_broker",
        "risk_enforced",
        "session_guard_enforced",
        "eod_force_close_enabled",
        "is_learning_mode",
        "capital_at_risk",
        "account_mode_hint"
      ],
      "properties": {
        "requires_live_broker": { "type": "boolean" },
        "risk_enforced": { "type": "boolean" },
        "session_guard_enforced": { "type": "boolean" },
        "eod_force_close_enabled": { "type": "boolean" },
        "is_learning_mode": { "type": "boolean" },
        "capital_at_risk": { "type": "boolean" },
        "account_mode_hint": {
          "type": "string",
          "enum": ["paper", "sim", "real"]
        }
      }
    },
    "OperatorContext": {
      "type": "object",
      "additionalProperties": false,
      "required": ["role", "api_key_name"],
      "properties": {
        "role": {
          "type": "string",
          "enum": ["admin", "user", "readonly"]
        },
        "api_key_name": {
          "type": "string",
          "minLength": 1,
          "maxLength": 64
        }
      }
    },
    "ConstitutionViolationSummary": {
      "type": "object",
      "additionalProperties": false,
      "required": ["violations_open", "last_audit_ok", "last_audit_ts", "violation_codes"],
      "properties": {
        "violations_open": {
          "type": "integer",
          "minimum": 0
        },
        "last_audit_ok": { "type": "boolean" },
        "last_audit_ts": {
          "oneOf": [{ "$ref": "#/$defs/UnixTimestamp" }, { "type": "null" }]
        },
        "violation_codes": {
          "type": "array",
          "items": { "type": "string", "minLength": 1 }
        }
      }
    },
    "RealPromotionPayload": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "schema_version",
        "dna_hash",
        "target_mode",
        "dna_content_digest",
        "promotion_epoch",
        "reason_context",
        "created_at",
        "expires_at"
      ],
      "properties": {
        "schema_version": {
          "type": "string",
          "const": "v1"
        },
        "dna_hash": { "$ref": "#/$defs/DnaHash" },
        "target_mode": {
          "type": "string",
          "const": "real"
        },
        "dna_content_digest": {
          "type": "string",
          "pattern": "^[a-f0-9]{64}$"
        },
        "promotion_epoch": {
          "type": "string",
          "minLength": 1
        },
        "reason_context": {
          "type": "string",
          "minLength": 1
        },
        "created_at": { "$ref": "#/$defs/IsoDateTime" },
        "expires_at": { "$ref": "#/$defs/IsoDateTime" }
      }
    },
    "SignedApproval": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "approver_id",
        "public_key_fingerprint",
        "signature_b64",
        "reason",
        "timestamp"
      ],
      "properties": {
        "approver_id": { "type": "string", "minLength": 1 },
        "public_key_fingerprint": { "type": "string", "minLength": 16 },
        "signature_b64": { "type": "string", "minLength": 16 },
        "reason": { "type": "string", "minLength": 1 },
        "timestamp": { "$ref": "#/$defs/IsoDateTime" }
      }
    },
    "HealthStatus": {
      "type": "string",
      "enum": ["healthy", "degraded", "critical", "unknown"]
    },
    "IntelligenceTier": {
      "type": "string",
      "enum": ["light", "standard", "high"]
    },
    "IntelligenceHealth": {
      "type": "string",
      "enum": ["ok", "degraded", "error"]
    },
    "ArbitrationResult": {
      "type": "string",
      "enum": ["approved", "rejected", "pending", "unknown"]
    },
    "MutationDepth": {
      "type": "string",
      "enum": ["conservative", "moderate", "radical"]
    },
    "DnaNodeStatus": {
      "type": "string",
      "enum": ["champion", "active", "candidate", "shadow", "rejected", "promoted", "archived"]
    },
    "ShadowVerdict": {
      "type": "string",
      "enum": ["pass", "fail", "pending"]
    },
    "PromotionStage": {
      "type": "string",
      "enum": ["applied", "shadow_queued", "awaiting_signatures", "rejected", "blocked"]
    },
    "WsCoreLiveChannel": {
      "type": "string",
      "enum": ["health", "intelligence", "risk", "regime", "signals", "execution", "constitution", "system"]
    },
    "WsEvolutionChannel": {
      "type": "string",
      "enum": ["proposals", "shadow", "promotion", "lineage", "mutations"]
    },
    "ErrorBlocker": {
      "type": "object",
      "additionalProperties": false,
      "required": ["code", "message"],
      "properties": {
        "code": { "type": "string", "minLength": 1 },
        "message": { "type": "string", "minLength": 1 }
      }
    },
    "ErrorResponse": {
      "type": "object",
      "additionalProperties": false,
      "required": ["detail", "code", "blockers", "ts"],
      "properties": {
        "detail": { "type": "string", "minLength": 1 },
        "code": { "type": "string", "minLength": 1 },
        "blockers": {
          "type": "array",
          "items": { "$ref": "#/$defs/ErrorBlocker" }
        },
        "ts": { "$ref": "#/$defs/UnixTimestamp" }
      }
    }
  }
}
```

---

## 3. GET /api/core/status

### 3.1 Overview

| Property | Value |
|----------|-------|
| Method | `GET` |
| Path | `/api/core/status` |
| Auth | `X-API-Key` required |
| Purpose | Authoritative organism snapshot for cockpit hydration |

### 3.2 Response Schema

`$id`: `https://lumina.local/schemas/core/v1/CoreStatusResponse`

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://lumina.local/schemas/core/v1/CoreStatusResponse",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "schema_version",
    "ts",
    "mode",
    "health",
    "intelligence",
    "birth",
    "risk",
    "constitution",
    "regime",
    "operator",
    "evolution_summary"
  ],
  "properties": {
    "schema_version": { "$ref": "https://lumina.local/schemas/core/v1/defs#/$defs/SchemaVersion" },
    "ts": { "$ref": "https://lumina.local/schemas/core/v1/defs#/$defs/UnixTimestamp" },
    "mode": {
      "type": "object",
      "additionalProperties": false,
      "required": ["current", "broker_backend", "capabilities"],
      "properties": {
        "current": { "$ref": "https://lumina.local/schemas/core/v1/defs#/$defs/TradeMode" },
        "broker_backend": { "$ref": "https://lumina.local/schemas/core/v1/defs#/$defs/BrokerBackend" },
        "capabilities": { "$ref": "https://lumina.local/schemas/core/v1/defs#/$defs/ModeCapabilities" }
      }
    },
    "health": {
      "type": "object",
      "additionalProperties": false,
      "required": ["status", "uptime_s", "kill_switch_active", "websocket_connected", "issues"],
      "properties": {
        "status": { "$ref": "https://lumina.local/schemas/core/v1/defs#/$defs/HealthStatus" },
        "uptime_s": { "type": "number", "minimum": 0 },
        "kill_switch_active": { "type": "boolean" },
        "websocket_connected": { "type": "boolean" },
        "issues": {
          "type": "array",
          "items": { "type": "string", "minLength": 1 }
        }
      }
    },
    "intelligence": {
      "type": "object",
      "additionalProperties": false,
      "required": ["tier", "health", "model_name", "gpu_available"],
      "properties": {
        "tier": { "$ref": "https://lumina.local/schemas/core/v1/defs#/$defs/IntelligenceTier" },
        "health": { "$ref": "https://lumina.local/schemas/core/v1/defs#/$defs/IntelligenceHealth" },
        "model_name": { "type": "string", "minLength": 1 },
        "gpu_available": { "type": "boolean" }
      }
    },
    "birth": {
      "type": "object",
      "additionalProperties": false,
      "required": ["phase", "progress_pct", "target_trades", "trades_completed"],
      "properties": {
        "phase": {
          "type": "string",
          "enum": ["pending", "in_progress", "complete", "failed"]
        },
        "progress_pct": { "type": "number", "minimum": 0, "maximum": 100 },
        "target_trades": { "type": "integer", "minimum": 0 },
        "trades_completed": { "type": "integer", "minimum": 0 }
      }
    },
    "risk": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "daily_pnl_usd",
        "var_95_usd",
        "var_99_usd",
        "es_95_usd",
        "mc_drawdown_pct",
        "session_guard_active",
        "last_arbitration"
      ],
      "properties": {
        "daily_pnl_usd": { "type": "number" },
        "var_95_usd": { "oneOf": [{ "type": "number" }, { "type": "null" }] },
        "var_99_usd": { "oneOf": [{ "type": "number" }, { "type": "null" }] },
        "es_95_usd": { "oneOf": [{ "type": "number" }, { "type": "null" }] },
        "mc_drawdown_pct": { "oneOf": [{ "type": "number", "minimum": 0 }, { "type": "null" }] },
        "session_guard_active": { "type": "boolean" },
        "last_arbitration": { "$ref": "https://lumina.local/schemas/core/v1/defs#/$defs/ArbitrationResult" }
      }
    },
    "constitution": { "$ref": "https://lumina.local/schemas/core/v1/defs#/$defs/ConstitutionViolationSummary" },
    "regime": {
      "type": "object",
      "additionalProperties": false,
      "required": ["current_regime", "regime_confidence", "fast_path_weight"],
      "properties": {
        "current_regime": {
          "type": "string",
          "enum": ["normal", "high_risk", "low_volatility", "unknown"]
        },
        "regime_confidence": { "type": "number", "minimum": 0, "maximum": 1 },
        "fast_path_weight": { "type": "number", "minimum": 0, "maximum": 1 }
      }
    },
    "operator": { "$ref": "https://lumina.local/schemas/core/v1/defs#/$defs/OperatorContext" },
    "evolution_summary": {
      "type": "object",
      "additionalProperties": false,
      "required": ["pending_mutations", "active_dna_hash", "champion_fitness"],
      "properties": {
        "pending_mutations": { "type": "integer", "minimum": 0 },
        "active_dna_hash": {
          "oneOf": [
            { "$ref": "https://lumina.local/schemas/core/v1/defs#/$defs/DnaHash" },
            { "type": "null" }
          ]
        },
        "champion_fitness": {
          "oneOf": [{ "type": "number" }, { "type": "null" }]
        }
      }
    }
  }
}
```

### 3.3 Example — SIM Mode

```json
{
  "schema_version": "1.0",
  "ts": 1716123456.789,
  "mode": {
    "current": "sim",
    "broker_backend": "live",
    "capabilities": {
      "requires_live_broker": true,
      "risk_enforced": false,
      "session_guard_enforced": true,
      "eod_force_close_enabled": false,
      "is_learning_mode": true,
      "capital_at_risk": false,
      "account_mode_hint": "sim"
    }
  },
  "health": {
    "status": "healthy",
    "uptime_s": 7200.0,
    "kill_switch_active": false,
    "websocket_connected": true,
    "issues": []
  },
  "intelligence": {
    "tier": "standard",
    "health": "ok",
    "model_name": "qwen2.5:14b",
    "gpu_available": false
  },
  "birth": {
    "phase": "complete",
    "progress_pct": 100,
    "target_trades": 500,
    "trades_completed": 512
  },
  "risk": {
    "daily_pnl_usd": 127.50,
    "var_95_usd": null,
    "var_99_usd": null,
    "es_95_usd": null,
    "mc_drawdown_pct": null,
    "session_guard_active": true,
    "last_arbitration": "approved"
  },
  "constitution": {
    "violations_open": 0,
    "last_audit_ok": true,
    "last_audit_ts": 1716123400.0,
    "violation_codes": []
  },
  "regime": {
    "current_regime": "normal",
    "regime_confidence": 0.82,
    "fast_path_weight": 0.65
  },
  "operator": {
    "role": "admin",
    "api_key_name": "launcher-admin"
  },
  "evolution_summary": {
    "pending_mutations": 3,
    "active_dna_hash": "a3f8c2d1e9b0476581920abcdef1234567890abcdef1234567890abcdef123456",
    "champion_fitness": 0.742
  }
}
```

### 3.4 Example — REAL Mode

```json
{
  "schema_version": "1.0",
  "ts": 1716123456.789,
  "mode": {
    "current": "real",
    "broker_backend": "live",
    "capabilities": {
      "requires_live_broker": true,
      "risk_enforced": true,
      "session_guard_enforced": true,
      "eod_force_close_enabled": true,
      "is_learning_mode": false,
      "capital_at_risk": true,
      "account_mode_hint": "real"
    }
  },
  "health": {
    "status": "healthy",
    "uptime_s": 14400.0,
    "kill_switch_active": false,
    "websocket_connected": true,
    "issues": []
  },
  "intelligence": {
    "tier": "high",
    "health": "ok",
    "model_name": "qwen3.5-35b",
    "gpu_available": true
  },
  "birth": {
    "phase": "complete",
    "progress_pct": 100,
    "target_trades": 500,
    "trades_completed": 500
  },
  "risk": {
    "daily_pnl_usd": -42.30,
    "var_95_usd": 850.0,
    "var_99_usd": 1200.0,
    "es_95_usd": 980.0,
    "mc_drawdown_pct": 4.2,
    "session_guard_active": true,
    "last_arbitration": "approved"
  },
  "constitution": {
    "violations_open": 0,
    "last_audit_ok": true,
    "last_audit_ts": 1716123440.0,
    "violation_codes": []
  },
  "regime": {
    "current_regime": "high_risk",
    "regime_confidence": 0.91,
    "fast_path_weight": 0.35
  },
  "operator": {
    "role": "admin",
    "api_key_name": "launcher-admin"
  },
  "evolution_summary": {
    "pending_mutations": 0,
    "active_dna_hash": "b7e4a1c9d2f0583617290abcdef1234567890abcdef1234567890abcdef12345678",
    "champion_fitness": 0.891
  }
}
```

---

## 4. GET /api/evolution/tree

### 4.1 Overview

| Property | Value |
|----------|-------|
| Method | `GET` |
| Path | `/api/evolution/tree` |
| Auth | `X-API-Key` required |
| Purpose | Full DNA lineage graph for Three.js evolution visualization |

Aligned with [`PolicyDNA`](../lumina_core/evolution/dna_registry.py).

### 4.2 Query Parameters Schema

`$id`: `https://lumina.local/schemas/core/v1/EvolutionTreeQuery`

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://lumina.local/schemas/core/v1/EvolutionTreeQuery",
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "depth": {
      "type": "integer",
      "minimum": 1,
      "maximum": 20,
      "default": 10
    },
    "include_rejected": {
      "type": "boolean",
      "default": false
    },
    "root_hash": {
      "$ref": "https://lumina.local/schemas/core/v1/defs#/$defs/DnaHash"
    }
  }
}
```

### 4.3 Response Schema

`$id`: `https://lumina.local/schemas/core/v1/EvolutionTreeResponse`

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://lumina.local/schemas/core/v1/EvolutionTreeResponse",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "schema_version",
    "ts",
    "mode",
    "active_hash",
    "champion",
    "nodes",
    "edges",
    "pending_mutations"
  ],
  "properties": {
    "schema_version": { "$ref": "https://lumina.local/schemas/core/v1/defs#/$defs/SchemaVersion" },
    "ts": { "$ref": "https://lumina.local/schemas/core/v1/defs#/$defs/UnixTimestamp" },
    "mode": { "$ref": "https://lumina.local/schemas/core/v1/defs#/$defs/TradeMode" },
    "active_hash": { "$ref": "https://lumina.local/schemas/core/v1/defs#/$defs/DnaHash" },
    "champion": { "$ref": "#/$defs/DnaNode" },
    "nodes": {
      "type": "array",
      "items": { "$ref": "#/$defs/DnaNode" }
    },
    "edges": {
      "type": "array",
      "items": { "$ref": "#/$defs/DnaEdge" }
    },
    "pending_mutations": {
      "type": "array",
      "items": { "$ref": "#/$defs/PendingMutation" }
    }
  },
  "$defs": {
    "DnaNode": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "hash",
        "prompt_id",
        "version",
        "fitness_score",
        "generation",
        "parent_ids",
        "mutation_rate",
        "lineage_hash",
        "created_at",
        "status",
        "mutation_depth",
        "content_digest"
      ],
      "properties": {
        "hash": { "$ref": "https://lumina.local/schemas/core/v1/defs#/$defs/DnaHash" },
        "prompt_id": { "type": "string", "minLength": 1 },
        "version": { "type": "string", "minLength": 1 },
        "fitness_score": { "type": "number" },
        "generation": { "type": "integer", "minimum": 0 },
        "parent_ids": {
          "type": "array",
          "items": { "$ref": "https://lumina.local/schemas/core/v1/defs#/$defs/DnaHash" }
        },
        "mutation_rate": { "type": "number", "minimum": 0, "maximum": 1 },
        "lineage_hash": { "type": "string", "minLength": 1 },
        "created_at": { "$ref": "https://lumina.local/schemas/core/v1/defs#/$defs/IsoDateTime" },
        "status": { "$ref": "https://lumina.local/schemas/core/v1/defs#/$defs/DnaNodeStatus" },
        "mutation_depth": { "$ref": "https://lumina.local/schemas/core/v1/defs#/$defs/MutationDepth" },
        "content_digest": {
          "type": "string",
          "pattern": "^[a-f0-9]{64}$"
        }
      }
    },
    "DnaEdge": {
      "type": "object",
      "additionalProperties": false,
      "required": ["from_hash", "to_hash", "mutation_type"],
      "properties": {
        "from_hash": { "$ref": "https://lumina.local/schemas/core/v1/defs#/$defs/DnaHash" },
        "to_hash": { "$ref": "https://lumina.local/schemas/core/v1/defs#/$defs/DnaHash" },
        "mutation_type": {
          "type": "string",
          "enum": ["crossover", "mutate", "bootstrap"]
        }
      }
    },
    "PendingMutation": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "proposal_id",
        "dna_hash",
        "status",
        "fitness_score",
        "shadow_verdict",
        "requires_human_approval"
      ],
      "properties": {
        "proposal_id": { "$ref": "https://lumina.local/schemas/core/v1/defs#/$defs/ProposalHash" },
        "dna_hash": { "$ref": "https://lumina.local/schemas/core/v1/defs#/$defs/DnaHash" },
        "status": {
          "type": "string",
          "enum": ["proposed", "shadow_pending", "awaiting_approval"]
        },
        "fitness_score": { "type": "number" },
        "shadow_verdict": {
          "oneOf": [
            { "$ref": "https://lumina.local/schemas/core/v1/defs#/$defs/ShadowVerdict" },
            { "type": "null" }
          ]
        },
        "requires_human_approval": { "type": "boolean" }
      }
    }
  }
}
```

### 4.4 Example — SIM Mode

Deep tree with radical mutations allowed and no human approval gate.

```json
{
  "schema_version": "1.0",
  "ts": 1716123456.789,
  "mode": "sim",
  "active_hash": "a3f8c2d1e9b0476581920abcdef1234567890abcdef1234567890abcdef123456",
  "champion": {
    "hash": "a3f8c2d1e9b0476581920abcdef1234567890abcdef1234567890abcdef123456",
    "prompt_id": "lumina_trader_v3",
    "version": "3.2.1",
    "fitness_score": 0.742,
    "generation": 8,
    "parent_ids": [
      "c1d2e3f4a5b678901234567890abcdef1234567890abcdef1234567890abcdef12",
      "d2e3f4a5b678901234567890abcdef1234567890abcdef1234567890abcdef1234"
    ],
    "mutation_rate": 0.15,
    "lineage_hash": "LINEAGE_SIM_008",
    "created_at": "2026-05-19T14:30:00.000Z",
    "status": "champion",
    "mutation_depth": "radical",
    "content_digest": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
  },
  "nodes": [
    {
      "hash": "0000000000000000000000000000000000000000000000000000000000000001",
      "prompt_id": "lumina_genesis",
      "version": "1.0.0",
      "fitness_score": 0.510,
      "generation": 0,
      "parent_ids": [],
      "mutation_rate": 0.0,
      "lineage_hash": "GENESIS",
      "created_at": "2026-05-01T08:00:00.000Z",
      "status": "archived",
      "mutation_depth": "conservative",
      "content_digest": "a1b2c3d4e5f678901234567890abcdef1234567890abcdef1234567890abcdef12"
    },
    {
      "hash": "a3f8c2d1e9b0476581920abcdef1234567890abcdef1234567890abcdef123456",
      "prompt_id": "lumina_trader_v3",
      "version": "3.2.1",
      "fitness_score": 0.742,
      "generation": 8,
      "parent_ids": [
        "c1d2e3f4a5b678901234567890abcdef1234567890abcdef1234567890abcdef12",
        "d2e3f4a5b678901234567890abcdef1234567890abcdef1234567890abcdef1234"
      ],
      "mutation_rate": 0.15,
      "lineage_hash": "LINEAGE_SIM_008",
      "created_at": "2026-05-19T14:30:00.000Z",
      "status": "champion",
      "mutation_depth": "radical",
      "content_digest": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    },
    {
      "hash": "f1a2b3c4d5e678901234567890abcdef1234567890abcdef1234567890abcdef56",
      "prompt_id": "lumina_trader_v3",
      "version": "3.3.0-candidate",
      "fitness_score": 0.768,
      "generation": 9,
      "parent_ids": ["a3f8c2d1e9b0476581920abcdef1234567890abcdef1234567890abcdef123456"],
      "mutation_rate": 0.22,
      "lineage_hash": "LINEAGE_SIM_009",
      "created_at": "2026-05-19T16:00:00.000Z",
      "status": "candidate",
      "mutation_depth": "radical",
      "content_digest": "b2c3d4e5f678901234567890abcdef1234567890abcdef1234567890abcdef1234"
    }
  ],
  "edges": [
    {
      "from_hash": "0000000000000000000000000000000000000000000000000000000000000001",
      "to_hash": "a3f8c2d1e9b0476581920abcdef1234567890abcdef1234567890abcdef123456",
      "mutation_type": "mutate"
    },
    {
      "from_hash": "a3f8c2d1e9b0476581920abcdef1234567890abcdef1234567890abcdef123456",
      "to_hash": "f1a2b3c4d5e678901234567890abcdef1234567890abcdef1234567890abcdef56",
      "mutation_type": "mutate"
    }
  ],
  "pending_mutations": [
    {
      "proposal_id": "prop_sim_20260519_001",
      "dna_hash": "f1a2b3c4d5e678901234567890abcdef1234567890abcdef1234567890abcdef56",
      "status": "proposed",
      "fitness_score": 0.768,
      "shadow_verdict": "pass",
      "requires_human_approval": false
    }
  ]
}
```

### 4.5 Example — REAL Mode

Shallow tree, conservative champion, all pending mutations require human approval and shadow pass.

```json
{
  "schema_version": "1.0",
  "ts": 1716123456.789,
  "mode": "real",
  "active_hash": "b7e4a1c9d2f0583617290abcdef1234567890abcdef1234567890abcdef12345678",
  "champion": {
    "hash": "b7e4a1c9d2f0583617290abcdef1234567890abcdef1234567890abcdef12345678",
    "prompt_id": "lumina_trader_prod",
    "version": "2.1.0",
    "fitness_score": 0.891,
    "generation": 3,
    "parent_ids": ["0000000000000000000000000000000000000000000000000000000000000002"],
    "mutation_rate": 0.05,
    "lineage_hash": "LINEAGE_REAL_003",
    "created_at": "2026-05-10T09:00:00.000Z",
    "status": "champion",
    "mutation_depth": "conservative",
    "content_digest": "c3d4e5f678901234567890abcdef1234567890abcdef1234567890abcdef12345678"
  },
  "nodes": [
    {
      "hash": "0000000000000000000000000000000000000000000000000000000000000002",
      "prompt_id": "lumina_genesis_prod",
      "version": "1.0.0",
      "fitness_score": 0.720,
      "generation": 0,
      "parent_ids": [],
      "mutation_rate": 0.0,
      "lineage_hash": "GENESIS",
      "created_at": "2026-05-01T08:00:00.000Z",
      "status": "archived",
      "mutation_depth": "conservative",
      "content_digest": "d4e5f678901234567890abcdef1234567890abcdef1234567890abcdef1234567890"
    },
    {
      "hash": "b7e4a1c9d2f0583617290abcdef1234567890abcdef1234567890abcdef12345678",
      "prompt_id": "lumina_trader_prod",
      "version": "2.1.0",
      "fitness_score": 0.891,
      "generation": 3,
      "parent_ids": ["0000000000000000000000000000000000000000000000000000000000000002"],
      "mutation_rate": 0.05,
      "lineage_hash": "LINEAGE_REAL_003",
      "created_at": "2026-05-10T09:00:00.000Z",
      "status": "champion",
      "mutation_depth": "conservative",
      "content_digest": "c3d4e5f678901234567890abcdef1234567890abcdef1234567890abcdef12345678"
    }
  ],
  "edges": [
    {
      "from_hash": "0000000000000000000000000000000000000000000000000000000000000002",
      "to_hash": "b7e4a1c9d2f0583617290abcdef1234567890abcdef1234567890abcdef12345678",
      "mutation_type": "mutate"
    }
  ],
  "pending_mutations": [
    {
      "proposal_id": "prop_real_20260519_001",
      "dna_hash": "e5f678901234567890abcdef1234567890abcdef1234567890abcdef123456789012",
      "status": "awaiting_approval",
      "fitness_score": 0.905,
      "shadow_verdict": "pass",
      "requires_human_approval": true
    }
  ]
}
```

---

## 5. POST /api/core/approve-mutation

### 5.1 Overview

| Property | Value |
|----------|-------|
| Method | `POST` |
| Path | `/api/core/approve-mutation` |
| Auth | `X-API-Key` with `admin` role |
| Purpose | Approve or reject a DNA mutation for promotion |
| Content-Type | `application/json` |

Mode-aware strictness. REAL mode requires Ed25519 multi-party signatures per [`ApprovalChain`](../lumina_core/governance/approval_chain.py).

### 5.2 Request Schema — Approve

`$id`: `https://lumina.local/schemas/core/v1/ApproveMutationRequestApprove`

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://lumina.local/schemas/core/v1/ApproveMutationRequestApprove",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "schema_version",
    "action",
    "proposal_hash",
    "dna_hash",
    "operator_ack",
    "challenger_name",
    "mode_context"
  ],
  "properties": {
    "schema_version": { "$ref": "https://lumina.local/schemas/core/v1/defs#/$defs/SchemaVersion" },
    "action": { "type": "string", "const": "approve" },
    "proposal_hash": { "$ref": "https://lumina.local/schemas/core/v1/defs#/$defs/ProposalHash" },
    "dna_hash": { "$ref": "https://lumina.local/schemas/core/v1/defs#/$defs/DnaHash" },
    "operator_ack": {
      "type": "string",
      "enum": ["APPROVE", "APPROVE_REAL"]
    },
    "challenger_name": { "type": "string", "minLength": 1, "maxLength": 128 },
    "mode_context": { "$ref": "https://lumina.local/schemas/core/v1/defs#/$defs/TradeMode" },
    "require_human_approval": { "type": "boolean", "default": false },
    "promotion_payload": { "$ref": "https://lumina.local/schemas/core/v1/defs#/$defs/RealPromotionPayload" },
    "approvals": {
      "type": "array",
      "items": { "$ref": "https://lumina.local/schemas/core/v1/defs#/$defs/SignedApproval" },
      "minItems": 0
    }
  },
  "allOf": [
    {
      "if": {
        "properties": { "mode_context": { "const": "real" } },
        "required": ["mode_context"]
      },
      "then": {
        "required": ["promotion_payload", "approvals", "operator_ack"],
        "properties": {
          "operator_ack": { "const": "APPROVE_REAL" },
          "approvals": { "minItems": 1 }
        }
      }
    },
    {
      "if": {
        "properties": {
          "mode_context": { "enum": ["paper", "sim", "sim_real_guard"] }
        },
        "required": ["mode_context"]
      },
      "then": {
        "properties": {
          "operator_ack": { "const": "APPROVE" }
        }
      }
    }
  ]
}
```

### 5.3 Request Schema — Reject

`$id`: `https://lumina.local/schemas/core/v1/ApproveMutationRequestReject`

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://lumina.local/schemas/core/v1/ApproveMutationRequestReject",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "schema_version",
    "action",
    "proposal_hash",
    "dna_hash",
    "operator_ack",
    "reason",
    "mode_context"
  ],
  "properties": {
    "schema_version": { "$ref": "https://lumina.local/schemas/core/v1/defs#/$defs/SchemaVersion" },
    "action": { "type": "string", "const": "reject" },
    "proposal_hash": { "$ref": "https://lumina.local/schemas/core/v1/defs#/$defs/ProposalHash" },
    "dna_hash": { "$ref": "https://lumina.local/schemas/core/v1/defs#/$defs/DnaHash" },
    "operator_ack": { "type": "string", "const": "REJECT" },
    "reason": { "type": "string", "minLength": 3, "maxLength": 500 },
    "mode_context": { "$ref": "https://lumina.local/schemas/core/v1/defs#/$defs/TradeMode" }
  }
}
```

### 5.4 Response Schema

`$id`: `https://lumina.local/schemas/core/v1/ApproveMutationResponse`

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://lumina.local/schemas/core/v1/ApproveMutationResponse",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "schema_version",
    "success",
    "action",
    "proposal_hash",
    "dna_hash",
    "mode",
    "promotion_stage",
    "constitution_violations",
    "audit_ref",
    "ts"
  ],
  "properties": {
    "schema_version": { "$ref": "https://lumina.local/schemas/core/v1/defs#/$defs/SchemaVersion" },
    "success": { "type": "boolean" },
    "action": { "type": "string", "enum": ["approve", "reject"] },
    "proposal_hash": { "$ref": "https://lumina.local/schemas/core/v1/defs#/$defs/ProposalHash" },
    "dna_hash": { "$ref": "https://lumina.local/schemas/core/v1/defs#/$defs/DnaHash" },
    "mode": { "$ref": "https://lumina.local/schemas/core/v1/defs#/$defs/TradeMode" },
    "promotion_stage": { "$ref": "https://lumina.local/schemas/core/v1/defs#/$defs/PromotionStage" },
    "constitution_violations": {
      "type": "array",
      "items": { "type": "string", "minLength": 1 }
    },
    "audit_ref": { "type": "string", "minLength": 1 },
    "ts": { "$ref": "https://lumina.local/schemas/core/v1/defs#/$defs/UnixTimestamp" }
  }
}
```

### 5.5 Error Response Schema

`$id`: `https://lumina.local/schemas/core/v1/ApproveMutationError`

Uses shared `ErrorResponse` from `$defs`. HTTP status mapping:

| Status | `code` value | When |
|--------|--------------|------|
| 401 | `AUTH_REQUIRED` | Missing/invalid API key |
| 403 | `ADMIN_REQUIRED` | Non-admin key |
| 409 | `ALREADY_DECIDED` | Proposal hash already in decisions log |
| 422 | `CONSTITUTION_BLOCKED` | Fatal constitution violations |
| 422 | `VALIDATION_FAILED` | Schema or mode_context mismatch |

### 5.6 Example — SIM Approve

Request:

```json
{
  "schema_version": "1.0",
  "action": "approve",
  "proposal_hash": "prop_sim_20260519_001",
  "dna_hash": "f1a2b3c4d5e678901234567890abcdef1234567890abcdef1234567890abcdef56",
  "operator_ack": "APPROVE",
  "challenger_name": "aggressive_kelly_v2",
  "mode_context": "sim",
  "require_human_approval": false
}
```

Response:

```json
{
  "schema_version": "1.0",
  "success": true,
  "action": "approve",
  "proposal_hash": "prop_sim_20260519_001",
  "dna_hash": "f1a2b3c4d5e678901234567890abcdef1234567890abcdef1234567890abcdef56",
  "mode": "sim",
  "promotion_stage": "applied",
  "constitution_violations": [],
  "audit_ref": "evolution_decisions:20260519T163045Z:prop_sim_20260519_001",
  "ts": 1716124245.123
}
```

### 5.7 Example — REAL Approve

Request:

```json
{
  "schema_version": "1.0",
  "action": "approve",
  "proposal_hash": "prop_real_20260519_001",
  "dna_hash": "e5f678901234567890abcdef1234567890abcdef1234567890abcdef123456789012",
  "operator_ack": "APPROVE_REAL",
  "challenger_name": "conservative_prod_v2",
  "mode_context": "real",
  "promotion_payload": {
    "schema_version": "v1",
    "dna_hash": "e5f678901234567890abcdef1234567890abcdef1234567890abcdef123456789012",
    "target_mode": "real",
    "dna_content_digest": "a1b2c3d4e5f678901234567890abcdef1234567890abcdef1234567890abcdef12",
    "promotion_epoch": "2026-05-19T16:30:00Z",
    "reason_context": "real_promotion",
    "created_at": "2026-05-19T16:30:00.000Z",
    "expires_at": "2026-05-19T17:00:00.000Z"
  },
  "approvals": [
    {
      "approver_id": "operator_steve",
      "public_key_fingerprint": "a1b2c3d4e5f6789012",
      "signature_b64": "MEUCIQDxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
      "reason": "Shadow pass confirmed, fitness delta +0.014",
      "timestamp": "2026-05-19T16:30:15.000Z"
    },
    {
      "approver_id": "risk_officer_1",
      "public_key_fingerprint": "b2c3d4e5f6789012345",
      "signature_b64": "MEUCIQByyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy",
      "reason": "VaR within REAL limits",
      "timestamp": "2026-05-19T16:30:20.000Z"
    }
  ]
}
```

Response:

```json
{
  "schema_version": "1.0",
  "success": true,
  "action": "approve",
  "proposal_hash": "prop_real_20260519_001",
  "dna_hash": "e5f678901234567890abcdef1234567890abcdef1234567890abcdef123456789012",
  "mode": "real",
  "promotion_stage": "applied",
  "constitution_violations": [],
  "audit_ref": "evolution_decisions:20260519T163045Z:prop_real_20260519_001",
  "ts": 1716124245.123
}
```

### 5.8 Example — REAL Blocked (422)

Request omitted — same as REAL approve but DNA triggers constitution fatals.

Response:

```json
{
  "detail": "Constitutional gate blocked mutation promotion",
  "code": "CONSTITUTION_BLOCKED",
  "blockers": [
    {
      "code": "KELLY_FRACTION_EXCEEDED",
      "message": "Kelly fraction 0.45 exceeds REAL limit 0.25"
    },
    {
      "code": "AGGRESSIVE_EVOLUTION_FORBIDDEN",
      "message": "Radical mutation depth not permitted in REAL mode"
    }
  ],
  "ts": 1716124245.123
}
```

### 5.9 Example — SIM Reject

Request:

```json
{
  "schema_version": "1.0",
  "action": "reject",
  "proposal_hash": "prop_sim_20260519_002",
  "dna_hash": "aabbccddeeff0011223344556677889900aabbccddeeff00112233445566778899",
  "operator_ack": "REJECT",
  "reason": "Fitness score below champion threshold by 0.08",
  "mode_context": "sim"
}
```

Response:

```json
{
  "schema_version": "1.0",
  "success": true,
  "action": "reject",
  "proposal_hash": "prop_sim_20260519_002",
  "dna_hash": "aabbccddeeff0011223344556677889900aabbccddeeff00112233445566778899",
  "mode": "sim",
  "promotion_stage": "rejected",
  "constitution_violations": [],
  "audit_ref": "evolution_decisions:20260519T164500Z:prop_sim_20260519_002",
  "ts": 1716125100.456
}
```

---

## 6. WS /ws/core/live

### 6.1 Overview

| Property | Value |
|----------|-------|
| URL | `ws://127.0.0.1:8000/ws/core/live` |
| Auth | JWT via first frame within 5 seconds |
| Purpose | Multiplexed real-time organism telemetry |

### 6.2 Connection Lifecycle

1. Obtain JWT via `POST /api/command-deck/ws/token`
2. Connect WebSocket
3. Send `{ "type": "auth", "token": "<jwt>" }`
4. Receive `{ "type": "auth_ok", ... }`
5. Send `{ "type": "subscribe", "channels": [...] }`
6. Receive event stream; send ping every 30 seconds

Close codes: `4401` auth failed, `4403` schema violation, `4429` rate limit.

### 6.3 Client Frame Schema

`$id`: `https://lumina.local/schemas/core/v1/WsCoreLiveClientFrame`

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://lumina.local/schemas/core/v1/WsCoreLiveClientFrame",
  "oneOf": [
    {
      "type": "object",
      "additionalProperties": false,
      "required": ["type", "token"],
      "properties": {
        "type": { "const": "auth" },
        "token": { "type": "string", "minLength": 16 }
      }
    },
    {
      "type": "object",
      "additionalProperties": false,
      "required": ["type", "channels"],
      "properties": {
        "type": { "const": "subscribe" },
        "channels": {
          "type": "array",
          "items": { "$ref": "https://lumina.local/schemas/core/v1/defs#/$defs/WsCoreLiveChannel" },
          "minItems": 1,
          "uniqueItems": true
        }
      }
    },
    {
      "type": "object",
      "additionalProperties": false,
      "required": ["type", "channels"],
      "properties": {
        "type": { "const": "unsubscribe" },
        "channels": {
          "type": "array",
          "items": { "$ref": "https://lumina.local/schemas/core/v1/defs#/$defs/WsCoreLiveChannel" },
          "minItems": 1,
          "uniqueItems": true
        }
      }
    },
    {
      "type": "object",
      "additionalProperties": false,
      "required": ["type", "ts"],
      "properties": {
        "type": { "const": "ping" },
        "ts": { "$ref": "https://lumina.local/schemas/core/v1/defs#/$defs/UnixTimestamp" }
      }
    }
  ]
}
```

### 6.4 Server Envelope Schema

`$id`: `https://lumina.local/schemas/core/v1/WsCoreLiveServerEnvelope`

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://lumina.local/schemas/core/v1/WsCoreLiveServerEnvelope",
  "oneOf": [
    {
      "type": "object",
      "additionalProperties": false,
      "required": ["type", "operator", "ts"],
      "properties": {
        "type": { "const": "auth_ok" },
        "operator": { "$ref": "https://lumina.local/schemas/core/v1/defs#/$defs/OperatorContext" },
        "ts": { "$ref": "https://lumina.local/schemas/core/v1/defs#/$defs/UnixTimestamp" }
      }
    },
    {
      "type": "object",
      "additionalProperties": false,
      "required": ["type", "channels", "ts"],
      "properties": {
        "type": { "const": "subscribed" },
        "channels": {
          "type": "array",
          "items": { "$ref": "https://lumina.local/schemas/core/v1/defs#/$defs/WsCoreLiveChannel" }
        },
        "ts": { "$ref": "https://lumina.local/schemas/core/v1/defs#/$defs/UnixTimestamp" }
      }
    },
    {
      "type": "object",
      "additionalProperties": false,
      "required": ["type", "channel", "topic", "seq", "ts", "payload"],
      "properties": {
        "type": { "const": "event" },
        "channel": { "$ref": "https://lumina.local/schemas/core/v1/defs#/$defs/WsCoreLiveChannel" },
        "topic": { "type": "string", "minLength": 1 },
        "seq": { "type": "integer", "minimum": 0 },
        "ts": { "$ref": "https://lumina.local/schemas/core/v1/defs#/$defs/UnixTimestamp" },
        "payload": { "type": "object" }
      }
    },
    {
      "type": "object",
      "additionalProperties": false,
      "required": ["type", "seq", "ts"],
      "properties": {
        "type": { "const": "heartbeat" },
        "seq": { "type": "integer", "minimum": 0 },
        "ts": { "$ref": "https://lumina.local/schemas/core/v1/defs#/$defs/UnixTimestamp" }
      }
    },
    {
      "type": "object",
      "additionalProperties": false,
      "required": ["type", "ts"],
      "properties": {
        "type": { "const": "pong" },
        "ts": { "$ref": "https://lumina.local/schemas/core/v1/defs#/$defs/UnixTimestamp" }
      }
    },
    {
      "type": "object",
      "additionalProperties": false,
      "required": ["type", "code", "message", "ts"],
      "properties": {
        "type": { "const": "error" },
        "code": { "type": "string", "minLength": 1 },
        "message": { "type": "string", "minLength": 1 },
        "ts": { "$ref": "https://lumina.local/schemas/core/v1/defs#/$defs/UnixTimestamp" }
      }
    }
  ]
}
```

### 6.5 Event Payload Schemas (strict $defs)

#### HealthEventPayload

```json
{
  "$id": "https://lumina.local/schemas/core/v1/HealthEventPayload",
  "type": "object",
  "additionalProperties": false,
  "required": ["status", "kill_switch_active", "uptime_s"],
  "properties": {
    "status": { "$ref": "https://lumina.local/schemas/core/v1/defs#/$defs/HealthStatus" },
    "kill_switch_active": { "type": "boolean" },
    "uptime_s": { "type": "number", "minimum": 0 }
  }
}
```

#### IntelligenceEventPayload

```json
{
  "$id": "https://lumina.local/schemas/core/v1/IntelligenceEventPayload",
  "type": "object",
  "additionalProperties": false,
  "required": ["tier", "health", "model_name"],
  "properties": {
    "tier": { "$ref": "https://lumina.local/schemas/core/v1/defs#/$defs/IntelligenceTier" },
    "health": { "$ref": "https://lumina.local/schemas/core/v1/defs#/$defs/IntelligenceHealth" },
    "model_name": { "type": "string", "minLength": 1 }
  }
}
```

#### RiskEventPayload

```json
{
  "$id": "https://lumina.local/schemas/core/v1/RiskEventPayload",
  "type": "object",
  "additionalProperties": false,
  "required": ["decision", "reason_code", "capital_at_risk", "mode"],
  "properties": {
    "decision": { "type": "string", "enum": ["allow", "deny", "advisory"] },
    "reason_code": { "type": "string", "minLength": 1 },
    "capital_at_risk": { "type": "boolean" },
    "mode": { "$ref": "https://lumina.local/schemas/core/v1/defs#/$defs/TradeMode" },
    "var_95_usd": { "oneOf": [{ "type": "number" }, { "type": "null" }] },
    "daily_pnl_usd": { "oneOf": [{ "type": "number" }, { "type": "null" }] }
  }
}
```

#### SignalEventPayload

```json
{
  "$id": "https://lumina.local/schemas/core/v1/SignalEventPayload",
  "type": "object",
  "additionalProperties": false,
  "required": ["signal", "confidence", "instrument"],
  "properties": {
    "signal": { "type": "string", "enum": ["BUY", "SELL", "HOLD", "FLAT"] },
    "confidence": { "type": "number", "minimum": 0, "maximum": 1 },
    "instrument": { "type": "string", "minLength": 1 },
    "stop": { "oneOf": [{ "type": "number" }, { "type": "null" }] },
    "target": { "oneOf": [{ "type": "number" }, { "type": "null" }] }
  }
}
```

#### ExecutionEventPayload

```json
{
  "$id": "https://lumina.local/schemas/core/v1/ExecutionEventPayload",
  "type": "object",
  "additionalProperties": false,
  "required": ["executed", "pnl", "instrument"],
  "properties": {
    "executed": { "type": "boolean" },
    "pnl": { "type": "number" },
    "instrument": { "type": "string", "minLength": 1 },
    "fill_price": { "oneOf": [{ "type": "number" }, { "type": "null" }] }
  }
}
```

#### ConstitutionEventPayload

```json
{
  "$id": "https://lumina.local/schemas/core/v1/ConstitutionEventPayload",
  "type": "object",
  "additionalProperties": false,
  "required": ["principle_name", "severity", "mode"],
  "properties": {
    "principle_name": { "type": "string", "minLength": 1 },
    "severity": { "type": "string", "enum": ["info", "warning", "fatal"] },
    "mode": { "$ref": "https://lumina.local/schemas/core/v1/defs#/$defs/TradeMode" },
    "description": { "oneOf": [{ "type": "string" }, { "type": "null" }] }
  }
}
```

### 6.6 Example — SIM Risk Event

```json
{
  "type": "event",
  "channel": "risk",
  "topic": "risk.policy.decision",
  "seq": 1042,
  "ts": 1716123456.789,
  "payload": {
    "decision": "advisory",
    "reason_code": "var_es_advisory_only",
    "capital_at_risk": false,
    "mode": "sim",
    "var_95_usd": null,
    "daily_pnl_usd": 127.50
  }
}
```

### 6.7 Example — REAL Risk Event (hard deny)

```json
{
  "type": "event",
  "channel": "risk",
  "topic": "risk.policy.decision",
  "seq": 2087,
  "ts": 1716127890.123,
  "payload": {
    "decision": "deny",
    "reason_code": "var_es_limit_exceeded",
    "capital_at_risk": true,
    "mode": "real",
    "var_95_usd": 1350.0,
    "daily_pnl_usd": -42.30
  }
}
```

### 6.8 Example — REAL Constitution Violation Event

```json
{
  "type": "event",
  "channel": "constitution",
  "topic": "safety.constitution.violation",
  "seq": 2088,
  "ts": 1716127891.456,
  "payload": {
    "principle_name": "MAX_RISK_PER_TRADE",
    "severity": "fatal",
    "mode": "real",
    "description": "Proposed trade risk 4.2% exceeds REAL limit of 3.0%"
  }
}
```

### 6.9 Example — SIM Intelligence Event

```json
{
  "type": "event",
  "channel": "intelligence",
  "topic": "inference.adaptive_intelligence.state",
  "seq": 512,
  "ts": 1716123500.0,
  "payload": {
    "tier": "standard",
    "health": "ok",
    "model_name": "qwen2.5:14b"
  }
}
```

### 6.10 Example — REAL Execution Event

```json
{
  "type": "event",
  "channel": "execution",
  "topic": "trading_engine.execution.aggregate",
  "seq": 2090,
  "ts": 1716127900.789,
  "payload": {
    "executed": true,
    "pnl": -18.50,
    "instrument": "MES JUN26",
    "fill_price": 5842.25
  }
}
```

---

## 7. WS /ws/evolution

### 7.1 Overview

| Property | Value |
|----------|-------|
| URL | `ws://127.0.0.1:8000/ws/evolution` |
| Auth | JWT via first frame (same as `/ws/core/live`) |
| Purpose | Evolution-specific stream for tree visualization and mutation workflow |

### 7.2 Channels

| Channel | Topics delivered |
|---------|------------------|
| `proposals` | `evolution.proposal.created` |
| `shadow` | `evolution.shadow.verdict` |
| `promotion` | `evolution.promotion.decision` |
| `lineage` | `meta.dna_lineage` |
| `mutations` | `core.mutation.approved`, `core.mutation.rejected` |

### 7.3 Client Frame Schema

`$id`: `https://lumina.local/schemas/core/v1/WsEvolutionClientFrame`

Same structure as `WsCoreLiveClientFrame` but `channels` items use `WsEvolutionChannel`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://lumina.local/schemas/core/v1/WsEvolutionClientFrame",
  "oneOf": [
    {
      "type": "object",
      "additionalProperties": false,
      "required": ["type", "token"],
      "properties": {
        "type": { "const": "auth" },
        "token": { "type": "string", "minLength": 16 }
      }
    },
    {
      "type": "object",
      "additionalProperties": false,
      "required": ["type", "channels"],
      "properties": {
        "type": { "const": "subscribe" },
        "channels": {
          "type": "array",
          "items": { "$ref": "https://lumina.local/schemas/core/v1/defs#/$defs/WsEvolutionChannel" },
          "minItems": 1,
          "uniqueItems": true
        }
      }
    },
    {
      "type": "object",
      "additionalProperties": false,
      "required": ["type", "channels"],
      "properties": {
        "type": { "const": "unsubscribe" },
        "channels": {
          "type": "array",
          "items": { "$ref": "https://lumina.local/schemas/core/v1/defs#/$defs/WsEvolutionChannel" },
          "minItems": 1,
          "uniqueItems": true
        }
      }
    },
    {
      "type": "object",
      "additionalProperties": false,
      "required": ["type", "ts"],
      "properties": {
        "type": { "const": "ping" },
        "ts": { "$ref": "https://lumina.local/schemas/core/v1/defs#/$defs/UnixTimestamp" }
      }
    }
  ]
}
```

### 7.4 Server Envelope Schema

`$id`: `https://lumina.local/schemas/core/v1/WsEvolutionServerEnvelope`

Same `oneOf` structure as `WsCoreLiveServerEnvelope` with `channel` referencing `WsEvolutionChannel`.

### 7.5 Event Payload Schemas

#### EvolutionProposalPayload (strict subset)

```json
{
  "$id": "https://lumina.local/schemas/core/v1/EvolutionProposalPayload",
  "type": "object",
  "additionalProperties": false,
  "required": ["status", "generations_run", "best_fitness", "timestamp"],
  "properties": {
    "status": { "type": "string", "enum": ["proposed", "running", "complete"] },
    "generations_run": { "type": "integer", "minimum": 0 },
    "promotions": { "type": "integer", "minimum": 0 },
    "best_fitness": { "type": "number" },
    "timestamp": { "$ref": "https://lumina.local/schemas/core/v1/defs#/$defs/IsoDateTime" },
    "dna_hash": {
      "oneOf": [
        { "$ref": "https://lumina.local/schemas/core/v1/defs#/$defs/DnaHash" },
        { "type": "null" }
      ]
    }
  }
}
```

#### ShadowVerdictPayload

```json
{
  "$id": "https://lumina.local/schemas/core/v1/ShadowVerdictPayload",
  "type": "object",
  "additionalProperties": false,
  "required": ["verdict", "dna_hash"],
  "properties": {
    "verdict": { "$ref": "https://lumina.local/schemas/core/v1/defs#/$defs/ShadowVerdict" },
    "dna_hash": { "$ref": "https://lumina.local/schemas/core/v1/defs#/$defs/DnaHash" },
    "sample_size": { "oneOf": [{ "type": "integer", "minimum": 0 }, { "type": "null" }] },
    "pnl": { "oneOf": [{ "type": "number" }, { "type": "null" }] }
  }
}
```

#### PromotionDecisionPayload

```json
{
  "$id": "https://lumina.local/schemas/core/v1/PromotionDecisionPayload",
  "type": "object",
  "additionalProperties": false,
  "required": ["dna_hash", "allowed", "reason", "stage", "mode"],
  "properties": {
    "dna_hash": { "$ref": "https://lumina.local/schemas/core/v1/defs#/$defs/DnaHash" },
    "allowed": { "type": "boolean" },
    "reason": { "type": "string", "minLength": 1 },
    "stage": {
      "type": "string",
      "enum": ["shadow", "promotion_gate", "human_approval", "final"]
    },
    "mode": { "type": "string", "enum": ["SIM", "PAPER", "REAL"] },
    "evidence_ref": { "oneOf": [{ "type": "string" }, { "type": "null" }] }
  }
}
```

#### DnaLineagePayload (strict subset)

```json
{
  "$id": "https://lumina.local/schemas/core/v1/DnaLineagePayload",
  "type": "object",
  "additionalProperties": false,
  "required": ["active_hash", "candidate_hash", "evolution_status", "timestamp"],
  "properties": {
    "active_hash": { "$ref": "https://lumina.local/schemas/core/v1/defs#/$defs/DnaHash" },
    "active_version": { "type": "string", "minLength": 1 },
    "candidate_hash": {
      "oneOf": [
        { "$ref": "https://lumina.local/schemas/core/v1/defs#/$defs/DnaHash" },
        { "type": "null" }
      ]
    },
    "candidate_version": { "oneOf": [{ "type": "string" }, { "type": "null" }] },
    "lineage_hash": { "type": "string", "minLength": 1 },
    "evolution_status": {
      "type": "string",
      "enum": ["stable", "mutating", "promoting", "shadowing"]
    },
    "timestamp": { "$ref": "https://lumina.local/schemas/core/v1/defs#/$defs/IsoDateTime" }
  }
}
```

#### MutationRejectedPayload

```json
{
  "$id": "https://lumina.local/schemas/core/v1/MutationRejectedPayload",
  "type": "object",
  "additionalProperties": false,
  "required": ["proposal_hash", "dna_hash", "reason", "mode", "ts"],
  "properties": {
    "proposal_hash": { "$ref": "https://lumina.local/schemas/core/v1/defs#/$defs/ProposalHash" },
    "dna_hash": { "$ref": "https://lumina.local/schemas/core/v1/defs#/$defs/DnaHash" },
    "reason": { "type": "string", "minLength": 3 },
    "mode": { "$ref": "https://lumina.local/schemas/core/v1/defs#/$defs/TradeMode" },
    "ts": { "$ref": "https://lumina.local/schemas/core/v1/defs#/$defs/UnixTimestamp" }
  }
}
```

### 7.6 Example — SIM Proposal Created

```json
{
  "type": "event",
  "channel": "proposals",
  "topic": "evolution.proposal.created",
  "seq": 301,
  "ts": 1716123600.0,
  "payload": {
    "status": "proposed",
    "generations_run": 5,
    "promotions": 2,
    "best_fitness": 0.768,
    "timestamp": "2026-05-19T16:00:00.000Z",
    "dna_hash": "f1a2b3c4d5e678901234567890abcdef1234567890abcdef1234567890abcdef56"
  }
}
```

### 7.7 Example — SIM Shadow Verdict (pass)

```json
{
  "type": "event",
  "channel": "shadow",
  "topic": "evolution.shadow.verdict",
  "seq": 302,
  "ts": 1716123700.0,
  "payload": {
    "verdict": "pass",
    "dna_hash": "f1a2b3c4d5e678901234567890abcdef1234567890abcdef1234567890abcdef56",
    "sample_size": 120,
    "pnl": 340.50
  }
}
```

### 7.8 Example — REAL Promotion Decision (blocked)

```json
{
  "type": "event",
  "channel": "promotion",
  "topic": "evolution.promotion.decision",
  "seq": 401,
  "ts": 1716128000.0,
  "payload": {
    "dna_hash": "e5f678901234567890abcdef1234567890abcdef1234567890abcdef123456789012",
    "allowed": false,
    "reason": "Insufficient shadow sample size for REAL promotion gate",
    "stage": "promotion_gate",
    "mode": "REAL",
    "evidence_ref": "state/shadow_results/prop_real_20260519_001.json"
  }
}
```

### 7.9 Example — REAL Mutation Approved (after signatures)

```json
{
  "type": "event",
  "channel": "mutations",
  "topic": "core.mutation.approved",
  "seq": 402,
  "ts": 1716128100.0,
  "payload": {
    "schema_version": "1.0",
    "success": true,
    "action": "approve",
    "proposal_hash": "prop_real_20260519_001",
    "dna_hash": "e5f678901234567890abcdef1234567890abcdef1234567890abcdef123456789012",
    "mode": "real",
    "promotion_stage": "applied",
    "constitution_violations": [],
    "audit_ref": "evolution_decisions:20260519T163045Z:prop_real_20260519_001",
    "ts": 1716128100.0
  }
}
```

### 7.10 Example — SIM DNA Lineage Update

```json
{
  "type": "event",
  "channel": "lineage",
  "topic": "meta.dna_lineage",
  "seq": 303,
  "ts": 1716123750.0,
  "payload": {
    "active_hash": "a3f8c2d1e9b0476581920abcdef1234567890abcdef1234567890abcdef123456",
    "active_version": "3.2.1",
    "candidate_hash": "f1a2b3c4d5e678901234567890abcdef1234567890abcdef1234567890abcdef56",
    "candidate_version": "3.3.0-candidate",
    "lineage_hash": "LINEAGE_SIM_009",
    "evolution_status": "mutating",
    "timestamp": "2026-05-19T16:02:30.000Z"
  }
}
```

### 7.11 Example — SIM Mutation Rejected

```json
{
  "type": "event",
  "channel": "mutations",
  "topic": "core.mutation.rejected",
  "seq": 304,
  "ts": 1716123800.0,
  "payload": {
    "proposal_hash": "prop_sim_20260519_002",
    "dna_hash": "aabbccddeeff0011223344556677889900aabbccddeeff00112233445566778899",
    "reason": "Fitness score below champion threshold by 0.08",
    "mode": "sim",
    "ts": 1716123800.0
  }
}
```

---

## 8. SIM vs REAL Mode Delta

Summary of field and behavior differences across all contracts:

| Field / Behavior | SIM | REAL |
|------------------|-----|------|
| `mode.capabilities.capital_at_risk` | `false` | `true` |
| `mode.capabilities.risk_enforced` | `false` | `true` |
| `mode.capabilities.is_learning_mode` | `true` | `false` |
| `risk.var_95_usd` / `es_95_usd` | Usually `null` (advisory) | Populated, hard-enforced |
| `RiskEventPayload.decision` | `"advisory"` or `"allow"` | `"deny"` when limits exceeded |
| `DnaNode.mutation_depth` | `"radical"` allowed | `"conservative"` only on champion |
| `PendingMutation.requires_human_approval` | `false` | `true` |
| `ApproveMutationRequest.operator_ack` | `"APPROVE"` | `"APPROVE_REAL"` |
| `ApproveMutationRequest.approvals` | Not required | Required, `minItems: 1` |
| `ApproveMutationRequest.promotion_payload` | Not required | Required |
| `PromotionDecisionPayload.mode` | `"SIM"` | `"REAL"` |
| Constitution violation `severity` | Usually `"warning"` | `"fatal"` blocks execution |
| Evolution tree depth | Deep (gen 0–8+) | Shallow (gen 0–3) |

---

## 9. Setup & Onboarding — GET /api/setup/onboarding

> **Namespace:** `/api/setup/*` (Command Deck first-boot and lifecycle gate)  
> **SSOT implementation:** [`lumina_launcher/core/onboarding.py`](../lumina_launcher/core/onboarding.py) → `resolve_app_surface()`  
> **Operator runbook:** [command-deck-startup-runbook.md](command-deck-startup-runbook.md)

Unauthenticated bootstrap endpoint used on every Tauri cold start. Returns wizard steps, birth status, and the canonical **`app_surface`** lifecycle gate.

### 9.1 Request

```http
GET /api/setup/onboarding
```

No body. No API key required for read (local operator machine).

### 9.2 Response (lifecycle fields)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `app_surface` | `"setup" \| "birth" \| "deck"` | yes | Canonical startup surface (SSOT) |
| `app_surface_reason` | string | yes | Diagnostic reason (e.g. `birth_pending`, `birth_complete`, `backend_unreachable`) |
| `setup_complete` | boolean | yes | Guided setup finished |
| `skip_wizard` | boolean | yes | `true` only when `app_surface === "deck"` |
| `birth.status` | string | yes | Birth service status (`idle`, `running`, `interrupted`, `error`, `completed`, …) |
| `birth.artifacts_ok` | boolean | yes | Policy zip present on disk |
| `birth.certificate_ok` | boolean | yes | Valid Birth Certificate v2 (`integrity_version: 2`) with matching policy hash and thresholds met — **deck gate** |
| `birth.certificate_reason` | string | no | Fail-closed reason when `certificate_ok === false` |
| `birth.certificate` | object | no | Parsed certificate payload when present |
| `birth.progress` | object | no | Training progress when birth active |
| `required_steps` | string[] | yes | Pending onboarding step ids |
| `wizard_steps` | string[] | yes | Steps shown in progressive wizard |
| `backend.reachable` | boolean | yes | FastAPI probe result |

### 9.3 `app_surface` resolution (normative)

Evaluated in order by `resolve_app_surface()`:

1. If `backend.reachable === false` → `setup` (`backend_unreachable`)
2. If `setup_complete === false` or pending setup steps → `setup` (`fresh_install` / `setup_incomplete`)
3. If `birth.certificate_ok === false` or `birth.artifacts_ok === false` → `birth` (reason from birth status: `birth_running`, `birth_interrupted`, `birth_error`, `birth_pending`, `certificate_failed`)
4. Else → `deck` (`birth_complete`)

### 9.3.1 Birth Certificate API

```http
GET /api/birth/certificate
GET /api/birth/status
```

`GET /api/birth/status` and `GET /api/birth/certificate` both expose `certificate_ok`, `certificate_reason`, `artifacts_ok`, and the parsed `certificate` object. Deck bootstrap requires **`certificate_ok === true`** (not legacy flag-only checks).

Pre-integrity-fix certificates (`integrity_version != 2`) are invalid — run mandatory re-birth after PR-A remediation.

**Fail-closed:** `skip_wizard` must not be `true` unless `app_surface === "deck"`.

### 9.4 Client mapping (Tauri)

| `app_surface` | Client phase | Primary component |
|---------------|--------------|-------------------|
| `setup` | `wizard` | `OnboardingWizard` |
| `birth` | `birth` | `BirthPhaseScreen` |
| `deck` | `cockpit` | `CockpitShell` |

Mapper: `tauri-app/src/lib/onboardingPhase.ts` → `mapAppPhase()`.

### 9.5 Example fragment

```json
{
  "setup_complete": true,
  "app_surface": "birth",
  "app_surface_reason": "birth_interrupted",
  "skip_wizard": false,
  "birth": {
    "status": "interrupted",
    "artifacts_ok": false,
    "certificate_ok": false,
    "certificate_reason": "certificate_integrity_version_invalid",
    "artifacts_label": "Artifacts missing",
    "message": "Training paused at checkpoint",
    "progress": { "progress_pct": 42, "trades_done": 10500, "target_trades": 25000 }
  },
  "backend": { "reachable": true, "url": "http://127.0.0.1:8000", "latency_ms": 12 },
  "required_steps": ["birth"]
}
```

---

## 10. Related Documents

| Document | Path | Relevance |
|----------|------|-----------|
| Neural Command Deck architecture | [lumina-core-architecture.md](lumina-core-architecture.md) | System design, deployment, security |
| LUMINA organism architecture | [architecture.md](architecture.md) | Python core bounded contexts |
| Constitutional principles ADR | [adr/ADR-001-constitutional-principles.md](adr/ADR-001-constitutional-principles.md) | Fail-closed safety rules |
| Event Bus contract ADR | [adr/ADR-003-event-bus-contract.md](adr/ADR-003-event-bus-contract.md) | Typed event payloads |
| SIM/REAL operator card | [OPERATOR_CARD_SIM_REAL_v52.md](OPERATOR_CARD_SIM_REAL_v52.md) | Operator mode-switch procedures |
| Command Deck startup runbook | [command-deck-startup-runbook.md](command-deck-startup-runbook.md) | Cold start / restart surfaces |
| Tauri lifecycle gate ADR | [adr/0011-tauri-lifecycle-gate-ssot.md](adr/0011-tauri-lifecycle-gate-ssot.md) | `app_surface` SSOT decision |
| Adaptive Intelligence design | [AdaptiveIntelligenceManager.md](../AdaptiveIntelligenceManager.md) | Intelligence tier semantics |
| Mode capabilities | [lumina_core/engine/mode_capabilities.py](../lumina_core/engine/mode_capabilities.py) | Authoritative mode matrix |
| Event Bus schemas | [lumina_core/agent_orchestration/schemas.py](../lumina_core/agent_orchestration/schemas.py) | Pydantic payload models |
| DNA registry | [lumina_core/evolution/dna_registry.py](../lumina_core/evolution/dna_registry.py) | PolicyDNA structure |
| Approval chain | [lumina_core/governance/approval_chain.py](../lumina_core/governance/approval_chain.py) | REAL signed promotion |

---

*Contract version 1.0 — schemas are authoritative for `tauri-app/` client code generation and backend validation.*
