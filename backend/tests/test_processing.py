"""Tests of process_meeting, the background processing of one meeting.

process_meeting is called directly, the way the background task calls it.
get_media_duration, extract_audio, transcribe_audio and analyze_transcript
are mocks (see ai_mocks in conftest.py), so ffprobe, ffmpeg and Gemini are
never called.
"""

from datetime import datetime
from unittest.mock import call

import pytest

from app.config import settings
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
    # The length of the video for the check, then of the MP3 for the log
    assert ai_mocks.get_media_duration.call_args_list == [
        call(video_path),
        call(audio_path),
    ]
    ai_mocks.transcribe_audio.assert_called_once_with(
        audio_path, meeting_id=meeting.id, audio_seconds=98.5
    )
    ai_mocks.analyze_transcript.assert_called_once_with(
        TRANSCRIPT, meeting_id=meeting.id
    )

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

    def user_sets_the_title_while_the_summary_is_made(transcript, meeting_id):
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


def test_process_meeting_fails_a_video_that_is_too_long_without_calling_gemini(
    db, make_meeting, ai_mocks, monkeypatch
):
    monkeypatch.setattr(settings, "max_video_minutes", 120)
    # Processed again (start_reprocessing leaves it in this status): an older
    # video, uploaded before the limit, or with a higher one
    meeting = make_meeting(status=MeetingStatus.TRANSCRIBING)
    # 2 h 14 min
    ai_mocks.get_media_duration.return_value = 2 * 60 * 60 + 14 * 60

    process_meeting(meeting.id)

    db.refresh(meeting)
    assert meeting.status == MeetingStatus.FAILED
    assert meeting.error_message == (
        "The video is 2 h 14 min long; the longest allowed is 2 hours."
    )
    assert meeting.transcript is None
    # Stopped before ffmpeg and before anything was sent to Gemini
    ai_mocks.extract_audio.assert_not_called()
    ai_mocks.transcribe_audio.assert_not_called()
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


# The results an earlier processing left on the meeting, which the user has
# edited since. Made up, like everything above
OLD_TRANSCRIPT = "Speaker 1: What do you use for training?\nAlex: Mostly paper."
OLD_INTERVIEWEE = {"name": "Alex", "role": "Coach", "location": None}
OLD_INSIGHTS = {
    "takeaway": "Edited by the user.",
    "context": "Alex plans on paper.",
    "likes": [],
    "dislikes": [],
    "wants": [],
}
EDITED_AT = datetime(2026, 10, 2, 8, 0)


@pytest.fixture
def processed_meeting(make_meeting):
    """Return a function that stores a processed and edited meeting in the
    status start_reprocessing leaves it in."""

    def _processed_meeting(status):
        return make_meeting(
            status=status,
            title="Interview with Alex",
            transcript=OLD_TRANSCRIPT,
            interviewee=OLD_INTERVIEWEE,
            insights=OLD_INSIGHTS,
            processed_at=datetime(2026, 10, 1, 9, 30),
            edited_at=EDITED_AT,
        )

    return _processed_meeting


def test_a_new_summary_only_does_not_transcribe_and_replaces_the_summary(
    db, processed_meeting, ai_mocks
):
    meeting = processed_meeting(MeetingStatus.SUMMARIZING)
    ai_mocks.analyze_transcript.return_value = ANALYSIS

    process_meeting(meeting.id, transcribe=False)

    # No ffprobe, ffmpeg or transcription: the summary is made from the
    # transcript the meeting already has
    ai_mocks.get_media_duration.assert_not_called()
    ai_mocks.extract_audio.assert_not_called()
    ai_mocks.transcribe_audio.assert_not_called()
    ai_mocks.analyze_transcript.assert_called_once_with(
        OLD_TRANSCRIPT, meeting_id=meeting.id
    )
    db.refresh(meeting)
    assert meeting.status == MeetingStatus.DONE
    assert meeting.transcript == OLD_TRANSCRIPT
    assert meeting.insights == ANALYSIS.insights.model_dump()
    assert meeting.interviewee == ANALYSIS.interviewee.model_dump()
    # The summary is the AI's again
    assert meeting.edited_at is None
    assert meeting.processed_at > datetime(2026, 10, 1, 9, 30)
    # The meeting has a title, so the AI title is not used
    assert meeting.title == "Interview with Alex"


def test_a_failed_new_summary_keeps_the_transcript_the_summary_and_the_changes(
    db, processed_meeting, ai_mocks
):
    meeting = processed_meeting(MeetingStatus.SUMMARIZING)
    ai_mocks.analyze_transcript.side_effect = AIServiceError(
        "The Gemini usage limit has been reached. Try again later."
    )

    process_meeting(meeting.id, transcribe=False)

    db.refresh(meeting)
    assert meeting.status == MeetingStatus.FAILED
    assert meeting.error_message == (
        "The Gemini usage limit has been reached. Try again later."
    )
    assert meeting.transcript == OLD_TRANSCRIPT
    assert meeting.interviewee == OLD_INTERVIEWEE
    assert meeting.insights == OLD_INSIGHTS
    assert meeting.edited_at == EDITED_AT
    assert meeting.processed_at == datetime(2026, 10, 1, 9, 30)


def test_a_new_transcript_replaces_the_transcript_and_the_summary(
    db, processed_meeting, ai_mocks
):
    meeting = processed_meeting(MeetingStatus.TRANSCRIBING)
    ai_mocks.transcribe_audio.return_value = TRANSCRIPT
    ai_mocks.analyze_transcript.return_value = ANALYSIS

    process_meeting(meeting.id, transcribe=True)

    ai_mocks.transcribe_audio.assert_called_once()
    # The summary is made from the new transcript
    ai_mocks.analyze_transcript.assert_called_once_with(
        TRANSCRIPT, meeting_id=meeting.id
    )
    db.refresh(meeting)
    assert meeting.status == MeetingStatus.DONE
    assert meeting.transcript == TRANSCRIPT
    assert meeting.insights == ANALYSIS.insights.model_dump()
    assert meeting.edited_at is None


def test_a_new_transcript_is_kept_when_the_new_summary_fails(
    db, processed_meeting, ai_mocks
):
    meeting = processed_meeting(MeetingStatus.TRANSCRIBING)
    ai_mocks.transcribe_audio.return_value = TRANSCRIPT
    ai_mocks.analyze_transcript.side_effect = AIServiceError(
        "The Gemini usage limit has been reached. Try again later."
    )

    process_meeting(meeting.id, transcribe=True)

    db.refresh(meeting)
    assert meeting.status == MeetingStatus.FAILED
    # The transcription was paid for, so its result is kept: "Try again" then
    # makes only a new summary. The old summary stays until a new one is ready
    assert meeting.transcript == TRANSCRIPT
    assert meeting.interviewee == OLD_INTERVIEWEE
    assert meeting.insights == OLD_INSIGHTS
    assert meeting.edited_at == EDITED_AT
