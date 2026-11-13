"""Tests of process_meeting, the background processing of one meeting.

process_meeting is called directly, the way the background task calls it.
extract_audio, transcribe_audio and analyze_transcript are mocks (see
ai_mocks in conftest.py), so ffmpeg and Gemini are never called.
"""

from app.models import MeetingStatus
from app.schemas import InsightItem, Insights, Interviewee
from app.services.ai import AIServiceError, MeetingAnalysis
from app.services.processing import UNEXPECTED_ERROR_MESSAGE, process_meeting

# A made-up interview with a made-up coach
TRANSCRIPT = (
    "Speaker 1: How do you plan your training sessions now?\n"
    "Alex: I write them in a notebook, and I would like to share them with the team."
)

ANALYSIS = MeetingAnalysis(
    title="Youth coach on planning training sessions",
    interviewee=Interviewee(name="Alex", role="U15 coach", location=None),
    insights=Insights(
        takeaway="The app fits Alex well if sessions can be shared with the team.",
        context="Alex coaches a U15 team and plans the sessions in a notebook.",
        likes=[],
        dislikes=[
            InsightItem(
                title="Paper notes",
                explanation="Notes in a notebook are easy to lose.",
            )
        ],
        wants=[
            InsightItem(
                title="Shared session plans",
                explanation="The players should see the plan before training.",
            )
        ],
    ),
)


def test_process_meeting_stores_the_transcript_and_the_analysis(
    db, make_meeting, ai_mocks, tmp_path
):
    meeting = make_meeting(status=MeetingStatus.UPLOADED, file_path="1/original.mp4")
    ai_mocks.transcribe_audio.return_value = TRANSCRIPT
    ai_mocks.analyze_transcript.return_value = ANALYSIS

    process_meeting(meeting.id)

    # Each step got what the previous one produced. tmp_path is the upload
    # folder of this test (see isolated_app in conftest.py)
    video_path = tmp_path / "1" / "original.mp4"
    audio_path = tmp_path / "1" / "audio.mp3"
    ai_mocks.extract_audio.assert_called_once_with(video_path, audio_path)
    ai_mocks.transcribe_audio.assert_called_once_with(audio_path)
    ai_mocks.analyze_transcript.assert_called_once_with(TRANSCRIPT)

    # process_meeting used a session of its own, so read the meeting again
    db.refresh(meeting)
    assert meeting.status == MeetingStatus.DONE
    assert meeting.error_message is None
    assert meeting.transcript == TRANSCRIPT
    assert meeting.title == "Youth coach on planning training sessions"
    assert meeting.processed_at is not None
    # The JSON columns hold plain dicts and lists, read back from the database
    assert meeting.interviewee == {
        "name": "Alex",
        "role": "U15 coach",
        "location": None,
    }
    assert meeting.insights == {
        "takeaway": "The app fits Alex well if sessions can be shared with the team.",
        "context": "Alex coaches a U15 team and plans the sessions in a notebook.",
        "likes": [],
        "dislikes": [
            {
                "title": "Paper notes",
                "explanation": "Notes in a notebook are easy to lose.",
            }
        ],
        "wants": [
            {
                "title": "Shared session plans",
                "explanation": "The players should see the plan before training.",
            }
        ],
    }


def test_process_meeting_keeps_a_title_the_user_set_during_the_processing(
    db, make_meeting, ai_mocks
):
    meeting = make_meeting(status=MeetingStatus.UPLOADED, title=None)
    ai_mocks.transcribe_audio.return_value = TRANSCRIPT

    def user_sets_the_title_while_the_summary_is_made(transcript):
        # Stands for PATCH /api/meetings/{id} arriving while the AI writes the
        # summary, after process_meeting has already read the meeting
        meeting.title = "Interview with Alex"
        db.commit()
        return ANALYSIS

    ai_mocks.analyze_transcript.side_effect = (
        user_sets_the_title_while_the_summary_is_made
    )

    process_meeting(meeting.id)

    db.refresh(meeting)
    assert meeting.status == MeetingStatus.DONE
    # The AI title is used only when there is no title
    assert meeting.title == "Interview with Alex"
    assert meeting.insights is not None


def test_process_meeting_stores_the_message_of_an_ai_error(
    db, make_meeting, ai_mocks
):
    meeting = make_meeting(status=MeetingStatus.UPLOADED)
    # side_effect: the mock raises this error instead of returning a value
    ai_mocks.transcribe_audio.side_effect = AIServiceError(
        "The Gemini usage limit has been reached. Try again later."
    )

    process_meeting(meeting.id)

    db.refresh(meeting)
    assert meeting.status == MeetingStatus.FAILED
    assert meeting.error_message == (
        "The Gemini usage limit has been reached. Try again later."
    )
    assert meeting.transcript is None
    assert meeting.processed_at is None
    ai_mocks.analyze_transcript.assert_not_called()


def test_process_meeting_hides_the_details_of_an_unexpected_error(
    db, make_meeting, ai_mocks
):
    meeting = make_meeting(status=MeetingStatus.UPLOADED)
    ai_mocks.transcribe_audio.return_value = TRANSCRIPT
    # Stands for a bug in the code: not an error the user should read
    ai_mocks.analyze_transcript.side_effect = RuntimeError("something broke")

    process_meeting(meeting.id)

    db.refresh(meeting)
    assert meeting.status == MeetingStatus.FAILED
    assert meeting.error_message == UNEXPECTED_ERROR_MESSAGE
    # The transcript was saved before the analysis, so it is kept
    assert meeting.transcript == TRANSCRIPT
    assert meeting.title is None
    assert meeting.interviewee is None
    assert meeting.insights is None
