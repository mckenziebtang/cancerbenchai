# Research workflow (local Phase 4 slice)

`POST /research` combines the prediction, explanation, and retrieval services.
It creates a research-only summary from their structured outputs. No LLM, API
key, or paid model service is called. The prediction is an experimental
`LN_IC50` estimate; PubMed passages are related context, not validation of an
individual prediction.

Start the local services with `docker compose up -d --build`. The research API
listens at `http://127.0.0.1:18003` on the host. Choose supported IDs from
`http://127.0.0.1:18000/cell-lines` and `/drugs`, then send:

```json
{
  "cell_line_id": "<supported ID>",
  "drug_name": "<supported drug>",
  "question": "What research discusses TP53 and drug resistance?"
}
```

The response includes the prediction, top SHAP features if the job finishes,
up to five PubMed citations returned by retrieval, limitations, and a trace ID.
If explanation or retrieval fails, the prediction remains available with an
explicit limitation. Invalid cell lines or drugs return an error before work
is queued. Explanation polling lasts at most twelve checks, with a short delay
between checks.

Run `python -m pytest -q tests/test_agent_service.py` for contract and failure
tests. This first slice does not perform natural-language synthesis with an LLM
and does not claim clinical validity.
