import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

import fakeredis
import pytest
from fastapi.testclient import TestClient
from redis.exceptions import ConnectionError
from rq.exceptions import NoSuchJobError

from explanation_service.cache import explanation_cache_key, explanation_job_id
from explanation_service.main import app
from explanation_service.tasks import build_explanation


client = TestClient(app)


@pytest.fixture
def fake_redis():
    return fakeredis.FakeRedis()


def submit(fake_redis, enqueue):
    with (
        patch("explanation_service.main.redis_connection", fake_redis),
        patch("explanation_service.main.explanation_queue.enqueue", enqueue),
    ):
        return client.post(
            "/explanations",
            json={"cell_line_id": "SIDM00001", "drug_name": "Cisplatin"},
        )


def test_submission_returns_202_and_plural_polling_url(fake_redis):
    enqueue = Mock(return_value=SimpleNamespace())
    response = submit(fake_redis, enqueue)

    assert response.status_code == 202
    assert response.json()["status"] == "queued"
    assert response.json()["status_url"].startswith("/explanations/exp_")
    assert response.json()["cache_hit"] is False
    enqueue.assert_called_once()


def test_duplicate_inflight_submission_reuses_job(fake_redis):
    enqueue = Mock(return_value=SimpleNamespace())
    first = submit(fake_redis, enqueue).json()
    second = submit(fake_redis, enqueue).json()

    assert second["job_id"] == first["job_id"]
    assert second["status"] == "queued"
    assert enqueue.call_count == 1


def test_live_job_is_reused_when_its_lock_was_lost(fake_redis):
    enqueue = Mock()
    existing_job = Mock()
    existing_job.get_status.return_value = "started"
    with (
        patch("explanation_service.main.redis_connection", fake_redis),
        patch("explanation_service.main.explanation_queue.enqueue", enqueue),
        patch("explanation_service.main.Job.fetch", return_value=existing_job),
    ):
        response = client.post(
            "/explanations",
            json={"cell_line_id": "SIDM00001", "drug_name": "Cisplatin"},
        )

    assert response.status_code == 202
    assert response.json()["status"] == "running"
    enqueue.assert_not_called()


def test_terminal_job_is_deleted_before_reusing_deterministic_id(fake_redis):
    enqueue = Mock(return_value=SimpleNamespace())
    existing_job = Mock()
    existing_job.get_status.return_value = "failed"
    with (
        patch("explanation_service.main.redis_connection", fake_redis),
        patch("explanation_service.main.explanation_queue.enqueue", enqueue),
        patch("explanation_service.main.Job.fetch", return_value=existing_job),
    ):
        response = client.post(
            "/explanations",
            json={"cell_line_id": "SIDM00001", "drug_name": "Cisplatin"},
        )

    assert response.status_code == 202
    assert response.json()["status"] == "queued"
    existing_job.delete.assert_called_once_with()
    enqueue.assert_called_once()


def test_completed_second_submission_is_cache_hit(fake_redis):
    cache_key = explanation_cache_key("SIDM00001", "Cisplatin")
    result = build_explanation("SIDM00001", "Cisplatin")
    fake_redis.set(cache_key, json.dumps(result))

    response = submit(fake_redis, Mock()).json()

    assert response["status"] == "completed"
    assert response["cache_hit"] is True
    assert int(fake_redis.get("explanation:metrics:cache_hits")) == 1


def test_cached_result_can_be_polled(fake_redis):
    cache_key = explanation_cache_key("SIDM00001", "Cisplatin")
    job_id = explanation_job_id(cache_key)
    fake_redis.set(cache_key, json.dumps(build_explanation("SIDM00001", "Cisplatin")))
    fake_redis.set(
        f"explanation:job:{job_id}",
        json.dumps({"cache_key": cache_key, "cache_hit": True}),
    )

    with patch("explanation_service.main.redis_connection", fake_redis):
        response = client.get(f"/explanations/{job_id}")

    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    assert response.json()["result"]["cache_hit"] is True


def test_failed_job_has_stable_error_object(fake_redis):
    job = Mock(id="exp_failed")
    job.get_status.return_value = "failed"
    with (
        patch("explanation_service.main.redis_connection", fake_redis),
        patch("explanation_service.main.Job.fetch", return_value=job),
    ):
        response = client.get("/explanations/exp_failed")

    assert response.json()["status"] == "failed"
    assert response.json()["error"] == {
        "code": "EXPLANATION_FAILED",
        "message": "The worker could not calculate this explanation.",
        "retryable": False,
    }


def test_unknown_job_returns_404(fake_redis):
    with (
        patch("explanation_service.main.redis_connection", fake_redis),
        patch("explanation_service.main.Job.fetch", side_effect=NoSuchJobError),
    ):
        response = client.get("/explanations/missing")
    assert response.status_code == 404


def test_polling_returns_503_when_redis_is_unavailable():
    unavailable = Mock()
    unavailable.get.side_effect = ConnectionError("unavailable")
    with patch("explanation_service.main.redis_connection", unavailable):
        response = client.get("/explanations/exp_unavailable")

    assert response.status_code == 503
    assert response.json()["detail"] == "Explanation queue is unavailable"


def test_cached_polling_returns_503_when_redis_fails_mid_read():
    unavailable = Mock()
    unavailable.get.side_effect = [
        json.dumps({"cache_key": "explanation:cached", "cache_hit": True}),
        ConnectionError("unavailable"),
    ]
    with patch("explanation_service.main.redis_connection", unavailable):
        response = client.get("/explanations/exp_cached")

    assert response.status_code == 503
    assert response.json()["detail"] == "Explanation queue is unavailable"


def test_submission_returns_503_and_releases_lock_on_enqueue_failure(fake_redis):
    enqueue = Mock(side_effect=ConnectionError("unavailable"))
    response = submit(fake_redis, enqueue)

    assert response.status_code == 503
    assert response.json()["detail"] == "Explanation queue is unavailable"
    cache_key = explanation_cache_key("SIDM00001", "Cisplatin")
    assert not fake_redis.exists(f"{cache_key}:inflight")


def test_unknown_identifier_is_not_enqueued(fake_redis):
    enqueue = Mock()
    with (
        patch("explanation_service.main.redis_connection", fake_redis),
        patch("explanation_service.main.explanation_queue.enqueue", enqueue),
    ):
        response = client.post(
            "/explanations",
            json={"cell_line_id": "unknown", "drug_name": "Cisplatin"},
        )
    assert response.status_code == 400
    enqueue.assert_not_called()


def test_model_version_changes_cache_key(monkeypatch):
    import explanation_service.cache as cache

    old_key = cache.explanation_cache_key("SIDM00001", "Cisplatin")
    monkeypatch.setattr(cache, "MODEL_VERSION", "xgb_v2")
    new_key = cache.explanation_cache_key("SIDM00001", "Cisplatin")
    assert old_key != new_key
