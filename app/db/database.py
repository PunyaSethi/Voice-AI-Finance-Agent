from __future__ import annotations

from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import create_engine, inspect, text

from app.config import get_settings


settings = get_settings()
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

engine = create_engine(settings.database_url, connect_args=connect_args)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False,
)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from app.db import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    if settings.database_url.startswith("sqlite"):
        _ensure_sqlite_columns()


def _ensure_sqlite_columns() -> None:
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    column_specs = {
        "invoices": {
            "due_date": "DATETIME",
            "updated_at": "DATETIME",
            "deleted_at": "DATETIME",
        },
        "transactions": {
            "updated_at": "DATETIME",
            "deleted_at": "DATETIME",
        },
        "reminders": {
            "updated_at": "DATETIME",
            "deleted_at": "DATETIME",
        },
        "interactions": {
            "updated_at": "DATETIME",
        },
    }

    with engine.begin() as connection:
        for table_name, columns in column_specs.items():
            if table_name not in table_names:
                continue
            existing_columns = {column["name"] for column in inspector.get_columns(table_name)}
            for column_name, column_type in columns.items():
                if column_name in existing_columns:
                    continue
                connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"))
