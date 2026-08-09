import json

from fastapi import FastAPI, HTTPException, status
from redis.exceptions import RedisError
from rq import Retry
from rq.exceptions import NoSuchJobError
from rq.job import Job

from app.model import build_feature_row
from explanation_service.cache import explanation_cache_key, explanation_job_id
from explanation_service.queue import explanation_queue, redis_connection
from explanation_service.schemas import (
    ExplainRequest, ExplainStatusResponse, ExplainSubmissionResponse,
    ExplanationError, ExplanationStatus,
)
from explanation_service.tasks import CACHE_TTL_SECONDS, run_explanation


app = FastAPI(title="CancerBench Explanation Service", version="0.2.0")
INFLIGHT_TTL_SECONDS = 360


@app.get("/health")
def health():
    try:
        redis_connection.ping()
    except RedisError as exc:
        raise HTTPException(status_code=503, detail="Redis is unavailable") from exc
    return {"status": "ok", "redis": "connected"}


@app.post(
    "/explanations",
    response_model=ExplainSubmissionResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def submit_explanation(req: ExplainRequest):
    try:
        build_feature_row(req.cell_line_id, req.drug_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    cache_key = explanation_cache_key(req.cell_line_id, req.drug_name)
    job_id = explanation_job_id(cache_key)
    status_url = f"/explanations/{job_id}"
    inflight_key = f"{cache_key}:inflight"

    try:
        if redis_connection.exists(cache_key):
            redis_connection.incr("explanation:metrics:cache_hits")
            redis_connection.set(
                f"explanation:job:{job_id}",
                json.dumps({"cache_key": cache_key, "cache_hit": True}),
                ex=CACHE_TTL_SECONDS,
            )
            return ExplainSubmissionResponse(
                job_id=job_id, status=ExplanationStatus.COMPLETED,
                status_url=status_url, cache_hit=True,
            )

        redis_connection.incr("explanation:metrics:cache_misses")
        acquired = redis_connection.set(inflight_key, job_id, nx=True, ex=INFLIGHT_TTL_SECONDS)
        if not acquired:
            existing = redis_connection.get(inflight_key)
            existing_id = existing.decode() if isinstance(existing, bytes) else existing
            return ExplainSubmissionResponse(
                job_id=existing_id or job_id, status=ExplanationStatus.QUEUED,
                status_url=f"/explanations/{existing_id or job_id}", cache_hit=False,
            )

        explanation_queue.enqueue(
            run_explanation, req.cell_line_id, req.drug_name,
            cache_key, inflight_key, job_id,
            job_id=job_id, job_timeout=300, result_ttl=CACHE_TTL_SECONDS,
            failure_ttl=86400, retry=Retry(max=2, interval=[5, 15]),
            description=f"Explain {req.cell_line_id} response to {req.drug_name}",
        )
    except RedisError as exc:
        redis_connection.delete(inflight_key)
        raise HTTPException(status_code=503, detail="Explanation queue is unavailable") from exc

    return ExplainSubmissionResponse(
        job_id=job_id, status=ExplanationStatus.QUEUED,
        status_url=status_url, cache_hit=False,
    )


@app.get("/explanations/{job_id}", response_model=ExplainStatusResponse)
def get_explanation(job_id: str):
    job_mapping = redis_connection.get(f"explanation:job:{job_id}")
    if isinstance(job_mapping, bytes):
        job_mapping = job_mapping.decode()
    if job_mapping:
        mapping = json.loads(job_mapping)
        cached = redis_connection.get(mapping["cache_key"])
        if cached:
            result = json.loads(cached)
            result["cache_hit"] = mapping["cache_hit"]
            return ExplainStatusResponse(
                job_id=job_id, status=ExplanationStatus.COMPLETED, result=result,
            )

    try:
        job = Job.fetch(job_id, connection=redis_connection)
    except NoSuchJobError as exc:
        raise HTTPException(status_code=404, detail="Explanation job not found or expired") from exc

    raw_status = job.get_status(refresh=True)
    rq_status = getattr(raw_status, "value", raw_status)
    mapped = {
        "queued": ExplanationStatus.QUEUED, "deferred": ExplanationStatus.QUEUED,
        "scheduled": ExplanationStatus.QUEUED, "started": ExplanationStatus.RUNNING,
        "finished": ExplanationStatus.COMPLETED, "failed": ExplanationStatus.FAILED,
        "stopped": ExplanationStatus.FAILED, "canceled": ExplanationStatus.FAILED,
    }.get(rq_status, ExplanationStatus.FAILED)

    if mapped == ExplanationStatus.COMPLETED:
        return ExplainStatusResponse(job_id=job.id, status=mapped, result=job.result)
    if mapped == ExplanationStatus.FAILED:
        redis_connection.delete(f"explanation:job:{job_id}")
        return ExplainStatusResponse(
            job_id=job.id, status=mapped,
            error=ExplanationError(
                code="EXPLANATION_FAILED",
                message="The worker could not calculate this explanation.",
                retryable=False,
            ),
        )
    return ExplainStatusResponse(job_id=job.id, status=mapped)
