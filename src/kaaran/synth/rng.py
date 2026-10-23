"""Named random streams: each component gets its own generator derived from (seed, name),
so adding or reordering components never shifts the random numbers of the others."""

from __future__ import annotations

import hashlib

import numpy as np


def stream(seed: int, name: str) -> np.random.Generator:
    tag = int.from_bytes(hashlib.sha256(name.encode("utf-8")).digest()[:8], "little")
    return np.random.default_rng([seed, tag])
