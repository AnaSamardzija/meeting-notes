import logging
import shutil
from collections.abc import Sequence
from pathlib import Path
from typing import BinaryIO

from sqlalchemy import Row, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import settings
from app.models import ActionItem, Meeting, MeetingStatus
from app.services.processing import IN_PROGRESS_STATUSES, reset_results
from app.storage import ALLOWED_EXTENSIONS, FileTooLargeError, save_upload

logger = logging.getLogger(__name__)

# The original_filename column in app/models.py is String(255)
FILENAME_MAX_LENGTH = 255


# The messages of these errors are written for the user. The service knows
# nothing about HTTP: the caller decides which status code each one becomes.
class MeetingNotFoundError(Exception):
    """There is no meeting with the given id."""


class UnsupportedMediaError(Exception):
    """The uploaded file is not one of the accepted video formats."""


class EmptyFileError(Exception):
    """The uploaded file has no content."""


class UploadSaveError(Exception):
    """The uploaded file or its row in the database could not be saved."""


class MeetingInProgressError(Exception):
    """The meeting is being processed, so it cannot be started again."""


def list_meetings(db: Session) -> Sequence[Row]:
    """Return the rows of the meetings list, the newest first."""
    # Counted by the database, one subquery per row of the same SELECT, so the
    # action items themselves are never loaded
    action_item_count = (
        select(func.count(ActionItem.id))
        .where(ActionItem.meeting_id == Meeting.id)
        .scalar_subquery()
    )
    # Only the columns the list shows: the transcript is not read at all
    query = select(
        Meeting.id,
        Meeting.original_filename,
        Meeting.title,
        Meeting.status,
        Meeting.uploaded_at,
        action_item_count.label("action_item_count"),
    ).order_by(
        # uploaded_at has a precision of one second, so id breaks the tie
        Meeting.uploaded_at.desc(),
        Meeting.id.desc(),
    )
    return db.execute(query).all()


def get_meeting(db: Session, meeting_id: int) -> Meeting:
    """Return the meeting, or raise MeetingNotFoundError."""
    meeting = db.get(Meeting, meeting_id)
    if meeting is None:
        raise MeetingNotFoundError("Meeting not found")
    return meeting


def _discard_upload(db: Session, meeting_dir: Path | None) -> None:
    """Leave nothing behind after a failed upload: neither the row nor a
    partial file."""
    if meeting_dir is not None:
        shutil.rmtree(meeting_dir, ignore_errors=True)
    db.rollback()


def create_meeting(
    db: Session,
    source: BinaryIO,
    filename: str | None,
    content_type: str | None,
    size: int | None,
) -> Meeting:
    """Check the uploaded video, save it to disk and create its meeting.

    The arguments are plain values, not the UploadFile of FastAPI, so the
    service does not depend on the web framework. The caller starts the
    processing.

    Raises UnsupportedMediaError, EmptyFileError, FileTooLargeError or
    UploadSaveError.
    """
    # Only the name itself, without any folders the client may have sent.
    # It is stored in the database and never used as a path on disk.
    original_filename = Path(filename or "").name[:FILENAME_MAX_LENGTH]
    extension = Path(original_filename).suffix.lower()

    # Both values come from the client, so this is only a first filter;
    # ffmpeg finds out what the file really is when it is processed
    if extension not in ALLOWED_EXTENSIONS or not (content_type or "").startswith(
        "video/"
    ):
        raise UnsupportedMediaError(
            "Only video files are accepted: " + ", ".join(sorted(ALLOWED_EXTENSIONS))
        )

    too_large = FileTooLargeError(
        f"The file is larger than {settings.max_upload_mb} MB"
    )
    if size == 0:
        raise EmptyFileError("The file is empty")
    if size is not None and size > settings.max_upload_bytes:
        raise too_large

    meeting_dir = None
    try:
        # file_path depends on the id, and the id exists only after the INSERT.
        # flush sends the INSERT inside the open transaction, so the row is not
        # permanent (or visible to anyone else) until commit.
        meeting = Meeting(original_filename=original_filename, file_path="")
        db.add(meeting)
        db.flush()

        stored_name = f"original{extension}"
        new_dir = settings.upload_path / str(meeting.id)
        # exist_ok=False: a folder that is already there belongs to something
        # else (e.g. the database was reset but the uploads were kept), so it
        # must not be reused. meeting_dir is set only after mkdir succeeds, so
        # the cleanup never deletes a folder this call did not create.
        new_dir.mkdir(parents=True, exist_ok=False)
        meeting_dir = new_dir
        save_upload(source, meeting_dir / stored_name, settings.max_upload_bytes)

        # Relative to UPLOAD_DIR and always with "/", on Windows too
        meeting.file_path = f"{meeting.id}/{stored_name}"
        db.commit()
    except FileTooLargeError:
        # The size was not known in advance, or it was wrong
        _discard_upload(db, meeting_dir)
        raise too_large from None
    except (OSError, SQLAlchemyError):
        # The user gets a short message; the real reason goes to the log
        logger.exception("Could not save the upload %r", original_filename)
        _discard_upload(db, meeting_dir)
        raise UploadSaveError("Could not save the uploaded file") from None
    except Exception:
        # Anything unexpected is a bug: clean up and let it through
        _discard_upload(db, meeting_dir)
        raise
    return meeting


def start_reprocessing(db: Session, meeting_id: int) -> Meeting:
    """Clear the old results of the meeting and mark it as being processed.

    The caller starts the processing itself. Raises MeetingNotFoundError, or
    MeetingInProgressError if the meeting is already being processed.
    """
    # with_for_update: SELECT ... FOR UPDATE locks the row until the commit
    # below. A second request for the same meeting waits here and then reads
    # the new status, so two requests can never both start the processing.
    meeting = db.get(Meeting, meeting_id, with_for_update=True)
    if meeting is None:
        raise MeetingNotFoundError("Meeting not found")
    if meeting.status in IN_PROGRESS_STATUSES:
        raise MeetingInProgressError("The meeting is already being processed")

    # The old results are removed first, so the action items are not doubled
    reset_results(meeting)
    meeting.status = MeetingStatus.TRANSCRIBING
    db.commit()
    return meeting
