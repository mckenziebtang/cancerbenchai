from datetime import date
import os
import uuid

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from retrieval_service.aliases import extract_normalized_terms, normalize_aliases
from retrieval_service.main import create_app
from retrieval_service.schemas import ArticleInput, RetrieveRequest
from retrieval_service.service import RetrievalService
from retrieval_service.store import InMemoryLiteratureStore, PostgresLiteratureStore


def article(
    pmid: str = "34769213",
    title: str = "The role of TP53 in cisplatin resistance",
    abstract: str = (
        "TP53 knockout increased cisplatin resistance in cancer cell lines. "
        "The p53 pathway altered platinum drug sensitivity."
    ),
    year: int = 2021,
    journal: str = "Cancer Research Journal",
) -> ArticleInput:
    return ArticleInput(
        pmid=pmid,
        doi="10.1000/example",
        title=title,
        abstract=abstract,
        authors=["Ada Researcher", "Grace Scientist"],
        year=year,
        journal=journal,
        url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        ingestion_date=date(2026, 8, 18),
        selection_query="cisplatin resistance TP53 cancer",
    )


@pytest.fixture
def service() -> RetrievalService:
    retrieval = RetrievalService(InMemoryLiteratureStore(), default_minimum_score=0.01)
    retrieval.initialize()
    retrieval.ingest(
        [
            article(),
            article(
                pmid="24861025",
                title="Therapeutic targeting of ERBB2 in breast cancer",
                abstract="HER2 amplification and trastuzumab resistance involve PI3K signaling.",
                year=2014,
                journal="Molecular Oncology",
            ),
        ]
    )
    return retrieval


def test_aliases_are_normalized_for_queries_and_ingestion():
    assert normalize_aliases("p53 response to CDDP and Herceptin") == (
        "TP53 response to CISPLATIN and TRASTUZUMAB"
    )
    assert extract_normalized_terms("Taxol response in HER2 positive cells") == [
        "ERBB2",
        "PACLITAXEL",
    ]


def test_ingestion_is_idempotent_and_updates_changed_pmids():
    store = InMemoryLiteratureStore()
    retrieval = RetrievalService(store)
    retrieval.initialize()

    first = retrieval.ingest([article()])
    duplicate = retrieval.ingest([article()])
    changed = retrieval.ingest([article(abstract="A changed TP53 and cisplatin abstract.")])

    assert first.inserted == 1
    assert first.chunks_written == 1
    assert duplicate.skipped == 1
    assert duplicate.chunks_written == 0
    assert changed.updated == 1
    assert len(store.records) == 1


def test_retrieval_returns_traceable_best_passage(service):
    response = service.retrieve(
        RetrieveRequest(query="p53-associated CDDP resistance", top_k=1)
    )

    assert response.normalized_query == "TP53-associated CISPLATIN resistance"
    assert response.embedding_version == "cbfh-384-v1"
    assert len(response.results) == 1
    result = response.results[0]
    assert result.pmid == "34769213"
    assert str(result.url) == "https://pubmed.ncbi.nlm.nih.gov/34769213/"
    assert result.selection_query == "cisplatin resistance TP53 cancer"
    assert result.authors == ["Ada Researcher", "Grace Scientist"]


def test_filters_apply_year_journal_and_normalized_entity(service):
    response = service.retrieve(
        RetrieveRequest(
            query="Herceptin resistance",
            top_k=5,
            filters={"year_from": 2010, "year_to": 2015, "journal": "molecular", "gene": "HER2"},
        )
    )

    assert [result.pmid for result in response.results] == ["24861025"]


def test_minimum_score_can_return_no_evidence(service):
    response = service.retrieve(
        RetrieveRequest(
            query="unrelated lunar geology",
            top_k=5,
            filters={"minimum_score": 0.99},
        )
    )
    assert response.results == []


def test_request_rejects_invalid_ranges_and_extra_fields():
    with pytest.raises(ValidationError):
        RetrieveRequest(query="cisplatin", filters={"year_from": 2020, "year_to": 2010})
    with pytest.raises(ValidationError):
        RetrieveRequest(query="cisplatin", clinical=True)


def test_retrieval_api_and_metadata(service):
    app = create_app(service)
    with TestClient(app) as client:
        response = client.post(
            "/retrieve",
            json={"query": "TP53 cisplatin resistance", "top_k": 1, "filters": {}},
        )
        metadata = client.get("/metadata")
        health = client.get("/health")

    assert response.status_code == 200
    assert response.json()["results"][0]["pmid"] == "34769213"
    assert metadata.json()["document_count"] == 2
    assert metadata.json()["embedding_dimensions"] == 384
    assert health.json() == {"status": "ok", "database": "connected"}


def test_retrieval_api_rejects_blank_query(service):
    with TestClient(create_app(service)) as client:
        response = client.post("/retrieve", json={"query": "   "})
    assert response.status_code == 422


@pytest.mark.integration
def test_postgres_pgvector_ingestion_and_retrieval():
    """Exercise the real schema, vector operator, filters, and idempotent upsert."""
    database_url = os.getenv("POSTGRES_TEST_URL")
    if not database_url:
        pytest.skip("Set POSTGRES_TEST_URL to run against an isolated PostgreSQL instance")

    import psycopg

    pmid = str(90_000_000 + uuid.uuid4().int % 10_000_000)
    store = PostgresLiteratureStore(database_url)
    retrieval = RetrievalService(store, default_minimum_score=0.0)

    try:
        retrieval.initialize()
        first = retrieval.ingest([article(pmid=pmid)])
        duplicate = retrieval.ingest([article(pmid=pmid)])
        response = retrieval.retrieve(
            RetrieveRequest(
                query="p53-associated CDDP resistance",
                top_k=5,
                filters={"gene": "p53", "drug": "CDDP"},
            )
        )

        assert first.inserted == 1
        assert first.failed == 0
        assert duplicate.skipped == 1
        assert [result.pmid for result in response.results] == [pmid]
        assert response.results[0].score > 0
    finally:
        with psycopg.connect(database_url) as connection, connection.cursor() as cursor:
            cursor.execute("DELETE FROM literature_articles WHERE pmid = %s", (pmid,))

