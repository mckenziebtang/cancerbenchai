import pandas as pd
import pytest
from app import model as app_model 

#make a small dumb model to test
class DummyXGBModel: 
    def predict(self, X):
        return [0.37]
    
@pytest.fixture 
def fake_model(monkeypatch):
    monkeypatch.setattr(app_model, "model", DummyXGBModel())

@pytest.fixture 
def fake_artifacts(monkeypatch):
    monkeypatch.setattr(app_model, "gene_cols", ["GENE1", "GENE2"])
    monkeypatch.setattr(app_model, "drug_categories", ["cisplatin", "paclitaxel"])

    df = pd.DataFrame(
        {
            "model_id": ["A549", "MCF7"],
            "GENE1": [1.0, 2.0],
            "GENE2": [3.0, 4.0]
        }
    )
    monkeypatch.setattr(app_model, "cell_line_features", df)

def test_build_feature_row_unknown_cell_line(fake_artifacts):
    with pytest.raises(ValueError, match="Unknown cell line"):
        app_model.build_feature_row("BAD_ID", "cisplatin")


def test_build_feature_row_unknown_drug(fake_artifacts):
    with pytest.raises(ValueError, match="Unknown drug"):
        app_model.build_feature_row("A549", "BAD_DRUG")


def test_predict_valid(fake_artifacts, fake_model):
    result = app_model.predict("A549", "cisplatin")

    assert result.prediction == 0.37
    assert result.cell_line_id == "A549"
    assert result.drug_name == "cisplatin"
    assert result.model_version == "xgb_v1"


def test_predict_unknown_cell_line(fake_artifacts, fake_model):
    with pytest.raises(ValueError, match="Unknown cell line"):
        app_model.predict("BAD_ID", "cisplatin")


def test_predict_unknown_drug(fake_artifacts, fake_model):
    with pytest.raises(ValueError, match="Unknown drug"):
        app_model.predict("A549", "BAD_DRUG")