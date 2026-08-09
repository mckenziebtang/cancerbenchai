import math

import pytest

from app.model import predict
from explanation_service.tasks import TOP_FEATURES, build_explanation


def test_explanation_contract_and_reconstruction():
    result = build_explanation("SIDM00001", "Cisplatin")
    expected = predict("SIDM00001", "Cisplatin")

    assert result["prediction"] == pytest.approx(expected.prediction, abs=1e-5)
    assert result["model_version"] == "xgb_v1"
    assert result["explainer_version"] == "treeshap_v1"
    assert len(result["features"]) == TOP_FEATURES

    magnitudes = [abs(feature["contribution"]) for feature in result["features"]]
    assert magnitudes == sorted(magnitudes, reverse=True)
    assert all(math.isfinite(feature["contribution"]) for feature in result["features"])

    reconstructed = (
        result["base_value"]
        + sum(feature["contribution"] for feature in result["features"])
        + result["other_contribution"]
    )
    assert reconstructed == pytest.approx(result["prediction"], abs=1e-5)


def test_feature_direction_matches_contribution_sign():
    result = build_explanation("SIDM00001", "Cisplatin")
    for feature in result["features"]:
        expected = "positive" if feature["contribution"] > 0 else "negative" if feature["contribution"] < 0 else "neutral"
        assert feature["direction"] == expected
