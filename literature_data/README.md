# CancerBench literature dataset

The committed manifest defines ten PubMed searches and 24 curated PMID
anchors used by the evaluation set. The anchors remain included when relevance
rankings change; the rest of the search-selected corpus may change over time.
Review evaluation labels and paper abstracts before reporting quality results.
Only records with an English abstract are retained.
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

The report averages recall@5 and mean reciprocal rank over the 19 positive
cases. It reports no-evidence accuracy separately, along with expected and
returned PMIDs, citation metadata completeness, and retrieval latency. A
zero-evidence case checks that the service can return an empty result.
