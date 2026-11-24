import logging
import shutil
from collections.abc import Sequence
from pathlib import Path
from typing import BinaryIO

from sqlalchemy import Row, Select, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Meeting, MeetingStatus, User, UserRole
from app.services.audio import (
    InvalidVideoError,
    check_video_length,
    get_media_duration,
)
from app.services.processing import IN_PROGRESS_STATUSES
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
    """The meeting is being processed, so it cannot be started again or
    deleted."""


def _visible_to(query: Select, user: User) -> Select:
    """Limit the query to the meetings the user may see: all of them for the
    admin, only their own for everyone else.

    The check is part of the SQL query, so the meeting of another user is
    simply not found, exactly like a meeting that does not exist: the user
    cannot tell that it is there.
    """
    if user.role == UserRole.ADMIN:
        return query
    return query.where(Meeting.user_id == user.id)


def list_meetings(db: Session, user: User) -> Sequence[Row]:
    """Return the rows of the meetings list the user may see, the newest
    first."""
    # Only the columns the list shows: the transcript and the insights are not
    # read at all
    query = (
        select(
            Meeting.id,
            Meeting.original_filename,
            Meeting.title,
            Meeting.status,
            Meeting.uploaded_at,
            Meeting.interviewee,
            # The email of the user who uploaded the meeting; the frontend
            # shows it only to the admin, who sees the meetings of everyone
            User.email.label("owner_email"),
        )
        # Every meeting has an owner (user_id cannot be NULL), so an inner
        # join never leaves a meeting out
        .join(User, Meeting.user_id == User.id)
        .order_by(
            # uploaded_at has a precision of one second, so id breaks the tie
            Meeting.uploaded_at.desc(),
            Meeting.id.desc(),
        )
    )
    return db.execute(_visible_to(query, user)).all()


def get_meeting(
    db: Session, meeting_id: int, user: User, *, for_update: bool = False
) -> Meeting:
    """Return the meeting if the user may see it, or raise
    MeetingNotFoundError.

    Every function that works on one meeting gets it through here, so the
    ownership is checked in one place. for_update=True locks the row until
    the commit (SELECT ... FOR UPDATE).
    """
    query = _visible_to(select(Meeting).where(Meeting.id == meeting_id), user)
    if for_update:
        # populate_existing: if the meeting is already in the session, its
        # values are read again from the locked row, so the caller never
        # checks an old status
        query = query.with_for_update().execution_options(populate_existing=True)
    meeting = db.scalar(query)
    if meeting is None:
        raise MeetingNotFoundError("Meeting not found")
    return meeting


def update_title(db: Session, meeting_id: int, user: User, title: str) -> Meeting:
    """Set the title of the meeting and return the meeting.

    The title has been checked by the schema already. Raises
    MeetingNotFoundError.
    """
    meeting = get_meeting(db, meeting_id, user)
    meeting.title = title
    db.commit()
    return meeting


def delete_meeting(db: Session, meeting_id: int, user: User) -> None:
    """Delete the meeting and its folder on disk (the video and the MP3).

    Raises MeetingNotFoundError, or MeetingInProgressError while the meeting
    is being processed: its background task still needs the row and the
    files.
    """
    # for_update: the same lock as in start_reprocessing, so a deletion and
    # a "process again" of the same meeting cannot overlap. The one that
    # comes second waits, then finds the meeting gone (404) or being
    # processed (409)
    meeting = get_meeting(db, meeting_id, user, for_update=True)
    if meeting.status in IN_PROGRESS_STATUSES:
        raise MeetingInProgressError(
            "The meeting is being processed, so it cannot be deleted"
        )

    db.delete(meeting)
    db.commit()

    # The files go only after the row is gone. If they cannot be deleted
    # (e.g. a file is locked on Windows), the meeting has still disappeared
    # from the app: only a folder nobody uses is left on disk. The other way
    # round, a failure could leave a meeting whose video is half deleted.
    # The same folder as in create_meeting
    meeting_dir = settings.upload_path / str(meeting_id)
    try:
        shutil.rmtree(meeting_dir)
    except FileNotFoundError:
        # Nothing to delete (e.g. the files were removed by hand)
        pass
    except OSError as error:
        # Only the id: the names of the files can hold the interviewee's name
        logger.warning(
            "Meeting %s was deleted, but not its folder: %s",
            meeting_id,
            error.strerror,
        )


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
    user_id: int,
    title: str | None = None,
) -> Meeting:
    """Check the uploaded video, save it to disk and create its meeting,
    owned by the user with user_id.

    The arguments are plain values, not the UploadFile of FastAPI, so the
    service does not depend on the web framework. The caller starts the
    processing. An empty title is stored as None, and the AI then writes one.

    Raises UnsupportedMediaError, EmptyFileError, FileTooLargeError,
    InvalidVideoError (too long, or not a readable video) or UploadSaveError.
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
        meeting = Meeting(
            user_id=user_id,
            original_filename=original_filename,
            file_path="",
            title=(title or "").strip() or None,
        )
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
        video_path = meeting_dir / stored_name
        save_upload(source, video_path, settings.max_upload_bytes)
        # ffprobe can read the length only from the saved file. A video that
        # is too long would cost too much in Gemini, so it is not kept
        check_video_length(get_media_duration(video_path))

        # Relative to UPLOAD_DIR and always with "/", on Windows too
        meeting.file_path = f"{meeting.id}/{stored_name}"
        db.commit()
    except FileTooLargeError:
        # The size was not known in advance, or it was wrong
        _discard_upload(db, meeting_dir)
        raise too_large from None
    except InvalidVideoError:
        # Its message is written for the user, so it is passed on as it is
        _discard_upload(db, meeting_dir)
        raise
    except (OSError, SQLAlchemyError):
        # The user gets a short message; the real reason goes to the log. The
        # file name is not logged: it often holds the name of the interviewee
        logger.exception("Could not save the upload of user %s", user_id)
        _discard_upload(db, meeting_dir)
        raise UploadSaveError("Could not save the uploaded file") from None
    except Exception:
        # Anything unexpected is a bug: clean up and let it through
        _discard_upload(db, meeting_dir)
        raise
    return meeting


def start_reprocessing(
    db: Session, meeting_id: int, user: User, transcribe: bool = False
) -> Meeting:
    """Mark the meeting as being processed again and return it.

    A meeting with a transcript gets only a new summary from it, unless
    transcribe is True; one without a transcript is always processed from the
    audio. The status tells which: transcribing for the whole processing,
    summarizing for the summary only. The old transcript and summary are kept
    until the new ones are ready (see process_meeting), so the details show
    them meanwhile and a failed processing does not lose them.

    The caller starts the processing itself. Raises MeetingNotFoundError, or
    MeetingInProgressError if the meeting is already being processed.
    """
    # for_update: SELECT ... FOR UPDATE locks the row until the commit below.
    # A second request for the same meeting waits here and then reads the new
    # status, so two requests can never both start the processing.
    meeting = get_meeting(db, meeting_id, user, for_update=True)
    if meeting.status in IN_PROGRESS_STATUSES:
        raise MeetingInProgressError("The meeting is already being processed")

    # A new transcript is never made without a new summary: the summary is
    # written from the transcript
    if transcribe or meeting.transcript is None:
        meeting.status = MeetingStatus.TRANSCRIBING
    else:
        meeting.status = MeetingStatus.SUMMARIZING
    # Only the message of an earlier failure is cleared; a new failure writes
    # its own
    meeting.error_message = None
    db.commit()
    return meeting
