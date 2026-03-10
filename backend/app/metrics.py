from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

REQUEST_COUNT = Counter(
    "request_count",
    "Total requests by endpoint and status code",
    ["endpoint", "status"],
)

REQUEST_LATENCY = Histogram(
    "request_latency_seconds", 
    "Total request duration in seconds",
    ["endpoint"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.2, 0.5, 1.0],
)

MODEL_INFERENCE = Histogram(
    "model_inference_seconds",
    "XGBoost predict_proba duration in seconds", 
    buckets=[0.001, 0.05, 0.01, 0.025, 0.05, 0.1],
)

def get_metrics() -> tuple[str, str]:
    return generate_latest().decode("utf-8"), CONTENT_TYPE_LATEST