from fastapi import FastAPI, HTTPException, status
from rq.exceptions import NoSuchJobError
from rq.job import Job

from app.model import build_feature_row
from explanation_service.queue import explanation_queue, redis_connection
from explanation_service.schemas import (
    ExplainRequest,
    ExplainStatusResponse,
    ExplainSubmissionResponse,
    ExplanationStatus,
)
from explanation_service.tasks import build_explanation


app = FastAPI(
    title="CancerBench Explanation Service",
    description="Asynchronous explanation jobs for CancerBench predictions.",
    version="0.1.0",
)


@app.get("/health")
def health():
    try:
        redis_connection.ping()
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="Redis is unavailable",
        )

    return {
        "status": "ok",
        "redis": "connected",
    }


@app.post(
    "/explain",
    response_model=ExplainSubmissionResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def submit_explanation(req: ExplainRequest):
    try:
        build_feature_row(req.cell_line_id, req.drug_name)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    job = explanation_queue.enqueue(
        build_explanation,
        req.cell_line_id,
        req.drug_name,
        job_timeout=300,
        result_ttl=3600,
        failure_ttl=86400,
        description=(
            f"Explain {req.cell_line_id} response to {req.drug_name}"
        ),
    )

    return ExplainSubmissionResponse(
        job_id=job.id,
        status=ExplanationStatus.QUEUED,
        status_url=f"/explain/{job.id}",
        cache_hit=False,
    )


@app.get(
    "/explain/{job_id}",
    response_model=ExplainStatusResponse,
)
def get_explanation(job_id: str):
    try:
        job = Job.fetch(
            job_id,
            connection=redis_connection,
        )
    except NoSuchJobError:
        raise HTTPException(
            status_code=404,
            detail="Explanation job not found",
        )

    rq_status = job.get_status(refresh=True)

    status_mapping = {
        "queued": ExplanationStatus.QUEUED,
        "deferred": ExplanationStatus.QUEUED,
        "scheduled": ExplanationStatus.QUEUED,
        "started": ExplanationStatus.RUNNING,
        "finished": ExplanationStatus.COMPLETED,
        "failed": ExplanationStatus.FAILED,
        "stopped": ExplanationStatus.FAILED,
        "canceled": ExplanationStatus.FAILED,
    }

    api_status = status_mapping.get(
        getattr(rq_status, "value", rq_status),
        ExplanationStatus.FAILED,
    )

    if api_status == ExplanationStatus.COMPLETED:
        return ExplainStatusResponse(
            job_id=job.id,
            status=api_status,
            result=job.result,
        )

    if api_status == ExplanationStatus.FAILED:
        return ExplainStatusResponse(
            job_id=job.id,
            status=api_status,
            error=job.exc_info or "Explanation job failed",
        )

    return ExplainStatusResponse(
        job_id=job.id,
        status=api_status,
    )
