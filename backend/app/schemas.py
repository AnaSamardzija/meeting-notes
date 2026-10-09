from datetime import datetime, timezone
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict

from app.models import MeetingStatus


def _as_utc(value: datetime) -> datetime:
    # The database returns times without a time zone, and all of them are UTC
    # (see app/models.py)
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


# Sent as "2026-10-09T10:00:00Z". Without the "Z" the browser would read the
# time as local time and show it shifted.
UtcDateTime = Annotated[datetime, AfterValidator(_as_utc)]


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
    uploaded_at: UtcDateTime


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
    processed_at: UtcDateTime | None
    action_items: list[ActionItemRead]
