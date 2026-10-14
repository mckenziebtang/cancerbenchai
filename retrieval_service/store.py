from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Protocol

from retrieval_service.embeddings import cosine_similarity
from retrieval_service.schemas import ArticleInput, RetrievalFilters


class LiteratureStore(Protocol):
    def initialize(self, dimensions: int) -> None: ...

    def health(self) -> bool: ...

    def upsert_article(
        self,
        article: ArticleInput,
        chunks: list[str],
        vectors: list[list[float]],
        normalized_terms: list[str],
        embedding_model: str,
        embedding_version: str,
    ) -> str: ...

    def search(
        self,
        query_vector: list[float],
        top_k: int,
        filters: RetrievalFilters,
        required_terms: list[str],
    ) -> list[dict[str, Any]]: ...

    def counts(self) -> tuple[int, int]: ...


def article_content_hash(article: ArticleInput) -> str:
    payload = article.model_dump(mode="json", exclude={"ingestion_date"})
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


class PostgresLiteratureStore:
    """PostgreSQL/pgvector repository. Connections are opened per operation."""

    def __init__(self, database_url: str):
        self.database_url = database_url
        self.dimensions: int | None = None

    def _connect(self):
        try:
            import psycopg
        except ImportError as exc:  # pragma: no cover - installation error path
            raise RuntimeError("psycopg is required for PostgreSQL retrieval") from exc
        return psycopg.connect(self.database_url)

    def initialize(self, dimensions: int) -> None:
        self.dimensions = dimensions
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute("CREATE EXTENSION IF NOT EXISTS vector")
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS literature_articles (
                    pmid TEXT PRIMARY KEY,
                    doi TEXT,
                    title TEXT NOT NULL,
                    abstract TEXT NOT NULL,
                    authors JSONB NOT NULL DEFAULT '[]',
                    publication_year INTEGER,
                    journal TEXT,
                    canonical_url TEXT NOT NULL,
                    ingestion_date DATE NOT NULL,
                    selection_query TEXT NOT NULL,
                    normalized_terms TEXT[] NOT NULL DEFAULT '{}',
                    content_hash TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS literature_chunks (
                    id BIGSERIAL PRIMARY KEY,
                    pmid TEXT NOT NULL REFERENCES literature_articles(pmid) ON DELETE CASCADE,
                    chunk_index INTEGER NOT NULL,
                    passage TEXT NOT NULL,
                    embedding vector({int(dimensions)}) NOT NULL,
                    embedding_model TEXT NOT NULL,
                    embedding_version TEXT NOT NULL,
                    UNIQUE (pmid, chunk_index)
                )
                """
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS literature_year_idx "
                "ON literature_articles(publication_year)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS literature_terms_idx "
                "ON literature_articles USING GIN(normalized_terms)"
            )

    def health(self) -> bool:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            return cursor.fetchone() == (1,)

    def upsert_article(
        self,
        article: ArticleInput,
        chunks: list[str],
        vectors: list[list[float]],
        normalized_terms: list[str],
        embedding_model: str,
        embedding_version: str,
    ) -> str:
        content_hash = article_content_hash(article)
        canonical_url = str(article.url or f"https://pubmed.ncbi.nlm.nih.gov/{article.pmid}/")
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT content_hash, embedding_version FROM literature_articles a "
                "LEFT JOIN literature_chunks c USING (pmid) WHERE a.pmid = %s LIMIT 1",
                (article.pmid,),
            )
            existing = cursor.fetchone()
            if existing == (content_hash, embedding_version):
                return "skipped"
            outcome = "updated" if existing else "inserted"
            cursor.execute(
                """
                INSERT INTO literature_articles (
                    pmid, doi, title, abstract, authors, publication_year, journal,
                    canonical_url, ingestion_date, selection_query, normalized_terms, content_hash
                ) VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (pmid) DO UPDATE SET
                    doi = EXCLUDED.doi, title = EXCLUDED.title,
                    abstract = EXCLUDED.abstract, authors = EXCLUDED.authors,
                    publication_year = EXCLUDED.publication_year,
                    journal = EXCLUDED.journal, canonical_url = EXCLUDED.canonical_url,
                    ingestion_date = EXCLUDED.ingestion_date,
                    selection_query = EXCLUDED.selection_query,
                    normalized_terms = EXCLUDED.normalized_terms,
                    content_hash = EXCLUDED.content_hash, updated_at = NOW()
                """,
                (
                    article.pmid, article.doi, article.title, article.abstract,
                    json.dumps(article.authors), article.year, article.journal,
                    canonical_url, article.ingestion_date, article.selection_query,
                    normalized_terms, content_hash,
                ),
            )
            cursor.execute("DELETE FROM literature_chunks WHERE pmid = %s", (article.pmid,))
            cursor.executemany(
                """
                INSERT INTO literature_chunks (
                    pmid, chunk_index, passage, embedding, embedding_model, embedding_version
                ) VALUES (%s, %s, %s, %s::vector, %s, %s)
                """,
                [
                    (
                        article.pmid, index, passage, _vector_literal(vector),
                        embedding_model, embedding_version,
                    )
                    for index, (passage, vector) in enumerate(zip(chunks, vectors))
                ],
            )
        return outcome

    def search(
        self,
        query_vector: list[float],
        top_k: int,
        filters: RetrievalFilters,
        required_terms: list[str],
    ) -> list[dict[str, Any]]:
        clauses = ["1 = 1"]
        params: list[Any] = [_vector_literal(query_vector)]
        if filters.year_from is not None:
            clauses.append("a.publication_year >= %s")
            params.append(filters.year_from)
        if filters.year_to is not None:
            clauses.append("a.publication_year <= %s")
            params.append(filters.year_to)
        if filters.journal:
            clauses.append("a.journal ILIKE %s")
            params.append(f"%{filters.journal}%")
        if required_terms:
            clauses.append("a.normalized_terms @> %s")
            params.append(required_terms)
        params.extend([_vector_literal(query_vector), top_k])
        sql = f"""
            SELECT * FROM (
                SELECT DISTINCT ON (a.pmid)
                       a.pmid, a.doi, a.title, a.abstract, c.passage, a.publication_year,
                       a.journal, a.authors, a.canonical_url, a.ingestion_date,
                       a.selection_query, 1 - (c.embedding <=> %s::vector) AS score
                FROM literature_chunks c
                JOIN literature_articles a USING (pmid)
                WHERE {' AND '.join(clauses)}
                ORDER BY a.pmid, c.embedding <=> %s::vector
            ) AS best_passages
            ORDER BY score DESC, pmid
            LIMIT %s
        """
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(sql, params)
            columns = [description.name for description in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def counts(self) -> tuple[int, int]:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT (SELECT COUNT(*) FROM literature_articles), "
                "(SELECT COUNT(*) FROM literature_chunks)"
            )
            documents, chunks = cursor.fetchone()
            return int(documents), int(chunks)


def _vector_literal(vector: list[float]) -> str:
    return "[" + ",".join(f"{value:.9g}" for value in vector) + "]"


@dataclass
class InMemoryLiteratureStore:
    """A deterministic store used by unit tests and small local experiments."""

    records: dict[str, dict[str, Any]] = field(default_factory=dict)
    dimensions: int | None = None

    def initialize(self, dimensions: int) -> None:
        self.dimensions = dimensions

    def health(self) -> bool:
        return True

    def upsert_article(
        self,
        article: ArticleInput,
        chunks: list[str],
        vectors: list[list[float]],
        normalized_terms: list[str],
        embedding_model: str,
        embedding_version: str,
    ) -> str:
        content_hash = article_content_hash(article)
        existing = self.records.get(article.pmid)
        if existing and existing["content_hash"] == content_hash and existing["embedding_version"] == embedding_version:
            return "skipped"
        outcome = "updated" if existing else "inserted"
        self.records[article.pmid] = {
            "article": article,
            "chunks": chunks,
            "vectors": vectors,
            "normalized_terms": normalized_terms,
            "embedding_model": embedding_model,
            "embedding_version": embedding_version,
            "content_hash": content_hash,
        }
        return outcome

    def search(
        self,
        query_vector: list[float],
        top_k: int,
        filters: RetrievalFilters,
        required_terms: list[str],
    ) -> list[dict[str, Any]]:
        matches: list[dict[str, Any]] = []
        for record in self.records.values():
            article: ArticleInput = record["article"]
            if filters.year_from is not None and (article.year is None or article.year < filters.year_from):
                continue
            if filters.year_to is not None and (article.year is None or article.year > filters.year_to):
                continue
            if filters.journal and filters.journal.lower() not in (article.journal or "").lower():
                continue
            if required_terms and not set(required_terms).issubset(record["normalized_terms"]):
                continue
            best: dict[str, Any] | None = None
            for passage, vector in zip(record["chunks"], record["vectors"]):
                candidate = {
                        "pmid": article.pmid,
                        "doi": article.doi,
                        "title": article.title,
                        "abstract": article.abstract,
                        "passage": passage,
                        "publication_year": article.year,
                        "journal": article.journal,
                        "authors": article.authors,
                        "canonical_url": str(
                            article.url or f"https://pubmed.ncbi.nlm.nih.gov/{article.pmid}/"
                        ),
                        "ingestion_date": article.ingestion_date,
                        "selection_query": article.selection_query,
                        "score": cosine_similarity(query_vector, vector),
                    }
                if best is None or candidate["score"] > best["score"]:
                    best = candidate
            if best is not None:
                matches.append(best)
        matches.sort(key=lambda item: (-item["score"], item["pmid"]))
        return matches[:top_k]

    def counts(self) -> tuple[int, int]:
        return len(self.records), sum(len(record["chunks"]) for record in self.records.values())
