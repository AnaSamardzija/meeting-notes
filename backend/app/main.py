import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import SQLAlchemyError

from app.config import settings
from app.routers import health, meetings
from app.services.processing import fail_interrupted_meetings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # The code before yield runs once, before the first request is accepted;
    # code after yield would run when the server shuts down
    try:
        interrupted = fail_interrupted_meetings()
        if interrupted:
            logger.warning(
                "Marked %s interrupted meeting(s) as failed at startup", interrupted
            )
    except SQLAlchemyError:
        # The database is not reachable (or not migrated) yet. The server
        # still starts, as it did before, and reports the problem in the log.
        logger.exception("Could not check for interrupted meetings at startup")
    yield


app = FastAPI(title="Meeting Notes AI", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",")],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")
app.include_router(meetings.router, prefix="/api")
