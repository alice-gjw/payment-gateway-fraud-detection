import pandas as pd
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
import joblib

DATA_PATH = "data/creditcard.csv"
MODEL_OUTPUT_PATH = "data/model.joblib"

df = pd.read_csv(DATA_PATH)

X = df.drop(columns=["Class"])
y = df["Class"]

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, stratify=y, random_state=42
)

model = xgb.XGBClassifier(
    n_estimators=100,
    max_depth=6,
    scale_pos_weight=len(y_train[y_train == 0]) / len(y_train[y_train == 1]),
    eval_metric="aucpr",
    random_state=42,
)

model.fit(X_train, y_train)

y_pred = model.predict(X_test)
print(classification_report(y_test, y_pred))

joblib.dump(model, MODEL_OUTPUT_PATH)
print(f"Model saved to {MODEL_OUTPUT_PATH}")
