import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import SQLAlchemyError

from app.config import settings
from app.error_handlers import register_error_handlers
from app.routers import admin, auth, health, meetings
from app.services.processing import fail_interrupted_meetings

# The base configuration for every logger of the application. The loggers in
# the other modules (logging.getLogger(__name__)) have no handler of their own:
# their messages travel up to the root logger, which is set up here. uvicorn
# keeps its own format for its own messages.
logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
)

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


# None turns the page off: FastAPI then does not add the route at all, so the
# address answers 404
app = FastAPI(
    title="Meeting Notes AI",
    lifespan=lifespan,
    docs_url="/docs" if settings.enable_docs else None,
    redoc_url="/redoc" if settings.enable_docs else None,
    openapi_url="/openapi.json" if settings.enable_docs else None,
)

# allow_credentials: the frontend runs on another origin (another port in
# development) and sends the login cookie with every request. Without it, the
# browser would not give the answer to the frontend. The cookie is accepted
# only from the exact addresses in CORS_ORIGINS ("*" is refused in config.py)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_error_handlers(app)

app.include_router(health.router, prefix="/api")
app.include_router(meetings.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
