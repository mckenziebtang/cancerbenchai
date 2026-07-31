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

Upcoming phases add asynchronous SHAP explanations, literature retrieval,
tool-based orchestration, distributed tracing, and a minimal research UI.
