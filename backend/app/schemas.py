from datetime import UTC, datetime
from typing import Annotated

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    StringConstraints,
)

from app.models import MeetingStatus, UserRole

# The title column in app/models.py is String(255)
TITLE_MAX_LENGTH = 255

# A title the user sets: the spaces around it are removed first, then it must
# have between 1 and TITLE_MAX_LENGTH characters. Anything else is a 422.
Title = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=1, max_length=TITLE_MAX_LENGTH
    ),
]


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
    interviewed (None until processing is done) and the email of the user
    who uploaded it."""

    interviewee: Interviewee | None
    owner_email: str


class MeetingUpdate(BaseModel):
    """The body of PATCH /api/meetings/{id}: what the user can change."""

    title: Title


class SummaryForm(BaseModel):
    """The summary as the user edits it: what GET /api/meetings/{id}/summary
    returns and PUT expects, the whole summary at once.

    An empty string means that the value is not known or the section is
    empty. likes, dislikes and wants are text with one paragraph per item (see
    app/services/summary.py); the backend turns them into InsightItem lists.
    """

    name: str
    role: str
    location: str
    takeaway: str
    context: str
    likes: str
    dislikes: str
    wants: str


class MeetingDetail(MeetingRead):
    """Everything about one meeting. The AI fields stay empty until processing
    is done."""

    error_message: str | None
    transcript: str | None
    interviewee: Interviewee | None
    insights: Insights | None
    processed_at: UtcDateTime | None
    # Set when the user has changed the summary, so the frontend can warn that
    # processing the meeting again replaces the changes
    edited_at: UtcDateTime | None


# A password must have at least 10 characters. The upper limit stops a
# request from sending megabytes of text to the (deliberately slow) password
# hash. Spaces are kept: they are part of the password
PASSWORD_MIN_LENGTH = 10
PASSWORD_MAX_LENGTH = 128


class RegisterRequest(BaseModel):
    """The body of POST /api/auth/register. Any other field, such as "role",
    is ignored: every new account is a regular user."""

    # EmailStr: checks that this is an email address (email-validator)
    email: EmailStr
    password: str = Field(
        min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH
    )


class LoginRequest(BaseModel):
    """The body of POST /api/auth/login. No format rules: anything that is
    not a known email and its password gets the same 401."""

    email: str = Field(max_length=255)
    password: str = Field(max_length=PASSWORD_MAX_LENGTH)


class ChangePasswordRequest(BaseModel):
    """The body of POST /api/auth/password. The new password has the same
    rules as at registration."""

    current_password: str = Field(max_length=PASSWORD_MAX_LENGTH)
    new_password: str = Field(
        min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH
    )


class UserActiveUpdate(BaseModel):
    """The body of PATCH /api/admin/users/{id}: activates or deactivates the
    account."""

    is_active: bool


class SetPasswordRequest(BaseModel):
    """The body of POST /api/admin/users/{id}/password: the new password the
    admin gives a user who forgot theirs. The same rules as at registration."""

    new_password: str = Field(
        min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH
    )


class UserRead(BaseModel):
    """What the API returns for a user; never the password hash."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    role: UserRole
    is_active: bool
    # True while the user must change the password the admin set; the
    # frontend then keeps the user on the profile page
    must_change_password: bool
    created_at: UtcDateTime
