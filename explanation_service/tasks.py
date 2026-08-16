import json
import math

import xgboost as xgb

from app.model import MODEL_VERSION, build_feature_row, model
from explanation_service.queue import redis_connection


EXPLAINER_VERSION = "treeshap_v1"
TOP_FEATURES = 10
CACHE_TTL_SECONDS = 3600
JOB_TIMEOUT_SECONDS = 300
JOB_MAX_RETRIES = 2
JOB_RETRY_INTERVALS = (5, 15)
# Cover the initial attempt, both retries, their delays, and worker overhead.
INFLIGHT_TTL_SECONDS = 1200


def build_explanation(cell_line_id: str, drug_name: str) -> dict:
    """Calculate a finite, ranked TreeSHAP explanation."""
    feature_row = build_feature_row(cell_line_id, drug_name)
    matrix = xgb.DMatrix(feature_row, enable_categorical=True)
    contributions = model.get_booster().predict(matrix, pred_contribs=True)[0]
    prediction = float(contributions.sum())
    base_value = float(contributions[-1])

    if not all(math.isfinite(float(number)) for number in contributions):
        raise ValueError("The model produced a non-finite explanation")

    ranked = []
    for name, contribution in zip(feature_row.columns, contributions[:-1]):
        raw_value = feature_row.iloc[0][name]
        value = str(raw_value) if name == "DRUG_NAME" else float(raw_value)
        amount = float(contribution)
        direction = "positive" if amount > 0 else "negative" if amount < 0 else "neutral"
        ranked.append(
            {"name": name, "value": value, "contribution": amount, "direction": direction}
        )

    ranked.sort(key=lambda feature: abs(feature["contribution"]), reverse=True)
    top_features = ranked[:TOP_FEATURES]
    other_contribution = sum(item["contribution"] for item in ranked[TOP_FEATURES:])
    reconstructed = base_value + sum(item["contribution"] for item in top_features) + other_contribution
    if not math.isclose(reconstructed, prediction, abs_tol=1e-5):
        raise ValueError("Feature contributions do not reconstruct the prediction")

    return {
        "cell_line_id": cell_line_id,
        "drug_name": drug_name,
        "prediction": prediction,
        "base_value": base_value,
        "features": top_features,
        "other_contribution": other_contribution,
        "model_version": MODEL_VERSION,
        "explainer_version": EXPLAINER_VERSION,
        "cache_hit": False,
    }


def run_explanation(
    cell_line_id: str,
    drug_name: str,
    cache_key: str,
    inflight_key: str,
    job_id: str,
) -> dict:
    """Worker entry point: calculate, cache, and release the duplicate lock."""
    result = build_explanation(cell_line_id, drug_name)
    pipeline = redis_connection.pipeline()
    pipeline.set(cache_key, json.dumps(result), ex=CACHE_TTL_SECONDS)
    pipeline.set(
        f"explanation:job:{job_id}",
        json.dumps({"cache_key": cache_key, "cache_hit": False}),
        ex=CACHE_TTL_SECONDS,
    )
    pipeline.delete(inflight_key)
    pipeline.execute()
    return result
