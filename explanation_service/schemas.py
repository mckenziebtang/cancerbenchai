from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


Identifier = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1),
]


class ExplanationStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ExplainRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cell_line_id: Identifier = Field(
        description="Supported Sanger model identifier",
        examples=["SIDM00001"],
    )
    drug_name: Identifier = Field(
        description="Supported case-sensitive drug name",
        examples=["Cisplatin"],
    )

#tells users where to poll
class ExplainSubmissionResponse(BaseModel):
    job_id: str
    status: ExplanationStatus
    status_url: str
    cache_hit: bool = False


class ExplanationResult(BaseModel):
    cell_line_id: str
    drug_name: str
    prediction: float
    base_value: float
    feature_contributions: dict[str, float]

#will be null when pending and have a value after 
class ExplainStatusResponse(BaseModel):
    job_id: str
    status: ExplanationStatus
    result: ExplanationResult | None = None
    error: str | None = None
