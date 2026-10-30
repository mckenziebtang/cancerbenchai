# Three-minute walkthrough

Run `make demo`, load the literature corpus as described in OPERATIONS.md, and
open the workspace. This is a recording script; the walkthrough video remains
pending. A real distributed trace screenshot and desktop/mobile evidence were
captured locally in `reports/` during the October 29 laptop verification.

| Time | Show | Explain |
| --- | --- | --- |
| 0:00–0:25 | Question form and disclaimer | A research question connects a cell-line model prediction with model contributions and related literature. |
| 0:25–1:00 | Submit SIDM00001, Cisplatin, and a TP53 resistance question | The progress stages come from the backend. Predictions are experimental LN_IC50 estimates. |
| 1:00–1:30 | Signed SHAP bars and PubMed cards | Contributions describe model behavior. Source titles and passages are linked by PMID; they do not validate the prediction. |
| 1:30–1:55 | Resubmit the same pair | The completed explanation should be a cache hit. Open the evidence panel and copy the trace ID. |
| 1:55–2:20 | Jaeger and Grafana | Inspect HTTP calls, queue submission, first-request worker execution, and system metrics. |
| 2:20–2:45 | Stop retrieval and submit again | Available prediction/explanation remain usable with missing-evidence limitations. Restart retrieval. |
| 2:45–3:00 | Evaluation results and CI checks | Show actual benchmark output and passing checks. Explain which evaluations use fixtures versus the real corpus. |

Capture the architecture diagram from ARCHITECTURE.md and a real Jaeger trace
showing the worker. Do not substitute an illustration for runtime evidence.

Resume summary after validation:

> Built a Dockerized research workflow combining XGBoost predictions, asynchronous
> TreeSHAP explanations, and traceable PubMed retrieval, with a browser interface,
> distributed tracing, system metrics, and automated reliability checks.
