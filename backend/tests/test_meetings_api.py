"""Tests of the meetings list, the meeting details and processing again."""

from datetime import datetime

from app.models import MeetingStatus

# Made-up results of a processed interview, in the shape of the JSON columns
INTERVIEWEE = {"name": "Alex", "role": "U15 coach", "location": "Springfield"}
INSIGHTS = {
    "takeaway": "The app fits Alex well if sessions can be shared with the team.",
    "context": "Alex coaches a U15 team and plans the sessions in a notebook.",
    "likes": [
        {"title": "Drill library", "explanation": "Saves time when planning."}
    ],
    "dislikes": [],
    "wants": [
        {
            "title": "Shared session plans",
            "explanation": "The players should see the plan before training.",
        }
    ],
}


def test_list_is_empty_when_there_are_no_meetings(client):
    response = client.get("/api/meetings")

    assert response.status_code == 200
    assert response.json() == []


def test_list_shows_the_newest_meeting_first_with_its_interviewee(
    client, make_meeting
):
    older = make_meeting(
        title="Youth coach on planning training sessions",
        uploaded_at=datetime(2026, 10, 1, 9, 0),
        interviewee=INTERVIEWEE,
        insights=INSIGHTS,
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
            # Not processed yet, so nobody is known
            "interviewee": None,
        },
        {
            "id": older.id,
            "original_filename": "weekly-sync.mp4",
            "title": "Youth coach on planning training sessions",
            "status": "done",
            "uploaded_at": "2026-10-01T09:00:00Z",
            "interviewee": INTERVIEWEE,
        },
    ]


def test_details_return_the_interviewee_and_the_insights(client, make_meeting):
    meeting = make_meeting(
        title="Youth coach on planning training sessions",
        transcript="Speaker 1: How do you plan your sessions?\nAlex: In a notebook.",
        interviewee=INTERVIEWEE,
        insights=INSIGHTS,
        processed_at=datetime(2026, 10, 1, 9, 30),
    )

    response = client.get(f"/api/meetings/{meeting.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "done"
    assert body["title"] == "Youth coach on planning training sessions"
    assert body["transcript"].startswith("Speaker 1: How do you plan your sessions?")
    assert body["interviewee"] == INTERVIEWEE
    assert body["insights"] == INSIGHTS
    assert body["processed_at"] == "2026-10-01T09:30:00Z"
    assert body["error_message"] is None
    # Internal fields and the removed old fields are not part of the response
    assert "file_path" not in body
    assert "summary" not in body
    assert "action_items" not in body


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


def test_processing_again_clears_the_old_results(
    client, db, make_meeting, process_meeting_mock
):
    meeting = make_meeting(
        title="Youth coach on planning training sessions",
        transcript="Speaker 1: How do you plan your sessions?\nAlex: In a notebook.",
        interviewee=INTERVIEWEE,
        insights=INSIGHTS,
        processed_at=datetime(2026, 10, 1, 9, 30),
    )

    response = client.post(f"/api/meetings/{meeting.id}/process")

    assert response.status_code == 202
    assert response.json()["status"] == "transcribing"
    db.refresh(meeting)
    assert meeting.status == MeetingStatus.TRANSCRIBING
    assert meeting.title is None
    assert meeting.transcript is None
    assert meeting.interviewee is None
    assert meeting.insights is None
    assert meeting.processed_at is None
    process_meeting_mock.assert_called_once_with(meeting.id)
