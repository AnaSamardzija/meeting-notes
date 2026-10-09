from fastapi import APIRouter, BackgroundTasks, Depends, UploadFile, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import MeetingDetail, MeetingListItem, MeetingRead
from app.services import meetings as meetings_service
from app.services.processing import process_meeting

# The errors the services raise are turned into HTTP responses in
# app/error_handlers.py, so the endpoints here do not catch them.
router = APIRouter(prefix="/meetings", tags=["meetings"])


@router.get("", response_model=list[MeetingListItem])
def list_meetings(db: Session = Depends(get_db)):
    return meetings_service.list_meetings(db)


@router.get("/{meeting_id}", response_model=MeetingDetail)
def get_meeting(meeting_id: int, db: Session = Depends(get_db)):
    # action_items are loaded by a second query when the response is built
    return meetings_service.get_meeting(db, meeting_id)


@router.post("", response_model=MeetingRead, status_code=status.HTTP_202_ACCEPTED)
def upload_meeting(
    file: UploadFile,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    meeting = meetings_service.create_meeting(
        db,
        source=file.file,
        filename=file.filename,
        content_type=file.content_type,
        size=file.size,
    )
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
    meeting = meetings_service.start_reprocessing(db, meeting_id)
    background_tasks.add_task(process_meeting, meeting.id)
    return meeting
