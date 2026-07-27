from app.schemas import PredictResponse

def predict(cell_line_id: str, drug_id: str) -> PredictResponse:
    # load features, run model, get prediction
    prediction = 0.82

    return PredictResponse(
        prediction=prediction,
        model_version="xgb_v1"
    )