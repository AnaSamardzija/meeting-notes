"""Tests of POST /api/meetings (uploading a video)."""

import pytest
from sqlalchemy import func, select

from app.config import settings
from app.models import Meeting, MeetingStatus

# Made-up content: the endpoint only checks the name, the type and the size,
# and the processing (where ffmpeg would read the file) is replaced in the tests
FAKE_VIDEO = b"not a real video, only bytes for the test"


def upload(client, filename, content, content_type):
    # files=: sent as multipart/form-data, the same way the browser form sends it
    return client.post(
        "/api/meetings", files={"file": (filename, content, content_type)}
    )


def count_meetings(db) -> int:
    return db.scalar(select(func.count(Meeting.id)))


def test_upload_rejects_a_file_that_is_not_a_video(
    client, db, tmp_path, process_meeting_mock
):
    response = upload(client, "notes.txt", b"some text", "text/plain")

    assert response.status_code == 415
    assert response.json()["detail"].startswith("Only video files are accepted")
    assert count_meetings(db) == 0
    assert list(tmp_path.iterdir()) == []
    process_meeting_mock.assert_not_called()


def test_upload_rejects_a_file_larger_than_the_limit(
    client, db, tmp_path, monkeypatch, process_meeting_mock
):
    # A small limit, so the test does not have to send 500 MB
    monkeypatch.setattr(settings, "max_upload_mb", 1)
    too_large = b"0" * (1024 * 1024 + 1)

    response = upload(client, "weekly-sync.mp4", too_large, "video/mp4")

    assert response.status_code == 413
    assert response.json()["detail"] == "The file is larger than 1 MB"
    assert count_meetings(db) == 0
    assert list(tmp_path.iterdir()) == []
    process_meeting_mock.assert_not_called()


def test_upload_rejects_an_empty_file(client, db, tmp_path, process_meeting_mock):
    response = upload(client, "weekly-sync.mp4", b"", "video/mp4")

    assert response.status_code == 400
    assert response.json()["detail"] == "The file is empty"
    assert count_meetings(db) == 0
    assert list(tmp_path.iterdir()) == []
    process_meeting_mock.assert_not_called()


def test_upload_saves_the_video_and_starts_the_processing(
    client, db, tmp_path, process_meeting_mock
):
    response = upload(client, "weekly-sync.mp4", FAKE_VIDEO, "video/mp4")

    assert response.status_code == 202
    body = response.json()
    assert body["original_filename"] == "weekly-sync.mp4"
    assert body["status"] == MeetingStatus.UPLOADED.value
    assert body["title"] is None

    meeting_id = body["id"]
    meeting = db.get(Meeting, meeting_id)
    assert meeting.file_path == f"{meeting_id}/original.mp4"
    # tmp_path is the upload folder of this test (see isolated_app in conftest.py)
    assert (tmp_path / str(meeting_id) / "original.mp4").read_bytes() == FAKE_VIDEO
    process_meeting_mock.assert_called_once_with(meeting_id)


@pytest.mark.parametrize(
    ("title", "stored_title"),
    [
        ("  Interview with Alex  ", "Interview with Alex"),
        # Only spaces count as no title, so the AI writes one
        ("   ", None),
    ],
)
def test_upload_stores_the_title_the_user_gave(client, db, title, stored_title):
    # data=: the other fields of the same multipart form
    response = client.post(
        "/api/meetings",
        files={"file": ("weekly-sync.mp4", FAKE_VIDEO, "video/mp4")},
        data={"title": title},
    )

    assert response.status_code == 202
    assert response.json()["title"] == stored_title
    meeting = db.get(Meeting, response.json()["id"])
    assert meeting.title == stored_title
