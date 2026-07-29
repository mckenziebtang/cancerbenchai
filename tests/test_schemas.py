import pytest
from pydantic import ValidationError 
from app.schemas import PredictRequest

#test case 
def test_predict_request_valid():
    req = PredictRequest(cell_line_id, drug_name)
    assert req.cell_line_id == "A549"
    assert req.drug_name == "cisplastin"

def test_predict_request_missing_field():
    with pytests.raises(ValidationError):
        PredictRequest(cell_line_id="A549")

def test_predict_request_wrong_type():
    with pytests.raises(ValidationError):
        PredictRequest(cell_line_id=123, drug_name="cisplastin")

def test_predict_response_valid():
    res = PredictResponse(prediction=0.42, model_version="v1", drug_name="cisplastin")
    assert req.prediction == 0.42