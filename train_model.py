import xgboost as xgb
from sklearn.model_selection import train_test_split, GroupShuffleSplit
from sklearn.metrics import accuracy_score, root_mean_squared_error
import pandas as pd 
from scipy.stats import pearsonr
import json #save model as json 
from pathlib import Path 

gdsc = pd.read_excel("gdsc2_ic50.xlsx")
mut = pd.read_csv("mutations_summary.csv")

mut = mut[mut["cancer_driver"] == "t"]

#find the top 50 most mutated genes
gene_counts =(
    mut.drop_duplicates(["model_id","gene_symbol"]).groupby("gene_symbol")["model_id"].nunique().sort_values(ascending=False)
)
top_fifty = 50
top_genes = gene_counts.head(top_fifty).index

#make a feature matrix so its easier to see which features go with what cellline
mut_top = mut[mut["gene_symbol"].isin(top_genes)].copy()
mut_top["mut"] = 1
X = mut_top.pivot_table (
    index = "model_id",
    columns = "gene_symbol", 
    values = "mut",
    aggfunc = "max", #tracks highest extremes
    fill_value = 0
).reset_index()

#join everything 
data = gdsc.merge(X, left_on="SANGER_MODEL_ID", right_on= "model_id", how="inner")

data["DRUG_NAME"] = data["DRUG_NAME"].astype("category")

y = data["LN_IC50"]
X_model = data.drop(columns=["LN_IC50", "SANGER_MODEL_ID", "model_id"])

gene_cols = [c for c in top_genes if c in X_model.columns]
X_model = X_model[gene_cols + ["DRUG_NAME"]]

#split into training anf test -- make sure no 2 drugs show up in the same place 
groups = data["SANGER_MODEL_ID"]
splitting = GroupShuffleSplit(test_size=0.2,random_state=42)
train_index, test_index = next(splitting.split(X_model, y, groups = groups))

X_train, X_test = X_model.iloc[train_index], X_model.iloc[test_index]
y_train, y_test = y.iloc[train_index], y.iloc[test_index]


model = xgb.XGBRegressor(
    n_estimators = 200,
    max_depth = 4,
    learning_rate = 0.1,
    subsample = 0.8,
    colsample_bytree = 0.8,
    random_state = 42,
    enable_categorical = True
)

model.fit(X_train, y_train)

#results of the modle

pred = model.predict(X_test)
rmse = root_mean_squared_error(y_test, pred)
corr, _ = pearsonr(y_test, pred)
print("RMSE:", rmse)
print("Pearson r:", corr)
print("Train rows:", len(X_train), "| Test rows:", len(X_test))
print("Train cell line:", groups.iloc[train_index].nunique(), "| Test cell lines:", groups.iloc[test_index].nunique())
ARTIFACT_DIR = Path("model_artifacts")
ARTIFACT_DIR.mkdir(exist_ok = True)
#save the model
model.save_model(ARTIFACT_DIR/"xgb_model.json")
metadata = {
    "gene_cols": gene_cols,
    "drug_categories": list(data["DRUG_NAME"].cat.categories)
}
with open(ARTIFACT_DIR/"model_metadata.json","w") as f:
    json.dump(metadata,f)

#save table
X.to_csv(ARTIFACT_DIR/"cell_line_mutation_features.csv", index=False)
print(f"Saved artifacts to {ARTIFACT_DIR.resolve()}")