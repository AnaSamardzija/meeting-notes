"""Tests of the meetings list, the meeting details and processing again."""

from datetime import datetime

from app.models import MeetingStatus


def test_list_is_empty_when_there_are_no_meetings(client):
    response = client.get("/api/meetings")

    assert response.status_code == 200
    assert response.json() == []


def test_list_shows_the_newest_meeting_first_with_its_action_item_count(
    client, make_meeting
):
    older = make_meeting(
        title="Planning the spring camp",
        uploaded_at=datetime(2026, 10, 1, 9, 0),
        action_items=[
            ("Alex", "Book the training pitch"),
            (None, "Send the schedule to the players"),
        ],
    )
    newer = make_meeting(
        status=MeetingStatus.TRANSCRIBING,
        original_filename="coach-feedback.mp4",
        uploaded_at=datetime(2026, 10, 2, 9, 0),
    )

    response = client.get("/api/meetings")

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": newer.id,
            "original_filename": "coach-feedback.mp4",
            "title": None,
            "status": "transcribing",
            # The "Z" marks the time as UTC (see UtcDateTime in app/schemas.py)
            "uploaded_at": "2026-10-02T09:00:00Z",
            "action_item_count": 0,
        },
        {
            "id": older.id,
            "original_filename": "weekly-sync.mp4",
            "title": "Planning the spring camp",
            "status": "done",
            "uploaded_at": "2026-10-01T09:00:00Z",
            "action_item_count": 2,
        },
    ]


def test_details_return_the_results_and_the_action_items(client, make_meeting):
    meeting = make_meeting(
        title="Planning the spring camp",
        transcript="Speaker 1: Let's plan the spring camp.\nAlex: I will book the pitch.",
        summary="The team planned the spring camp.",
        key_topics=["Spring camp", "Training pitch"],
        processed_at=datetime(2026, 10, 1, 9, 30),
        action_items=[("Alex", "Book the training pitch")],
    )

    response = client.get(f"/api/meetings/{meeting.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "done"
    assert body["title"] == "Planning the spring camp"
    assert body["transcript"].startswith("Speaker 1: Let's plan the spring camp.")
    assert body["summary"] == "The team planned the spring camp."
    assert body["key_topics"] == ["Spring camp", "Training pitch"]
    assert body["processed_at"] == "2026-10-01T09:30:00Z"
    assert body["error_message"] is None
    assert [
        (item["assignee"], item["description"]) for item in body["action_items"]
    ] == [("Alex", "Book the training pitch")]
    # Internal fields are not part of the response
    assert "file_path" not in body


def test_details_of_a_meeting_that_does_not_exist_return_404(client):
    response = client.get("/api/meetings/999999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Meeting not found"}


def test_processing_again_is_refused_while_the_meeting_is_being_processed(
    client, db, make_meeting, process_meeting_mock
):
    meeting = make_meeting(status=MeetingStatus.TRANSCRIBING)

    response = client.post(f"/api/meetings/{meeting.id}/process")

    assert response.status_code == 409
    assert response.json() == {"detail": "The meeting is already being processed"}
    # Read the meeting from the database again, not from the session's memory
    db.refresh(meeting)
    assert meeting.status == MeetingStatus.TRANSCRIBING
    process_meeting_mock.assert_not_called()
