# Real-Time Sentiment Analysis API with Auto-Scaling on EKS

## Project Overview

Build and deploy a real-time sentiment analysis API on AWS EKS with full CI/CD automation, autoscaling, observability, and load testing. The focus is on deployment infrastructure and operations, not model training. The model is a pre-trained Hugging Face classifier used as-is.

The end goal is to have a live API endpoint that accepts text, returns a sentiment classification, scales automatically under load, and can be stress-tested with Locust while observing autoscaling behavior in real time on Grafana dashboards.

## Model

- **Model:** `distilbert-base-uncased-finetuned-sst-2-english` from Hugging Face
- **Task:** Sentiment classification (positive/negative)
- **No training required.** Load directly using `transformers.pipeline("sentiment-analysis", model="distilbert-base-uncased-finetuned-sst-2-english")`
- Runs on CPU, ~260MB, fast startup

## Tech Stack

| Component | Tool |
|---|---|
| Model serving | FastAPI |
| Containerization | Docker |
| Container registry | AWS ECR |
| Orchestration | AWS EKS (Kubernetes) |
| CI/CD | GitHub Actions |
| Autoscaling | Kubernetes HPA (CPU first, then custom metrics) |
| Metrics collection | Prometheus |
| Metrics visualization | Grafana |
| Custom metrics bridge | Prometheus Adapter (Phase 2) |
| Load testing | Locust |
| Deployment strategy | Rolling update (Phase 1), Argo Rollouts canary (Phase 2) |

## Project Phases

### Phase 1: Core Deployment Pipeline

#### Step 1: FastAPI Serving Application

- Create a FastAPI app with a POST endpoint (`/predict`) that accepts a JSON body with a `text` field and returns the sentiment label and confidence score.
- Add a GET `/health` endpoint for Kubernetes readiness and liveness probes.
- Add a GET `/metrics` endpoint using the `prometheus_client` library to expose request count, request latency histogram, and prediction label distribution as Prometheus metrics.
- Test locally to confirm the model loads and serves predictions correctly.

#### Step 2: Dockerize the Application

- Write a Dockerfile that installs dependencies, downloads/caches the model at build time (so the model is baked into the image, not downloaded at pod startup), and runs the FastAPI app with uvicorn.
- Build and test the container locally. Confirm the `/predict`, `/health`, and `/metrics` endpoints work.
- Optimize the image size where reasonable (use a slim base image, minimize layers).

#### Step 3: Push to AWS ECR

- Create an ECR repository for the project.
- Tag and push the Docker image to ECR.
- Confirm the image is accessible from ECR.

#### Step 4: Deploy to EKS

Write the following Kubernetes manifests:

- **Deployment (`deployment.yaml`):** Defines the pod spec referencing the ECR image. Set resource requests and limits for CPU and memory. Configure readiness and liveness probes pointing at the `/health` endpoint. Start with 2 replicas.
- **Service (`service.yaml`):** ClusterIP service that exposes the deployment internally on port 80, targeting the container port.
- **Ingress (`ingress.yaml`):** Use the AWS Load Balancer Controller to provision an ALB. Configure the ingress to route external traffic to the service. This gives you a public URL.
- **HPA (`hpa.yaml`):** Configure Horizontal Pod Autoscaler targeting CPU utilization (e.g., 50% average). Set min replicas to 2 and max replicas to 10.

Deploy all manifests to the EKS cluster. Verify:
- Pods are running and healthy.
- The service is reachable internally.
- The ingress provisions an ALB and the API is reachable externally.
- Sending a request to the public URL returns a sentiment prediction.

#### Step 5: CI/CD with GitHub Actions

Create a GitHub Actions workflow (`.github/workflows/deploy.yml`) that triggers on push to `main` and does the following:

1. Checks out the code.
2. Logs into AWS ECR.
3. Builds the Docker image and tags it with the Git SHA.
4. Pushes the image to ECR.
5. Updates the Kubernetes deployment to use the new image tag (using `kubectl set image` or by applying an updated manifest).
6. Waits for the rollout to complete (`kubectl rollout status`).

After this step, every push to `main` automatically builds and deploys a new version.

#### Step 6: Observability with Prometheus and Grafana

