"""W3C tracing, bounded metrics, and allowlisted JSON logs.

Never capture request bodies, raw URLs, exception text, SQL, or Redis keys.
Providers are created per process so RQ's forked jobs get a live exporter.
"""

from __future__ import annotations

import functools
import inspect
import json
import logging
import os
import re
import sys
import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor
from opentelemetry.trace import SpanKind, StatusCode
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Counter, Histogram, generate_latest
from starlette.responses import Response

REQUEST_ID: ContextVar[str] = ContextVar("request_id", default="")
PROPAGATOR = TraceContextTextMapPropagator()
PROVIDERS: dict[tuple[int, str], TracerProvider] = {}
METRICS: dict[tuple[int, str], Metrics] = {}
IDENTIFIER = re.compile(r"(?:[a-fA-F0-9]{32}|[a-fA-F0-9]{8}(?:-[a-fA-F0-9]{4}){3}-[a-fA-F0-9]{12})")
LOGGER = logging.getLogger("cancerbench.telemetry")


class JsonFormatter(logging.Formatter):
    def format(self, record):
        fields = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "event": "request" if record.msg == "request" else "operation",
        }
        for key in ("service", "request_id", "trace_id", "model_version", "duration_ms", "status", "error_category", "route", "operation"):
            value = getattr(record, key, None)
            if value is not None:
                fields[key] = value
        return json.dumps(fields, separators=(",", ":"))


def configure_logging():
    if not LOGGER.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        LOGGER.addHandler(handler)
        LOGGER.setLevel(logging.INFO)
        LOGGER.propagate = False


def provider(service: str) -> TracerProvider:
    key = (os.getpid(), service)
    if key not in PROVIDERS:
        created = TracerProvider(resource=Resource.create({"service.name": f"cancerbench-{service}"}))
        endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
        if endpoint:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

            exporter = OTLPSpanExporter(endpoint=endpoint.rstrip("/") + "/v1/traces", timeout=2)
            processor = SimpleSpanProcessor if service == "worker" else BatchSpanProcessor
            created.add_span_processor(processor(exporter))
        PROVIDERS[key] = created
    return PROVIDERS[key]


def trace_id() -> str:
    return f"{trace.get_current_span().get_span_context().trace_id:032x}"


def carrier() -> dict[str, str]:
    result: dict[str, str] = {}
    PROPAGATOR.inject(result)
    if REQUEST_ID.get():
        result["x-request-id"] = REQUEST_ID.get()
    return result


class Metrics:
    def __init__(self, service):
        self.registry = CollectorRegistry()
        self.requests = Counter("cancerbench_http_requests_total", "HTTP requests", ["service", "route", "method", "status"], registry=self.registry)
        self.http_duration = Histogram("cancerbench_http_duration_seconds", "HTTP latency", ["service", "route"], registry=self.registry)
        self.operations = Histogram("cancerbench_operation_duration_seconds", "Operation latency", ["service", "operation", "status"], registry=self.registry)
        self.partial = Counter("cancerbench_partial_responses_total", "Research responses with incomplete evidence", registry=self.registry)
        self.service = service


def metrics(service: str) -> Metrics:
    key = (os.getpid(), service)
    if key not in METRICS:
        METRICS[key] = Metrics(service)
    return METRICS[key]


@contextmanager
def operation(service: str, name: str, parent: dict | None = None, kind=SpanKind.INTERNAL):
    configure_logging()
    started = time.perf_counter()
    status = "ok"
    error_category = "none"
    token = None
    if parent is not None:
        incoming = parent.get("x-request-id", "")
        token = REQUEST_ID.set(incoming if IDENTIFIER.fullmatch(incoming) else uuid.uuid4().hex)
    context = PROPAGATOR.extract(parent) if parent is not None else None
    tracer = provider(service).get_tracer("cancerbench")
    with tracer.start_as_current_span(name, context=context, kind=kind, record_exception=False, set_status_on_exception=False) as span:
        try:
            yield span
        except Exception as exc:
            status = "error"
            error_category = type(exc).__name__
            span.set_status(StatusCode.ERROR)
            span.set_attribute("error.type", error_category)
            raise
        finally:
            elapsed = time.perf_counter() - started
            metrics(service).operations.labels(service, name, status).observe(elapsed)
            LOGGER.info("operation", extra={"service": service, "operation": name, "request_id": REQUEST_ID.get(), "trace_id": trace_id(), "model_version": os.getenv("MODEL_VERSION", "xgb_v1"), "duration_ms": round(elapsed * 1000, 3), "status": status, "error_category": error_category})
            if token is not None:
                REQUEST_ID.reset(token)


def traced(service: str, name: str, kind=SpanKind.INTERNAL):
    def decorate(function):
        @functools.wraps(function)
        def wrapped(*args, **kwargs):
            with operation(service, name, kind=kind):
                return function(*args, **kwargs)
        wrapped.__signature__ = inspect.signature(function, eval_str=True)
        return wrapped
    return decorate


class TelemetryMiddleware:
    def __init__(self, app, service):
        self.app = app
        self.service = service

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["path"] == "/metrics":
            return await self.app(scope, receive, send)
        headers = {k.decode("latin-1"): v.decode("latin-1") for k, v in scope["headers"] if k in {b"traceparent", b"tracestate", b"x-request-id"}}
        incoming = headers.get("x-request-id", "")
        request_id = incoming if IDENTIFIER.fullmatch(incoming) else uuid.uuid4().hex
        headers["x-request-id"] = request_id
        token = REQUEST_ID.set(request_id)
        status = 500
        method = scope["method"] if scope["method"] in {"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"} else "OTHER"
        started = time.perf_counter()
        try:
            with operation(self.service, "http.request", headers, SpanKind.SERVER) as span:
                async def respond(message):
                    nonlocal status
                    if message["type"] == "http.response.start":
                        status = message["status"]
                        message["headers"] = list(message.get("headers", [])) + [(b"x-trace-id", trace_id().encode()), (b"x-request-id", request_id.encode())]
                    await send(message)
                try:
                    await self.app(scope, receive, respond)
                finally:
                    route = getattr(scope.get("route"), "path", "unmatched")
                    span.update_name(f"{method} {route}")
                    span.set_attribute("http.route", route)
                    span.set_attribute("http.request.method", method)
                    span.set_attribute("http.response.status_code", status)
                    if status >= 500:
                        span.set_status(StatusCode.ERROR)
                    elapsed = time.perf_counter() - started
                    data = metrics(self.service)
                    data.requests.labels(self.service, route, method, str(status)).inc()
                    data.http_duration.labels(self.service, route).observe(elapsed)
                    LOGGER.info("request", extra={"service": self.service, "route": route, "request_id": request_id, "trace_id": trace_id(), "model_version": os.getenv("MODEL_VERSION", "xgb_v1"), "duration_ms": round(elapsed * 1000, 3), "status": status, "error_category": "server" if status >= 500 else "client" if status >= 400 else "none"})
        finally:
            REQUEST_ID.reset(token)


def instrument_app(app, service: str, collector=None):
    configure_logging()
    data = metrics(service)
    if collector is not None:
        # Factory-created apps can share a registry during tests.
        if not getattr(data, "custom_collector", None):
            data.registry.register(collector)
            data.custom_collector = collector
    app.add_middleware(TelemetryMiddleware, service=service)

    @app.get("/metrics", include_in_schema=False)
    def prometheus_metrics():
        return Response(generate_latest(data.registry), media_type=CONTENT_TYPE_LATEST)

    return app
