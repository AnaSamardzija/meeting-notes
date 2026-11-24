"""Refuse an upload that is too large before its body is read.

FastAPI reads the whole multipart form (and writes the file to a temporary
file on disk) before the endpoint runs, so before the login and the size are
checked. Without this middleware anyone, even without logging in, could fill
the disk with large requests. In production this is replaced by uploading
straight to Cloud Storage (issue 033).
"""

from fastapi import status
from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.config import settings

# The only request with a large body: POST /api/meetings (the upload)
UPLOAD_METHOD = "POST"
UPLOAD_PATH = "/api/meetings"

# The body holds more than the file: the title, the file name and the
# boundaries between the parts of the form. 1 MB is far more than they need
FORM_OVERHEAD_BYTES = 1024 * 1024


def _check_content_length(headers: Headers) -> tuple[int, str] | None:
    """Return the status code and the message of the error, or None when the
    upload may go on."""
    # Content-Length: the size of the body in bytes, sent before the body.
    # Without it (Transfer-Encoding: chunked) the size is known only after the
    # whole body has arrived, which is too late
    value = headers.get("content-length")
    if value is None:
        return (
            status.HTTP_411_LENGTH_REQUIRED,
            "The size of the upload must be known in advance (Content-Length)",
        )
    try:
        size = int(value)
    except ValueError:
        size = -1
    if size < 0:
        return status.HTTP_400_BAD_REQUEST, "Content-Length is not a valid number"
    if size > settings.max_upload_bytes + FORM_OVERHEAD_BYTES:
        # The same message as the upload service gives for a file that is
        # too large (app/services/meetings.py)
        return (
            status.HTTP_413_CONTENT_TOO_LARGE,
            f"The file is larger than {settings.max_upload_mb} MB",
        )
    return None


class UploadSizeLimitMiddleware:
    """A pure ASGI middleware: it gets every request before the app does.

    ASGI is the interface between the server (uvicorn) and the app. A request
    is three things: scope (method, path, headers), receive (a function that
    reads the body piece by piece) and send (a function that sends the
    answer). This middleware looks only at the scope and never calls receive,
    so a refused body is never read.
    """

    def __init__(self, app: ASGIApp) -> None:
        # The next layer: another middleware or the FastAPI app itself
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        # scope["type"] is also "lifespan" (startup) or "websocket"
        if (
            scope["type"] == "http"
            and scope["method"] == UPLOAD_METHOD
            and scope["path"] == UPLOAD_PATH
        ):
            error = _check_content_length(Headers(scope=scope))
            if error is not None:
                status_code, message = error
                # The same shape as every other error: {"detail": "..."}
                response = JSONResponse(
                    status_code=status_code, content={"detail": message}
                )
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)
