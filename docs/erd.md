# Schema ERD

```mermaid
erDiagram
    USERS ||--o{ SAVED_SEARCHES : "saves"
    JUDGMENTS ||--o{ CHUNKS : "split into"
    JUDGMENTS ||--o{ CITATIONS : "cites (as citing_judgment)"
    JUDGMENTS ||--o{ CITATIONS : "cited by (as cited_judgment)"

    USERS {
        uuid id PK
        text email UK
        text hashed_password "nullable, no auth flows yet"
        text full_name
        boolean is_active
        timestamptz created_at
        timestamptz updated_at
    }

    JUDGMENTS {
        bigint id PK
        text source_dataset
        text source_url
        text external_id "UK with source_dataset"
        text title
        text court
        text case_type
        date decision_date
        text[] judges
        text petitioner
        text respondent
        text raw_text
        tsvector text_tsv "GENERATED, GIN indexed"
        text language
        text ingestion_status "pending|chunked|embedded|failed"
        timestamptz created_at
        timestamptz updated_at
    }

    CHUNKS {
        bigint id PK
        bigint judgment_id FK
        int chunk_index "UK with judgment_id"
        text text
        tsvector text_tsv "GENERATED, GIN indexed"
        vector_384 embedding "pgvector, HNSW indexed"
        text embedding_model
        int token_count
        timestamptz created_at
    }

    CITATIONS {
        bigint id PK
        bigint citing_judgment_id FK
        bigint cited_judgment_id FK "nullable, target may be outside corpus"
        text cited_text
        text citation_type
        timestamptz created_at
    }

    SAVED_SEARCHES {
        bigint id PK
        uuid user_id FK "nullable, no auth flows yet"
        text query_text
        jsonb filters
        timestamptz created_at
    }
```

## Index rationale

| Index | Type | Why |
|---|---|---|
| `chunks_text_tsv_gin` | GIN on tsvector | Primary BM25 keyword-search path (`ts_rank_cd` + `@@`). |
| `chunks_embedding_hnsw` | HNSW, cosine ops | ANN search for the semantic path. Chosen over IVFFlat because IVFFlat needs a `lists` param tuned to *final* row count and gives poor recall if built before the table is populated — a bad fit for an incrementally-growing, resumable ingest. HNSW builds incrementally and gives better recall/latency at this project's ~150–250K vector scale. Built as its own migration (`0002`), separate from schema DDL, so routine schema changes don't pay HNSW build cost. |
| `judgments_text_tsv_gin` | GIN on tsvector | Doc-level keyword fallback / admin queries. |
| `judgments_court_idx`, `judgments_decision_date_idx` | btree | Filter predicates that commonly accompany a search query. |
| FK indexes on `chunks`, `citations`, `saved_searches` | btree | Join paths (chunk→judgment, citation→judgment, saved_search→user). |
