# Run, inspect, and recover

## Local startup

Install Docker with Compose v2. From the repository root run `make up`, then open
<http://localhost:18003>. No API key is needed. `make demo` also starts Jaeger,
Prometheus, and Grafana and sets the local OTLP endpoint for all APIs and the worker.
The optional monitoring images consume additional local CPU and memory.

Keep all API keys in the local `.env` file, which Git and Docker builds ignore.
Copy `.env.example` to `.env` if needed and restrict it with `chmod 600 .env`.
The only key currently used is optional `NCBI_API_KEY`; Compose passes it only
to `retrieval-api`. The ingestion CLI also reads `.env` from the current working
directory. Exported environment variables take precedence over the file.
Leave the key blank to use PubMed without one. No LLM key is used until Phase 4
synthesis is implemented. Never put key values in source files or examples.

| Surface | Local URL |
| --- | --- |
| Research workspace and API | http://localhost:18003 |
| Prediction API docs | http://localhost:18000/docs |
| Explanation API docs | http://localhost:18001/docs |
| Retrieval API docs | http://localhost:18002/docs |
| Trace UI | http://localhost:16686 |
| Grafana dashboard | http://localhost:3000/d/cancerbench |
| Prometheus | http://localhost:9090 |

An empty database returns no citations. Build and load the real corpus explicitly:

```bash
docker compose exec retrieval-api python -m retrieval_service.ingest download
docker compose exec retrieval-api python -m retrieval_service.ingest load
docker compose exec retrieval-api python -m retrieval_service.evaluate --output /tmp/evaluation.json
docker compose cp retrieval-api:/tmp/evaluation.json literature_data/evaluation_report.json
```

PubMed access uses NCBI's public endpoint and does not require a key at the
downloader's unauthenticated rate. An optional NCBI key is unrelated to an LLM key.
Do not distribute source abstracts without reviewing their usage terms.

## Traces, logs, and metrics

Copy a response's `trace_id` from the evidence panel and search for it in Jaeger.
The `x-trace-id` response header uses the same ID. First requests with uncached
SHAP work should include the worker under explanation submission. Repeat
requests can show cache hits and no new worker execution. Wait a few seconds for
batched HTTP spans to arrive. Jaeger data resets when its container is recreated.

JSON telemetry records include service, request ID, trace ID, model version,
duration, status, and error category. Prompt bodies, full URLs, exception text,
SQL, and Redis keys are excluded from the shared telemetry layer. Uvicorn access
logs are disabled in the supplied container commands. Upstream libraries can
still emit their own operational logs; do not submit personal information.
The logged model version defaults to `xgb_v1`; set `MODEL_VERSION` consistently
with `model_metadata.json` after publishing a new model.

Grafana shows requests, errors, prediction/retrieval latency, queue depth,
processing duration, cache hits, partial results, and scrape health. Rates need
multiple scrapes and requests. No-data panels are not proof of zero errors.
Worker totals count execution attempts, including retries. Cache misses count
requests without cached data, including requests reusing in-flight work.

## Failure behavior

| Failure | Expected behavior | Coverage |
| --- | --- | --- |
| Prediction unavailable or malformed | Research request fails with a stable error | Failure matrix; malformed numeric data rejected |
| Redis unavailable | Explanation endpoints return 503; research can return prediction and literature | Explanation tests and failure matrix |
| Worker unavailable | Explanation remains queued; research returns `timed_out` after bounded polling | Queue timeout scenario; manual demo below |
| Job fails or exceeds RQ timeout | Failed explanation with available prediction/literature | Job failure scenarios; RQ enforces execution timeout |
| Retrieval unavailable, malformed, or empty | Empty citations and an explicit limitation | Retrieval failure matrix and no-evidence scenario |
| LLM timeout | Not applicable: no LLM is configured | Must be added with Phase 4 synthesis |
| Monitoring unavailable | Application continues; traces can be dropped and metrics report collection availability | Exporter timeout and guarded Redis metrics |

To demonstrate retrieval failure after normal startup, stop `retrieval-api`,
submit the same research request, inspect its limitations, then restart the
service. For a worker failure, stop `explanation-worker` and choose a cell/drug
pair whose explanation is not cached. A cached pair will still succeed.

```bash
docker compose stop retrieval-api
# Submit a research request in the UI; inspect partial evidence.
docker compose start retrieval-api
docker compose stop explanation-worker
# Use a new cell/drug pair; inspect the bounded explanation timeout.
docker compose start explanation-worker
```

Use `docker compose logs --tail=100` to inspect service status. `make down` keeps
the literature volume. Avoid `down -v` unless you intend to delete the local data.

## Deployment and rollback

The included `render.yaml` describes the existing prediction API only. It does
not deploy the full Compose stack or change your Render account automatically.
The Render service must be linked to the repository; enable deployment after
checks pass and require the `release-checks` job on the main branch. Confirm the
existing Render service matches this blueprint before adopting it, to avoid
creating a second service. Health checking uses `/health`.

Store hosted `REDIS_URL`, `DATABASE_URL`, and telemetry credentials in the hosting
provider's environment settings. The supplied Compose database password is a
local demo value. There is no LLM API key variable in this implementation.
The full research stack is local until hosting is configured separately; adding
hosted databases and workers can incur provider charges.

Before release, retain the last passing commit and its image/artifact version.
After deployment, check `/health`, `/metadata`, and a known prediction. On
regression, use Render's rollback action to restore the previous successful
deploy and pause automatic deployment while diagnosing. For local rollback,
check out that known-good commit and run `docker compose up -d --build --wait`.
Keep database backups before any future migration that changes stored data.
