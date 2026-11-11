"""API simples que simula processamento de métricas e expõe dados no formato Prometheus."""

import asyncio
import random
import time

from fastapi import FastAPI, HTTPException, Request, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

app = FastAPI(title="Metrics Simulator", version="1.0.0")

# --- Métricas HTTP genéricas -------------------------------------------------
HTTP_REQUESTS = Counter(
    "http_requests_total",
    "Total de requisições HTTP",
    ["method", "path", "status"],
)
HTTP_LATENCY = Histogram(
    "http_request_duration_seconds",
    "Latência das requisições HTTP",
    ["method", "path"],
)
IN_PROGRESS = Gauge("http_requests_in_progress", "Requisições HTTP em andamento")

# --- Métricas de negócio (simuladas) ----------------------------------------
JOBS_PROCESSED = Counter(
    "jobs_processed_total", "Jobs processados", ["job_type", "result"]
)
JOB_DURATION = Histogram(
    "job_processing_seconds",
    "Tempo de processamento dos jobs",
    ["job_type"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.0),
)
QUEUE_SIZE = Gauge("job_queue_size", "Tamanho atual (simulado) da fila de jobs")

JOB_TYPES = {"report", "billing", "email"}


@app.middleware("http")
async def prometheus_middleware(request: Request, call_next):
    # Não instrumenta o próprio endpoint de métricas
    if request.url.path == "/metrics":
        return await call_next(request)

    IN_PROGRESS.inc()
    start = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        # Usa o template da rota (ex: /process/{job_type}) para evitar alta cardinalidade
        route = request.scope.get("route")
        path = getattr(route, "path", "unmatched")
        HTTP_LATENCY.labels(request.method, path).observe(time.perf_counter() - start)
        HTTP_REQUESTS.labels(request.method, path, str(status)).inc()
        IN_PROGRESS.dec()


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/process/{job_type}")
async def process(job_type: str):
    """Simula o processamento de um job com latência e falhas aleatórias."""
    if job_type not in JOB_TYPES:
        raise HTTPException(status_code=404, detail=f"job_type inválido: {sorted(JOB_TYPES)}")

    QUEUE_SIZE.set(random.randint(0, 100))
    duration = random.uniform(0.02, 1.0)

    with JOB_DURATION.labels(job_type).time():
        await asyncio.sleep(duration)

    if random.random() < 0.1:  # 10% de falha simulada
        JOBS_PROCESSED.labels(job_type, "error").inc()
        raise HTTPException(status_code=500, detail="Falha simulada no processamento")

    JOBS_PROCESSED.labels(job_type, "success").inc()
    return {"job_type": job_type, "status": "done", "duration_s": round(duration, 3)}


@app.get("/metrics")
async def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
