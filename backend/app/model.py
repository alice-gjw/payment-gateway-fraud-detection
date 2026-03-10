"""Model serving layer: Loads model, checks readiness, runs inference""" 

import joblib
import numpy as np
import xgboost as xgb

MODEL_PATH = "model/model.joblib"

_model: xgb.XGBClassifier | None = None


def load_model():
    global _model
    _model = joblib.load(MODEL_PATH)


def is_ready() -> bool:
    return _model is not None


def predict(features: list[float]) -> dict:
    X = np.array(features).reshape(1, -1)
    fraud_score = float(_model.predict_proba(X)[0][1])
    return {
        "fraud_score": round(fraud_score, 4),
        "is_fraud": fraud_score >= 0.5,
    }
