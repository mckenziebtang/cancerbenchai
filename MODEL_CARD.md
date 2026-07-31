# CancerBench XGBoost Model Card

## Summary

CancerBench uses an XGBoost regression model to predict `LN_IC50` for a
cell-line and drug combination. It is a portfolio and research demonstration,
not a clinically validated model.

## Intended use

- Demonstrate a reproducible machine-learning inference service.
- Support research-oriented exploration of drug-response predictions.
- Serve as the prediction component in the CancerBench explanation and
  literature-grounding workflow.

The model must not be used to select treatment, diagnose disease, estimate an
individual patient's outcome, or replace review by qualified researchers and
clinicians.

## Data and features

- Drug-response source: GDSC2 data provided in `gdsc2_ic50.xlsx`.
- Mutation source: `mutations_summary.csv`.
- Target: `LN_IC50`, the natural logarithm of the half-maximal inhibitory
  concentration reported by the dataset.
- Cell-line features: binary mutation indicators for the 50 cancer-driver genes
  observed in the greatest number of cell lines.
- Drug feature: one categorical `DRUG_NAME` feature.
- Total joined observations: 226,607.
- Total represented cell lines: 908.

Lower `LN_IC50` values indicate greater drug sensitivity within this dataset.
The score is not a probability, diagnosis, or treatment recommendation.

## Training and evaluation

The data is divided with `GroupShuffleSplit(test_size=0.2, random_state=42)`,
grouped by cell-line ID. This prevents the same cell line from appearing in both
training and test sets.

| Measure | Value |
| --- | ---: |
| Training observations | 181,366 |
| Test observations | 45,241 |
| Training cell lines | 726 |
| Test cell lines | 182 |
| Test RMSE | 1.468506 |
| Test Pearson correlation | 0.849208 |

These values were calculated against the checked-in `xgb_model.json` using the
same feature-building and held-out split defined in `train_model.py`. They are
internal held-out results, not external validation.

## Model configuration

- Estimators: 200
- Maximum tree depth: 4
- Learning rate: 0.1
- Row subsampling: 0.8
- Column subsampling per tree: 0.8
- Random seed: 42
- Native categorical features enabled
- Current service model version: `xgb_v1`

## Limitations

- The model uses cell-line experiments, not patient data.
- Only the selected mutation indicators and drug identity are represented.
- Gene expression, copy-number variation, tissue context, dosage protocol, and
  other potentially important factors are omitted.
- Performance may vary substantially across drugs and biological subgroups.
- A strong overall correlation does not establish calibration or reliability
  for a specific drug/cell-line pair.
- Dataset biases, experimental noise, and missing measurements propagate into
  the model.
- The current evaluation does not measure external generalization, subgroup
performance, uncertainty, or clinical utility.

## Versioning

Prediction responses include `model_version`. Any retraining that changes model
weights, features, preprocessing, or drug categories should create a new model
version and update the saved metadata. Future explanation caches must include
this version in their cache keys.
