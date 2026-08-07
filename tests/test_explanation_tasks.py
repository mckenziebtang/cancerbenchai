import pytest

from app.model import predict
from explanation_service.tasks import build_explanation


def test_build_explanation_matches_prediction():
    result = build_explanation("SIDM00001", "Cisplatin")
    expected = predict("SIDM00001", "Cisplatin")

    assert result["cell_line_id"] == "SIDM00001"
    assert result["drug_name"] == "Cisplatin"
    assert result["prediction"] == pytest.approx(expected.prediction, abs=1e-5)
    assert "DRUG_NAME" in result["feature_contributions"]
    assert len(result["feature_contributions"]) == 51
