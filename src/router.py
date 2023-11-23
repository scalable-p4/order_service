from databases.interfaces import Record
from fastapi import APIRouter, BackgroundTasks, Depends, Response, status
from src.database import database, user_order
from dotenv import load_dotenv
from celery import Celery
from sqlalchemy import insert, select
from celery.result import AsyncResult
router = APIRouter()

@router.get("/hello", status_code=status.HTTP_200_OK)
async def say_hi():
    return {"message": "Hello World auth4"}

@router.post("/order", status_code=status.HTTP_201_CREATED)
async def order(
    request_data: dict
)-> dict[str, str]:
    username: str = request_data.get("username")
    payment_amt: int = request_data.get("payment_amt")
    quantity = request_data.get("quantity")
    insert_query = (
        insert(user_order)
        .values({
                "username": username,
                "payment_amt": payment_amt,
                "quantity": quantity,
            })
    )
    await database.fetch_one(insert_query)
    return {"message": "Order Created"}