from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

# The engine owns the connection pool. pool_pre_ping tests a connection before
# handing it out, so the app recovers by itself after the database restarts.
engine = create_engine(settings.database_url, pool_pre_ping=True)

# Session factory: every call to SessionLocal() returns a new session.
# expire_on_commit=False keeps loaded objects readable after commit.
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    """Base class for all models; its metadata is what Alembic reads."""


def get_db():
    """FastAPI dependency: one session per request, always closed at the end."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
