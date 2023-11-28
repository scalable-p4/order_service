from fastapi import FastAPI
from src.database import database
from src.router import router as router
from starlette.middleware.cors import CORSMiddleware
from src.config import app_configs, settings
import aioredis
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.exporter.prometheus import PrometheusMetricsExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleExportSpanProcessor

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_origin_regex=settings.CORS_ORIGINS_REGEX,
    allow_credentials=True,
    allow_methods=("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"),
    allow_headers=settings.CORS_HEADERS,
)

@app.on_event("startup")
async def startup() -> None:
    trace.set_tracer_provider(TracerProvider(resource=Resource.create().add_service("app")))
    FastAPIInstrumentor().instrument()

    exporter = PrometheusMetricsExporter(endpoint="http://prometheus:9090/metrics")
    trace.get_tracer_provider().add_span_processor(SimpleExportSpanProcessor(exporter))
    await database.connect()


@app.get("/")
async def root():
    return {"message": "Hello World"}

app.include_router(router, prefix="/api", tags=["API"])