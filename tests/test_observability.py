import json
import logging
from unittest.mock import patch

import fakeredis
from fastapi import FastAPI
from fastapi.testclient import TestClient
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from observability.telemetry import JsonFormatter, carrier, instrument_app, operation, provider, trace_id


def test_trace_and_request_ids_propagate_without_logging_inputs(caplog):
    app = instrument_app(FastAPI(), "telemetry-test")

    @app.get("/jobs/{job_id}")
    def job(job_id: str):
        return {"trace": trace_id()}

    trace = "a" * 32
    with TestClient(app) as client:
        result = client.get("/jobs/PRIVATE_VALUE?prompt=PRIVATE_PROMPT", headers={"traceparent": f"00-{trace}-{'b' * 16}-01", "x-request-id": "c" * 32})
        metrics = client.get("/metrics").text
    assert result.json()["trace"] == trace
    assert result.headers["x-trace-id"] == trace
    assert result.headers["x-request-id"] == "c" * 32
    assert 'route="/jobs/{job_id}"' in metrics
    assert "PRIVATE_VALUE" not in metrics
    assert "PRIVATE_PROMPT" not in metrics


def test_formatter_drops_exception_and_unapproved_fields():
    record = logging.LogRecord("test", logging.ERROR, "", 1, "PRIVATE_PROMPT", (), None)
    record.question = "PRIVATE_PROMPT"
    record.service = "research"
    record.trace_id = "a" * 32
    rendered = JsonFormatter().format(record)
    assert "PRIVATE_PROMPT" not in rendered
    assert json.loads(rendered)["service"] == "research"


def test_error_spans_do_not_capture_exception_text():
    exporter = InMemorySpanExporter()
    provider("error-test").add_span_processor(SimpleSpanProcessor(exporter))
    try:
        with operation("error-test", "safe.operation"):
            raise ValueError("PRIVATE_PROMPT")
    except ValueError:
        pass
    span = exporter.get_finished_spans()[-1]
    assert span.status.is_ok is False
    assert not span.events
    assert "PRIVATE_PROMPT" not in str(span.attributes)


def test_worker_continues_request_trace_and_persists_metrics():
    from explanation_service.tasks import run_explanation

    exporter = InMemorySpanExporter()
    provider("worker").add_span_processor(SimpleSpanProcessor(exporter))
    fake = fakeredis.FakeRedis()
    with operation("queue-test", "request"):
        expected = trace_id()
        job_context = carrier()
    with patch("explanation_service.tasks.redis_connection", fake), patch("explanation_service.tasks.build_explanation", return_value={"features": []}):
        run_explanation("cell", "drug", "cache", "lock", "job", job_context)
    span = exporter.get_finished_spans()[-1]
    assert f"{span.context.trace_id:032x}" == expected
    assert span.parent is not None
    assert int(fake.get("explanation:metrics:processed_jobs")) == 1
    assert fake.exists("cache")


def test_outgoing_http_carries_trace_headers():
    from agent_service.client import HttpServiceClient

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read(self, *args):
            return b'{"status":"ok"}'

    with operation("client-test", "incoming"):
        expected = trace_id()
        with patch("urllib.request.urlopen", return_value=Response()) as send:
            HttpServiceClient().get("prediction", "/health")
        sent = dict((key.lower(), value) for key, value in send.call_args.args[0].header_items())
    assert sent["traceparent"].split("-")[1] == expected
