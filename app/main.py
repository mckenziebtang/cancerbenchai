from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.model import (
    MODEL_VERSION,
    UnknownCellLineError,
    UnknownDrugError,
    gene_cols,
    predict,
    supported_cell_line_ids,
    supported_drug_names,
)
from app.schemas import (
    CellLineListResponse,
    DrugListResponse,
    ErrorResponse,
    PredictRequest,
    PredictResponse,
    ServiceMetadataResponse,
)

app = FastAPI(
    title="CancerBench Prediction Service",
    description=(
        "Research-only API for predicted drug response using an XGBoost model "
        "trained on a GDSC2 subset. Not for clinical decision-making."
    ),
    version=MODEL_VERSION,
)

@app.get("/")
def root():
    return {"message": "CancerBench Prediction Service is running"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/metadata", response_model=ServiceMetadataResponse)
def service_metadata():
    cell_lines = supported_cell_line_ids()
    drugs = supported_drug_names()
    return ServiceMetadataResponse(
        service="cancerbench-prediction",
        model_version=MODEL_VERSION,
        model_type="XGBoost regressor",
        dataset="GDSC2 drug-response data with cancer-driver mutation features",
        target="LN_IC50",
        target_description=(
            "Natural logarithm of IC50; lower values indicate greater predicted "
            "drug sensitivity within this research dataset."
        ),
        feature_count=len(gene_cols) + 1,
        cell_line_count=len(cell_lines),
        drug_count=len(drugs),
        intended_use="Research and software-engineering demonstration only",
    )


@app.get("/cell-lines", response_model=CellLineListResponse)
def list_cell_lines():
    cell_lines = supported_cell_line_ids()
    return CellLineListResponse(count=len(cell_lines), cell_line_ids=cell_lines)


@app.get("/drugs", response_model=DrugListResponse)
def list_drugs():
    drugs = supported_drug_names()
    return DrugListResponse(count=len(drugs), drug_names=drugs)


@app.post(
    "/predict",
    response_model=PredictResponse,
    responses={400: {"model": ErrorResponse}},
)
def predict_endpoint(req: PredictRequest):
    try:
        return predict(req.cell_line_id, req.drug_name)
    except UnknownCellLineError as exc:
        return JSONResponse(
            status_code=400,
            content=ErrorResponse(
                code="UNKNOWN_CELL_LINE",
                message=str(exc),
            ).model_dump(),
        )
    except UnknownDrugError as exc:
        return JSONResponse(
            status_code=400,
            content=ErrorResponse(
                code="UNKNOWN_DRUG",
                message=str(exc),
            ).model_dump(),
        )
