from app.db.models import Chunk, Judgment
from app.ingestion.embedder import embed_texts

KEYWORD_CHUNK_TEXT = (
    "The right to privacy is a fundamental right protected under Article 21 "
    "of the Constitution of India."
)
SEMANTIC_CHUNK_TEXT = (
    "An individual's autonomy over their personal information and bodily "
    "integrity is safeguarded by the constitutional guarantee of liberty."
)
UNRELATED_CHUNK_TEXT = (
    "The assessee failed to file returns under the Income Tax Act within "
    "the prescribed statutory limitation period."
)


def _seed_judgment(db_session, title: str, raw_text: str, chunk_text: str) -> tuple[int, int]:
    judgment = Judgment(
        source_dataset="test-fixture",
        external_id=title,
        title=title,
        raw_text=raw_text,
        ingestion_status="embedded",
    )
    db_session.add(judgment)
    db_session.flush()

    [embedding] = embed_texts([chunk_text])
    chunk = Chunk(judgment_id=judgment.id, chunk_index=0, text=chunk_text, embedding=embedding)
    db_session.add(chunk)
    db_session.flush()
    db_session.commit()
    return judgment.id, chunk.id


def test_search_returns_both_keyword_and_semantic_matches(client, db_session):
    # keyword_judgment: literally contains the query's words -> found by the BM25 path.
    keyword_judgment_id, _ = _seed_judgment(
        db_session, "Privacy Rights Case", KEYWORD_CHUNK_TEXT, KEYWORD_CHUNK_TEXT
    )
    # semantic_judgment: same meaning, none of the query's literal words -> found only
    # via cosine similarity on the vector path, proving semantic retrieval works.
    semantic_judgment_id, _ = _seed_judgment(
        db_session, "Personal Autonomy Case", SEMANTIC_CHUNK_TEXT, SEMANTIC_CHUNK_TEXT
    )
    # unrelated third judgment, present only to prove search operates correctly
    # over a multi-judgment corpus rather than a single-row special case. Not
    # asserted absent below: with just 3 chunks in the DB, the unfiltered vector
    # query trivially returns all of them as "nearest neighbors".
    _seed_judgment(db_session, "Tax Assessment Case", UNRELATED_CHUNK_TEXT, UNRELATED_CHUNK_TEXT)

    response = client.post("/search", json={"query": "privacy fundamental right", "limit": 10})

    assert response.status_code == 200
    body = response.json()
    result_judgment_ids = {r["judgment_id"] for r in body["results"]}

    assert keyword_judgment_id in result_judgment_ids
    assert semantic_judgment_id in result_judgment_ids

    keyword_result = next(r for r in body["results"] if r["judgment_id"] == keyword_judgment_id)
    assert keyword_result["matched_keyword"] is True


def test_search_with_no_matches_returns_empty_results(client, db_session):
    response = client.post("/search", json={"query": "zzz nonexistent legal doctrine qqq"})

    assert response.status_code == 200
    assert response.json()["results"] == []


def test_get_judgment_returns_seeded_judgment(client, db_session):
    judgment_id, _ = _seed_judgment(
        db_session, "Sample Case", KEYWORD_CHUNK_TEXT, KEYWORD_CHUNK_TEXT
    )

    response = client.get(f"/judgments/{judgment_id}")

    assert response.status_code == 200
    assert response.json()["title"] == "Sample Case"


def test_get_judgment_returns_404_for_unknown_id(client, db_session):
    response = client.get("/judgments/999999")

    assert response.status_code == 404
