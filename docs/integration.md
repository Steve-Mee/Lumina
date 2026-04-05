# Integration Guide

## Existing LuminaEngine

`LuminaEngine` can continue to work if `BibleEngine` is imported from `lumina_bible`.

Recommended pattern:

```python
from lumina_bible import BibleEngine
```

## Reflection and Feedback Workflows

Use the workflow helpers in `lumina_bible.workflows`:

- `reflect_on_trade(...)`
- `process_user_feedback(...)`
- `dna_rewrite_daemon(...)`

These functions accept the existing runtime context object used in Lumina.

## Sacred Core Redaction

When exposing Bible content publicly, use:

```python
public_bible = bible_engine.export_public_bible()
```

This redacts `sacred_core` unless `LUMINA_BIBLE_EXPOSE_SACRED_CORE=true`.
