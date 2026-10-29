# Research bars (not in git)

NT8 1-minute MES/MNQ continuous files are **not** committed. They are private
and too large. Load them with:

```text
export LUMINA_RESEARCH_DATA_DIR=/absolute/path/to/data/research
```

Expected layout:

```text
$LUMINA_RESEARCH_DATA_DIR/MES/1m/*.csv
$LUMINA_RESEARCH_DATA_DIR/MNQ/1m/*.csv
```

The tracked file `data/research/manifest.json` records sha256s, ranges, NT8
roll dates, and known gaps. Never fill a gap. Never commit the CSVs.
