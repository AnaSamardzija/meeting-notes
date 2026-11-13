"""Tests of analyze_transcript: how the answer of Gemini is read.

Gemini is never called: fake_gemini (see conftest.py) replaces the client, and
each test decides what the "answer" is.
"""

import json
from types import SimpleNamespace

import pytest

from app.services.ai import AIServiceError, analyze_transcript

# A made-up interview
TRANSCRIPT = (
    "Speaker 1: How do you plan your training sessions now?\n"
    "Speaker 2: In a notebook, and I would like to share them with the team."
)


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
    # The transcript was sent to Gemini together with the instructions
    sent_input = fake_gemini.interactions.create.call_args.kwargs["input"]
    assert sent_input.endswith(TRANSCRIPT)


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
