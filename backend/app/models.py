import enum
from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class MeetingStatus(str, enum.Enum):
    UPLOADED = "uploaded"
    TRANSCRIBING = "transcribing"
    SUMMARIZING = "summarizing"
    DONE = "done"
    FAILED = "failed"


class Meeting(Base):
    __tablename__ = "meetings"

    id: Mapped[int] = mapped_column(primary_key=True)
    # The user who uploaded the meeting. Only they and the admin can see it
    # (see get_meeting in app/services/meetings.py)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    original_filename: Mapped[str] = mapped_column(String(255))
    # Set by the user, or written by the AI after processing when the user
    # did not set one
    title: Mapped[str | None] = mapped_column(String(255))
    file_path: Mapped[str] = mapped_column(String(500))
    # MySQL DATETIME has no time zone, so all times are stored as UTC
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    # native_enum=False: stored as VARCHAR, so a new status needs no migration.
    # values_callable: store the values ("uploaded"), not the names ("UPLOADED").
    status: Mapped[MeetingStatus] = mapped_column(
        Enum(
            MeetingStatus,
            native_enum=False,
            length=20,
            values_callable=lambda statuses: [s.value for s in statuses],
        ),
        default=MeetingStatus.UPLOADED,
    )
    error_message: Mapped[str | None] = mapped_column(Text)
    # LONGTEXT: TEXT holds only 64 KB, which a long meeting can exceed
    transcript: Mapped[str | None] = mapped_column(LONGTEXT)
    # The person who was interviewed: {"name", "role", "location"}, each of
    # them null when the interview does not say it. The shape is Interviewee
    # in app/schemas.py
    interviewee: Mapped[dict | None] = mapped_column(JSON)
    # The rest of the summary: {"takeaway", "context", "likes", "dislikes",
    # "wants"}, the shape of Insights in app/schemas.py. One JSON column, so a
    # section can be added or changed without a migration
    insights: Mapped[dict | None] = mapped_column(JSON)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime)
    # When the user last changed the summary (interviewee and insights); None
    # while the summary is the one the AI wrote
    edited_at: Mapped[datetime | None] = mapped_column(DateTime)

class UserRole(str, enum.Enum):
    USER = "user"
    ADMIN = "admin"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Always stored in lower case (see app/services/auth.py), so the unique
    # index and the login do not depend on upper and lower case
    email: Mapped[str] = mapped_column(String(255), unique=True)
    # Only the argon2 hash; the password itself is never stored
    password_hash: Mapped[str] = mapped_column(String(255))
    # Stored as VARCHAR, like MeetingStatus. Registration always gives "user";
    # an admin is made only by python -m app.create_admin
    role: Mapped[UserRole] = mapped_column(
        Enum(
            UserRole,
            native_enum=False,
            length=20,
            values_callable=lambda roles: [r.value for r in roles],
        ),
        default=UserRole.USER,
    )
    # A deactivated user cannot log in, and a token they already have stops
    # working at once
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Written into every login token ("ver"). A password change increases it,
    # so every token made before the change stops working (see
    # app/services/auth.py and get_current_user in app/dependencies.py)
    token_version: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    # True after the admin set the password: until the user changes it, every
    # endpoint except /api/auth/me and /api/auth/password answers 403 (see
    # get_current_user in app/dependencies.py)
    must_change_password: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="0"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
