"""Exercise the real Compose stack. Uses no external API or paid service."""

import argparse
import json
import os
import subprocess
import time
import urllib.request

PORTS = {"prediction": 18000, "explanation": 18001, "retrieval": 18002, "research": 18003}


def request(service, path, data=None):
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(f"http://127.0.0.1:{PORTS[service]}{path}", data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as response:
        return json.load(response)


def fixture(remove=False):
    # CI uses a unique, clearly synthetic ID and removes it afterward.
    if not os.getenv("COMPOSE_PROJECT_NAME", "").startswith("cancerbench-ci"):
        raise RuntimeError("Fixture seeding is restricted to a cancerbench-ci Compose project")
    setup = '''
import os
from datetime import date
from retrieval_service.schemas import ArticleInput
from retrieval_service.service import RetrievalService
from retrieval_service.store import PostgresLiteratureStore
service = RetrievalService(PostgresLiteratureStore(os.environ['DATABASE_URL']))
service.initialize()
stats = service.ingest([ArticleInput(pmid='999999999999', title='Synthetic CI fixture: TP53 cisplatin resistance', abstract='Synthetic test record about TP53 and cisplatin resistance. This is not a scientific publication.', authors=['CI Fixture'], year=2024, journal='Synthetic CI fixture', url='https://pubmed.ncbi.nlm.nih.gov/999999999999/', ingestion_date=date(2026,10,14), selection_query='CI smoke test')])
assert stats.failed == 0
'''
    cleanup = '''
import os, psycopg
with psycopg.connect(os.environ['DATABASE_URL']) as connection:
    connection.execute("DELETE FROM literature_articles WHERE pmid = %s", ('999999999999',))
'''
    subprocess.run(["docker", "compose", "exec", "-T", "retrieval-api", "python", "-c", cleanup if remove else setup], check=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed-fixture", action="store_true")
    args = parser.parse_args()
    try:
        if args.seed_fixture:
            fixture()
        for service in PORTS:
            assert request(service, "/health")["status"] == "ok"
        catalog = request("research", "/catalog")
        cell = "SIDM00001" if "SIDM00001" in catalog["cell_line_ids"] else catalog["cell_line_ids"][0]
        drug = "Cisplatin" if "Cisplatin" in catalog["drug_names"] else catalog["drug_names"][0]
        inputs = {"cell_line_id": cell, "drug_name": drug}
        submission = request("explanation", "/explanations", inputs)
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            status = request("explanation", submission["status_url"])
            if status["status"] == "completed":
                break
            assert status["status"] != "failed", status
            time.sleep(0.5)
        else:
            raise AssertionError("Worker did not complete an explanation in 60 seconds")
        assert request("explanation", "/explanations", inputs)["cache_hit"] is True
        result = request("research", "/research", {**inputs, "question": "TP53 cisplatin resistance"})
        assert result["explanation_status"] == "completed"
        assert result["top_features"]
        assert result["explanation_cache_hit"] is True
        assert len(result["trace_id"]) == 32 and result["trace_id"] != "0" * 32
        if args.seed_fixture:
            assert "999999999999" in [item["pmid"] for item in result["citations"]]
        print(json.dumps({"status": "passed", "trace_id": result["trace_id"], "cache_hit": True, "citations": len(result["citations"])}, indent=2))
    finally:
        if args.seed_fixture:
            fixture(remove=True)


if __name__ == "__main__":
    main()
