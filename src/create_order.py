import subprocess
import os
import sys
import time
from dotenv import load_dotenv
from celery import Celery
from celery.result import AsyncResult
from sqlalchemy import insert, select
from sqlalchemy import create_engine, insert
from sqlalchemy.orm import sessionmaker
from src.database import user_order
import json

# OpenTelemetry imports for tracing and metrics
from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.instrumentation.celery import CeleryInstrumentor

# Logging imports
from opentelemetry._logs import set_logger_provider
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
import logging
service_name = "order_worker"

# Initialize TracerProvider for OTLP
resource = Resource(attributes={SERVICE_NAME: service_name})
trace_provider = TracerProvider(resource=resource)
otlp_trace_exporter = OTLPSpanExporter(endpoint="otel-collector:4317", insecure=True)
trace_provider.add_span_processor(BatchSpanProcessor(otlp_trace_exporter))
trace.set_tracer_provider(trace_provider)

# Initialize MeterProvider for OTLP
metric_reader = PeriodicExportingMetricReader(OTLPMetricExporter(endpoint="otel-collector:4317", insecure=True))
metric_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
metrics.set_meter_provider(metric_provider)

# Initialize LoggerProvider for OTLP
logger_provider = LoggerProvider(resource=resource)
set_logger_provider(logger_provider)
otlp_log_exporter = OTLPLogExporter(endpoint="otel-collector:4317", insecure=True)
logger_provider.add_log_record_processor(BatchLogRecordProcessor(otlp_log_exporter))
handler = LoggingHandler(level=logging.DEBUG, logger_provider=logger_provider)

# Attach OTLP handler to root logger
logging.getLogger().addHandler(handler)

tracer = trace.get_tracer(__name__)
meter = metrics.get_meter(__name__)
logger = logging.getLogger(__name__)
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)

BROKER_URL = os.getenv("CELERY_BROKER_URL")
RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND")
celery_app = Celery('create_order', broker=BROKER_URL,
                    backend=RESULT_BACKEND)
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)

CeleryInstrumentor().instrument()

# Metrics
order_counter = meter.create_counter(
    "orders_created",
    description="Number of orders created",
    unit="1",
)
payment_results_counter = meter.create_counter(
    "payment_results_waited",
    description="Counts how many times payment results were waited for",
    unit="1",
)

order_commit_counter = meter.create_counter(
    "orders_committed",
    description="Counts how many orders were committed",
    unit="1",
)

order_rollback_counter = meter.create_counter(
    "orders_rollback",
    description="Counts how many orders were rolled back",
    unit="1",
)

@celery_app.task(name="create_order")
def create_order(payload: dict, fn: str):
    with tracer.start_as_current_span("create_order_task"):
        logger.info("Creating order", extra={"payload": payload, "function": fn})
        order_counter.add(1)

        username = payload.get("username")
        quantity = payload.get("quantity")
        delivery = payload.get("delivery")

        logger.info(f"Order details: username={username}, quantity={quantity}, delivery={delivery}")

        if fn == "order":
            logger.info("Creating order in database", extra={"username": username, "quantity": quantity, "delivery": delivery})
            commit_create_order(username, quantity, delivery)
            logger.info("Order committed", extra={"username": username, "quantity": quantity, "delivery": delivery})

            payment_task = celery_app.send_task("create_payment", queue='q02', args=[payload, "pay"])
            return waiting_payment_result(payment_task.id)

        elif fn == "rollback_order":
            logger.warning("Rolling back order", extra={"username": username, "quantity": quantity, "delivery": delivery})
            rollback_order(username, quantity, delivery)
            logger.info("Order rolled back", extra={"username": username, "quantity": quantity, "delivery": delivery})
            return "failed_token_transaction"

        elif fn == "success_token_transaction":
            logger.info("Token transaction successful", extra={"username": username, "quantity": quantity, "delivery": delivery})
            return "success_token_transaction"

        else:
            logger.error("Invalid function called", extra={"function": fn, "username": username, "quantity": quantity, "delivery": delivery})
            return "failed_token_transaction"


@celery_app.task
def waiting_payment_result(payment_task_id):
    with tracer.start_as_current_span("waiting_payment_result"):
        time.sleep(2)
        payment_result = AsyncResult(payment_task_id)
        payment_results_counter.add(1)

        if payment_result.ready():
            result_value = payment_result.result
            logger.info(f"Payment task result: {result_value}")
            return result_value
        else:
            logger.info("Timeout: Payment task is still running...")
            return "Payment Timeout"

@celery_app.task
def commit_create_order(username, quantity, delivery):
    with tracer.start_as_current_span("commit_create_order"):
        session = Session()
        try:
            insert_query = insert(user_order).values(username=username, quantity=quantity, delivery=delivery)
            session.execute(insert_query)
            session.commit()
            logger.info("Order committed", extra={"username": username, "quantity": quantity, "delivery": delivery})
            order_commit_counter.add(1)
        except Exception as e:
            logger.error("Error during database operation", exc_info=True)
            raise
        finally:
            session.close()

@celery_app.task
def rollback_order(username, quantity, delivery):
    with tracer.start_as_current_span("rollback_order"):
        session = Session()
        try:
            query = "DELETE FROM user_order WHERE (username, delivery, quantity, uuid) = " \
                    "(SELECT username, delivery, quantity, uuid FROM user_order " \
                    "WHERE username = :username AND delivery = :delivery AND " \
                    "quantity = :quantity ORDER BY uuid DESC LIMIT 1);"
            session.execute(query, {"username": username, "delivery": delivery, "quantity": quantity})
            session.commit()
            logger.info("Order rollback committed", extra={"username": username, "quantity": quantity, "delivery": delivery})
            order_rollback_counter.add(1)
        except Exception as e:
            logger.error("Error during database operation", exc_info=True)
            raise
        finally:
            session.close()
