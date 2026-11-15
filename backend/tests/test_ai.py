"""Tests of app/services/ai.py: what is sent to Gemini and how its answer is
read.

Gemini is never called: fake_gemini (see conftest.py) replaces the client, and
each test decides what the "answer" is.
"""

import json
import logging
from types import SimpleNamespace

import pytest
from google.genai import types

from app.schemas import Insights
from app.services.ai import (
    ANALYZE_INSTRUCTIONS,
    TRANSCRIBE_INSTRUCTIONS,
    TRANSCRIBE_TASK,
    AIServiceError,
    MeetingAnalysis,
    analyze_transcript,
    transcribe_audio,
)

# A made-up interview
TRANSCRIPT = (
    "Interviewer: How do you plan your training sessions now?\n"
    "Interviewee: In a notebook, and I would like to share them with the team."
)


def test_transcribe_audio_sends_the_audio_first_and_the_task_after_it(
    fake_gemini, tmp_path
):
    audio_path = tmp_path / "audio.mp3"
    audio_path.write_bytes(b"not a real mp3")
    # What the Files API "returns" for the upload: a file that is ready
    fake_gemini.files.upload.return_value = SimpleNamespace(
        name="files/test",
        uri="https://example.com/files/test",
        mime_type="audio/mpeg",
        state=types.FileState.ACTIVE,
    )
    fake_gemini.interactions.create.return_value = SimpleNamespace(
        status="completed", output_text=TRANSCRIPT + "\n"
    )

    transcript = transcribe_audio(audio_path)

    assert transcript == TRANSCRIPT
    sent = fake_gemini.interactions.create.call_args.kwargs
    # The rules are in the system instruction, the input holds the audio and
    # then only the short task
    assert sent["system_instruction"] == TRANSCRIBE_INSTRUCTIONS
    assert [part["type"] for part in sent["input"]] == ["audio", "text"]
    assert sent["input"][0]["uri"] == "https://example.com/files/test"
    assert sent["input"][1]["text"] == TRANSCRIBE_TASK
    # The uploaded audio is removed from Google's storage after the call
    fake_gemini.files.delete.assert_called_once_with(name="files/test")


def test_the_schema_puts_the_conclusions_after_the_points():
    # Gemini writes the fields in the order of the schema, so the takeaway and
    # the title must come after the points they are drawn from
    assert list(MeetingAnalysis.model_json_schema()["properties"]) == [
        "interviewee",
        "insights",
        "title",
    ]
    assert list(Insights.model_json_schema()["properties"]) == [
        "context",
        "likes",
        "dislikes",
        "wants",
        "takeaway",
    ]


def answer(fake_gemini, data) -> None:
    """Make the fake client answer with data as JSON text, the way Gemini does."""
    fake_gemini.interactions.create.return_value = SimpleNamespace(
        status="completed", output_text=json.dumps(data)
    )


def test_analyze_transcript_returns_the_tidied_insights(fake_gemini):
    answer(
        fake_gemini,
        {
            "title": "  Youth coach on planning training sessions  ",
            # Gemini sometimes writes "" or spaces instead of null
            "interviewee": {"name": "", "role": " U15 coach ", "location": "  "},
            "insights": {
                "takeaway": " The app fits if sessions can be shared. ",
                "context": "Coaches a U15 team and plans in a notebook.",
                "likes": [],
                "dislikes": [
                    # An item with no title says nothing and is dropped
                    {"title": " ", "explanation": "Something."},
                ],
                "wants": [
                    {
                        "title": " Shared session plans ",
                        "explanation": " The players should see the plan. ",
                    }
                ],
            },
        },
    )

    analysis = analyze_transcript(TRANSCRIPT)

    assert analysis.title == "Youth coach on planning training sessions"
    assert analysis.interviewee.model_dump() == {
        "name": None,
        "role": "U15 coach",
        "location": None,
    }
    assert analysis.insights.takeaway == "The app fits if sessions can be shared."
    assert analysis.insights.likes == []
    assert analysis.insights.dislikes == []
    assert [(item.title, item.explanation) for item in analysis.insights.wants] == [
        ("Shared session plans", "The players should see the plan.")
    ]
    # The rules went to the system instruction, and the transcript was sent
    # between its tags, before the task
    sent = fake_gemini.interactions.create.call_args.kwargs
    assert sent["system_instruction"] == ANALYZE_INSTRUCTIONS
    assert sent["input"].startswith(f"<transcript>\n{TRANSCRIPT}\n</transcript>")


def test_analyze_transcript_rejects_an_answer_without_a_takeaway(fake_gemini):
    answer(
        fake_gemini,
        {
            "title": "Youth coach on planning training sessions",
            "interviewee": {"name": None, "role": None, "location": None},
            "insights": {
                "context": "Coaches a U15 team.",
                "likes": [],
                "dislikes": [],
                "wants": [],
            },
        },
    )

    # pytest.raises: the test passes only if this error is raised inside
    with pytest.raises(AIServiceError, match="unexpected format"):
        analyze_transcript(TRANSCRIPT)


def test_a_failed_answer_is_logged_with_its_usage_but_without_its_content(
    fake_gemini, caplog
):
    # An answer that came back but is not usable (the takeaway is missing):
    # Google charges for it, so it must be logged, but its text is the
    # content of the interview and must not be
    context = "Coaches a U15 team and plans every session in a notebook."
    fake_gemini.interactions.create.return_value = SimpleNamespace(
        status="completed",
        output_text=json.dumps(
            {
                "title": "Youth coach on planning training sessions",
                "interviewee": {"name": None, "role": None, "location": None},
                "insights": {
                    "context": context,
                    "likes": [],
                    "dislikes": [],
                    "wants": [],
                },
            }
        ),
        usage=SimpleNamespace(
            total_input_tokens=1200,
            total_output_tokens=300,
            total_thought_tokens=450,
        ),
    )
    # caplog collects the log records written during the test
    caplog.set_level(logging.INFO, logger="app.services.ai")

    with pytest.raises(AIServiceError):
        analyze_transcript(TRANSCRIPT, meeting_id=7)

    usage_records = [r for r in caplog.records if hasattr(r, "input_tokens")]
    assert len(usage_records) == 1
    record = usage_records[0]
    # The numbers are separate fields of the record, not only in the text
    assert (record.meeting_id, record.step) == (7, "analysis")
    assert (record.input_tokens, record.output_tokens, record.thought_tokens) == (
        1200,
        300,
        450,
    )
    # Neither the answer nor the transcript reached any log line
    for logged in caplog.records:
        assert context not in logged.getMessage()
        assert "notebook" not in logged.getMessage()
