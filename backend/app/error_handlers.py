import logging

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError

from app.services.meetings import (
    EmptyFileError,
    MeetingInProgressError,
    MeetingNotFoundError,
    UnsupportedMediaError,
    UploadSaveError,
)
from app.storage import FileTooLargeError

logger = logging.getLogger(__name__)

# The one place that decides which HTTP status an error of a service becomes.
# The message of each of these errors is written for the user.
SERVICE_ERROR_STATUS_CODES: dict[type[Exception], int] = {
    MeetingNotFoundError: status.HTTP_404_NOT_FOUND,
    MeetingInProgressError: status.HTTP_409_CONFLICT,
    EmptyFileError: status.HTTP_400_BAD_REQUEST,
    FileTooLargeError: status.HTTP_413_CONTENT_TOO_LARGE,
    UnsupportedMediaError: status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
    UploadSaveError: status.HTTP_500_INTERNAL_SERVER_ERROR,
}


def _handle_service_error(request: Request, error: Exception) -> JSONResponse:
    # The same shape as the errors FastAPI itself returns: {"detail": "..."}
    return JSONResponse(
        status_code=SERVICE_ERROR_STATUS_CODES[type(error)],
        content={"detail": str(error)},
    )


def _handle_database_unavailable(
    request: Request, error: OperationalError
) -> JSONResponse:
    # OperationalError: the database could not be reached or the connection
    # was lost. The details stay in the log; the client gets a short message.
    logger.error("The database is not available: %s", error)
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": "Database is not available"},
    )


def register_error_handlers(app: FastAPI) -> None:
    """Tell FastAPI how to turn the errors of the services into responses."""
    for error_class in SERVICE_ERROR_STATUS_CODES:
        app.add_exception_handler(error_class, _handle_service_error)
    app.add_exception_handler(OperationalError, _handle_database_unavailable)
