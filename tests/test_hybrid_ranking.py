from retrieval_service.ranking import rerank


def test_lexical_reranking_promotes_exact_title_over_hash_collision():
    rows = [
        {"pmid": "1", "title": "General cancer treatment", "abstract": "Treatment outcomes.",
         "passage": "General cancer treatment", "score": 0.55},
        {"pmid": "2", "title": "Olaparib-resistant BRCA2 ovarian cancer cells",
         "abstract": "Restored BRCA2 causes olaparib resistance.",
         "passage": "Olaparib-resistant BRCA2 ovarian cancer cells", "score": 0.25},
    ]
    ranked = rerank("BRCA2 olaparib resistance in ovarian cancer cells", rows)
    assert [row["pmid"] for row in ranked] == ["2", "1"]
    assert all(0 <= row["score"] <= 1 for row in ranked)
