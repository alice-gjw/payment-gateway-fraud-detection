"""Written fully by Claude, mainly to see where it fits in the GitHub Actions Workflow"""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_predict_positive():
    response = client.post("/predict", json={"text": "This is wonderful and amazing!"})
    assert response.status_code == 200
    data = response.json()
    assert data["label"] == "POSITIVE"
    assert 0.0 <= data["score"] <= 1.0


def test_predict_negative():
    response = client.post("/predict", json={"text": "This is terrible and awful."})
    assert response.status_code == 200
    data = response.json()
    assert data["label"] == "NEGATIVE"
    assert 0.0 <= data["score"] <= 1.0


def test_predict_missing_text():
    response = client.post("/predict", json={})
    assert response.status_code == 422  # Pydantic validation error


def test_metrics_endpoint():
    # Make a prediction first so there is something to report.
    client.post("/predict", json={"text": "test"})

    response = client.get("/metrics")
    assert response.status_code == 200
    # Prometheus metrics are plain text, check for our custom metric names.
    assert "prediction_requests_total" in response.text
    assert "prediction_request_duration_seconds" in response.text