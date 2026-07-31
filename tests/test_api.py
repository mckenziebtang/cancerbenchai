from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_predict_success_endpoint():
    res = client.post(
        "/predict",
        json={
            "cell_line_id": "SIDM00001",
            "drug_name": "Cisplatin"
        }
    )

    assert res.status_code == 200
    data = res.json()
    assert "prediction" in data
    assert "model_version" in data
    assert data["cell_line_id"] == "SIDM00001"
    assert data["drug_name"] == "Cisplatin"
    assert set(data) == {
        "prediction",
        "cell_line_id",
        "drug_name",
        "model_version",
    }
    assert isinstance(data["prediction"], float)
    assert data["model_version"] == "xgb_v1"


def test_predict_endpoint_missing_field():
    res = client.post(
        "/predict",
        json={
            "cell_line_id": "SIDM00001"
        }
    )
    assert res.status_code == 422

def test_predict_endpoint_unknown_cell_line():
    res = client.post(
        "/predict",
        json={
            "cell_line_id": "NOT_A_REAL_CELL_LINE",
            "drug_name": "Cisplatin",
        },
    )

    assert res.status_code == 400
    assert res.json()["code"] == "UNKNOWN_CELL_LINE"
    assert "Unknown cell line" in res.json()["message"]

def test_predict_endpoint_unknown_drug():
    res = client.post(
        "/predict",
        json={
            "cell_line_id": "SIDM00001",
            "drug_name": "NotARealDrug",
        },
    )

    assert res.status_code == 400
    assert res.json()["code"] == "UNKNOWN_DRUG"
    assert "Unknown drug" in res.json()["message"]

def test_predict_endpoint_empty_body():
    res = client.post("/predict", json={})

    assert res.status_code == 422

    errors = res.json()["detail"]
    missing_fields = {error["loc"][-1] for error in errors}

    assert missing_fields == {"cell_line_id", "drug_name"}


def test_predict_endpoint_rejects_blank_identifier():
    res = client.post(
        "/predict",
        json={
            "cell_line_id": "   ",
            "drug_name": "Cisplatin",
        },
    )

    assert res.status_code == 422


def test_predict_endpoint_rejects_extra_fields():
    res = client.post(
        "/predict",
        json={
            "cell_line_id": "SIDM00001",
            "drug_name": "Cisplatin",
            "clinical_recommendation": True,
        },
    )

    assert res.status_code == 422


def test_metadata_endpoint_describes_model():
    res = client.get("/metadata")

    assert res.status_code == 200
    data = res.json()
    assert data["model_version"] == "xgb_v1"
    assert data["target"] == "LN_IC50"
    assert data["feature_count"] == 51
    assert data["cell_line_count"] > 0
    assert data["drug_count"] > 0
    assert "Research" in data["intended_use"]


def test_cell_lines_endpoint_returns_supported_ids():
    res = client.get("/cell-lines")

    assert res.status_code == 200
    data = res.json()
    assert data["count"] == len(data["cell_line_ids"])
    assert "SIDM00001" in data["cell_line_ids"]


def test_drugs_endpoint_returns_supported_names():
    res = client.get("/drugs")

    assert res.status_code == 200
    data = res.json()
    assert data["count"] == len(data["drug_names"])
    assert "Cisplatin" in data["drug_names"]
