# Real-Time Fraud Detection with Horizontal Pod Autoscaling on AWS EKS

## Problem Statement

In payment gateway fraud detection, every transaction must be scored by an ML model before it is approved or declined. Under normal load, a fixed number of inference pods can handle the volume within the required latency window -- typically under 100 milliseconds. But transaction volume is not constant. It spikes during events like flash sales (e.g. Shopee 9.9 or 11.11 mega sales), holiday shopping, concert ticket drops, or payroll cycles.

When volume exceeds what the current pods can handle, one of two things happens:

- **Fail open:** The payment gateway bypasses the fraud model entirely to keep transactions flowing, approving them unscored. This lets fraudulent transactions through, resulting in chargebacks and financial loss.
- **Fail closed:** The gateway declines or times out transactions it cannot score, blocking legitimate customers and costing the business revenue and user trust.

Horizontal Pod Autoscaling solves this by spinning up additional inference pods as request volume or latency crosses a threshold, and scaling back down when the spike passes. The system maintains its fraud detection SLA without over-provisioning expensive compute during quiet periods.

## Project Overview

Build and deploy a real-time fraud detection inference API on AWS EKS with full CI/CD, observability, autoscaling, and load testing. The goal is to demonstrate production-grade MLOps practices for a latency-sensitive ML service.

## Architecture

```
GitHub (push to main)
  → GitHub Actions CI/CD
    → Build Docker image
    → Push to AWS ECR
    → Deploy to AWS EKS

Traffic flow:
  Locust (load generator)
    → AWS Load Balancer
      → NGINX Ingress Controller
        → Kubernetes Service
          → Fraud Detection Pods (scaled by HPA)

Observability:
  Pods expose Prometheus metrics
    → Prometheus scrapes metrics
      → Grafana dashboards visualize latency, throughput, CPU, HPA events
```

## Components

### 1. ML Model -- Fraud Detection

- **Dataset:** Kaggle Credit Card Fraud Detection dataset (or similar tabular fraud dataset)
- **Model:** XGBoost binary classifier (fraud / not fraud)
- **Why XGBoost:** Small model size, fast inference on CPU (no GPU required), low memory footprint. This keeps container startup fast (important when HPA spins up new pods during a traffic spike) and per-pod resource requirements low.
- **Output:** A trained model artifact saved as a `.joblib` or `.json` file, packaged into the container image.

### 2. Inference API -- FastAPI

- **Framework:** FastAPI
- **Endpoint:** `POST /predict` -- accepts a JSON payload representing a transaction and returns a fraud score or binary decision.
- **Example request payload:**
  ```json
  {
    "amount": 49.99,
    "merchant_category": "electronics",
    "card_country": "SG",
    "transaction_hour": 14,
    "is_online": true
  }
  ```
- **Example response:**
  ```json
  {
    "fraud_score": 0.87,
    "is_fraud": true,
    "latency_ms": 4.2
  }
  ```
- **Prometheus instrumentation:** The API must expose custom Prometheus metrics at `/metrics`:
  - `request_count` (counter) -- total requests, labeled by endpoint and status code
  - `request_latency_seconds` (histogram) -- request duration, labeled by endpoint
  - `model_inference_seconds` (histogram) -- just the model prediction time, separate from total request handling
- **Use `prometheus_fastapi_instrumentator` or manual `prometheus_client` instrumentation.**

### 3. Containerization -- Docker

- **Dockerfile:** Multi-stage or single-stage, based on a slim Python image (e.g. `python:3.11-slim`).
- **Model loading:** The trained model file is copied into the image at build time. The model loads into memory on container startup.
- **Health checks:** Implement `/health` (liveness) and `/ready` (readiness) endpoints. The readiness probe should only return 200 after the model is loaded into memory.

### 4. CI/CD -- GitHub Actions

- **Trigger:** On push to `main` branch.
- **Pipeline steps:**
  1. Run unit tests (if any)
  2. Build Docker image
  3. Tag image with commit SHA
  4. Push image to AWS Elastic Container Registry (ECR)
  5. Update the EKS deployment to use the new image tag (via `kubectl set image` or by updating the manifest and applying it)

### 5. Kubernetes Manifests

All manifests go in a `k8s/` directory. The following resources are required:

#### Deployment (`deployment.yaml`)
- Container image from ECR
- Resource requests and limits (determine these through profiling -- see Capacity Planning section below)
- Liveness probe on `/health`
- Readiness probe on `/ready`
- Environment variables for any configuration (e.g. model path, log level)

#### Service (`service.yaml`)
- ClusterIP service exposing the pod port

