import xgboost as xgb

from app.model import build_feature_row, model


def build_explanation(cell_line_id: str, drug_name: str) -> dict:
    """Calculate per-feature XGBoost contributions for one prediction."""
    features = build_feature_row(cell_line_id, drug_name)
    matrix = xgb.DMatrix(features, enable_categorical=True)
    contributions = model.get_booster().predict(matrix, pred_contribs=True)[0]

    feature_values = {
        name: float(value)
        for name, value in zip(features.columns, contributions[:-1])
    }

    return {
        "cell_line_id": cell_line_id,
        "drug_name": drug_name,
        "prediction": float(contributions.sum()),
        "base_value": float(contributions[-1]),
        "feature_contributions": feature_values,
    }
