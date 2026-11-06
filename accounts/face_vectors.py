"""Shared validation and normalization for 512-dimensional face embeddings."""
import math


def normalized_vector(vector):

    if not isinstance(vector, list) or len(vector) != 512:
        raise ValueError('Expected 512 dimensions')

    if any(
        isinstance(x, bool)
        or not isinstance(x, (float, int))
        or not math.isfinite(x)
        for x in vector
    ):
        raise ValueError('Expected finite numeric vector')

    # Scale first to avoid overflow
    scale = max(abs(x) for x in vector)

    if not scale:
        raise ValueError('Zero vector')

    scaled = [x / scale for x in vector]

    norm = math.sqrt(
        math.fsum(x * x for x in scaled)
    )

    return [
        x / norm
        for x in scaled
    ]
