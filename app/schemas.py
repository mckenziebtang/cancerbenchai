from pydantic import BaseModel

class PredictRequest(BaseModel):
    cell_line_id: str
    drug_id: str

class PredictResponse(BaseModel):
    prediction: float
    model_version: str
