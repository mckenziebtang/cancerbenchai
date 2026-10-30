"""Rebuild the demo's disposable literature database from the committed manifest."""

import json
import os
from pathlib import Path
import time
import urllib.request


def seed():
    from retrieval_service.ingest import load_jsonl
    from retrieval_service.pubmed import download_manifest
    from retrieval_service.service import RetrievalService
    from retrieval_service.store import PostgresLiteratureStore

    output = Path("/tmp/cancerbench-demo/pubmed_abstracts.jsonl")
    download_manifest(Path("literature_data/pubmed_manifest.json"), output, os.getenv("NCBI_API_KEY") or None)
    articles, invalid = load_jsonl(output)
    if invalid:
        raise ValueError("Invalid literature records")
    service = RetrievalService(PostgresLiteratureStore(os.environ["DATABASE_URL"]))
    service.initialize()
    stats = service.ingest(articles)
    if stats.failed:
        raise ValueError("Literature ingestion failed")
    print(json.dumps({"event": "demo_literature_ready", "articles": len(articles)}), flush=True)


def wait_for_api():
    url = f"http://127.0.0.1:{int(os.getenv('PORT', '10000'))}/health"
    for _ in range(240):
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return True
        except OSError:
            pass
        time.sleep(0.5)
    return False


def main():
    # The web lifespan owns schema creation; seed only after it has finished.
    if not wait_for_api():
        print(json.dumps({"event": "demo_literature_unavailable", "stage": "startup"}), flush=True)
        return 1
    for attempt in range(1, 4):
        try:
            seed()
            return 0
        except Exception:
            # Never print exception text: a downloader URL may contain an API key.
            print(json.dumps({"event": "demo_literature_unavailable", "attempt": attempt}), flush=True)
            if attempt < 3:
                time.sleep(attempt * 5)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
