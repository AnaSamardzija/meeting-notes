import enum
from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, Enum, String, Text
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
