# CancerBench literature dataset

The committed manifest is the reproducible source definition for the Phase 3
corpus. It selects up to 300 unique, relevance-ranked PubMed records across ten
cancer drug-response topics. Only records with an English abstract are retained.
Each downloaded record preserves its PMID, DOI when present, title, abstract,
authors, year, journal, canonical PubMed URL, selection query, and download date.

Rebuild the local JSONL snapshot:

```bash
python -m retrieval_service.ingest download
```

NCBI permits three E-utilities requests per second without an API key. Set
`NCBI_API_KEY` to use the higher authenticated rate. The downloader identifies
itself as the `cancerbench` tool, throttles requests, and writes
`pubmed_abstracts.jsonl`. The generated snapshot is intentionally gitignored:
abstract reuse rights can vary by publisher, while the search manifest remains
reviewable and reproducible. Review the [NCBI data usage
guidelines](https://www.ncbi.nlm.nih.gov/home/about/policies/) and source-publisher
terms before redistributing abstract text.

Load the downloaded records into PostgreSQL/pgvector:

```bash
python -m retrieval_service.ingest load
```

Ingestion is idempotent by PMID and content hash. Logs report inserted, updated,
skipped, failed, and chunk counts. The ingestion date is updated only when the
source snapshot changes, and embedding model/version metadata is stored on every
chunk.

Run the 20-case retrieval evaluation after ingestion:

```bash
python -m retrieval_service.evaluate --output literature_data/evaluation_report.json
```

The report includes recall@5, mean reciprocal rank, expected and returned PMIDs,
citation metadata completeness, and mean/p95 retrieval latency. A zero-evidence
case verifies that the service does not manufacture support from weak matches.
