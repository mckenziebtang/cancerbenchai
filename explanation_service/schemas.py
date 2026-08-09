from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


Identifier = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class ExplanationStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ExplainRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cell_line_id: Identifier = Field(examples=["SIDM00001"])
    drug_name: Identifier = Field(examples=["Cisplatin"])


class ExplainSubmissionResponse(BaseModel):
    job_id: str
    status: ExplanationStatus
    status_url: str
    cache_hit: bool


class FeatureContribution(BaseModel):
    name: str
    value: float | str
    contribution: float
    direction: Literal["positive", "negative", "neutral"]


class ExplanationResult(BaseModel):
    cell_line_id: str
    drug_name: str
    prediction: float
    base_value: float
    features: list[FeatureContribution]
    other_contribution: float
    model_version: str
    explainer_version: str
    cache_hit: bool = False


class ExplanationError(BaseModel):
    code: str
    message: str
    retryable: bool


class ExplainStatusResponse(BaseModel):
    job_id: str
    status: ExplanationStatus
    result: ExplanationResult | None = None
    error: ExplanationError | None = None
