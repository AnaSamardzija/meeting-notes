from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models import MeetingStatus


class MeetingRead(BaseModel):
    """What the API returns for a meeting. Internal fields such as file_path
    are left out on purpose."""

    # from_attributes: build the schema from an ORM object (meeting.id), not
    # only from a dict (meeting["id"])
    model_config = ConfigDict(from_attributes=True)

    id: int
    original_filename: str
    title: str | None
    status: MeetingStatus
    uploaded_at: datetime


class MeetingListItem(MeetingRead):
    """One row of the meetings list: no transcript or summary, only the number
    of action items."""

    action_item_count: int


class ActionItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    # None when the meeting does not say who is responsible
    assignee: str | None
    description: str


class MeetingDetail(MeetingRead):
    """Everything about one meeting. The AI fields stay empty until processing
    is done."""

    error_message: str | None
    transcript: str | None
    summary: str | None
    key_topics: list[str] | None
    processed_at: datetime | None
    action_items: list[ActionItemRead]
