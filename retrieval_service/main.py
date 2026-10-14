from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from retrieval_service.schemas import RetrievalMetadata, RetrieveRequest, RetrieveResponse
from retrieval_service.service import RetrievalService
from retrieval_service.store import PostgresLiteratureStore


def create_app(service: RetrievalService | None = None) -> FastAPI:
    retrieval_service = service or RetrievalService(
        PostgresLiteratureStore(
            os.getenv("DATABASE_URL", "postgresql://cancerbench:cancerbench@localhost:5432/cancerbench")
        ),
        default_minimum_score=float(os.getenv("RETRIEVAL_MINIMUM_SCORE", "0.08")),
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        retrieval_service.initialize()
        yield

    app = FastAPI(
        title="CancerBench Literature Retrieval Service",
        version="0.3.0",
        description="Research literature retrieval with traceable PubMed provenance.",
        lifespan=lifespan,
    )
    app.state.retrieval_service = retrieval_service

    @app.get("/health")
    def health():
        try:
            connected = app.state.retrieval_service.store.health()
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Literature database is unavailable") from exc
        return {"status": "ok", "database": "connected" if connected else "unavailable"}

    @app.post("/retrieve", response_model=RetrieveResponse)
    def retrieve(request: RetrieveRequest):
        try:
            return app.state.retrieval_service.retrieve(request)
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Literature retrieval is unavailable") from exc

    @app.get("/metadata", response_model=RetrievalMetadata)
    def metadata():
        try:
            return app.state.retrieval_service.metadata()
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Literature database is unavailable") from exc

    return app


app = create_app()
