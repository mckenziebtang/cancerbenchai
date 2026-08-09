import os
import uuid

import pytest
import fakeredis
from redis import Redis
from rq import Queue, SimpleWorker

from explanation_service.tasks import run_explanation


def test_job_transitions_from_queued_to_completed(monkeypatch):
    redis = fakeredis.FakeRedis()
    queue = Queue("explanation-test", connection=redis)
    job = queue.enqueue(
        run_explanation,
        "SIDM00001",
        "Cisplatin",
        "test:explanation:cache",
        "test:explanation:inflight",
        "exp_transition",
        job_id="exp_transition",
    )
    assert job.get_status().value == "queued"

    monkeypatch.setattr("explanation_service.tasks.redis_connection", redis)
    SimpleWorker([queue], connection=redis).work(
        burst=True, with_scheduler=False, logging_level="WARNING"
    )
    job.refresh()

    assert job.get_status().value == "finished"
    assert redis.exists("test:explanation:cache")


@pytest.mark.integration
def test_isolated_redis_atomic_duplicate_lock():
    url = os.getenv("REDIS_TEST_URL")
    if not url:
        pytest.skip("Set REDIS_TEST_URL to run against an isolated Redis instance")

    redis = Redis.from_url(url)
    key = f"cancerbench-test:{uuid.uuid4()}:inflight"
    try:
        assert redis.set(key, "exp_1", nx=True, ex=30) is True
        assert redis.set(key, "exp_2", nx=True, ex=30) is None
        assert redis.get(key) == b"exp_1"
        assert 0 < redis.ttl(key) <= 30
    finally:
        redis.delete(key)
