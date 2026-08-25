# Data sources

This project does not scrape Indian Kanoon directly: they have no free bulk
API, and automated bulk scraping at the target scale is slow, ToS-questionable,
and easy to get IP-blocked partway through. Instead, judgments are sourced
from an open dataset built by academically scraping official court records.

## Current source (default, no auth required)

[`sinhal/Indian_Supreme_Court_Judgments`](https://huggingface.co/datasets/sinhal/Indian_Supreme_Court_Judgments)
— **~41.8K real Supreme Court of India judgments**, OpenRAIL license, sourced
from [JUDIS.NIC.IN](http://judis.nic.in), the Supreme Court's own official
judgment repository (an even more authoritative primary source than Indian
Kanoon, which itself draws from JUDIS). No HuggingFace account or token
required — `scripts/download_datasets.py` pulls it directly.

Per-judgment structured fields: `pet`/`res` (petitioner/respondent, ~97%
populated), `bench` (judges, ~74% populated, comma-separated — parsed into an
array), `judgment_dates` (~100% populated, normalized from source `DD-MM-YYYY`
to ISO at download time), `case_no` (used to derive a rough `case_type`), and
`full_text` (the judgment itself). `court` is a constant, "Supreme Court of
India" — this source is single-court, not multi-court. Fields genuinely
absent in the source (not present ~3–26% of the time depending on the field)
are stored as SQL `NULL` rather than guessed at.

The raw text retains original OCR/scrape artifacts from the source pipeline
(e.g. "company" substituted for "com", "number" for "no" — a known corruption
pattern in some older Indian court OCR runs). Left as-is: silently
"correcting" judgment text is worse than a visible, honest artifact.

## Datasets considered during planning, not used

Two multi-court datasets were originally identified for their court/case-type
diversity — `opennyaiorg/InJudgements_dataset` (Apache-2.0, ~13K judgments,
24 courts) and `Exploration-Lab/IL-TUR`'s `CJPE` config (CC-BY-NC-SA-4.0,
~34K SC judgments, text-only). At ingestion-build time both turned out to be
**gated HuggingFace repos** requiring an authenticated, access-approved
account — not surfaced by a plain dataset-card read during planning, only by
actually attempting a download. `scripts/download_datasets.py` keeps both
download functions (`download_injudgements`, `download_il_tur`) for anyone
who runs `huggingface-cli login` with an approved account and wants that
court diversity; they are not the default path.

## Scale

`sinhal/Indian_Supreme_Court_Judgments` alone is ~41.8K judgments — close to
the original "~50K" target on its own, though single-court rather than
multi-court. `scripts/download_datasets.py --max-rows N` caps the download for
a fast local sample (e.g. `--max-rows 500` for a Week 1 proof-of-pipeline
run); the full corpus is the Week 2–3 scale-up target, ingested as an
unattended offline batch job via `scripts/ingest_judgments.py` or
`app.ingestion.ingest_cli` — the same idempotent code path either way, only
`--limit`/`--max-rows` differ. Every `judgments` row stores `source_dataset`
and `source_url` (a JUDIS.NIC.IN-relative path) for provenance.
