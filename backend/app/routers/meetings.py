from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Form, UploadFile, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import (
    TITLE_MAX_LENGTH,
    MeetingDetail,
    MeetingListItem,
    MeetingRead,
    MeetingUpdate,
)
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
    return meetings_service.get_meeting(db, meeting_id)


# PATCH: changes only the fields that are sent (for now only the title), and
# returns the whole meeting, so the frontend can show it without another GET
@router.patch("/{meeting_id}", response_model=MeetingDetail)
def update_meeting(
    meeting_id: int,
    data: MeetingUpdate,
    db: Session = Depends(get_db),
):
    return meetings_service.update_title(db, meeting_id, data.title)


@router.post("", response_model=MeetingRead, status_code=status.HTTP_202_ACCEPTED)
def upload_meeting(
    file: UploadFile,
    background_tasks: BackgroundTasks,
    # Form: a field of the same multipart form as the file. Optional: when it
    # is left empty, the AI writes the title
    title: Annotated[str, Form(max_length=TITLE_MAX_LENGTH)] = "",
    db: Session = Depends(get_db),
):
    meeting = meetings_service.create_meeting(
        db,
        source=file.file,
        filename=file.filename,
        content_type=file.content_type,
        size=file.size,
        title=title,
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
