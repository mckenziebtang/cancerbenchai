from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path

from pydantic import ValidationError

from retrieval_service.pubmed import download_manifest
from retrieval_service.schemas import ArticleInput
from retrieval_service.service import RetrievalService
from retrieval_service.store import PostgresLiteratureStore


LOGGER = logging.getLogger("cancerbench.ingestion")


def load_jsonl(path: Path) -> tuple[list[ArticleInput], int]:
    articles: list[ArticleInput] = []
    invalid = 0
    with path.open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            if not line.strip():
                continue
            try:
                articles.append(ArticleInput.model_validate_json(line))
            except (ValidationError, ValueError):
                invalid += 1
                LOGGER.exception("Invalid article at line %s", line_number)
    return articles, invalid


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Download and ingest CancerBench PubMed abstracts")
    subcommands = parser.add_subparsers(dest="command", required=True)
    download = subcommands.add_parser("download", help="Rebuild JSONL from the PubMed manifest")
    download.add_argument("--manifest", type=Path, default=Path("literature_data/pubmed_manifest.json"))
    download.add_argument("--output", type=Path, default=Path("literature_data/pubmed_abstracts.jsonl"))
    ingest = subcommands.add_parser("load", help="Embed JSONL records and upsert them into PostgreSQL")
    ingest.add_argument("--input", type=Path, default=Path("literature_data/pubmed_abstracts.jsonl"))
    ingest.add_argument("--batch-size", type=int, default=64)
    return parser


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = build_parser().parse_args()
    if args.command == "download":
        counts = download_manifest(args.manifest, args.output, os.getenv("NCBI_API_KEY"))
        LOGGER.info("PubMed download: %s", json.dumps(counts, sort_keys=True))
        return 0

    service = RetrievalService(
        PostgresLiteratureStore(
            os.getenv("DATABASE_URL", "postgresql://cancerbench:cancerbench@localhost:5432/cancerbench")
        )
    )
    service.initialize()
    articles, invalid = load_jsonl(args.input)
    stats = service.ingest(articles, batch_size=args.batch_size)
    stats.failed += invalid
    LOGGER.info("Ingestion result: %s", stats.model_dump_json())
    return 1 if stats.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

