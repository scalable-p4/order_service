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

BROKER_URL = os.getenv("CELERY_BROKER_URL")
RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND")
celery_app = Celery('create_order', broker=BROKER_URL,
                    backend=RESULT_BACKEND)
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)


@celery_app.task(name="create_order")
def create_order(payload: dict, fn: str):
    print("fn="+str(fn))
    print("payload="+str(payload))
    username: str = payload.get("username")
    quantity: int = payload.get("quantity")
    delivery: bool = payload.get("delivery")
    print("username="+str(username))
    print("quantity="+str(quantity))
    print("delivery="+str(delivery))
    if fn == "order":
        print("creating order")
        commit_create_order(username, quantity, delivery)
        print("order committed"+str(username)+str(quantity)+str(delivery))
        payment_task = celery_app.send_task("create_payment", queue='q02', args=[payload, "pay"])
        return waiting_payment_result(payment_task.id)

    elif fn == "rollback_order":
        print("rollbacking order")
        rollback_order(username, quantity, delivery)
        print("order rollbacked"+str(username)+str(quantity)+str(delivery))
        return "failed_token_transaction"
    elif fn == "success_token_transaction":
        print("success_token_transaction")
        return "success_token_transaction"
    else:
        print("invalid function"+str(username)+str(quantity)+str(delivery))
        return "failed_token_transactopm"

@celery_app.task
def waiting_payment_result(payment_task_id):
    time.sleep(0.3)
    payment_result = AsyncResult(payment_task_id)
    if payment_result.ready():
        result_value = payment_result.result
        print(f"Task result: {result_value}")
        return result_value
    else:
        print("inventory task is still running...")
        return "inventory task is still running..."

@celery_app.task
def commit_create_order(username, quantity, delivery):
    session = Session()
    try:
        insert_query = (
            insert(user_order)
            .values({
                "username": username,
                "quantity": quantity,
                "delivery": delivery,
            })
        )
        session.execute(insert_query)
        session.commit()
        print("order committed in try")
    except Exception as e:
        print(f"Error during database operation: {e}")
    finally:
        session.close()


@celery_app.task
def rollback_order(username, quantity, delivery):
    session = Session()
    try:
        query = "DELETE FROM user_order WHERE (username, delivery, quantity, uuid) = " \
                "(SELECT username, delivery, quantity, uuid FROM user_order " \
                "WHERE username = :username AND delivery = :delivery AND " \
                "quantity = :quantity ORDER BY uuid DESC LIMIT 1);"
        session.execute(query, {"username": username, "delivery": delivery, "quantity": quantity})
        session.commit()
        print("order rollback commited in try")
    except Exception as e:
        print(f"Error during database operation: {e}")
    finally:
        session.close()
