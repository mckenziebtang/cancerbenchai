from __future__ import annotations

import json
from pathlib import Path

import anyio
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from agent_service.client import HttpServiceClient, UpstreamError
from agent_service.schemas import ErrorResponse, ResearchRequest, ResearchResponse
from agent_service.service import ResearchService
from observability.telemetry import instrument_app


def create_app(service: ResearchService | None = None) -> FastAPI:
    app = FastAPI(title="CancerBench Research Service", version="0.1.0")
    app.state.research_service = service or ResearchService(HttpServiceClient())
    instrument_app(app, "research")
    frontend = Path(__file__).resolve().parent.parent / "frontend"
    app.mount("/static", StaticFiles(directory=frontend), name="static")

    @app.get("/", include_in_schema=False)
    def frontend_page():
        return FileResponse(frontend / "index.html")

    @app.get("/catalog")
    def catalog():
        try:
            client = app.state.research_service.client
            cells = client.get("prediction", "/cell-lines")["cell_line_ids"]
            drugs = client.get("prediction", "/drugs")["drug_names"]
            if not all(isinstance(items, list) and all(isinstance(item, str) for item in items) for items in (cells, drugs)):
                raise ValueError("Invalid catalog")
            return {"cell_line_ids": cells, "drug_names": drugs}
        except (UpstreamError, KeyError, TypeError, ValueError):
            return JSONResponse(status_code=503, content={"code": "CATALOG_UNAVAILABLE", "message": "Could not load supported identifiers. Try again when prediction is available."})

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.post("/research", response_model=ResearchResponse,
              responses={400: {"model": ErrorResponse}, 502: {"model": ErrorResponse},
                         503: {"model": ErrorResponse}})
    def research(request: ResearchRequest):
        try:
            return app.state.research_service.run(request)
        except UpstreamError as exc:
            return JSONResponse(
                status_code=exc.status,
                content=ErrorResponse(code=exc.code, message=exc.message).model_dump(),
            )

    @app.post("/research/stream")
    async def research_stream(request: ResearchRequest):
        async def events():
            send, receive = anyio.create_memory_object_stream(10)

            def progress(stage, status):
                anyio.from_thread.run(send.send, {"event": "progress", "stage": stage, "status": status})

            async def run():
                async with send:
                    try:
                        result = await anyio.to_thread.run_sync(lambda: app.state.research_service.run(request, progress))
                        await send.send({"event": "result", "data": result.model_dump(mode="json")})
                    except UpstreamError as exc:
                        await send.send({"event": "error", "code": exc.code, "message": exc.message})
                    except Exception:
                        await send.send({"event": "error", "code": "RESEARCH_FAILED", "message": "Research could not be completed. Check service health and retry."})

            async with anyio.create_task_group() as group:
                group.start_soon(run)
                async with receive:
                    async for event in receive:
                        yield json.dumps(event) + "\n"

        return StreamingResponse(events(), media_type="application/x-ndjson", headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})

    return app


app = create_app()
