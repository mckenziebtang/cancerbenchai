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
    assert "Unknown cell line" in res.json()["detail"]

def test_predict_endpoint_unknown_drug():
    res = client.post(
        "/predict",
        json={
            "cell_line_id": "SIDM00001",
            "drug_name": "NotARealDrug",
        },
    )

    assert res.status_code == 400
    assert "Unknown drug" in res.json()["detail"]

def test_predict_endpoint_empty_body():
    res = client.post("/predict", json={})

    assert res.status_code == 422

    errors = res.json()["detail"]
    missing_fields = {error["loc"][-1] for error in errors}

    assert missing_fields == {"cell_line_id", "drug_name"}