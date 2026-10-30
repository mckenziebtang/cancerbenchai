from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, StringConstraints


NonBlank = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class ResearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cell_line_id: NonBlank
    drug_name: NonBlank
    question: NonBlank = Field(max_length=1000)


class Prediction(BaseModel):
    prediction: float = Field(allow_inf_nan=False)
    cell_line_id: str
    drug_name: str
    model_version: str


class Feature(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    name: str
    value: float | str
    contribution: float = Field(allow_inf_nan=False)
    direction: Literal["positive", "negative", "neutral"]


class Citation(BaseModel):
    pmid: str
    title: str
    snippet: str
    url: HttpUrl
    year: int | None = None


class ResearchResponse(BaseModel):
    answer: str
    prediction: Prediction
    prediction_unit: Literal["LN_IC50"] = "LN_IC50"
    top_features: list[Feature]
    explanation_status: Literal["completed", "failed", "unavailable", "timed_out"]
    explanation_cache_hit: bool = False
    citations: list[Citation]
    limitations: list[str]
    trace_id: str
    disclaimer: str = "Research use only. Not for clinical decisions."


class ErrorResponse(BaseModel):
    code: str
    message: str
