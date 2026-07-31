from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


Identifier = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]

class PredictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cell_line_id: Identifier = Field(
        description="Sanger model identifier from the supported cell-line list",
        examples=["SIDM00001"],
    )
    drug_name: Identifier = Field(
        description="Case-sensitive drug name from the supported drug list",
        examples=["Cisplatin"],
    )

class PredictResponse(BaseModel):
    prediction: float
    cell_line_id: str
    drug_name: str
    model_version: str


class ErrorResponse(BaseModel):
    code: str
    message: str


class ServiceMetadataResponse(BaseModel):
    service: str
    model_version: str
    model_type: str
    dataset: str
    target: str
    target_description: str
    feature_count: int
    cell_line_count: int
    drug_count: int
    intended_use: str


class CellLineListResponse(BaseModel):
    count: int
    cell_line_ids: list[str]


class DrugListResponse(BaseModel):
    count: int
    drug_names: list[str]
