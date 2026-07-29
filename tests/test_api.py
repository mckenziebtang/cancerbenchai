from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_predict_success_endpoint():
    res = client.post(
        "/predict",
        json= {
            "cell_line_id": "A549",
            "drug_name": "cisplatin"
        }
    )

    assert res.status_code == 200
    data = res.json() 
    assert "prediction" in data
    assert "model_version" in data
    assert data["drug_name"] == "cisplatin"


def test_predict_endpoint_missing_field():
    res = client.post(
        "/predict",
        json={
            "cell_line_id" : "A549"
        }
    )
    assert res.status_code == 422