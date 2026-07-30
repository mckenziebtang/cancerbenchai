from pydantic import BaseModel

class PredictRequest(BaseModel):
    cell_line_id: str
    drug_name: str

class PredictResponse(BaseModel):
    prediction: float
    cell_line_id: str
    drug_name: str
    model_version: str
