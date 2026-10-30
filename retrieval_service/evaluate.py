from __future__ import annotations

import argparse
import json
import statistics
import time
import math
from pathlib import Path

from retrieval_service.schemas import RetrieveRequest
from retrieval_service.service import RetrievalService
from retrieval_service.store import PostgresLiteratureStore


def evaluate(service: RetrievalService, cases: list[dict], top_k: int) -> dict:
    reciprocal_ranks: list[float] = []
    recalls: list[float] = []
    latencies: list[float] = []
    completeness: list[float] = []
    no_evidence_checks: list[bool] = []
    details = []
    for case in cases:
        started = time.perf_counter()
        response = service.retrieve(
            RetrieveRequest(query=case["query"], top_k=top_k, filters=case.get("filters", {}))
        )
        latencies.append((time.perf_counter() - started) * 1000)
        returned = [result.pmid for result in response.results]
        expected = set(case["expected_pmids"])
        relevant_returned = expected.intersection(returned)
        rank = next((index + 1 for index, pmid in enumerate(returned) if pmid in expected), None)
        if expected:
            recall = len(relevant_returned) / len(expected)
            reciprocal_rank = 1 / rank if rank else 0.0
            recalls.append(recall)
            reciprocal_ranks.append(reciprocal_rank)
        else:
            recall = None
            reciprocal_rank = None
            no_evidence_checks.append(not returned)
        for result in response.results:
            fields = [result.pmid, result.title, result.url, result.year, result.journal, result.ingestion_date]
            completeness.append(sum(value is not None and value != "" for value in fields) / len(fields))
        details.append(
            {
                "name": case["name"], "returned_pmids": returned,
                "expected_pmids": sorted(expected), "recall_at_k": recall,
                "reciprocal_rank": reciprocal_rank,
                "no_evidence_correct": not returned if not expected else None,
            }
        )
    return {
        "case_count": len(cases), "top_k": top_k,
        "positive_case_count": len(recalls),
        "no_evidence_case_count": len(no_evidence_checks),
        "recall_at_k": statistics.fmean(recalls) if recalls else 0.0,
        "mean_reciprocal_rank": statistics.fmean(reciprocal_ranks) if reciprocal_ranks else 0.0,
        "no_evidence_accuracy": (
            statistics.fmean(no_evidence_checks) if no_evidence_checks else None
        ),
        "citation_metadata_completeness": statistics.fmean(completeness) if completeness else 0.0,
        "latency_ms": {
            "mean": statistics.fmean(latencies) if latencies else 0.0,
            "p95": sorted(latencies)[max(0, math.ceil(len(latencies) * 0.95) - 1)] if latencies else 0.0,
        },
        "cases": details,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate CancerBench literature retrieval")
    parser.add_argument("--cases", type=Path, default=Path("literature_data/evaluation_queries.json"))
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    cases = json.loads(args.cases.read_text(encoding="utf-8"))["cases"]
    import os
    service = RetrievalService(
        PostgresLiteratureStore(
            os.getenv("DATABASE_URL", "postgresql://cancerbench:cancerbench@localhost:5432/cancerbench")
        )
    )
    report = evaluate(service, cases, args.top_k)
    rendered = json.dumps(report, indent=2)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

