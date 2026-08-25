import re

_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+")


def split_sentences(text: str) -> list[str]:
    text = text.strip()
    if not text:
        return []
    return [s for s in _SENTENCE_BOUNDARY.split(text) if s]


def _approx_token_count(sentence: str) -> int:
    return len(sentence.split())


def chunk_text(text: str, chunk_size: int = 256, overlap: int = 30) -> list[str]:
    """Split judgment text into sentence-boundary-aware chunks of ~chunk_size tokens,
    carrying ~overlap trailing tokens of context into the next chunk.

    Token counts are approximated by whitespace word counts rather than the
    embedder's real subword tokenizer: chunk boundaries only need a rough budget,
    and keeping this module dependency-free (no transformers import) is what makes
    it fast and offline-safe to unit test. A single sentence longer than
    chunk_size is kept intact as its own chunk rather than split mid-sentence.
    """
    sentences = split_sentences(text)
    if not sentences:
        return []

    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for sentence in sentences:
        sentence_len = _approx_token_count(sentence)
        if current and current_len + sentence_len > chunk_size:
            chunks.append(" ".join(current))
            overlap_sentences: list[str] = []
            overlap_len = 0
            for s in reversed(current):
                s_len = _approx_token_count(s)
                if overlap_len + s_len > overlap:
                    break
                overlap_sentences.insert(0, s)
                overlap_len += s_len
            current, current_len = overlap_sentences, overlap_len

        current.append(sentence)
        current_len += sentence_len

    if current:
        chunks.append(" ".join(current))

    return chunks
