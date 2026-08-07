from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from explanation_service.main import app


client = TestClient(app)


def test_submit_explanation_returns_polling_url():
    queued_job = SimpleNamespace(id="job-123")

    with patch(
        "explanation_service.main.explanation_queue.enqueue",
        return_value=queued_job,
    ) as enqueue:
        response = client.post(
            "/explain",
            json={"cell_line_id": "SIDM00001", "drug_name": "Cisplatin"},
        )

    assert response.status_code == 202
    assert response.json() == {
        "job_id": "job-123",
        "status": "queued",
        "status_url": "/explain/job-123",
        "cache_hit": False,
    }
    enqueue.assert_called_once()


def test_submit_explanation_rejects_unknown_input():
    response = client.post(
        "/explain",
        json={"cell_line_id": "unknown", "drug_name": "Cisplatin"},
    )

    assert response.status_code == 400
    assert "Unknown cell line" in response.json()["detail"]


def test_get_completed_explanation():
    job = Mock(
        id="job-123",
        result={
            "cell_line_id": "SIDM00001",
            "drug_name": "Cisplatin",
            "prediction": 1.25,
            "base_value": 2.0,
            "feature_contributions": {"DRUG_NAME": -0.75},
        },
    )
    job.get_status.return_value = "finished"

    with patch("explanation_service.main.Job.fetch", return_value=job):
        response = client.get("/explain/job-123")

    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    assert response.json()["result"]["prediction"] == 1.25


def test_get_unknown_job_returns_404():
    from rq.exceptions import NoSuchJobError

    with patch(
        "explanation_service.main.Job.fetch",
        side_effect=NoSuchJobError,
    ):
        response = client.get("/explain/missing")

    assert response.status_code == 404
