from fastapi import FastAPI, Response
from src.database import database
from src.router import router as router
from starlette.middleware.cors import CORSMiddleware
from src.config import app_configs, settings
import aioredis
import os

# OpenTelemetry imports for tracing and metrics
from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

# Prometheus imports
from prometheus_client import start_http_server
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.resources import SERVICE_NAME, Resource

import logging

# Initialize Tracer for Jaeger
trace.set_tracer_provider(TracerProvider())
jaeger_exporter = JaegerExporter(
    agent_host_name='localhost',
    agent_port=6831,
)
trace.get_tracer_provider().add_span_processor(
    BatchSpanProcessor(jaeger_exporter)
)

# Initialize MeterProvider for Prometheus
resource = Resource(attributes={
    SERVICE_NAME: "app-metrics"
})
reader = PrometheusMetricReader()
provider = MeterProvider(resource=resource, metric_readers=[reader])
metrics.set_meter_provider(provider)

meter = metrics.get_meter("example_meter")

# Test counter metric
request_counter = meter.create_counter(
    name="requests_counter",
    description="Counts total number of requests",
    unit="1",
)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_origin_regex=settings.CORS_ORIGINS_REGEX,
    allow_credentials=True,
    allow_methods=("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"),
    allow_headers=settings.CORS_HEADERS,
)

FastAPIInstrumentor.instrument_app(app)

start_http_server(port=8006)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.on_event("startup")
async def startup() -> None:
    await database.connect()


@app.get("/")
async def root():
    # Increment the counter
    request_counter.add(1)
    return {"message": "Hello World"}

app.include_router(router, prefix="/api", tags=["API"])