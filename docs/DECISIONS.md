# Engineering decisions

| Decision | Reason and tradeoff |
| --- | --- |
| XGBoost | Fits the existing tabular mutation and drug features. Evaluation must account for cell-line and drug leakage; this service does not establish clinical performance. |
| TreeSHAP through XGBoost | Native contribution prediction uses the same trained booster. Top features plus the residual preserve reconstruction. Contributions describe this model, not causal mechanisms. |
| Asynchronous explanations | Moves potentially slow work out of submission requests and demonstrates queue states, retries, and idempotency. Requires polling and worker monitoring. |
| RQ rather than Celery | One queue is sufficient for the current workflow. It avoids a larger task framework; more complex routing may justify revisiting this. |
| Redis | Supports job state, duplicate locks, versioned result caching, and worker metric aggregates. Cache expiry and Redis outages must remain explicit. |
| PostgreSQL and pgvector | Keeps PMID metadata and vectors in one store. The small corpus does not require a separate Qdrant deployment. |
| Static ingestion | A reviewed manifest makes corpus construction inspectable. Literature goes stale and the generated snapshot's date must be recorded. |
| Hashing embeddings plus lexical ranking | Runs locally without embedding API fees. Collisions and lexical overlap limit semantic relevance; measure retrieval on expected PMIDs. |
| Deterministic orchestration | The required prediction, explanation, and literature steps are known. A future LLM can synthesize validated evidence without deciding every action. |
| Structured response | Typed prediction, features, citations, limitations, and trace ID support a stable frontend. Titles and snippets remain untrusted text in the DOM. |
| Docker Compose | Reproduces the portfolio stack in one command. Kubernetes adds little value at this scale. |
| Versioned artifacts and caches | Prediction and SHAP share the image's model directory. Model and explainer versions enter cache keys; embedding version enters literature records. Retrain or re-embed with new versions. |
| Manual OpenTelemetry spans | Controls which data are exported and covers the RQ boundary. Requires explicit instrumentation when adding new operations. |
| Static frontend on the research API | Avoids a separate build pipeline and cross-origin configuration. A larger application could justify a dedicated frontend framework. |
