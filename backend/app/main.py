"""HTTP layer"""

import time 
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from app.model import load_model, is_ready, predict
from app.metrics import REQUEST_COUNT, REQUEST_LATENCY, MODEL_INFERENCE, get_metrics

class TransactionRequest(BaseModel):
    features: list[float] # [Time, V1-V28, Amount] - 30 values
    
class PredictionResponse(BaseModel):
    fraud_score: float
    is_fraud: bool
    
@asynccontextmanager
async def lifespan(app: FastAPI):
    load_model()
    yield
    
app = FastAPI(title="Fraud Detection API", lifespan=lifespan)

@app.post("/predict", response_model=PredictionResponse)
async def predict_endpoint(req: TransactionRequest):
    start = time.perf_counter()
    
    with MODEL_INFERENCE.time():
        result = predict(req.features)
    
    latency = time.perf_counter() - start
    
    REQUEST_LATENCY.observe(latency)
    REQUEST_COUNT.labels(status="200", endpoint="/predict").inc()
    
    return PredictionResponse(
        fraud_score=result["fraud_score"],
        is_fraud=result["is_fraud"],
    )
    
app.get("/health")
async def health():
    return {"status": "healthy"}

@app.get("/ready")
async def ready():
    if not is_ready():
        return PlainTextResponse("model not loaded", status_code=503)
    return {"status": "ready"}

@app.get("/metrics")
async def metrics():
    body, content_type = get)metrics()
    return PlainTextResponse(body, media_type=content_type)