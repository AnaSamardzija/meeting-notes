from datetime import UTC, datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict

from app.models import MeetingStatus


def _as_utc(value: datetime) -> datetime:
    # The database returns times without a time zone, and all of them are UTC
    # (see app/models.py)
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


# Sent as "2026-10-09T10:00:00Z". Without the "Z" the browser would read the
# time as local time and show it shifted.
UtcDateTime = Annotated[datetime, AfterValidator(_as_utc)]


# The summary of an interview. The same classes describe three things: the
# JSON that Gemini must return (see app/services/ai.py), what is stored in the
# JSON columns of app/models.py, and what the API returns. What each field
# should hold is written only in ANALYZE_INSTRUCTIONS in app/services/ai.py,
# so the rules are in one place. The order of the fields is the order in which
# Gemini writes them, so it matters (see the same file).
class Interviewee(BaseModel):
    """The person who was interviewed. Each field is None when the interview
    does not say it."""

    name: str | None
    role: str | None
    location: str | None


class InsightItem(BaseModel):
    """One point of feedback."""

    title: str
    explanation: str


class Insights(BaseModel):
    """Everything in the summary except the title and the interviewee."""

    context: str
    likes: list[InsightItem]
    dislikes: list[InsightItem]
    wants: list[InsightItem]
    takeaway: str


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
