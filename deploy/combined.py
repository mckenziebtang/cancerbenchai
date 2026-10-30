"""One web process for the free demo, with authenticated loopback HTTP calls."""

import asyncio
import os
import secrets
from contextlib import asynccontextmanager

from starlette.responses import JSONResponse

from agent_service.client import HttpServiceClient
from agent_service.main import create_app as research_app
from agent_service.service import ResearchService


class DemoGateway:
    def __init__(self, app, token):
        self.app = app
        self.token = token.encode()
        self.research_slot = asyncio.Semaphore(1)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        path = scope["path"]
        if path.startswith("/internal/"):
            supplied = dict(scope["headers"]).get(b"x-cancerbench-internal", b"")
            if not secrets.compare_digest(supplied, self.token):
                return await JSONResponse({"code": "NOT_FOUND"}, status_code=404)(scope, receive, send)
        limited = scope["method"] == "POST" and path in {"/research", "/research/stream"}
        if not limited:
            return await self.app(scope, receive, send)
        if self.research_slot.locked():
            response = JSONResponse(
                {"code": "DEMO_BUSY", "message": "The free demo is handling another question. Please retry shortly."},
                status_code=429, headers={"Retry-After": "5"},
            )
            return await response(scope, receive, send)
        async with self.research_slot:
            return await self.app(scope, receive, send)


def create_app(service=None, *, backends=None, token=None):
    token = token or os.environ["INTERNAL_API_TOKEN"]
    if len(token) < 32:
        raise ValueError("Internal service token must have at least 32 characters")
    application = research_app(service or ResearchService(
        HttpServiceClient(timeout=20, internal_token=token), max_polls=240, poll_interval=0.25,
    ))
    if backends is None:
        from app.main import app as prediction
        from explanation_service.main import app as explanation
        from retrieval_service.main import app as literature

        backends = {"prediction": prediction, "explanation": explanation, "literature": literature}

        @asynccontextmanager
        async def lifespan(_):
            async with literature.router.lifespan_context(literature):
                yield

        application.router.lifespan_context = lifespan
    for name, backend in backends.items():
        application.mount(f"/internal/{name}", backend)
    application.add_middleware(DemoGateway, token=token)
    return application
