"""Tests of POST /api/meetings (uploading a video)."""

import pytest
from sqlalchemy import func, select

from app.config import settings
from app.models import Meeting, MeetingStatus

# Made-up content: the endpoint checks the name, the type and the size, its
# length comes from a mock of ffprobe (see ai_mocks in conftest.py), and the
# processing (where ffmpeg would read the file) is replaced in the tests
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


# 2 h 14 min: longer than the limit of 2 hours the tests below set
TOO_LONG_SECONDS = 2 * 60 * 60 + 14 * 60


@pytest.mark.parametrize(
    ("seconds", "message"),
    [
        (
            TOO_LONG_SECONDS,
            "The video is 2 h 14 min long; the longest allowed is 2 hours.",
        ),
        # ffprobe could not read the length, so it is not a usable video
        (None, "The video file is corrupted or is not a valid video"),
    ],
    ids=["too long", "length unknown"],
)
def test_upload_rejects_a_video_that_is_too_long_or_unreadable(
    client, db, tmp_path, monkeypatch, ai_mocks, process_meeting_mock, seconds, message
):
    # Set here, so the test does not depend on MAX_VIDEO_MINUTES in .env
    monkeypatch.setattr(settings, "max_video_minutes", 120)
    # What ffprobe "reads" from the saved file (see ai_mocks in conftest.py)
    ai_mocks.get_media_duration.return_value = seconds

    response = upload(client, "weekly-sync.mp4", FAKE_VIDEO, "video/mp4")

    assert response.status_code == 422
    assert response.json()["detail"] == message
    # The file had been saved to read its length; neither it nor the row is kept
    assert count_meetings(db) == 0
    assert list(tmp_path.iterdir()) == []
    process_meeting_mock.assert_not_called()


@pytest.mark.parametrize(
    ("headers", "content", "status_code", "message"),
    [
        # The header says 10 GB, but only one byte is sent: the request is
        # refused from the header alone, before the body is read
        (
            {"Content-Length": str(10 * 1024 * 1024 * 1024)},
            b"x",
            413,
            "The file is larger than 1 MB",
        ),
        # A generator as the body: httpx sends it in chunks
        # (Transfer-Encoding: chunked), without Content-Length
        (
            {},
            (chunk for chunk in [b"x"]),
            411,
            "The size of the upload must be known in advance (Content-Length)",
        ),
    ],
    ids=["larger than the limit", "size unknown"],
)
def test_a_large_upload_is_refused_before_the_login_is_checked(
    anonymous_client,
    tmp_path,
    monkeypatch,
    process_meeting_mock,
    headers,
    content,
    status_code,
    message,
):
    monkeypatch.setattr(settings, "max_upload_mb", 1)

    # Not logged in: without the middleware the body would be read (and the
    # file written to a temporary file) before the 401
    response = anonymous_client.post("/api/meetings", content=content, headers=headers)

    assert response.status_code == status_code
    assert response.json()["detail"] == message
    assert list(tmp_path.iterdir()) == []
    process_meeting_mock.assert_not_called()


def test_upload_saves_the_video_and_starts_the_processing(
    client, db, tmp_path, process_meeting_mock, owner
):
    response = upload(client, "weekly-sync.mp4", FAKE_VIDEO, "video/mp4")

    assert response.status_code == 202
    body = response.json()
    assert body["original_filename"] == "weekly-sync.mp4"
    assert body["status"] == MeetingStatus.UPLOADED.value
    assert body["title"] is None

    meeting_id = body["id"]
    meeting = db.get(Meeting, meeting_id)
    # The meeting belongs to the user who uploaded it
    assert meeting.user_id == owner.id
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
