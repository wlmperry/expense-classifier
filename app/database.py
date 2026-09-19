"""SQLAlchemy engine, session, and declarative base for the application.

Database configuration comes from the DATABASE_URL environment variable.
A local, untracked .env file may be used for development configuration.
See docs/development.md for setup instructions.
"""

import os
from collections.abc import Generator

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

load_dotenv()


def get_database_url() -> str:
    database_url = os.environ.get("DATABASE_URL")

    if not database_url:
        raise RuntimeError(
            "DATABASE_URL is not set. Copy .env.example to .env and "
            "configure it for your local PostgreSQL database."
        )

    return database_url


engine = create_engine(get_database_url())
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    """Yield a request-scoped database session."""
    with SessionLocal() as db:
        yield db