- Deploy Prometheus on the EKS cluster (use the `kube-prometheus-stack` Helm chart, which includes Prometheus, Grafana, and default Kubernetes dashboards).
- Configure Prometheus to scrape the `/metrics` endpoint on the FastAPI pods (via a ServiceMonitor or pod annotations).
- Create a Grafana dashboard with the following panels:
  - Request rate (requests per second)
  - Request latency (p50, p95, p99)
  - Error rate (HTTP 5xx responses)
  - CPU and memory utilization per pod
  - Active pod count over time
  - HPA desired vs. current replicas

#### Step 7: Load Testing with Locust

- Write a Locust test file (`locustfile.py`) that defines a user behavior: send POST requests to `/predict` with randomized text inputs.
- Configure a ramp-up profile: start with 10 users, ramp to 500+ users over several minutes, hold steady, then spike to 1000+.
- Run Locust against the public ALB endpoint.
- Observe on the Grafana dashboard: latency increasing, CPU spiking, HPA scaling up pod count, latency stabilizing as new pods come online, and pods scaling back down when load drops.
- Tune HPA thresholds and scaling parameters based on what you observe.

### Phase 2: Advanced Features

#### Step 8: HPA with Custom Metrics (Prometheus Adapter)

- Deploy the Prometheus Adapter on the cluster.
- Configure it to expose the request latency metric (from your FastAPI `/metrics` endpoint) as a custom metric that the HPA can read.
- Update the HPA to scale on request latency (e.g., scale up when p95 latency exceeds 200ms) instead of or in addition to CPU.
- Re-run Locust and compare the autoscaling behavior to CPU-based scaling. Custom metrics typically react more precisely to actual user-facing degradation.

#### Step 9: Canary Deployments with Argo Rollouts

- Install Argo Rollouts on the cluster.
- Convert the Deployment manifest to an Argo Rollout resource.
- Define a canary strategy: e.g., send 10% of traffic to the new version, wait 2 minutes, check Prometheus metrics (error rate, latency), if healthy promote to 50%, wait again, then promote to 100%. If metrics degrade, automatically roll back.
- Make a code change (e.g., update the API response format or swap to a different model), push to `main`, and watch the canary rollout proceed on the Argo Rollouts dashboard.
- Optionally, deliberately deploy a broken version to verify that automatic rollback works.

## Project Goals

1. **Hands-on EKS deployment experience:** Go from a container to a live, publicly reachable API endpoint on Kubernetes.
2. **CI/CD automation:** Every code change automatically builds, pushes, and deploys without manual intervention.
3. **Observable autoscaling:** See HPA react to real load in real time on Grafana. Understand the relationship between load, latency, pod count, and scaling parameters.
4. **Load testing proficiency:** Use Locust to simulate realistic traffic patterns and identify scaling bottlenecks.
5. **Custom metrics scaling:** Move beyond basic CPU scaling to application-level metrics that reflect actual user experience.
6. **Canary deployment safety:** Practice controlled rollouts that catch bad deployments before they affect all users.

## Directory Structure (Suggested)

```
sentiment-api/
├── app/
│   ├── main.py              # FastAPI application
│   ├── model.py             # Model loading and inference
│   └── metrics.py           # Prometheus metrics setup
├── tests/
│   └── test_api.py          # API tests
├── k8s/
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── ingress.yaml
│   ├── hpa.yaml
│   └── rollout.yaml         # Phase 2: Argo Rollout manifest
├── monitoring/
│   ├── servicemonitor.yaml  # Prometheus scrape config
│   └── grafana-dashboard.json
├── loadtest/
│   └── locustfile.py
├── Dockerfile
├── requirements.txt
├── .github/
│   └── workflows/
│       └── deploy.yml
└── README.md
```

## Key Metrics to Track During Load Testing

- **Request throughput:** requests/second hitting the API
- **Latency percentiles:** p50, p95, p99 response times
- **Error rate:** percentage of 5xx responses
- **Pod count:** current vs. desired replicas over time
- **HPA scaling events:** when and why the autoscaler triggered
- **CPU/memory per pod:** resource utilization driving scaling decisions
- **Pod startup time:** how long from HPA decision to pod ready (affects how fast scaling relieves load)