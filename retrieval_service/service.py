from __future__ import annotations

import time
import logging
from collections.abc import Iterable

from retrieval_service.aliases import extract_normalized_terms, normalize_aliases, normalize_filter_term
from retrieval_service.chunking import chunk_abstract
from retrieval_service.embeddings import HashingEmbedder
from retrieval_service.schemas import (
    ArticleInput,
    IngestionStats,
    RetrievalMetadata,
    RetrievalResult,
    RetrieveRequest,
    RetrieveResponse,
)
from retrieval_service.store import LiteratureStore


LOGGER = logging.getLogger("cancerbench.ingestion")


class RetrievalService:
    def __init__(
        self,
        store: LiteratureStore,
        embedder: HashingEmbedder | None = None,
        default_minimum_score: float = 0.08,
    ):
        self.store = store
        self.embedder = embedder or HashingEmbedder()
        self.default_minimum_score = default_minimum_score

    def initialize(self) -> None:
        self.store.initialize(self.embedder.dimensions)

    def ingest(self, articles: Iterable[ArticleInput], batch_size: int = 64) -> IngestionStats:
        stats = IngestionStats()
        for article in articles:
            try:
                chunks = chunk_abstract(article.title, article.abstract)
                vectors: list[list[float]] = []
                for start in range(0, len(chunks), batch_size):
                    vectors.extend(self.embedder.embed(chunks[start : start + batch_size]))
                terms = extract_normalized_terms(f"{article.title} {article.abstract}")
                outcome = self.store.upsert_article(
                    article, chunks, vectors, terms,
                    self.embedder.model_name, self.embedder.version,
                )
                setattr(stats, outcome, getattr(stats, outcome) + 1)
                if outcome != "skipped":
                    stats.chunks_written += len(chunks)
            except Exception:
                stats.failed += 1
                LOGGER.exception("Failed to ingest PMID %s", article.pmid)
        return stats

    def retrieve(self, request: RetrieveRequest) -> RetrieveResponse:
        started = time.perf_counter()
        normalized_query = normalize_aliases(request.query)
        query_vector = self.embedder.embed([normalized_query])[0]
        required_terms = []
        if request.filters.drug:
            required_terms.append(normalize_filter_term(request.filters.drug))
        if request.filters.gene:
            required_terms.append(normalize_filter_term(request.filters.gene))
        rows = self.store.search(query_vector, request.top_k, request.filters, required_terms)
        minimum_score = (
            request.filters.minimum_score
            if request.filters.minimum_score is not None
            else self.default_minimum_score
        )
        results = [
            RetrievalResult(
                pmid=str(row["pmid"]), doi=row["doi"], title=row["title"],
                snippet=row["passage"], score=round(float(row["score"]), 6),
                year=row["publication_year"], journal=row["journal"],
                authors=row["authors"] or [], url=row["canonical_url"],
                ingestion_date=row["ingestion_date"],
                selection_query=row["selection_query"],
            )
            for row in rows
            if float(row["score"]) >= minimum_score
        ]
        return RetrieveResponse(
            results=results,
            embedding_version=self.embedder.version,
            normalized_query=normalized_query,
            latency_ms=round((time.perf_counter() - started) * 1000, 3),
        )

    def metadata(self) -> RetrievalMetadata:
        documents, chunks = self.store.counts()
        return RetrievalMetadata(
            embedding_model=self.embedder.model_name,
            embedding_version=self.embedder.version,
            embedding_dimensions=self.embedder.dimensions,
            document_count=documents,
            chunk_count=chunks,
        )
