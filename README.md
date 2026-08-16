# CancerBench AI

CancerBench AI is a research-only drug-response prediction service built to
demonstrate production-oriented machine-learning engineering. Its first phase
serves an XGBoost model through a validated, tested, Dockerized FastAPI API.

> This project is not clinically validated and must not be used for diagnosis,
> treatment selection, or other medical decisions.

## Live API

- Service: <https://cancerbenchai.onrender.com>
- Interactive documentation: <https://cancerbenchai.onrender.com/docs>
- Health check: <https://cancerbenchai.onrender.com/health>
- Model metadata: <https://cancerbenchai.onrender.com/metadata>

The free Render service can take additional time to respond after an idle
period.

## Make a prediction

```bash
curl -X POST https://cancerbenchai.onrender.com/predict \
  -H "Content-Type: application/json" \
  -d '{
    "cell_line_id": "SIDM00001",
    "drug_name": "Cisplatin"
  }'
```

Example response:

```json
{
  "prediction": 3.234267234802246,
  "cell_line_id": "SIDM00001",
  "drug_name": "Cisplatin",
  "model_version": "xgb_v1"
}
```

The prediction is `LN_IC50`, not a probability. Lower values indicate greater
predicted sensitivity within the source research dataset.

## Run locally

Install development dependencies and start FastAPI:

```bash
python3 -m pip install -r requirements-dev.txt
uvicorn app.main:app --reload
```

Run the tests:

```bash
python3 -m pytest -q
```

## Generate an explanation

The phase-two service calculates XGBoost feature contributions asynchronously.
Start its API, Redis queue, and worker together:

```bash
docker compose up --build
```

Submit a job at <http://localhost:8001/explanations>:

```bash
curl -X POST http://localhost:8001/explanations \
  -H "Content-Type: application/json" \
  -d '{"cell_line_id":"SIDM00001","drug_name":"Cisplatin"}'
```

Poll the `status_url` returned by that request until its status is `completed`.
The result contains the prediction, model base value, and ten largest mutation
or drug contributions ranked by absolute magnitude. `other_contribution`
preserves exact reconstruction of the prediction.

Completed results are cached for one hour under a key containing both the model
and explainer versions. Identical in-progress requests reuse one job. Transient
worker failures are retried twice; validation failures are rejected before a job
is created. If a worker crashes, RQ's worker monitoring marks the interrupted
job for failure or retry, while the duplicate lock expires after twenty minutes
so it covers the initial attempt and both retries without blocking new work
indefinitely. Failed responses expose a stable error object and do not expose
internal tracebacks.

For local development, both services use the same versioned artifact directory
included in the shared Docker image. At production scale artifacts should be immutable,
versioned artifacts fetched from an artifact registry during deployment.
These explanations describe model behavior, not biological causality or
clinical recommendations.

To run the test that exercises a real isolated Redis instance, provide a
dedicated database URL:

```bash
REDIS_TEST_URL=redis://localhost:6379/15 python3 -m pytest -m integration
```

## Run with Docker

```bash
docker build -t cancerbench-prediction:latest .
docker run --rm -p 8000:8000 cancerbench-prediction:latest
```

Then open <http://localhost:8000/docs>.

## Model

The model uses 50 binary cancer-driver mutation features and a categorical drug
feature. See [MODEL_CARD.md](MODEL_CARD.md) for data, evaluation, intended use,
and limitations.

## Current architecture

```text
Client -> FastAPI validation -> feature construction -> XGBoost -> JSON response
```

The phase-two explanation service adds Redis-backed asynchronous XGBoost feature
contributions. Upcoming phases add literature retrieval, tool-based
orchestration, distributed tracing, and a minimal research UI.
