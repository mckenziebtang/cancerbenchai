# app/model.py
from pathlib import Path
import json
import pandas as pd
import xgboost as xgb
from app.schemas import PredictResponse

BASE_DIR = Path(__file__).resolve().parent.parent
ARTIFACT_DIR = BASE_DIR / "model_artifacts"

MODEL_PATH = ARTIFACT_DIR / "xgb_model.json"
METADATA_PATH = ARTIFACT_DIR / "model_metadata.json"
FEATURES_PATH = ARTIFACT_DIR / "cell_line_mutation_features.csv"

with open(METADATA_PATH, "r") as f:
    metadata = json.load(f)

gene_cols = metadata["gene_cols"]
drug_categories = metadata["drug_categories"]

model = xgb.XGBRegressor()
model.load_model(MODEL_PATH)

cell_line_features = pd.read_csv(FEATURES_PATH)

def build_feature_row(cell_line_id: str, drug_name: str) -> pd.DataFrame:
    row = cell_line_features[cell_line_features["model_id"] == cell_line_id].copy()

    if row.empty:
        raise ValueError(f"Unknown cell line: {cell_line_id}")

    row = row[gene_cols].copy()

    if drug_name not in drug_categories:
        raise ValueError(f"Unknown drug: {drug_name}")

    row["DRUG_NAME"] = pd.Categorical([drug_name], categories=drug_categories)

    return row[gene_cols + ["DRUG_NAME"]]

def predict(cell_line_id: str, drug_name: str) -> PredictResponse:
    features = build_feature_row(cell_line_id, drug_name)
    prediction = float(model.predict(features)[0])

    return PredictResponse(
        prediction=prediction,
        cell_line_id=cell_line_id,
        drug_name=drug_name,
        model_version="xgb_v1",
    )