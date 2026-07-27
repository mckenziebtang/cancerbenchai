from pydantic import BaseModel

class PredictRequest(BaseModel):
    cell_line_id: str
    drug_name: str

class PredictResponse(BaseModel):
    prediction: float
    model_version: str
    drug_name: str
