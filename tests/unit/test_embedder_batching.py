from app.ingestion.embedder import EMBEDDING_DIM, embed_texts


class FakeModel:
    def __init__(self):
        self.calls: list[dict] = []

    def encode(self, texts, batch_size, show_progress_bar):
        self.calls.append({"n_texts": len(texts), "batch_size": batch_size})
        return [[0.1] * EMBEDDING_DIM for _ in texts]


def test_embed_texts_makes_a_single_batched_model_call_not_one_per_text():
    model = FakeModel()
    texts = [f"chunk {i}" for i in range(130)]

    embed_texts(texts, model=model, batch_size=64)

    assert len(model.calls) == 1
    assert model.calls[0]["n_texts"] == 130
    assert model.calls[0]["batch_size"] == 64


def test_embed_texts_returns_correct_dimension_per_vector():
    model = FakeModel()

    vectors = embed_texts(["a", "b", "c"], model=model)

    assert len(vectors) == 3
    assert all(len(v) == EMBEDDING_DIM for v in vectors)


def test_embed_texts_empty_input_returns_empty_list_without_calling_model():
    model = FakeModel()

    assert embed_texts([], model=model) == []
    assert model.calls == []


def test_embed_texts_output_vectors_are_plain_float_lists():
    model = FakeModel()

    [vector] = embed_texts(["chunk"], model=model)

    assert isinstance(vector, list)
    assert all(isinstance(x, float) for x in vector)
