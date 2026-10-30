from __future__ import annotations

import re
import time
from typing import Any, Protocol, Callable

from pydantic import ValidationError

from agent_service.client import UpstreamError
from agent_service.schemas import Citation, Feature, Prediction, ResearchRequest, ResearchResponse
from observability.telemetry import metrics, trace_id, traced


class ServiceClient(Protocol):
    def post(self, service: str, path: str, payload: dict[str, Any]) -> dict[str, Any]: ...
    def get(self, service: str, path: str) -> dict[str, Any]: ...


CLINICAL_ADVICE = re.compile(
    r"\b(?:should i take|what should i take|which drug should i take|"
    r"what dose should i|treat my cancer|prescribe me)\b", re.IGNORECASE
)


class ResearchService:
    def __init__(self, client: ServiceClient, max_polls: int = 12, poll_interval: float = 0.25):
        self.client = client
        self.max_polls = max_polls
        self.poll_interval = poll_interval

    @traced("research", "research.workflow")
    def run(self, req: ResearchRequest, progress: Callable | None = None) -> ResearchResponse:
        emit = progress or (lambda *args: None)
        if CLINICAL_ADVICE.search(req.question):
            raise UpstreamError(400, "CLINICAL_ADVICE_UNSUPPORTED",
                                "CancerBench cannot recommend personal treatment or doses")

        prediction = self._prediction(req)
        emit("prediction", "completed")
        limitations = [
            "The prediction is an experimental LN_IC50 estimate, not a clinical outcome.",
            "Retrieved articles provide research context; they do not validate this prediction.",
        ]

        submission: dict[str, Any] | None = None
        try:
            submission = self.client.post("explanation", "/explanations", {
                "cell_line_id": req.cell_line_id, "drug_name": req.drug_name,
            })
        except UpstreamError:
            limitations.append("Explanation service was unavailable.")
        emit("explanation", "queued" if submission else "unavailable")

        citations: list[Citation] = []
        try:
            retrieved = self.client.post("retrieval", "/retrieve", {
                "query": f"{req.drug_name} {req.question}", "top_k": 5, "filters": {},
            })
            if not isinstance(retrieved.get("results"), list):
                raise TypeError("Invalid retrieval result list")
            for item in retrieved.get("results", [])[:5]:
                # Cite only PMIDs supplied by retrieval, with canonical PubMed URLs.
                pmid = str(item["pmid"])
                if not pmid.isdecimal():
                    continue
                citations.append(Citation(
                    pmid=pmid, title=item["title"], snippet=item["snippet"],
                    url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/", year=item.get("year"),
                ))
        except (UpstreamError, KeyError, TypeError, AttributeError, ValidationError):
            citations = []
            limitations.append("Literature retrieval was unavailable or returned invalid data.")
        if not citations:
            limitations.append("No supporting literature passages are available for this response.")
        emit("literature", "completed" if citations else "unavailable")

        status, features = self._explanation(submission)
        emit("explanation", status)
        if status == "failed":
            limitations.append("Explanation calculation failed.")
        elif status == "unavailable" and submission is not None:
            limitations.append("Explanation result was unavailable or invalid.")
        elif status == "timed_out":
            limitations.append("Explanation did not finish within the polling window.")

        if citations:
            # Titles identify what each retrieved paper discusses without
            # inventing a finding or implying it studied this cell line.
            studies = "; ".join(
                f"{citation.title.rstrip('.')} (PMID {citation.pmid})"
                for citation in citations[:3]
            )
            answer = f"Retrieved research on {req.drug_name} includes: {studies}."
            if len(citations) > 3:
                answer += f" {len(citations) - 3} more cited studies are listed below."
            answer += " These studies do not validate the cell-line prediction."
        else:
            answer = (
                f"No PubMed passages were retrieved for this question about "
                f"{req.drug_name}; no literature conclusion can be drawn here."
            )
        answer += (
            f" The research model predicts LN_IC50 {prediction.prediction:.3f} for "
            f"{prediction.cell_line_id} and {prediction.drug_name}."
        )
        if features:
            names = ", ".join(feature.name for feature in features[:3])
            answer += f" Its leading model feature contributions are {names}."
        if status != "completed" or not citations:
            metrics("research").partial.inc()
        return ResearchResponse(
            answer=answer, prediction=prediction, top_features=features,
            explanation_status=status, citations=citations,
            explanation_cache_hit=bool(submission and submission.get("cache_hit")),
            limitations=limitations, trace_id=trace_id(),
        )

    def _prediction(self, req: ResearchRequest) -> Prediction:
        payload = self.client.post("prediction", "/predict", {
            "cell_line_id": req.cell_line_id, "drug_name": req.drug_name,
        })
        try:
            return Prediction.model_validate(payload)
        except ValidationError as exc:
            raise UpstreamError(502, "INVALID_PREDICTION_RESPONSE",
                                "Prediction service returned invalid data") from exc

    def _explanation(self, submission: dict[str, Any] | None) -> tuple[str, list[Feature]]:
        if not submission:
            return "unavailable", []
        job_id = submission.get("job_id")
        if not isinstance(job_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", job_id):
            return "unavailable", []
        for attempt in range(self.max_polls):
            try:
                job = self.client.get("explanation", f"/explanations/{job_id}")
            except UpstreamError:
                return "unavailable", []
            if job.get("status") == "failed":
                return "failed", []
            if job.get("status") == "completed":
                try:
                    result = job["result"]
                    if not isinstance(result["features"], list):
                        raise TypeError("Invalid feature list")
                    return "completed", [Feature.model_validate(item)
                                         for item in result["features"][:10]]
                except (KeyError, TypeError, AttributeError, ValidationError):
                    return "unavailable", []
            if attempt + 1 < self.max_polls:
                time.sleep(self.poll_interval)
        return "timed_out", []
