from datetime import date

from retrieval_service.evaluate import evaluate
from retrieval_service.schemas import ArticleInput
from retrieval_service.service import RetrievalService
from retrieval_service.store import InMemoryLiteratureStore


def test_retrieval_evaluation_smoke():
    service = RetrievalService(InMemoryLiteratureStore())
    service.initialize()
    service.ingest([ArticleInput(pmid="12345678", title="TP53 cisplatin resistance", abstract="TP53 mutation and cisplatin resistance in cancer cell lines.", authors=["Test Author"], year=2024, journal="Synthetic fixture", url="https://pubmed.ncbi.nlm.nih.gov/12345678/", ingestion_date=date(2026, 10, 14), selection_query="test fixture")])
    report = evaluate(service, [{"name": "gene-drug", "query": "TP53 cisplatin resistance", "expected_pmids": ["12345678"]}, {"name": "no-evidence", "query": "lunar geology", "filters": {"minimum_score": 0.99}, "expected_pmids": []}], 5)
    assert report["recall_at_k"] == 1
    assert report["no_evidence_accuracy"] == 1
    assert report["citation_metadata_completeness"] == 1
