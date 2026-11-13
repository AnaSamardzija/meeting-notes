from datetime import datetime, timezone
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from app.models import MeetingStatus


def _as_utc(value: datetime) -> datetime:
    # The database returns times without a time zone, and all of them are UTC
    # (see app/models.py)
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


# Sent as "2026-10-09T10:00:00Z". Without the "Z" the browser would read the
# time as local time and show it shifted.
UtcDateTime = Annotated[datetime, AfterValidator(_as_utc)]


# The summary of an interview. The same classes describe three things: the
# JSON that Gemini must return (see app/services/ai.py), what is stored in the
# JSON columns of app/models.py, and what the API returns. The descriptions
# become part of the JSON schema, so Gemini reads them too.
class Interviewee(BaseModel):
    """The person who was interviewed. Each field is None when the interview
    does not say it."""

    name: str | None = Field(description="Name, only when it is said")
    role: str | None = Field(description="e.g. 'U17 coach' or 'amateur player'")
    location: str | None = Field(description="City or country")


class InsightItem(BaseModel):
    """One point of feedback."""

    title: str = Field(description="A few words")
    explanation: str


class Insights(BaseModel):
    """Everything in the summary except the title and the interviewee."""

    takeaway: str = Field(description="The main conclusion")
    context: str = Field(description="Who the person is and how they work")
    likes: list[InsightItem]
    dislikes: list[InsightItem]
    wants: list[InsightItem] = Field(description="The most important first")


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
    """One row of the meetings list: no transcript or summary, only who was
    interviewed (None until processing is done)."""

    interviewee: Interviewee | None


class MeetingDetail(MeetingRead):
    """Everything about one meeting. The AI fields stay empty until processing
    is done."""

    error_message: str | None
    transcript: str | None
    interviewee: Interviewee | None
    insights: Insights | None
    processed_at: UtcDateTime | None
