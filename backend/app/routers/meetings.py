import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import Meeting
from app.schemas import MeetingRead
from app.storage import ALLOWED_EXTENSIONS, FileTooLargeError, save_upload

router = APIRouter(prefix="/meetings", tags=["meetings"])


@router.post("", response_model=MeetingRead, status_code=status.HTTP_202_ACCEPTED)
def upload_meeting(file: UploadFile, db: Session = Depends(get_db)):
    # Only the name itself, without any folders the client may have sent.
    # It is stored in the database and never used as a path on disk.
    original_filename = Path(file.filename or "").name[:255]
    extension = Path(original_filename).suffix.lower()
    content_type = file.content_type or ""

    # Both values come from the client, so this is only a first filter;
    # ffmpeg finds out what the file really is when it is processed
    if extension not in ALLOWED_EXTENSIONS or not content_type.startswith("video/"):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only video files are accepted: "
            + ", ".join(sorted(ALLOWED_EXTENSIONS)),
        )

    too_large = HTTPException(
        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
        detail=f"The file is larger than {settings.max_upload_mb} MB",
    )
    if file.size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="The file is empty"
        )
    if file.size is not None and file.size > settings.max_upload_bytes:
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
        # the cleanup below never deletes a folder this request did not create.
        new_dir.mkdir(parents=True, exist_ok=False)
        meeting_dir = new_dir
        save_upload(file.file, meeting_dir / stored_name, settings.max_upload_bytes)

        # Relative to UPLOAD_DIR and always with "/", on Windows too
        meeting.file_path = f"{meeting.id}/{stored_name}"
        db.commit()
    except Exception as error:
        # Leave nothing behind, whatever went wrong: neither the row nor a
        # partial file
        if meeting_dir is not None:
            shutil.rmtree(meeting_dir, ignore_errors=True)
        db.rollback()
        if isinstance(error, FileTooLargeError):
            raise too_large
        if isinstance(error, (OSError, SQLAlchemyError)):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Could not save the uploaded file",
            )
        # Anything unexpected is a bug: re-raise it so FastAPI logs the
        # traceback and answers with 500
        raise

    return meeting
