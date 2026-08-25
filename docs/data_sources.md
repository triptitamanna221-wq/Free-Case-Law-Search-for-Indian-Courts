# Data sources

This project does not scrape Indian Kanoon directly: they have no free bulk
API, and automated bulk scraping at the target scale is slow, ToS-questionable,
and easy to get IP-blocked partway through. Instead, judgments are sourced from
two open datasets that were themselves built by academically scraping Indian
Kanoon, unioned for scale and diversity:

| Dataset | Size | License | Role |
|---|---|---|---|
| [`opennyaiorg/InJudgements_dataset`](https://huggingface.co/datasets/opennyaiorg/InJudgements_dataset) | ~13K judgments, 1950–2017, 24 courts, 8 case types | Apache-2.0 | Week 1 sample; richer per-judgment metadata (court, case type, IndianKanoon source URL). |
| [`Exploration-Lab/IL-TUR`](https://huggingface.co/datasets/Exploration-Lab/IL-TUR) (`CJPE` config) | ~34K Supreme Court judgments | CC-BY-NC-SA-4.0 | Week 2–3 scale-up. Built from the ILDC corpus ([Malik et al., ACL 2021](https://aclanthology.org/2021.acl-long.313/)); text-only, no structured court/date/party fields. |

After light dedup, the union is **~47–48K judgments** — reported honestly in
the README as "~48K", not padded to a literal 50,000.

**License note:** IL-TUR is CC-BY-NC-SA-4.0 (non-commercial). This is fine for
a free portfolio tool but blocks any future monetization of that slice of the
corpus without renegotiating with the dataset authors. Every `judgments` row
stores `source_dataset` and `source_url` for provenance.

## Scale

Full-corpus ingestion (chunking + embedding all ~48K judgments, ~150–250K
chunks) runs as an unattended offline batch job via
`app.ingestion.ingest_cli`, taking an estimated 1.5–3 hours of CPU embedding
time. It is not a Week 1 deliverable — Week 1 proves the same code path
end-to-end on a ~500–1,000 judgment sample.
