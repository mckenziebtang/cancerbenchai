import json

import pytest
from fastapi.testclient import TestClient

from agent_service.client import UpstreamError
from agent_service.main import create_app
from agent_service.service import ResearchService

REQUEST = {"cell_line_id": "SIDM00001", "drug_name": "Cisplatin", "question": "TP53 resistance research"}


class ScenarioClient:
    def __init__(self, scenario):
        self.scenario = scenario

    def post(self, service, path, payload):
        scenario = self.scenario
        if service == "prediction":
            if scenario in {"unknown_drug", "unknown_cell", "prediction_down"}:
                code = {"unknown_drug": "UNKNOWN_DRUG", "unknown_cell": "UNKNOWN_CELL_LINE", "prediction_down": "PREDICTION_UNAVAILABLE"}[scenario]
                raise UpstreamError(503 if scenario == "prediction_down" else 400, code, "Prediction unavailable")
            if scenario == "bad_prediction":
                return {"prediction": "invalid"}
            return {"prediction": 3.234, "cell_line_id": "SIDM00001", "drug_name": "Cisplatin", "model_version": "xgb_v1"}
        if service == "explanation":
            if scenario == "explanation_down":
                raise UpstreamError(503, "EXPLANATION_UNAVAILABLE", "Unavailable")
            return {"job_id": "../invalid" if scenario == "bad_job" else "exp_test", "cache_hit": scenario == "cache_hit"}
        if scenario == "retrieval_timeout":
            raise UpstreamError(503, "RETRIEVAL_UNAVAILABLE", "Timed out")
        if scenario == "bad_retrieval":
            return {"results": None}
        if scenario == "no_evidence":
            return {"results": []}
        return {"results": [{"pmid": "invalid" if scenario == "bad_pmid" else "12345678", "title": "Fixture study", "snippet": "Synthetic test evidence.", "year": 2024}]}

    def get(self, service, path):
        if service == "prediction":
            return {"cell_line_ids": ["SIDM00001"]} if path == "/cell-lines" else {"drug_names": ["Cisplatin"]}
        if self.scenario == "poll_down":
            raise UpstreamError(503, "EXPLANATION_UNAVAILABLE", "Unavailable")
        if self.scenario in {"failed_job", "worker_timeout", "queued_job"}:
            return {"status": "queued" if self.scenario == "queued_job" else "failed"}
        if self.scenario == "bad_features":
            return {"status": "completed", "result": {"features": None}}
        return {"status": "completed", "result": {"features": [{"name": "TP53", "value": 1, "contribution": 0.1, "direction": "positive"}]}}


@pytest.mark.parametrize("scenario,status,explanation,citations", [
    ("success", 200, "completed", 1), ("cache_hit", 200, "completed", 1),
    ("unknown_drug", 400, None, None), ("unknown_cell", 400, None, None),
    ("prediction_down", 503, None, None), ("bad_prediction", 502, None, None),
    ("explanation_down", 200, "unavailable", 1), ("bad_job", 200, "unavailable", 1),
    ("poll_down", 200, "unavailable", 1), ("failed_job", 200, "failed", 1),
    ("worker_timeout", 200, "failed", 1), ("queued_job", 200, "timed_out", 1),
    ("bad_features", 200, "unavailable", 1), ("retrieval_timeout", 200, "completed", 0),
    ("bad_retrieval", 200, "completed", 0), ("no_evidence", 200, "completed", 0),
    ("bad_pmid", 200, "completed", 0),
])
def test_research_failure_matrix(scenario, status, explanation, citations):
    with TestClient(create_app(ResearchService(ScenarioClient(scenario), max_polls=1, poll_interval=0))) as client:
        response = client.post("/research", json=REQUEST)
    assert response.status_code == status
    if status == 200:
        data = response.json()
        assert data["explanation_status"] == explanation
        assert len(data["citations"]) == citations
        assert data["trace_id"] == response.headers["x-trace-id"]
        assert data["trace_id"] != "0" * 32
        assert data["explanation_cache_hit"] == (scenario == "cache_hit")


@pytest.mark.parametrize("field", ["cell_line_id", "drug_name", "question"])
def test_blank_inputs_are_rejected(field):
    with TestClient(create_app(ResearchService(ScenarioClient("success")))) as client:
        response = client.post("/research", json={**REQUEST, field: " "})
    assert response.status_code == 422


def test_frontend_catalog_and_stream_have_real_progress():
    with TestClient(create_app(ResearchService(ScenarioClient("success"), max_polls=1))) as client:
        assert client.get("/").status_code == 200
        assert client.get("/static/app.js").status_code == 200
        assert client.get("/catalog").json()["drug_names"] == ["Cisplatin"]
        response = client.post("/research/stream", json=REQUEST)
    events = [json.loads(line) for line in response.text.splitlines()]
    assert events[0] == {"event": "progress", "stage": "prediction", "status": "completed"}
    assert events[-1]["event"] == "result"
    assert events[-1]["data"]["trace_id"] == response.headers["x-trace-id"]


def test_stream_returns_structured_failure():
    with TestClient(create_app(ResearchService(ScenarioClient("prediction_down")))) as client:
        response = client.post("/research/stream", json=REQUEST)
    assert json.loads(response.text)["code"] == "PREDICTION_UNAVAILABLE"
