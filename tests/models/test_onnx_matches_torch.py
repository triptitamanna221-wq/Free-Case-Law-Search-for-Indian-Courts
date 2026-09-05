"""Guards the two properties that make the onnx serving path safe to use.

These need the real models (~90MB download, cached in CI), so they're marked
`models` and kept out of tests/unit, which stays offline and torch-free.
"""

import subprocess
import sys

import numpy as np
import pytest

pytestmark = pytest.mark.models

TEXTS = [
    "oppression and mismanagement of a company",
    "The appellant challenged the order of the High Court dated 12 March 1998.",
    "arbitration clause",
    "a" * 5000,  # exercises truncation at max_seq_length=256
    "x",  # single token
]


def test_onnx_vectors_match_sentence_transformers():
    """The ~883K chunk embeddings in Postgres were written by the torch path.

    Query vectors come from the onnx path now, so if these two drifted apart,
    cosine distance against the stored corpus would silently return nonsense
    rather than fail loudly. 0.9999 leaves room for float32 noise (observed
    max abs difference is ~1e-7) while still catching a real divergence, like
    a pooling or normalization mismatch.
    """
    from app.ingestion.embedder import embed_texts
    from app.ingestion.onnx_embedder import embed_texts_onnx

    onnx_vecs = np.array(embed_texts_onnx(TEXTS))
    torch_vecs = np.array(embed_texts(TEXTS))

    assert onnx_vecs.shape == torch_vecs.shape == (len(TEXTS), 384)

    cosines = np.sum(onnx_vecs * torch_vecs, axis=1)
    assert cosines.min() > 0.9999, f"onnx/torch vectors diverged: {cosines}"


def test_onnx_vectors_are_unit_length():
    """Normalization has to happen here explicitly.

    sentence-transformers applies a Normalize module after pooling; onnx
    returns raw last_hidden_state, so forgetting this step would leave
    unnormalized vectors that still *look* plausible but rank differently
    under cosine distance.
    """
    from app.ingestion.onnx_embedder import embed_texts_onnx

    norms = np.linalg.norm(np.array(embed_texts_onnx(TEXTS)), axis=1)
    np.testing.assert_allclose(norms, 1.0, atol=1e-5)


def test_pooling_is_independent_of_batch_padding():
    """Padding must be masked out of the mean, not averaged in.

    Encoded alone vs. alongside a much longer text, a short string gets very
    different amounts of padding. If the mask were dropped, its vector would
    change depending on what it was batched with -- which is exactly the kind
    of bug that survives a smoke test and quietly degrades retrieval.
    """
    from app.ingestion.onnx_embedder import embed_texts_onnx

    [alone] = embed_texts_onnx(["arbitration clause"])
    batched = embed_texts_onnx(["arbitration clause", "word " * 300])[0]

    np.testing.assert_allclose(np.array(alone), np.array(batched), atol=1e-5)


def test_serving_path_never_imports_torch():
    """Regression guard for the OOM this whole module exists to fix.

    `import torch` alone measured ~315MB RSS, against a 512MB container
    limit. Run in a subprocess because the other tests in this file import
    torch deliberately.
    """
    code = (
        "import sys;"
        "from app.main import app;"
        "from app.ingestion.onnx_embedder import embed_texts_onnx;"
        "embed_texts_onnx(['arbitration clause']);"
        "print('torch' in sys.modules)"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    assert result.stdout.strip().endswith("False"), (
        f"the serving path imported torch, which reintroduces the OOM: {result.stdout}"
    )
