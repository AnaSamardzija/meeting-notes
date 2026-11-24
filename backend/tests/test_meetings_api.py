"""Tests of the meetings list, the meeting details, changing the title and
processing again."""

from datetime import datetime

import pytest

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
            # The user who uploaded it (owner in conftest.py)
            "owner_email": "owner@example.com",
        },
        {
            "id": older.id,
            "original_filename": "weekly-sync.mp4",
            "title": "Youth coach on planning training sessions",
            "status": "done",
            "uploaded_at": "2026-10-01T09:00:00Z",
            "interviewee": INTERVIEWEE,
            "owner_email": "owner@example.com",
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


def test_changing_the_title_stores_it_and_returns_the_meeting(
    client, db, make_meeting
):
    meeting = make_meeting(title="Youth coach on planning training sessions")

    response = client.patch(
        f"/api/meetings/{meeting.id}", json={"title": "  Interview with Alex  "}
    )

    assert response.status_code == 200
    body = response.json()
    # The spaces around the title are removed
    assert body["title"] == "Interview with Alex"
    # The whole meeting comes back, so the details can show it at once
    assert body["id"] == meeting.id
    assert "transcript" in body
    db.refresh(meeting)
    assert meeting.title == "Interview with Alex"


# parametrize: the same test runs once for each value in the list
@pytest.mark.parametrize("title", ["", "   ", "x" * 256])
def test_an_empty_or_too_long_title_is_refused(client, db, make_meeting, title):
    meeting = make_meeting(title="Youth coach on planning training sessions")

    response = client.patch(f"/api/meetings/{meeting.id}", json={"title": title})

    assert response.status_code == 422
    db.refresh(meeting)
    assert meeting.title == "Youth coach on planning training sessions"


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


OLD_TRANSCRIPT = "Speaker 1: How do you plan your sessions?\nAlex: In a notebook."


@pytest.mark.parametrize(
    ("transcript", "body", "expected_status", "transcribe"),
    [
        # A meeting with a transcript gets only a new summary by default
        (OLD_TRANSCRIPT, None, MeetingStatus.SUMMARIZING, False),
        (OLD_TRANSCRIPT, {"transcribe": False}, MeetingStatus.SUMMARIZING, False),
        # A new transcript only when it is asked for...
        (OLD_TRANSCRIPT, {"transcribe": True}, MeetingStatus.TRANSCRIBING, True),
        # ...or when there is none (e.g. the transcription failed)
        (None, None, MeetingStatus.TRANSCRIBING, True),
    ],
    ids=["summary only", "transcribe false", "transcribe true", "no transcript"],
)
def test_processing_again_keeps_the_old_results_until_the_new_ones_are_ready(
    client,
    db,
    make_meeting,
    process_meeting_mock,
    transcript,
    body,
    expected_status,
    transcribe,
):
    meeting = make_meeting(
        status=MeetingStatus.FAILED,
        error_message="The Gemini usage limit has been reached. Try again later.",
        title="Youth coach on planning training sessions",
        transcript=transcript,
        interviewee=INTERVIEWEE,
        insights=INSIGHTS,
        processed_at=datetime(2026, 10, 1, 9, 30),
        edited_at=datetime(2026, 10, 2, 8, 0),
    )

    response = client.post(f"/api/meetings/{meeting.id}/process", json=body)

    assert response.status_code == 202
    assert response.json()["status"] == expected_status.value
    db.refresh(meeting)
    assert meeting.status == expected_status
    # Only the message of the earlier failure is cleared
    assert meeting.error_message is None
    # Nothing else is cleared: if the processing fails, the meeting keeps
    # its transcript, its summary and the user's changes
    assert meeting.title == "Youth coach on planning training sessions"
    assert meeting.transcript == transcript
    assert meeting.interviewee == INTERVIEWEE
    assert meeting.insights == INSIGHTS
    assert meeting.processed_at == datetime(2026, 10, 1, 9, 30)
    assert meeting.edited_at == datetime(2026, 10, 2, 8, 0)
    process_meeting_mock.assert_called_once_with(meeting.id, transcribe=transcribe)
