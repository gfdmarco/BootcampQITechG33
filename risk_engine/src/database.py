import os
from contextvars import ContextVar
from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg2://risk:risk@db_risk:5432/risk")

engine = create_engine(DATABASE_URL, pool_size=5, pool_recycle=600, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False)


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
        raise Exception("Nao existe contexto. O middleware de sessao nao rodou.")
    return context
