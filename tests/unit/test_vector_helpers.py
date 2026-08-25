import dataclasses

import pytest

from hybrid_search.types import BM25Hit, RankedResult, VectorHit
from hybrid_search.vector import cosine_distance_to_similarity


@pytest.mark.parametrize(
    ("distance", "expected_similarity"),
    [(0.0, 1.0), (1.0, 0.0), (2.0, -1.0)],
)
def test_cosine_distance_to_similarity_boundaries(distance, expected_similarity):
    assert cosine_distance_to_similarity(distance) == pytest.approx(expected_similarity)


@pytest.mark.parametrize("cls", [BM25Hit, VectorHit, RankedResult])
def test_dataclasses_are_frozen(cls):
    assert cls.__dataclass_params__.frozen is True


def test_frozen_dataclass_rejects_mutation():
    hit = BM25Hit(chunk_id=1, rank=0.5)

    with pytest.raises(dataclasses.FrozenInstanceError):
        hit.rank = 0.9
