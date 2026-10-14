from __future__ import annotations

from datetime import date
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, StringConstraints, model_validator


NonBlank = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class RetrievalFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    year_from: int | None = Field(default=None, ge=1800, le=2200)
    year_to: int | None = Field(default=None, ge=1800, le=2200)
    drug: NonBlank | None = None
    gene: NonBlank | None = None
    journal: NonBlank | None = None
    minimum_score: float | None = Field(default=None, ge=0, le=1)

    @model_validator(mode="after")
    def validate_year_range(self):
        if self.year_from and self.year_to and self.year_from > self.year_to:
            raise ValueError("year_from must be less than or equal to year_to")
        return self


class RetrieveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: NonBlank = Field(max_length=1000)
    top_k: int = Field(default=5, ge=1, le=25)
    filters: RetrievalFilters = Field(default_factory=RetrievalFilters)


class RetrievalResult(BaseModel):
    pmid: str
    doi: str | None = None
    title: str
    snippet: str
    score: float = Field(ge=0, le=1)
    year: int | None = None
    journal: str | None = None
    authors: list[str] = Field(default_factory=list)
    url: HttpUrl
    ingestion_date: date
    selection_query: str


class RetrieveResponse(BaseModel):
    results: list[RetrievalResult]
    embedding_version: str
    normalized_query: str
    latency_ms: float = Field(ge=0)


class ArticleInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pmid: NonBlank
    doi: str | None = None
    title: NonBlank
    abstract: NonBlank
    authors: list[str] = Field(default_factory=list)
    year: int | None = Field(default=None, ge=1800, le=2200)
    journal: str | None = None
    url: HttpUrl | None = None
    ingestion_date: date
    selection_query: NonBlank


class IngestionStats(BaseModel):
    inserted: int = 0
    updated: int = 0
    skipped: int = 0
    failed: int = 0
    chunks_written: int = 0


class RetrievalMetadata(BaseModel):
    embedding_model: str
    embedding_version: str
    embedding_dimensions: int
    document_count: int
    chunk_count: int

