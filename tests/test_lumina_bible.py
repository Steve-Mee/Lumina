from __future__ import annotations

import json
from pathlib import Path

from lumina_core.evolution.lumina_bible import LuminaBible


def test_lumina_bible_appends_generated_rule_and_links_hash(tmp_path: Path) -> None:
    bible_path = tmp_path / "bible.jsonl"
    bible = LuminaBible(path=bible_path)

    first = bible.append_generated_rule(
        dna_hash="dna-1",
        lineage_hash="L1",
        generation=1,
        fitness=1.25,
        hypothesis="h1",
        code="def generated_strategy(context):\n    return {}\n",
    )
    second = bible.append_generated_rule(
        dna_hash="dna-2",
        lineage_hash="L1",
        generation=2,
        fitness=1.45,
        hypothesis="h2",
        code="def generated_strategy(context):\n    return {}\n",
    )

    assert first.previous_hash == "GENESIS"
    assert second.previous_hash == first.entry_hash
    assert bible_path.exists()


def test_lumina_bible_lists_recent_generated_rules(tmp_path: Path) -> None:
    bible_path = tmp_path / "bible.jsonl"
    with bible_path.open("w", encoding="utf-8") as handle:
        handle.write(json.dumps({"entry_type": "other", "dna_hash": "x"}) + "\n")

    bible = LuminaBible(path=bible_path)
    bible.append_generated_rule(
        dna_hash="dna-1",
        lineage_hash="L2",
        generation=3,
        fitness=2.0,
        hypothesis="h",
        code="def generated_strategy(context):\n    return {}\n",
    )

    rows = bible.list_recent_generated_rules(limit=10)

    assert len(rows) == 1
    assert rows[0]["entry_type"] == "generated_strategy_rule"
