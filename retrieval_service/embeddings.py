"""Deterministic, dependency-light text embeddings for literature retrieval."""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass

from retrieval_service.aliases import normalize_aliases


TOKEN_PATTERN = re.compile(r"[A-Za-z0-9]+(?:[-_][A-Za-z0-9]+)*")


@dataclass(frozen=True)
class HashingEmbedder:
    """Feature-hashing embeddings with word and adjacent-token features.

    This local model is deterministic, has no network dependency, and is useful
    for a compact curated corpus. The model name/version are persisted on every
    chunk so a neural embedder can replace it without silently mixing vectors.
    """

    dimensions: int = 384
    model_name: str = "cancerbench-biomedical-feature-hashing"
    version: str = "cbfh-384-v1"

    def _features(self, text: str) -> list[str]:
        tokens = [token.lower() for token in TOKEN_PATTERN.findall(normalize_aliases(text))]
        features = list(tokens)
        features.extend(f"{left}::{right}" for left, right in zip(tokens, tokens[1:]))
        return features

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            vector = [0.0] * self.dimensions
            for feature in self._features(text):
                digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
                bucket = int.from_bytes(digest[:4], "big") % self.dimensions
                sign = 1.0 if digest[4] & 1 else -1.0
                vector[bucket] += sign
            norm = math.sqrt(sum(value * value for value in vector))
            vectors.append([value / norm for value in vector] if norm else vector)
        return vectors


def cosine_similarity(left: list[float], right: list[float]) -> float:
    return max(0.0, min(1.0, sum(a * b for a, b in zip(left, right))))

