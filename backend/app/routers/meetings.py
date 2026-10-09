from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import MeetingDetail, MeetingListItem, MeetingRead
from app.services import meetings as meetings_service
from app.services.meetings import (
    EmptyFileError,
    MeetingInProgressError,
    MeetingNotFoundError,
    UnsupportedMediaError,
    UploadSaveError,
)
from app.services.processing import process_meeting
from app.storage import FileTooLargeError

router = APIRouter(prefix="/meetings", tags=["meetings"])


@router.get("", response_model=list[MeetingListItem])
def list_meetings(db: Session = Depends(get_db)):
    return meetings_service.list_meetings(db)


@router.get("/{meeting_id}", response_model=MeetingDetail)
def get_meeting(meeting_id: int, db: Session = Depends(get_db)):
    try:
        # action_items are loaded by a second query when the response is built
        return meetings_service.get_meeting(db, meeting_id)
    except MeetingNotFoundError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(error))


@router.post("", response_model=MeetingRead, status_code=status.HTTP_202_ACCEPTED)
def upload_meeting(
    file: UploadFile,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    try:
        meeting = meetings_service.create_meeting(
            db,
            source=file.file,
            filename=file.filename,
            content_type=file.content_type,
            size=file.size,
        )
    except UnsupportedMediaError as error:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=str(error))
    except EmptyFileError as error:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(error))
    except FileTooLargeError as error:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, detail=str(error))
    except UploadSaveError as error:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(error))

    # Runs after the response has been sent, so the upload does not wait for
    # the processing. Only the id is passed: the session of this request is
    # closed by then.
    background_tasks.add_task(process_meeting, meeting.id)
    return meeting


@router.post(
    "/{meeting_id}/process",
    response_model=MeetingRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def process_meeting_again(
    meeting_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    try:
        meeting = meetings_service.start_reprocessing(db, meeting_id)
    except MeetingNotFoundError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(error))
    except MeetingInProgressError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(error))

    background_tasks.add_task(process_meeting, meeting.id)
    return meeting
