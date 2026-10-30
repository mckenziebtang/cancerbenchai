# Free online research demo

The optional compact deployment uses one Render **Free** web service and the
Dockerfile at `deploy/free.Dockerfile`. The research, prediction, explanation,
and retrieval APIs share one Uvicorn process. Their existing HTTP contracts,
real Redis/RQ worker, PostgreSQL 17/pgvector database, and native TreeSHAP are
retained. The normal local Compose stack remains the engineering reference.

The deployment uses CPU-only XGBoost at the same pinned version. Backend HTTP
routes require a runtime-generated internal token. Public research requests are
limited to one at a time; overlapping requests receive 429 and a retry hint.
Database and Redis sockets bind only to loopback. The container runs without
root privileges. Model computations use one native thread.

## Hosting settings

| Setting | Value |
| --- | --- |
| Type | Web Service |
| Runtime | Docker |
| Instance | Free, $0/month |
| Dockerfile | `deploy/free.Dockerfile` |
| Docker context | Repository root |
| Health path | `/health` |
| Git branch | `codex/free-hosting` |
| Auto-deploy | After CI checks pass |
| Paid databases, workers, disks, monitoring | None |

Do not select a paid instance or attach a paid disk. The existing prediction-only
`render.yaml` is a separate blueprint and does not configure this demo.
The optional `NCBI_API_KEY` belongs in Render's runtime environment settings;
local keys remain in the ignored `.env`. No key is required, and `.env` is never
uploaded or included in the image. There are no LLM API calls.

## Free-tier behavior

Render's free web service sleeps after 15 minutes without inbound traffic and
can take approximately a minute to wake. Its filesystem is ephemeral. Redis
state and the database can disappear on restarts, sleep, or deployment. The
committed PubMed manifest is downloaded and embedded into the real database
again in the background. During that warm-up, the UI explicitly reports missing
literature rather than displaying synthetic citations. Refresh a question once
the literature loader has finished. Cache hits disappear after a restart too.

This is a disposable research demo. Store no user or patient data in it. The
local Jaeger/Grafana stack is not hosted in this free profile. Trace IDs and JSON
logs remain available for diagnosis, but no external telemetry account is used.

Free instance hours (750/month) are shared with other services in the Render
workspace. Bandwidth/build quotas also apply. Keep the deployment on Free and
review the account's usage if the demo becomes popular; no paid upgrade or extra
resource is part of this setup.

Current provider limits: [Render free hosting](https://render.com/docs/free).
The package variant is documented in the [XGBoost installation guide](https://xgboost.readthedocs.io/en/stable/install.html#minimal-installation-cpu-only).

## Reproduce the constrained runtime

```bash
docker build -f deploy/free.Dockerfile -t cancerbench-free .
docker run --rm --memory=512m --memory-swap=512m --cpus=1 \
  -p 127.0.0.1:18004:10000 cancerbench-free
```

Open `http://localhost:18004`. Check a first explanation and a repeat cache hit,
real PMID citations, `/health`, and rejection of unauthenticated `/internal/`
routes. Only publish after these checks pass under the memory limit.
