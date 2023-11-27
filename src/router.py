from databases.interfaces import Record
from fastapi import APIRouter, BackgroundTasks, Depends, Response, status
from src.database import database, user_order
import os
from dotenv import load_dotenv
from celery import Celery
from sqlalchemy import insert, select
from celery.result import AsyncResult
import json

router = APIRouter()
BROKER_URL = os.getenv("CELERY_BROKER_URL")
RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND")
celery_app = Celery('backend', broker=BROKER_URL,
                    backend=RESULT_BACKEND)

@router.get("/hello", status_code=status.HTTP_200_OK)
async def say_hi():
    return {"message": "Hello World auth4"}

@router.post("/order", status_code=status.HTTP_201_CREATED)
async def order(
    request_data: dict
)-> dict[str, str]:
    print("recieved order in router v2")
    fn: str = request_data.get("fn")
    payload: dict = request_data.get("payload")
    print("payload="+str(payload))
    #await commit_create_order(payload.get("username"), payload.get("quantity"), payload.get("delivery"))
    celery_app.send_task("create_order", queue='q01', args=[payload, fn])
    return {"message": "order created"}

async def commit_create_order(username, quantity, delivery):
    print(" inside commit_create_order")
    insert_query = (
        insert(user_order)
        .values({
                "username": username,
                "quantity": quantity,
                "delivery": delivery,
            })
    )
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