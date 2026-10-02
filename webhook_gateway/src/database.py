import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from contextvars import ContextVar
from typing import Optional

DATABASE_URL = os.getenv(
    "WEBHOOK_DATABASE_URL",
    "postgresql+psycopg2://webhook:webhook@db_webhook:5432/webhook"
)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Context:
    def __init__(self) -> None:
        self.db_session: Optional[Session] = None

    def get_or_create_session(self) -> Session:
        if self.db_session is None:
            self.db_session = SessionLocal()
        return self.db_session


_context: ContextVar[Optional[Context]] = ContextVar("context", default=None)


def open_context() -> Context:
    context = Context()
    _context.set(context)
    return context


def clear_context() -> None:
    _context.set(None)


def get_context() -> Context:
    context = _context.get()
    if context is None:
        raise Exception("Nao existe contexto...")
    return context