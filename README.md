# CancerBench AI

CancerBench connects experimental drug-response predictions with model feature
contributions and related PubMed literature. Researchers can inspect all three
outputs, their limitations, and the request's trace in one browser workspace.

> Research use only. Not clinically validated; do not use for diagnosis or
> treatment selection. Do not enter personal or patient health information.

## Start locally

Install Docker with Compose v2. From this repository:

```bash
make up
```

Open <http://localhost:18003>. Use `make demo` to include local Jaeger traces,
Prometheus metrics, and Grafana. No OpenAI key, paid embedding API, or hosted
monitoring account is required. The current workflow makes no LLM calls.

Keep optional API keys in the Git-ignored local `.env` file; `.env.example`
contains variable names only. Currently only `NCBI_API_KEY` is used. See
[OPERATIONS.md](docs/OPERATIONS.md) for environment loading and key handling.

The literature database begins empty. Download and load the real corpus using
[OPERATIONS.md](docs/OPERATIONS.md); until then responses show a no-evidence
limitation. All services run locally; containers use your machine's resources.

| Surface | URL |
| --- | --- |
| Research workspace and API docs | http://localhost:18003 and /docs |
| Prediction API docs | http://localhost:18000/docs |
| Explanation API docs | http://localhost:18001/docs |
| Literature API docs | http://localhost:18002/docs |
| Trace viewer, with monitoring | http://localhost:16686 |
| Dashboard, with monitoring | http://localhost:3000/d/cancerbench |

The previously deployed prediction service is at
<https://cancerbenchai.onrender.com> and its docs at
<https://cancerbenchai.onrender.com/docs>. This change does not publish the full
workspace there. Free Render instances can have cold starts.

## Architecture and workflow

See [ARCHITECTURE.md](docs/ARCHITECTURE.md) for the diagram. Four FastAPI services
share versioned model artifacts and a Docker image. Prediction runs XGBoost;
explanation uses an RQ worker and Redis; literature retrieval uses pgvector and
PostgreSQL; the research API serves the frontend and assembles structured evidence.

A question triggers identifier validation through prediction, explanation job
submission, literature retrieval, and bounded explanation polling. Streamed
progress reports real backend stages. The response contains prediction, signed
SHAP features, PMID citations, limitations, and a distributed trace ID. Evidence
failures preserve available results. Prediction failures stop the workflow.

The summary identifies retrieved titles and model outputs deterministically.
Phase 4 LLM synthesis and semantic agent evaluation remain separate work.

## API example

Get supported identifiers from `/catalog`, then submit:

```bash
curl http://localhost:18003/catalog
curl -X POST http://localhost:18003/research \
  -H 'Content-Type: application/json' \
  -d '{"cell_line_id":"SIDM00001","drug_name":"Cisplatin","question":"What research discusses TP53 and cisplatin resistance?"}'
```

Use `curl -N` with `/research/stream` for newline-delimited progress. Once
streaming begins, workflow failures appear as `event: "error"` records. The
ordinary `/research` route retains non-2xx error statuses.

Prediction units are `LN_IC50`, the natural logarithm of IC50. Lower values
indicate greater predicted sensitivity within the training dataset. SHAP
contributions describe model behavior, not biological causality. Related papers
do not validate the cell-line prediction.

## Tests and CI

Use Python 3.12 and Node for local development:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python scripts/check_source.py
python -m ruff check .
python -m pytest -q
node --test tests/frontend.test.cjs
```

Fast tests use synthetic literature, fake Redis, and injected clients. Set
`REDIS_TEST_URL` and `POSTGRES_TEST_URL` only to isolated test instances to run
real integration checks. `make smoke` exercises a running Compose stack and a
cache hit. CI seeds and removes one synthetic article in its isolated database.

GitHub Actions runs source syntax/whitespace checks, lint, unit/API tests, real
Redis/pgvector integration, retrieval evaluation smoke, the research failure
matrix, frontend interactions, Docker/Compose integration, dependency advisory
auditing, and secret scanning. `release-checks` gates all four jobs. The Render
blueprint selects deployment after passing CI; branch protection and the Render
account still need configuration.

## Evaluation and limitations

Run the committed 20-query retrieval benchmark against the loaded real corpus:

```bash
docker compose exec retrieval-api python -m retrieval_service.evaluate --output /tmp/evaluation.json
docker compose cp retrieval-api:/tmp/evaluation.json literature_data/evaluation_report.json
```

Results include recall@5 and MRR on positive queries, separate no-evidence
accuracy, citation metadata completeness, and nearest-rank p95 latency. The CI
fixture smoke test is not a real-corpus relevance measurement. Rerun previously
reported project results on the exact corpus and ranking version being released.

The research failure matrix covers invalid inputs, outages, malformed tool
outputs, explanation failures/timeouts, and missing evidence. It does not
measure LLM unsupported claims, refusal robustness, tokens, or LLM cost. No LLM
is connected. Local hashing embeddings and lexical ranking have limited semantic
understanding. Metrics assume one Uvicorn process per service. Monitoring data
are local and ephemeral.

Model and dataset provenance, leakage limitations, and intended use are in
[MODEL_CARD.md](MODEL_CARD.md). Literature provenance, usage terms, and rebuild
instructions are in [literature_data/README.md](literature_data/README.md).

## Release and demo

- [Operations, failure demos, deployment, rollback, and costs](docs/OPERATIONS.md)
- [Architecture and future production changes](docs/ARCHITECTURE.md)
- [Engineering decisions](docs/DECISIONS.md)
- [Three-minute demo script](docs/DEMO.md)
- [Verification status and remaining release steps](docs/RELEASE_STATUS.md)

`render.yaml` describes the existing prediction service only. `render-free.yaml`
describes a separate $0 research demo service using the compact deployment.

For the optional full research demo on a single free web instance, see
[FREE_HOSTING.md](docs/FREE_HOSTING.md). That profile has an ephemeral database,
cold starts, and one active research request at a time.
