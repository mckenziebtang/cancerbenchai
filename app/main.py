from fastapi import FastAPI, HTTPException
from app.schemas import PredictRequest, PredictResponse
from app.model import predict

app = FastAPI(title="CancerBench Prediction Service")

@app.get("/")
def root():
    return {"message": "CancerBench Prediction Service is running"}
@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/predict", response_model=PredictResponse)
def predict_endpoint(req: PredictRequest):
    try:
        result = predict(req.cell_line_id, req.drug_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))