#### Ingress (`ingress.yaml`)
- NGINX Ingress Controller (or AWS Load Balancer Controller)
- Routes external traffic to the service

#### HPA (`hpa.yaml`)
- Scale based on average CPU utilization (target: 70% of CPU request)
- Min replicas: 2 (for availability)
- Max replicas: 20 (or whatever the cluster can support)
- Optional: scale on custom Prometheus metric (request latency) using the Prometheus Adapter

### 6. Observability -- Prometheus + Grafana

#### Prometheus
- Deploy via `kube-prometheus-stack` Helm chart or standalone
- Scrape the `/metrics` endpoint from the fraud detection pods
- Also scrape node-level and pod-level metrics (CPU, memory) via kube-state-metrics and node-exporter

#### Grafana Dashboard
Build a dashboard with the following panels:
- **Request throughput** (rps) over time
- **Request latency** (p50, p95, p99) over time
- **CPU utilization** per pod over time
- **Memory utilization** per pod over time
- **Pod count** over time (to visualize HPA scaling events)
- **Model inference time** (p50, p95, p99) separate from total request latency
- **HTTP error rate** (4xx, 5xx) over time

### 7. Load Testing -- Locust

#### Locust test file (`locustfile.py`)
- Define a user class that sends `POST /predict` with realistic transaction payloads
- Vary the payload data (randomize amounts, merchant categories, countries, timestamps) to simulate realistic traffic
- Configure different load profiles:
  - **Baseline test:** Slow ramp from 1 to 50 users over 5 minutes, hold for 5 minutes. Used for capacity planning.
  - **Spike test:** Start at 10 users, jump to 500 users within 30 seconds, hold for 3 minutes, drop back to 10. Simulates a flash sale.
  - **Soak test:** Hold at a moderate steady-state load for 30+ minutes to check for memory leaks or degradation.

## Capacity Planning Procedure

Before configuring HPA thresholds, profile the system:

1. **Profile the container locally.** Run the container with no resource constraints. Use `docker stats` to observe CPU and memory during startup (model loading) and during inference. Note the idle memory after model load and peak CPU per request.

2. **Set initial resource requests and limits based on profiling:**
   - CPU request: steady-state usage under moderate load
   - CPU limit: peak usage + 25-50% buffer
   - Memory request: model loaded + baseline overhead
   - Memory limit: memory request + buffer for request handling

3. **Single-pod capacity test.** Deploy one pod on EKS. Run Locust with a slow ramp (baseline test). Monitor Prometheus/Grafana. Find the inflection point where p95 latency starts exceeding the SLA (100ms). Record the rps at that point -- this is one pod's usable capacity.

4. **Multi-pod linear scaling validation.** Scale to 2 pods manually. Run the same test. Verify you get roughly double the throughput at the same latency. If not, investigate bottlenecks in the network path (ingress controller, load balancer, service mesh).

5. **Set HPA thresholds.** Based on measured single-pod capacity:
   - Target CPU utilization: 70% of CPU request (gives ~30% headroom for scaling lag)
   - Min replicas: 2
   - Max replicas: calculated from expected peak traffic / per-pod capacity, plus buffer

## Project Structure

```
fraud-detection-autoscaling/
├── model/
│   ├── train.py              # Train XGBoost on fraud dataset, save model artifact
│   └── model.joblib           # Trained model artifact
├── app/
│   ├── main.py                # FastAPI application with /predict, /health, /ready, /metrics
│   ├── model.py               # Model loading and inference logic
│   └── requirements.txt       # Python dependencies
├── Dockerfile
├── k8s/
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── ingress.yaml
│   └── hpa.yaml
├── monitoring/
│   ├── prometheus-values.yaml  # Helm values for kube-prometheus-stack
│   └── grafana-dashboard.json  # Exported Grafana dashboard
├── loadtest/
│   └── locustfile.py           # Locust load test definitions
├── .github/
│   └── workflows/
│       └── deploy.yaml         # GitHub Actions CI/CD pipeline
└── README.md
```

## Key Metrics to Demonstrate

After running the spike test with Locust, the Grafana dashboard should show:

1. Transaction volume (rps) spiking sharply
2. HPA responding by increasing pod count
3. Latency briefly rising during the scaling lag, then stabilizing as new pods come online
4. CPU utilization per pod dropping as load is distributed across more pods
5. No increase in error rate (no transactions dropped or timed out)
6. Pod count scaling back down after the spike subsides

This demonstrates that the system maintains its fraud detection SLA under realistic production traffic patterns without manual intervention.