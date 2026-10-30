from fastapi.testclient import TestClient

from agent_service.client import UpstreamError
from agent_service.main import create_app
from agent_service.service import ResearchService


class FakeClient:
    def __init__(self, *, retrieval_error=False, explanation_status="completed",
                 prediction_error=False, empty_retrieval=False):
        self.calls = []
        self.retrieval_error = retrieval_error
        self.explanation_status = explanation_status
        self.prediction_error = prediction_error
        self.empty_retrieval = empty_retrieval

    def post(self, service, path, payload):
        self.calls.append((service, path))
        if service == "prediction":
            if self.prediction_error:
                raise UpstreamError(400, "UNKNOWN_DRUG", "Unknown drug")
            return {"prediction": 3.234, "cell_line_id": "SIDM00001",
                    "drug_name": "Cisplatin", "model_version": "xgb_v1"}
        if service == "explanation":
            return {"job_id": "exp_123", "status": "queued",
                    "status_url": "/explanations/exp_123", "cache_hit": False}
        if self.retrieval_error:
            raise UpstreamError(503, "RETRIEVAL_UNAVAILABLE", "Unavailable")
        if self.empty_retrieval:
            return {"results": []}
        return {"results": [{"pmid": "23839309", "title": "TP53 and cisplatin",
                            "snippet": "Research passage", "year": 2013,
                            "url": "https://pubmed.ncbi.nlm.nih.gov/23839309/"}]}

    def get(self, service, path):
        self.calls.append((service, path))
        assert service == "explanation" and path == "/explanations/exp_123"
        if self.explanation_status == "failed":
            return {"status": "failed", "error": {"code": "EXPLANATION_FAILED"}}
        if self.explanation_status == "queued":
            return {"status": "queued"}
        return {"status": "completed", "result": {"features": [
            {"name": "TP53", "value": 1, "contribution": 0.31, "direction": "positive"}
        ]}}


REQUEST = {"cell_line_id": "SIDM00001", "drug_name": "Cisplatin",
           "question": "TP53-associated resistance"}


def test_research_combines_services_without_inventing_citations():
    client = FakeClient()
    with TestClient(create_app(ResearchService(client, max_polls=1, poll_interval=0))) as app:
        response = app.post("/research", json=REQUEST)
    assert response.status_code == 200
    result = response.json()
    assert result["prediction"]["prediction"] == 3.234
    assert result["top_features"][0]["name"] == "TP53"
    assert [item["pmid"] for item in result["citations"]] == ["23839309"]
    assert "TP53 and cisplatin (PMID 23839309)" in result["answer"]
    assert "do not validate the cell-line prediction" in result["answer"]
    assert result["citations"][0]["url"] == "https://pubmed.ncbi.nlm.nih.gov/23839309/"
    assert result["explanation_status"] == "completed"
    assert client.calls == [("prediction", "/predict"), ("explanation", "/explanations"),
                            ("retrieval", "/retrieve"), ("explanation", "/explanations/exp_123")]


def test_unknown_drug_stops_before_other_services():
    client = FakeClient(prediction_error=True)
    with TestClient(create_app(ResearchService(client))) as app:
        response = app.post("/research", json=REQUEST)
    assert response.status_code == 400
    assert response.json()["code"] == "UNKNOWN_DRUG"
    assert client.calls == [("prediction", "/predict")]


def test_partial_result_when_retrieval_and_explanation_fail():
    client = FakeClient(retrieval_error=True, explanation_status="failed")
    with TestClient(create_app(ResearchService(client, max_polls=1, poll_interval=0))) as app:
        response = app.post("/research", json=REQUEST)
    assert response.status_code == 200
    result = response.json()
    assert result["prediction"]["prediction"] == 3.234
    assert result["citations"] == [] and result["top_features"] == []
    assert result["explanation_status"] == "failed"
    assert any("Literature retrieval" in item for item in result["limitations"])


def test_rejects_personal_treatment_question():
    client = FakeClient()
    with TestClient(create_app(ResearchService(client))) as app:
        response = app.post("/research", json={**REQUEST, "question": "What dose should I take?"})
    assert response.status_code == 400
    assert response.json()["code"] == "CLINICAL_ADVICE_UNSUPPORTED"
    assert client.calls == []


def test_no_literature_and_queued_explanation_return_partial_result():
    client = FakeClient(empty_retrieval=True, explanation_status="queued")
    with TestClient(create_app(ResearchService(client, max_polls=2, poll_interval=0))) as app:
        response = app.post("/research", json=REQUEST)
    assert response.status_code == 200
    result = response.json()
    assert result["citations"] == []
    assert result["explanation_status"] == "timed_out"
    assert "No PubMed passages were retrieved" in result["answer"]
    assert "PMID" not in result["answer"]
    assert len([call for call in client.calls if call == ("explanation", "/explanations/exp_123")]) == 2
    assert any("No supporting literature" in item for item in result["limitations"])
