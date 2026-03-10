"""Prometheus metrics setup"""

from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

REQUEST_COUNT = Counter(
    "prediction_requests_total",
    "Total number of prediction requests",
    ["status", "label"],
)

REQUEST_LATENCY = Histogram(
    "prediction_request_duration_seconds",
    "Time spent processing prediction request",
    buckets=[0.01, 0.025, 0.05, 0.075, 0.1, 0.2, 0.3, 0.5, 0.75, 1.0, 2.5],
)

def get_metrics() -> tuple[str, str]:
    """
    Generate Prometheus-formatted metrics string. 
    Returns (metrics_text, content_type) for use in the /metrics endpoint. 
    
    