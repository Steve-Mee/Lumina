# Protobuf contracts

## Execution Fabric (`lumina.execution.v1`)

| File | Purpose |
|------|---------|
| `lumina/execution/v1/fabric.proto` | gRPC SSOT for Brain ↔ NT8 Execution Fabric |

### Generate Python stubs

```bash
pip install -r requirements-trading.txt -r requirements-dev.txt
python scripts/generate_fabric_proto.py
```

Output: `lumina_core/broker/ninjatrader/generated/`

### Rules

- Additive fields only within a major package version
- Unknown critical enums → Fabric rejects fail-closed
- `client_order_id` is the place-order idempotency key
