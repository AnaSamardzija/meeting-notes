import enum
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


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
    # Filled in by the AI after processing
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
    summary: Mapped[str | None] = mapped_column(Text)
    key_topics: Mapped[list[str] | None] = mapped_column(JSON)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime)

    # cascade: deleting a meeting through the ORM deletes its action items.
    # passive_deletes: let the database do it (ON DELETE CASCADE) instead of
    # loading the items first.
    action_items: Mapped[list["ActionItem"]] = relationship(
        back_populates="meeting",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class ActionItem(Base):
    __tablename__ = "action_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    meeting_id: Mapped[int] = mapped_column(
        ForeignKey("meetings.id", ondelete="CASCADE"), index=True
    )
    # Empty when the meeting does not say who is responsible
    assignee: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)

    meeting: Mapped["Meeting"] = relationship(back_populates="action_items")
