from app.ingestion.chunking import chunk_text


def test_short_text_produces_a_single_chunk():
    text = "The appellant filed this suit in 1998. The trial court dismissed it."

    chunks = chunk_text(text, chunk_size=256, overlap=30)

    assert len(chunks) == 1
    assert chunks[0] == text


def test_empty_text_produces_no_chunks():
    assert chunk_text("", chunk_size=256, overlap=30) == []


def test_whitespace_only_text_produces_no_chunks():
    assert chunk_text("   \n\t  ", chunk_size=256, overlap=30) == []


def test_long_text_splits_into_multiple_chunks_with_overlap():
    # 10 distinct 5-word sentences; chunk_size=12 fits 2 sentences/chunk,
    # overlap=6 fits exactly 1 sentence, so consecutive chunks should share one.
    sentences = [f"sentence{i} alpha beta gamma end." for i in range(10)]
    text = " ".join(sentences)

    chunks = chunk_text(text, chunk_size=12, overlap=6)

    assert len(chunks) > 1
    for prev, nxt in zip(chunks, chunks[1:], strict=False):
        prev_tail_sentence = prev.rsplit(" alpha", 1)[0].split()[-1]
        assert prev_tail_sentence in nxt


def test_chunks_preserve_original_sentence_order():
    text = "First sentence here. Second sentence here. Third sentence here."

    chunks = chunk_text(text, chunk_size=2, overlap=0)

    joined = " ".join(chunks)
    assert joined.index("First") < joined.index("Second") < joined.index("Third")


def test_sentence_longer_than_chunk_size_is_kept_intact():
    long_sentence = ("word " * 100).strip() + "."

    chunks = chunk_text(long_sentence, chunk_size=10, overlap=2)

    assert chunks == [long_sentence]
