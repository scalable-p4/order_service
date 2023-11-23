from databases import Database
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Identity,
    Integer,
    LargeBinary,
    MetaData,
    String,
    Table,
    create_engine,
    func,
)
from sqlalchemy.dialects.postgresql import UUID

from src.config import settings
from src.constants import DB_NAMING_CONVENTION

DATABASE_URL = settings.DATABASE_URL

engine = create_engine(DATABASE_URL)
metadata = MetaData(naming_convention=DB_NAMING_CONVENTION)

database = Database(DATABASE_URL, force_rollback=settings.ENVIRONMENT.is_testing)


user_order = Table(
    "user_order",
    metadata,
    Column("uuid", Integer, Identity(), primary_key=True),
    Column("username", String, nullable=False),
    Column("payment_amt", LargeBinary, nullable=False),
    Column("quantity", Boolean, server_default="false", nullable=False),
)

metadata.create_all(engine)


