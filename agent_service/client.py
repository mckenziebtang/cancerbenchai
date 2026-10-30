"""Small HTTP client for the three existing services; no external model calls."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any
from opentelemetry import trace
from opentelemetry.trace import SpanKind
from observability.telemetry import carrier, traced


class UpstreamError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


class HttpServiceClient:
    def __init__(self, timeout: float = 5.0):
        self.timeout = timeout
        self.urls = {
            "prediction": os.getenv("PREDICTION_URL", "http://localhost:18000").rstrip("/"),
            "explanation": os.getenv("EXPLANATION_URL", "http://localhost:18001").rstrip("/"),
            "retrieval": os.getenv("RETRIEVAL_URL", "http://localhost:18002").rstrip("/"),
        }

    def post(self, service: str, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request(service, path, payload)

    def get(self, service: str, path: str) -> dict[str, Any]:
        return self._request(service, path)

    @traced("research", "upstream.call", kind=SpanKind.CLIENT)
    def _request(
        self, service: str, path: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        if not path.startswith("/") or path.startswith("//"):
            raise ValueError("Expected a local service path")
        span = trace.get_current_span()
        route = "/explanations/{job_id}" if path.startswith("/explanations/") else path
        span.update_name(f"{service} {route}")
        span.set_attribute("cancerbench.upstream.service", service)
        span.set_attribute("http.request.method", "POST" if payload is not None else "GET")
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = urllib.request.Request(
            self.urls[service] + path, data=data,
            headers={**carrier(), **({"Content-Type": "application/json"} if data is not None else {})},
            method="POST" if data is not None else "GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                result = json.load(response)
        except urllib.error.HTTPError as exc:
            try:
                error = json.load(exc)
            except (ValueError, OSError):
                error = {}
            if service == "prediction" and exc.code == 400 and isinstance(error, dict):
                raise UpstreamError(400, error.get("code", "INVALID_PREDICTION_INPUT"),
                                    error.get("message", "Invalid cell line or drug")) from exc
            raise UpstreamError(503, f"{service.upper()}_UNAVAILABLE",
                                f"{service.capitalize()} service returned an error") from exc
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            raise UpstreamError(503, f"{service.upper()}_UNAVAILABLE",
                                f"{service.capitalize()} service is unavailable") from exc
        if not isinstance(result, dict):
            raise UpstreamError(502, "INVALID_UPSTREAM_RESPONSE", "Invalid service response")
        return result
