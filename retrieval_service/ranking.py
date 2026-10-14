"""Local lexical reranking for the small Phase 3 PubMed corpus."""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any

from retrieval_service.aliases import normalize_aliases


TOKEN = re.compile(r"[a-z0-9]+")
STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "by", "cause", "does", "for", "from",
    "how", "in", "is", "of", "on", "or", "the", "to", "with",
}


def _terms(text: str) -> set[str]:
    return {term for term in TOKEN.findall(normalize_aliases(text).lower()) if term not in STOPWORDS}


def rerank(query: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Combine hashed-vector similarity with IDF-weighted title/abstract matches.

    Keep vector retrieval as a candidate generator. Exact biomedical names in a
    title matter more than an accidental collision in the hashing embedding.
    The score stays in [0, 1] for the public minimum_score filter.
    """
    query_terms = _terms(query)
    if not query_terms or not rows:
        return rows

    document_terms = [
        (_terms(row["title"]), _terms(row.get("abstract") or row["passage"]))
        for row in rows
    ]
    frequencies: Counter[str] = Counter()
    for title_terms, abstract_terms in document_terms:
        frequencies.update(query_terms & (title_terms | abstract_terms))
    weights = {
        term: 1.0 + math.log((len(rows) + 1) / (frequencies[term] + 1))
        for term in query_terms
    }
    denominator = sum(weights.values())

    ranked = []
    for row, (title_terms, abstract_terms) in zip(rows, document_terms):
        lexical = sum(
            weight * (1.0 if term in title_terms else 0.65 if term in abstract_terms else 0.0)
            for term, weight in weights.items()
        ) / denominator
        vector = max(0.0, min(1.0, float(row["score"])))
        ranked.append({**row, "score": 0.45 * vector + 0.55 * lexical})
    return sorted(ranked, key=lambda row: (-row["score"], row["pmid"]))
