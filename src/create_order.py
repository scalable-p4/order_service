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
from opentelemetry import trace, metrics
import logging

tracer = trace.get_tracer(__name__)
meter = metrics.get_meter(__name__)
logger = logging.getLogger(__name__)

BROKER_URL = os.getenv("CELERY_BROKER_URL")
RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND")
celery_app = Celery('create_order', broker=BROKER_URL,
                    backend=RESULT_BACKEND)
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)

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
        time.sleep(0.3)
        payment_result = AsyncResult(payment_task_id)
        payment_results_counter.add(1)

        if payment_result.ready():
            result_value = payment_result.result
            logger.info(f"Payment task result: {result_value}")
            return result_value
        else:
            logger.info("Inventory task is still running...")
            return "inventory task is still running..."

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
