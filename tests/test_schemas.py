import pytest
from pydantic import ValidationError 
from app.schemas import PredictRequest, PredictResponse

#test case 
def test_predict_request_valid():
    req = PredictRequest(cell_line_id ="A549", drug_name="cisplatin")
    assert req.cell_line_id == "A549"
    assert req.drug_name == "cisplatin"

def test_predict_request_missing_field():
    with pytest.raises(ValidationError):
        PredictRequest(cell_line_id="A549")

def test_predict_request_wrong_type():
    with pytest.raises(ValidationError):
        PredictRequest(cell_line_id=123, drug_name="cisplatin")

def test_predict_response_valid():
    res = PredictResponse(
        prediction=0.42,
        cell_line_id="SIDM00001",
        drug_name="Cisplatin",
        model_version="xgb_v1",
    )
    assert res.prediction == 0.42

def test_predict_response_missing_field():
    with pytest.raises(ValidationError):
        PredictResponse(
            prediction=0.42,
            drug_name="Cisplatin",
            model_version="xgb_v1",
        )

def test_predict_response_invalid_prediction():
    with pytest.raises(ValidationError):
        PredictResponse(
            prediction="not-a-number",
            cell_line_id="SIDM00001",
            drug_name="Cisplatin",
            model_version="xgb_v1",
        )