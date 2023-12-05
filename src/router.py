from databases.interfaces import Record
from fastapi import APIRouter, BackgroundTasks, Depends, Response, status
from src.database import database, user_order
import os
from dotenv import load_dotenv
from celery import Celery
from sqlalchemy import insert, select
from celery.result import AsyncResult
import json
from opentelemetry import trace, metrics
import logging

tracer = trace.get_tracer(__name__)
meter = metrics.get_meter(__name__)
logger = logging.getLogger(__name__)

order_requests_counter = meter.create_counter(
    "order_requests",
    description="Number of order requests",
    unit="1",
)

router = APIRouter()
BROKER_URL = os.getenv("CELERY_BROKER_URL")
RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND")
celery_app = Celery('backend', broker=BROKER_URL,
                    backend=RESULT_BACKEND)

@router.get("/hello", status_code=status.HTTP_200_OK)
async def say_hi():
    with tracer.start_as_current_span("get_hello"):
        logger.info("Hello World request received")
        return {"message": "Hello World auth4"}

@router.post("/order", status_code=status.HTTP_201_CREATED)
async def order(request_data: dict) -> dict[str, str]:
    with tracer.start_as_current_span("post_order"):
        order_requests_counter.add(1)
        logger.info("Received order in router v2", extra={"request_data": request_data})

        fn = request_data.get("fn")
        payload = request_data.get("payload")

        result = celery_app.send_task("create_order", queue='q01', args=[payload, fn])
        return_result = result.get()
        logger.info(f"Order result: {return_result}", extra={"return_result": return_result})

        return {"message": f"order created with result = {return_result}"}

async def commit_create_order(username, quantity, delivery):
    with tracer.start_as_current_span("commit_create_order"):
        logger.info("Inside commit_create_order", extra={"username": username, "quantity": quantity, "delivery": delivery})
        insert_query = insert(user_order).values(username=username, quantity=quantity, delivery=delivery)
        await database.fetch_one(insert_query)

# def rollback(username, quantity, delivery):
#     insert_query = (
#         insert(user_order)
#         .values({
#                 "username": username,
#                 "quantity": quantity,
#                 "delivery": delivery,
#             })
#     )
#     database.execute(insert_query)