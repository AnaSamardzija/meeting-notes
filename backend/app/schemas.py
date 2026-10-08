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
